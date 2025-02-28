import json
import logging
import time
from django.http import JsonResponse
from xrpl.models import Ledger
from ..accounts.account_utils import get_account_objects

logger = logging.getLogger('xrpl_app')


def get_remaining_time_for_ledger_close(client):
    """
    Returns the remaining time in seconds for the current ledger to close.
    """
    ledger_info = client.request(Ledger())
    close_time = ledger_info.result['closed']['ledger']['close_time']

    if close_time is None:
        raise ValueError("Ledger close time not found in the response.")

    current_time = int(time.time())  # Get current time in seconds
    remaining_time = close_time - current_time  # Remaining time until ledger close

    remaining_time = max(remaining_time, 0)  # Ensure non-negative remaining time
    return remaining_time


def calculate_last_ledger_sequence(client, buffer_time=30):
    """
    Calculates an appropriate LastLedgerSequence dynamically based on the remaining time
    until the current ledger closes.
    buffer_time is the amount of time in seconds that should be added as a buffer to avoid tecTOO_SOON error.
    """
    # Get the remaining time until the ledger closes
    remaining_time = get_remaining_time_for_ledger_close(client)

    # If there's not enough time left, wait until the next ledger
    if remaining_time <= buffer_time:
        logger.warning("Not enough time left in the current ledger. Waiting for the next ledger...")
        time.sleep(buffer_time)  # Wait for the buffer time to pass
        remaining_time = get_remaining_time_for_ledger_close(client)  # Recheck for the next ledger

    # Get the current ledger index
    ledger_info = client.request(Ledger())
    current_ledger = ledger_info.result['closed']['ledger']['ledger_index']

    # Calculate the number of ledgers that can be closed within the remaining time
    # Assuming an average ledger close time of 4 seconds
    avg_ledger_close_time = 4  # seconds
    ledgers_ahead = max(1, int((remaining_time + buffer_time) / avg_ledger_close_time))

    # Set the LastLedgerSequence to the current ledger + ledgers_ahead
    last_ledger_sequence = current_ledger + ledgers_ahead

    # Ensure that LastLedgerSequence is strictly greater than the current ledger index
    last_ledger_sequence = max(last_ledger_sequence, current_ledger + 1)

    logger.info(f"Calculated LastLedgerSequence: {last_ledger_sequence}")
    return last_ledger_sequence


def check_ripple_state_entries(account_objects):
    # Filter ripple state entries
    ripple_state_entries = [entry for entry in account_objects if entry.get('LedgerEntryType') == 'RippleState']

    if ripple_state_entries:
        logger.error(f"RippleState entries found: {json.dumps(ripple_state_entries, indent=2)}")
        return False

    logger.info("No RippleState entries found.")
    return True


def check_account_ledger_entries(account: str):
    # Get account objects
    account_objects = get_account_objects(account)

    # Return early if account objects are None
    if account_objects is None:
        return False

    # Return True and the account objects if they exist
    return True, account_objects


def ledger_info_response(response):
    return JsonResponse({
        'status': 'success',
        'message': 'Server info fetched successfully.',
        'result': response.result
    })