import json
import logging
from decimal import Decimal

from django.http import JsonResponse
from xrpl.models import Payment

from ..accounts.account_utils import update_sender_account_balances, update_receiver_account_balances
from ..models import XrplPaymentData
from ..utils import handle_error

logger = logging.getLogger('xrpl_app')

# Function to check for PayChannel entries
def check_pay_channel_entries(account_objects):
    pay_channel_entries = [entry for entry in account_objects if entry.get('LedgerEntryType') == 'PayChannel']
    if pay_channel_entries:
        logger.info(f"PayChannel entries found: {json.dumps(pay_channel_entries, indent=2)}")
        return False
    else:
        logger.info("No PayChannel entries found.")
        return True


def process_payment_response(payment_response, sender_address: str, receiver_address: str, amount_xrp: Decimal,
                             fee_drops: int):
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
        return send_payment_response(transaction_hash, sender_address, receiver_address, amount_xrp, fee_drops)
    except (AttributeError, KeyError, TypeError, ValueError) as e:
        # Log critical error and handle it by sending an error response
        logger.error(f"Unexpected error in process_payment_response: {str(e)}", exc_info=True)
        return handle_error({'status': 'failure', 'message': f'Internal error: {str(e)}'}, 500, 'send_payment')
    except Exception as e:
        # Log critical error and handle it by sending an error response
        logger.error(f"Unexpected error in process_payment_response: {str(e)}", exc_info=True)
        return handle_error({'status': 'failure', 'message': f'{str(e)}'}, 500, 'send_payment')


def send_payment_response(transaction_hash, sender_address, receiver_address, amount_xrp, fee_drops):
    """
    Constructs a JSON response for a successfully sent payment.

    Args:
        transaction_hash (str): The hash of the transaction that was sent.
        sender_address (str): The address of the account sending the payment.
        receiver_address (str): The address of the account receiving the payment.
        amount_xrp (float): The amount of XRP being sent in dollars.
        fee_drops (int): The fee for the transaction in drops.

    Returns:
        JsonResponse: A Django JsonResponse object containing details of the payment transaction.

    This function prepares a JSON response indicating that a payment has been successfully sent.
    It takes five arguments:
    - `transaction_hash`: The hash of the transaction that was sent.
    - `sender_address`: The address of the account sending the payment.
    - `receiver_address`: The address of the account receiving the payment.
    - `amount_xrp`: The amount of XRP being sent in dollars.
    - `fee_drops`: The fee for the transaction in drops.

    The function returns a Django JsonResponse object with keys for 'status', 'message', 'transaction_hash', 'sender', 'receiver', 'amount', and 'fee_drops'.
    - 'status' indicates the outcome of the operation ('success').
    - 'message' provides a brief description of the operation result.
    - 'transaction_hash' contains the hash of the transaction that was sent.
    - 'sender' contains the address of the account sending the payment.
    - 'receiver' contains the address of the account receiving the payment.
    - 'amount' contains the amount of XRP being sent in dollars.
    - 'fee_drops' contains the fee for the transaction in drops.

    This allows for a consistent format to inform clients about whether the payment was successfully sent and provide additional details if needed.
    """
    # Prepare and return a JSON response indicating successful payment
    return JsonResponse({
        'status': 'success',
        'message': 'Payment successfully sent.',
        'transaction_hash': transaction_hash,
        'sender': sender_address,
        'receiver': receiver_address,
        'amount': amount_xrp,
        'fee_drops': fee_drops,
    })


def create_payment_transaction(sender_address: str, receiver_address: str, amount_drops: int, fee_drops: int,
                               send_and_delete_wallet: bool) -> Payment:
    """
    Creates a Payment transaction object for transferring funds between two addresses.

    This function constructs a Payment transaction based on the provided parameters. Depending on the
    `send_and_delete_wallet` flag, the transaction may or may not include a fee. This is useful in scenarios
    where the sender's wallet is to be deleted after the transaction (e.g., for account deletion workflows).

    Parameters:
    - sender_address (str): The address of the sender initiating the payment.
    - receiver_address (str): The address of the receiver receiving the payment.
    - amount_drops (int): The amount to send, specified in drops (the smallest unit of the currency).
    - fee_drops (int): The transaction fee, specified in drops. Only applied if `send_and_delete_wallet` is False.
    - send_and_delete_wallet (bool): A flag indicating whether the sender's wallet will be deleted after the transaction.
                                     If True, the fee is omitted from the transaction.

    Returns:
    - Payment: A Payment object representing the transaction, configured based on the provided parameters.
    """
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
    """
    Saves a payment transaction record to the database.

    Args:
        sender (str): The classic address of the sender.
        receiver (str): The classic address of the receiver.
        amount (Decimal): The amount sent in XRP.
        transaction_hash (str): The hash of the transaction on the XRPL network.

    This function creates a new record in the XrplPaymentData model to store information about a payment
    transaction, including details such as sender, receiver, amount, and transaction hash. If there is an error
    during this process, it will raise a DatabaseError.
    """
    XrplPaymentData.objects.create(
        sender=sender,
        receiver=receiver,
        amount=amount,
        transaction_hash=transaction_hash,
    )