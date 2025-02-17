import json
import logging
from decimal import Decimal

from django.http import JsonResponse
from xrpl.models import Payment

from ..accounts.account_utils import update_sender_account_balances, update_receiver_account_balances
from ..models import XrplPaymentData
from ..utils import handle_error

logger = logging.getLogger('xrpl_app')


def check_pay_channel_entries(account_objects):
    pay_channel_entries = [entry for entry in account_objects if entry.get('LedgerEntryType') == 'PayChannel']
    if pay_channel_entries:
        logger.info(f"PayChannel entries found: {json.dumps(pay_channel_entries, indent=2)}")
        return False
    else:
        logger.info("No PayChannel entries found.")
        return True


def process_payment_response(result: dict, payment_response, sender_address: str, receiver_address: str, amount_xrp: Decimal, fee_drops: str):
    try:
        logger.debug(f"Payment response: {payment_response}")

        # Extract the transaction hash from the response
        transaction_hash = payment_response.result.get('hash')
        if not transaction_hash:
            raise ValueError("Transaction hash missing in response.")

        logger.info(f"Payment successful: {transaction_hash}")

        # Save the transaction details
        save_transaction(sender_address, receiver_address, amount_xrp, transaction_hash)

        # Update the balances of both sender and receiver accounts
        update_sender_account_balances(sender_address, amount_xrp)
        update_receiver_account_balances(receiver_address, amount_xrp)

        # Send a response to indicate successful payment
        return send_payment_response(result, transaction_hash, sender_address, receiver_address, amount_xrp, str(fee_drops))
    except (AttributeError, KeyError, TypeError, ValueError) as e:
        # Log critical error and handle it by sending an error response
        logger.error(f"Unexpected error in process_payment_response: {str(e)}", exc_info=True)
        return handle_error({'status': 'failure', 'message': f'Internal error: {str(e)}'}, 500, 'send_payment')
    except Exception as e:
        # Log critical error and handle it by sending an error response
        logger.error(f"Unexpected error in process_payment_response: {str(e)}", exc_info=True)
        return handle_error({'status': 'failure', 'message': f'{str(e)}'}, 500, 'send_payment')


def send_payment_response(result: dict, transaction_hash: str, sender_address: str, receiver_address: str, amount_xrp: Decimal, fee_drops: str):
    return JsonResponse({
        'status': 'success',
        'message': 'Payment successfully sent.',
        'result': result,
        'transaction_hash': transaction_hash,
        'sender': sender_address,
        'receiver': receiver_address,
        'amount': amount_xrp,
        'fee_drops': fee_drops,
    })


def create_payment_transaction(sender_address: str, receiver_address: str, amount_drops: str, fee_drops: str, send_and_delete_wallet: bool) -> Payment:
    if send_and_delete_wallet:
        # Create a Payment transaction without a fee (used when the sender's wallet will be deleted)
        return Payment(
            account=sender_address,
            destination=receiver_address,
            amount=str(amount_drops)  # Amount must be passed as a string
        )
    else:
        # Create a Payment transaction with a fee (standard use case)
        return Payment(
            account=sender_address,
            destination=receiver_address,
            amount=str(amount_drops),
            fee=str(fee_drops),  # Fee must be passed as a string
        )


def save_transaction(sender: str, receiver: str, amount: Decimal, transaction_hash: str):
    XrplPaymentData.objects.create(
        sender=sender,
        receiver=receiver,
        amount=amount,
        transaction_hash=transaction_hash,
    )