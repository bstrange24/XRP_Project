import json
import logging
import time
from decimal import Decimal

import asyncio
from django.http import JsonResponse
from xrpl.asyncio.clients import AsyncJsonRpcClient
from xrpl.asyncio.transaction import submit_and_wait
from xrpl.models import Payment, Ledger, ServerInfo, AccountObjects

from ..accounts.account_utils import update_sender_account_balances, update_receiver_account_balances
from ..models import XrplPaymentData
from ..utils import handle_error

logger = logging.getLogger('xrpl_app')

# Ensure this function runs properly in Django's event loop
async def process_payment(payment_tx, client, sender_wallet):
    result = await submit_and_wait(payment_tx, client, sender_wallet)
    return result


async def check_account_ledger_entries(client, account, *args, **kwargs):
    account_objects_request = AccountObjects(account=account)
    account_objects_response = await client.request(account_objects_request)

    if "error" in account_objects_response.result:
        logger.error(f"Account {account} not found!")
        return None

    account_objects = account_objects_response.result.get('account_objects', [])

    # Return early if account objects are None
    if account_objects is None:
        return False

    # Return True and the account objects if they exist
    return True, account_objects


async def get_account_reserves(client, *args, **kwargs):
    try:
        # Request ledger info from the XRP Ledger using the XRPL client
        response = await client.request(ServerInfo())

        # Extract the 'validated_ledger' object from the ledger info response
        validated_ledger = response.result.get('info', {}).get('validated_ledger', {})

        # Retrieve the base reserve and reserve increment values from the validated ledger
        base_reserve = validated_ledger.get('reserve_base_xrp')
        reserve_inc = validated_ledger.get('reserve_inc_xrp')

        # Check if either value is missing (None)
        if base_reserve is None or reserve_inc is None:
            logger.error("Reserve data not found in ledger info.")
            return None, None

        # Convert the values to integers and return them
        return int(base_reserve), int(reserve_inc)

    except Exception as e:
        # Log any exceptions that occur during the process
        logger.error(f"Error fetching ledger info: {e}")
        return None, None


async def calculate_last_ledger_sequence(client: AsyncJsonRpcClient, buffer_time=60, retries=5, delay=4):
    """
    Calculate a safe LastLedgerSequence for an XRPL transaction.

    :param client: The XRPL AsyncJsonRpcClient.
    :param buffer_time: Extra time in seconds before the ledger closes.
    :param retries: Number of retries if we get an invalid ledger sequence.
    :param delay: Delay in seconds between retries.
    :return: LastLedgerSequence index.
    """

    for attempt in range(1, retries + 1):
        try:
            # 🔹 Get the latest validated ledger index
            ledger_info = await client.request(Ledger(ledger_index="validated"))
            latest_ledger = ledger_info.result["ledger_index"]

            # 🔹 Ensure we set a reasonable LastLedgerSequence
            avg_ledger_close_time = 4  # XRPL ledgers close every ~4 seconds
            min_ledgers_ahead = 10  # Ensure at least 10 ledgers ahead
            max_ledgers_ahead = 15  # Prevent setting it too far ahead

            safe_ledger_gap = max(min_ledgers_ahead, (buffer_time // avg_ledger_close_time) + 5)
            last_ledger_sequence = latest_ledger + min(safe_ledger_gap, max_ledgers_ahead)

            logger.info(
                f"Attempt {attempt}: Latest Ledger {latest_ledger}, Setting LastLedgerSequence: {last_ledger_sequence}")
            return last_ledger_sequence  # ✅ Success

        except Exception as e:
            logger.error(f"Attempt {attempt} failed: {str(e)}")
            if attempt < retries:
                logger.info(f"Retrying in {delay} seconds...")
                await asyncio.sleep(delay)  # 🔹 Wait for the next ledger to close
            else:
                logger.error("All retry attempts failed.")
                raise  # Rethrow exception after max retries


async def get_remaining_time_for_ledger_close(client):
    """
    Returns the remaining time in seconds for the current ledger to close.
    """
    ledger_info = await client.request(Ledger())
    close_time = ledger_info.result['closed']['ledger']['close_time']

    if close_time is None:
        raise ValueError("Ledger close time not found in the response.")

    current_time = int(time.time())  # Get current time in seconds
    remaining_time = close_time - current_time  # Remaining time until ledger close

    remaining_time = max(remaining_time, 0)  # Ensure non-negative remaining time
    return remaining_time


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
        save_transaction(sender_address, receiver_address, Decimal(amount_xrp), transaction_hash)

        # Update the balances of both sender and receiver accounts
        update_sender_account_balances(sender_address, Decimal(amount_xrp))
        update_receiver_account_balances(receiver_address, Decimal(amount_xrp))

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