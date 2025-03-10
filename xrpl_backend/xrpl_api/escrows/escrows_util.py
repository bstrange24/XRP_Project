# Function to check for Escrow entries
import hashlib
import json
import logging

from os import urandom

from cryptoconditions import PreimageSha256
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

def generate_escrow_condition_and_fulfillment():
    # """Generate a condition and fulfillment for escrows"""

    # Generate a random preimage with at least 32 bytes of cryptographically-secure randomness.
    secret = urandom(32)

    # Generate cryptic image from secret
    fufill = PreimageSha256(preimage=secret)

    # Parse image and return the condition and fulfillment
    condition = str.upper(fufill.condition_binary.hex())  # conditon
    fulfillment = str.upper(fufill.serialize_binary().hex())  # fulfillment

    # Print condition and fulfillment
    print(f"condition: {condition}\nfulfillment {fulfillment}")
    return condition, fulfillment


def validate_fulfillment(condition, fulfillment):
    fulfillment_preimage = bytes.fromhex(fulfillment[8:])  # Raw preimage without 'A0228020'
    computed_hash = hashlib.sha256(fulfillment_preimage).hexdigest().upper()
    condition_hash = condition[8:-6]  # Hash without 'A0258020' and '810120'
    if computed_hash != condition_hash:
        logger.error(f"Computed: {computed_hash}, Expected: {condition_hash}")
        return False
    else:
        logger.info(f"Valid condition and fulfillment")
        return True


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
        "seconds": {"seconds": number},
        "min": {"minutes": number},
        "minutes": {"minutes": number},
        "hour": {"hours": number},
        "hours": {"hours": number},
        "day": {"days": number},
        "days": {"days": number},
        "month": {"days": number * 30},  # Approx: 30 days per month
        "months": {"days": number * 30},  # Approx: 30 days per month
        "year": {"days": number * 365},  # Approx: 365 days per year
        "years": {"days": number * 365}  # Approx: 365 days per year
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
        "transaction_hash": result["hash"],
        "result": result["meta"]["TransactionResult"],
        "sequence": result["tx_json"]["Sequence"],
        "last_ledger_sequence": result["tx_json"]["LastLedgerSequence"]
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

def create_escrow_transaction(escrow_creator_account, amount_to_escrow, escrow_receiver_account, condition, sequence, fee, last_ledger):
    return EscrowCreate(
        account=escrow_creator_account,
        amount=xrp_to_drops(amount_to_escrow),
        destination=escrow_receiver_account,
        sequence=sequence,
        fee=fee,
        last_ledger_sequence=last_ledger + 300,
        finish_after=datetime_to_ripple_time(datetime.now() + timedelta(minutes=5)),
        cancel_after=datetime_to_ripple_time(datetime.now() + timedelta(days=1)),
        condition=condition,
    )

def create_escrow_transaction_condition_only(escrow_creator_account, amount_to_escrow, escrow_receiver_account, condition, sequence, fee, last_ledger):
    return EscrowCreate(
        account=escrow_creator_account,
        amount=xrp_to_drops(amount_to_escrow),
        destination=escrow_receiver_account,
        # sequence=sequence,
        # fee=fee,
        last_ledger_sequence=last_ledger + 300,
        condition=condition,
    )

def create_escrow_transaction_time_based_only(escrow_creator_account, amount_to_escrow, escrow_receiver_account, sequence, fee, last_ledger, finish_after, cancel_after):
    return EscrowCreate(
        account=escrow_creator_account,
        amount=xrp_to_drops(amount_to_escrow),
        destination=escrow_receiver_account,
        # sequence=sequence,
        # fee=fee,
        last_ledger_sequence=last_ledger + 300,
        finish_after=finish_after,
        cancel_after=cancel_after,
        # condition=condition,
    )


def create_escrow_transaction_combination(escrow_creator_account, amount_to_escrow, escrow_receiver_account, condition, sequence, fee, last_ledger, finish_after, cancel_after):
    return EscrowCreate(
        account=escrow_creator_account,
        amount=xrp_to_drops(amount_to_escrow),
        destination=escrow_receiver_account,
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


def create_finish_escrow_transaction(creator_wallet, escrow_creator_account, offer_sequence, condition, fulfillment, sequence, fee, last_ledger_sequence):
    return EscrowFinish(
        account=creator_wallet, # The account finishing the escrow (typically the Destination or an authorized account).
        owner=escrow_creator_account, # Owner: The account that created the escrow (from the EscrowCreate transaction).
        offer_sequence=offer_sequence, # The sequence number of the EscrowCreate transaction.
        condition=condition,
        fulfillment=fulfillment,
        sequence=sequence,
        fee=fee,
        last_ledger_sequence=last_ledger_sequence
    )
