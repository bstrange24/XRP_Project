# Function to check for Escrow entries
import json
import logging

from os import urandom

from django.core.exceptions import ObjectDoesNotExist, MultipleObjectsReturned
from django.http import JsonResponse
from xrpl import XRPLException
from xrpl.models import AccountObjects, EscrowCreate, EscrowCancel, EscrowFinish, AccountObjectType
from xrpl.utils import xrp_to_drops, datetime_to_ripple_time
from datetime import datetime, timedelta

from .models.escrow_models import EscrowTransaction
from ..errors.error_handling import error_response, process_transaction_error
from ..transactions.transactions_util import prepare_tx
from ..utilities.utilities import validate_xrpl_response_data

logger = logging.getLogger('xrpl_app')


def check_escrow_entries(account_objects):
    escrow_entries = [entry for entry in account_objects if entry.get('LedgerEntryType') == 'Escrow']

    if escrow_entries:
        logger.error(f"Escrow entries found: {json.dumps(escrow_entries, indent=2)}")
        return False

    logger.info("No Escrow entries found.")
    return True


from cryptoconditions import PreimageSha256

def generate_escrow_condition_and_fulfillment():
    # Generate a random preimage with at least 32 bytes of cryptographically-secure randomness.
    secret = urandom(32)

    fulfillment1 = PreimageSha256(preimage=secret)

    condition = fulfillment1.condition_binary.hex().upper()
    print("Condition", condition)

    # Keep secret until you want to finish the escrow
    fulfillment = fulfillment1.serialize_binary().hex().upper()
    print("Fulfillment", fulfillment)

    # # Generate cryptic image from secret
    # fulfillment = PreimageSha256(preimage=secret)
    #
    # # Parse image and return the condition and fulfillment
    # condition = str.upper(fulfillment.condition_binary.hex()) # condition
    # fulfillment = str.upper(fulfillment.serialize_binary().hex()) # fulfillment

    # Print condition and fulfillment
    logger.info(f"condition: {condition}")
    logger.debug(f"fulfillment {fulfillment}")
    return condition, fulfillment

def parse_time_delta(finish_after_time):
    """
    Parse a string like 'X:unit' (e.g., '1:sec', '3:min') into a timedelta.

    Args:
        finish_after_time (str): String in format 'X:unit' where unit is sec, min, hour, day, month, year.

    Returns:
        timedelta: Corresponding timedelta object.

    Raises:
        ValueError: If the format or unit is invalid.
    """
    # Split the string into number and unit
    try:
        number, unit = finish_after_time.split(":")
        number = int(number)  # Convert number to integer
    except ValueError:
        raise ValueError(error_response(f"Invalid finish_after_time format: {finish_after_time}. Expected 'X:unit'."))

    # Map units to timedelta arguments
    unit_map = {
        "sec": {"seconds": number},
        "min": {"minutes": number},
        "hour": {"hours": number},
        "day": {"days": number},
        "month": {"days": number * 30},  # Approx: 30 days per month
        "year": {"days": number * 365}   # Approx: 365 days per year
    }

    # Check if unit is valid
    if unit not in unit_map:
        raise ValueError(error_response(f"Invalid time unit: {unit}. Supported units: sec, min, hour, day, month, year."))

    # Return the timedelta
    return timedelta(**unit_map[unit])

def get_escrow_data_from_db(txn_hash):
    # Validate condition
    if not isinstance(txn_hash, str) or txn_hash is None:
        logger.error(f"Invalid txn_hash: {txn_hash}")
        raise ValueError(error_response(f"Invalid txn_hash: {txn_hash}"))

    try:
        query_filters = {}
        if txn_hash:
            query_filters['hash'] = txn_hash.upper()

        # Query EscrowTransaction with related affected_nodes, filtering for non-null sequence
        escrow_tx = EscrowTransaction.objects.filter(
            **query_filters,
            affected_nodes__sequence__isnull=False  # Filter for non-null sequence in related model
        ).prefetch_related('affected_nodes').first()  # Use prefetch_related for reverse relation

        if escrow_tx:
            escrow_sequence  = escrow_tx.sequence
            condition =  escrow_tx.condition
            fulfillment = escrow_tx.fulfillment
            logger.info( f"Found escrow data from the database for escrow_sequence: {escrow_sequence} condition: {condition} fulfillment: {fulfillment}")
            return escrow_sequence, condition, fulfillment
        else:
            logger.warning(f"No escrow transaction found for hash: {txn_hash}")
            return None
    except ObjectDoesNotExist:
        logger.warning(f"No escrow transaction found for hash: {txn_hash}")
        return None
    except MultipleObjectsReturned:
        logger.error(f"Multiple escrow transactions found for hash: {txn_hash}")
        raise MultipleObjectsReturned(error_response(f"Multiple transactions match hash {txn_hash}."))
    except Exception as e:
        logger.error(f"Unexpected error querying fulfillment for hash {txn_hash}: {str(e)}")
        raise Exception(error_response(f"Unexpected error when processing hash {txn_hash}: {str(e)}"))


# def set_claim_date(time_str, base_time):
#     """Convert a time string (e.g., '3:sec') to Ripple epoch time, added to base_time."""
#     if ":" not in time_str:
#         raise ValueError(f"Invalid time format: {time_str}. Expected 'value:unit'.")
#     value, unit = time_str.split(":")
#     value = int(value)
#     if unit == "sec":
#         return base_time + value
#     elif unit == "min":
#         return base_time + (value * 60)
#     elif unit == "hour":
#         return base_time + (value * 3600)
#     else:
#         raise ValueError(f"Unsupported time unit: {unit}. Use 'sec', 'min', or 'hour'.")

