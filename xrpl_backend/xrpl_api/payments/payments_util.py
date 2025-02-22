import asyncio
import json
import logging
import time
from decimal import Decimal

from django.http import JsonResponse
from xrpl import XRPLException
from xrpl.asyncio.clients import AsyncJsonRpcClient
from xrpl.asyncio.transaction import submit_and_wait
from xrpl.models import Payment, Ledger, ServerInfo, AccountObjects

from .db_operations.payments_db_operations import save_payment_data
from ..errors.error_handling import error_response, handle_error_new

logger = logging.getLogger('xrpl_app')


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

    if account_objects is None:
        return False

    return True, account_objects


async def get_account_reserves(client, *args, **kwargs):
    try:
        response = await client.request(ServerInfo())

        validated_ledger = response.result.get('info', {}).get('validated_ledger', {})

        base_reserve = validated_ledger.get('reserve_base_xrp')
        reserve_inc = validated_ledger.get('reserve_inc_xrp')

        if base_reserve is None or reserve_inc is None:
            logger.error("Reserve data not found in ledger info.")
            return None, None

        return int(base_reserve), int(reserve_inc)

    except Exception as e:
        logger.error(f"Error fetching ledger info: {e}")
        return None, None


async def calculate_last_ledger_sequence(client: AsyncJsonRpcClient, buffer_time=60, retries=5, delay=4):
    for attempt in range(1, retries + 1):
        try:
            ledger_info = await client.request(Ledger(ledger_index="validated"))
            latest_ledger = ledger_info.result["ledger_index"]

            avg_ledger_close_time = 4
            min_ledgers_ahead = 10
            max_ledgers_ahead = 15

            safe_ledger_gap = max(min_ledgers_ahead, (buffer_time // avg_ledger_close_time) + 5)
            last_ledger_sequence = latest_ledger + min(safe_ledger_gap, max_ledgers_ahead)

            logger.info(
                f"Attempt {attempt}: Latest Ledger {latest_ledger}, Setting LastLedgerSequence: {last_ledger_sequence}")
            return last_ledger_sequence

        except Exception as e:
            logger.error(f"Attempt {attempt} failed: {str(e)}")
            if attempt < retries:
                logger.info(f"Retrying in {delay} seconds...")
                await asyncio.sleep(delay)
            else:
                logger.error("All retry attempts failed.")
                raise e


async def get_remaining_time_for_ledger_close(client):
    ledger_info = await client.request(Ledger())
    close_time = ledger_info.result['closed']['ledger']['close_time']

    if close_time is None:
        raise ValueError(error_response("Ledger close time not found in the response."))

    current_time = int(time.time())
    remaining_time = close_time - current_time

    remaining_time = max(remaining_time, 0)
    return remaining_time


def check_pay_channel_entries(account_objects):
    pay_channel_entries = [entry for entry in account_objects if entry.get('LedgerEntryType') == 'PayChannel']
    if pay_channel_entries:
        logger.info(f"PayChannel entries found: {json.dumps(pay_channel_entries, indent=2)}")
        return False
    else:
        logger.info("No PayChannel entries found.")
        return True


def process_payment_response(payment_result: dict, payment_response, sender_address: str, receiver_address: str,
                             amount_xrp: Decimal, fee_drops: str):
    function_name = "process_payment_response"
    try:
        logger.debug(f"Payment response: {payment_response}")

        # Extract the transaction hash from the response
        transaction_hash = payment_response.result.get('hash')
        if not transaction_hash:
            raise XRPLException(error_response("Transaction hash missing in response."))

        logger.info(f"Payment successful: {transaction_hash}")

        # Save the payment transaction details
        logger.info(f"Saving payment data in table")
        save_payment_data(payment_result.result, transaction_hash, sender_address, receiver_address, amount_xrp,
                                     str(fee_drops))

        # Send a response to indicate successful payment
        return send_payment_response(payment_result, transaction_hash, sender_address, receiver_address, amount_xrp,
                                     str(fee_drops))
    except (XRPLException, AttributeError, KeyError, TypeError, ValueError) as e:
        # Handle error message
        return handle_error_new(e, status_code=500, function_name=function_name)
    except Exception as e:
        # Handle error message
        return handle_error_new(e, status_code=500, function_name=function_name)
    finally:
        pass


def send_payment_response(result: dict, transaction_hash: str, sender_address: str, receiver_address: str,
                          amount_xrp: Decimal, fee_drops: str):
    return JsonResponse({
        'status': 'success',
        'message': 'Payment successfully sent.',
        'result': result.result,
        'transaction_hash': transaction_hash,
        'sender': sender_address,
        'receiver': receiver_address,
        'amount': amount_xrp,
        'fee_drops': fee_drops,
    })


def create_payment_transaction(sender_address: str, receiver_address: str, amount_drops: str, fee_drops: str,
                               send_and_delete_wallet: bool) -> Payment:
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
