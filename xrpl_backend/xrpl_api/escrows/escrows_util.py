# Function to check for Escrow entries
import json
import logging

import secrets
import hashlib

from django.http import JsonResponse
from xrpl.models import AccountObjects, EscrowCreate, EscrowCancel, EscrowFinish
from xrpl.utils import xrp_to_drops, datetime_to_ripple_time
from datetime import datetime, timedelta

logger = logging.getLogger('xrpl_app')


def check_escrow_entries(account_objects):
    # Filter escrow entries
    escrow_entries = [entry for entry in account_objects if entry.get('LedgerEntryType') == 'Escrow']

    if escrow_entries:
        logger.error(f"Escrow entries found: {json.dumps(escrow_entries, indent=2)}")
        return False

    logger.info("No Escrow entries found.")
    return True


def generate_escrow_condition_and_fulfillment(secret_length=1):
    """
    Generate a condition and fulfillment pair for an XRPL escrow (xrpl-py 4.1.0 compatible).

    Args:
        secret_length (int): Length of the random secret (fulfillment) in bytes (default 1).

    Returns:
        tuple: (condition, fulfillment) as hex strings; condition includes preimage prefix.
    """
    fulfillment_bytes = secrets.token_bytes(secret_length)
    fulfillment = fulfillment_bytes.hex().upper()

    sha256_hash = hashlib.sha256(fulfillment_bytes).digest()
    condition = (b'\xA0\x25\x80\x80' + sha256_hash).hex().upper()  # 72 hex chars, prefixed

    computed_hash = hashlib.sha256(bytes.fromhex(fulfillment)).digest()
    if computed_hash != bytes.fromhex(condition)[4:]:
        raise ValueError("Condition and fulfillment mismatch")

    logger.info(f"Condition length: {len(condition)} hex chars ({len(condition)//2} bytes)")
    logger.info(f"Fulfillment length: {len(fulfillment)} hex chars ({len(fulfillment)//2} bytes)")
    return condition, fulfillment


def get_escrow_account_response(all_escrows_dict):
    return JsonResponse({
        'status': 'success',
        'message': 'Successfully retrieved escrow information.',
        'escrow_response': all_escrows_dict,
    })

def get_escrow_tx_id_account_response(result):
    return JsonResponse({
        'status': 'success',
        'message': 'Successfully retrieved escrow information.',
        'escrow_response': result,
    })

def create_escrow_account_response(result):
    return JsonResponse({
        'status': 'success',
        'message': 'Successfully created escrow.',
        'escrow_response': result,
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
        type="escrow"
    )


def create_escrow_transaction(sender_address, amount_to_escrow, receiving_account, condition, sequence, fee, last_ledger):
    return EscrowCreate(
        account=sender_address,
        amount=xrp_to_drops(amount_to_escrow),
        destination=receiving_account,
        condition=condition,
        sequence=sequence,
        fee=fee,
        cancel_after=datetime_to_ripple_time(datetime.now() + timedelta(days=1)),
        finish_after=datetime_to_ripple_time(datetime.now() + timedelta(minutes=5)),
        last_ledger_sequence=last_ledger + 300
    )


def create_cancel_escrow_transaction(sender_wallet_address, escrow_sequence):
    return EscrowCancel(
        account=sender_wallet_address,
        owner=sender_wallet_address,
        offer_sequence=escrow_sequence
    )


def create_finish_escrow_transaction(sender_wallet_address, escrow_creator, escrow_sequence, condition, fulfillment):
    return EscrowFinish(
        account=sender_wallet_address,
        owner=escrow_creator,
        offer_sequence=escrow_sequence,
        condition=condition,
        fulfillment=fulfillment
    )