def set_claim_date(finish_after_time):
    # Parse the time delta from the request parameter
    time_delta = parse_time_delta(finish_after_time)

    # Calculate claim_date using datetime_to_ripple_time
    claim_date = datetime_to_ripple_time(datetime.now() + time_delta)
    return claim_date


def get_escrow_sequence(client, prev_txn_id):
    """
    Retrieve the sequence number or ticket sequence for an escrow transaction.

    Args:
        client: XRPL client instance.
        prev_txn_id (str): Previous transaction ID.

    Returns:
        tuple: (sequence_number, sequence_type) or (None, None) if not found.
    """
    if not prev_txn_id:
        raise XRPLException(error_response("Invalid Previous Transaction Id"))

    # Build and send request for previous transaction
    prev_txn_id_request = prepare_tx(prev_txn_id)
    prev_txn_id_response = client.request(prev_txn_id_request)

    # Validate client response. Raise exception on error
    if validate_xrpl_response_data(prev_txn_id_response):
        process_transaction_error(prev_txn_id_response)

    result = prev_txn_id_response.result

    # Extract sequence or ticket sequence
    if "Sequence" in result['tx_json']:
        sequence = result['tx_json']["Sequence"]
        tx_hash = result['hash']
        ledger_index = result['ledger_index']
        logger.info(f'escrow sequence: {sequence} tx_hash {tx_hash} ledger_index {ledger_index}')
        return sequence, tx_hash, ledger_index
    elif "TicketSequence" in result['tx_json']:
        logger.info(f'escrow ticket sequence: {result["tx_json"]["TicketSequence"]}')
        sequence = result['tx_json']["TicketSequence"]
        tx_hash = result['hash']
        ledger_index = result['ledger_index']
        logger.info(f'escrow sequence: {sequence} tx_hash {tx_hash} ledger_index {ledger_index}')
        return sequence, tx_hash, ledger_index
    else:
        return None, None, None

def get_escrow_account_response(all_escrows_dict):
    return JsonResponse({
        'status': 'success',
        'message': 'Successfully retrieved escrow information.',
        'result': all_escrows_dict,
    })

def get_escrow_tx_id_account_response(result):
    return JsonResponse({
        'status': 'success',
        'message': 'Successfully retrieved escrow information.',
        'result': result,
    })

def create_escrow_account_response(result):
    return JsonResponse({
        'status': 'success',
        'message': 'Successfully created escrow.',
        'result': result,
    })

def create_escrow_sequence_number_response(result):
    if result is None:
        return JsonResponse({
            'status': 'failure',
            'message': f'No Sequence or Ticket Sequence for the provided Previous Transaction Id.',
        })
    else:
        return JsonResponse({
            'status': 'success',
            'message': f'Successfully retrieved escrow.',
            'result': result,
        })

def create_escrow_cancel_response(result):
    return JsonResponse({
        'status': 'success',
        'message': f'Successfully cancelled escrow.',
        'result': result,
    })

def create_finish_escrow_response(result):
    return JsonResponse({
        'status': 'success',
        'message': f'Successfully finished escrow.',
        'result': result,
    })

# def get_escrow_account_response_pagination(paginated_transactions, paginator):
#     return JsonResponse({
#         "status": "success",
#         "message": "Transaction history successfully retrieved.",
#         "transactions": paginated_transactions.object_list,
#         "page": paginated_transactions.number,
#         "total_pages": paginator.num_pages,
#         "total_offers": paginator.count
#     })

def create_escrow_account_transaction(account):
    return AccountObjects(
        account=account,
        ledger_index="validated",
        type=AccountObjectType.ESCROW
    )


def create_escrow_transaction(sender_address, amount_to_escrow, receiving_account, condition, sequence, fee, last_ledger):
    return EscrowCreate(
        account=sender_address,
        amount=xrp_to_drops(amount_to_escrow),
        destination=receiving_account,
        sequence=sequence,
        fee=fee,
        last_ledger_sequence=last_ledger + 300,
        finish_after=datetime_to_ripple_time(datetime.now() + timedelta(minutes=5)),
        cancel_after=datetime_to_ripple_time(datetime.now() + timedelta(days=1)),
        condition=condition,
    )

def create_escrow_transaction_with_finsh_cancel(sender_address, amount_to_escrow, receiving_account, condition, sequence, fee, last_ledger, finish_after, cancel_after):
    return EscrowCreate(
        account=sender_address,
        amount=xrp_to_drops(amount_to_escrow),
        destination=receiving_account,
        # sequence=sequence,
        # fee=fee,
        last_ledger_sequence=last_ledger + 300,
        finish_after=finish_after,
        cancel_after=cancel_after,
        condition=condition,
    )


def create_cancel_escrow_transaction(sender_wallet_address, escrow_sequence):
    return EscrowCancel(
        account=sender_wallet_address,
        owner=sender_wallet_address,
        offer_sequence=escrow_sequence
    )


def create_finish_escrow_transaction(sender_wallet_address, escrow_creator, escrow_sequence, condition, fulfillment):
    return EscrowFinish(
        account=sender_wallet_address, # The account finishing the escrow (typically the Destination or an authorized account).
        owner=escrow_creator, # Owner: The account that created the escrow (from the EscrowCreate transaction).
        offer_sequence=escrow_sequence, # The sequence number of the EscrowCreate transaction.
        condition=condition,
        fulfillment=fulfillment,
    )
