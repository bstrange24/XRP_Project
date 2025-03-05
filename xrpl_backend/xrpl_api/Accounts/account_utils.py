import json
import logging
from decimal import Decimal
import time
from django.http import JsonResponse
from xrpl.models import ServerInfo, AccountDelete, AccountInfo, AccountTx, AccountSet, AccountObjects, SetRegularKey, \
    AccountLines

from django.db import transaction
from xrpl.transaction import submit_and_wait
from .models.account_models import XrplAccountData
from ..constants.constants import XRPL_RESPONSE
from ..errors.error_handling import handle_engine_result, handle_error_new, process_transaction_error, error_response
from ..transactions.transactions_util import prepare_tx
from ..utilities.utilities import get_xrpl_client, parse_boolean_param, validate_xrpl_response_data, \
    total_execution_time_in_millis, map_request_parameters_to_flag_variables, \
    get_account_set_flags_from_request_parameters, count_xrp_received

logger = logging.getLogger('xrpl_app')


def process_all_flags(sender_address, client, sender_wallet, flags_to_enable, all_flags):
    """
    Iterate over all flags and process them individually.
    Returns a list of transaction responses.
    """
    tx_results = []
    for counter, flag in enumerate(all_flags, start=1):
        logger.info(f"Processing flag {counter} of {len(all_flags)}: {flag.name}")
        result = process_flag(sender_address, flag, client, sender_wallet, flags_to_enable)
        tx_results.append(result)
    return tx_results


def process_flag(sender_address, flag, client, sender_wallet, flags_to_enable):
    """
    Process a single flag by preparing, submitting, and validating the AccountSet transaction.
    """
    flag_start_time = time.time()
    if flag in flags_to_enable:
        logger.info(f"Processing enabled flag: {flag.name}")
        account_set_tx = prepare_account_set_enabled_tx(sender_address, flag)
    else:
        logger.info(f"Processing disabled flag: {flag.name}")
        account_set_tx = prepare_account_set_disabled_tx(sender_address, flag)

    # Submit the transaction and wait for ledger inclusion
    response = submit_and_wait(account_set_tx, client, sender_wallet)
    if validate_xrpl_response_data(response):
        process_transaction_error(response)

    count_xrp_received(response.result, sender_address)

    # Request transaction details using the returned hash
    tx_hash = response.result.get("hash")
    if not tx_hash:
        raise ValueError(error_response("Missing transaction hash in response"))

    tx_response = client.request(prepare_tx(tx_hash))
    if validate_xrpl_response_data(tx_response):
        process_transaction_error(tx_response)

    elapsed = total_execution_time_in_millis(flag_start_time)
    logger.info(f"Processed flag {flag.name} in {elapsed} ms")
    return tx_response.result


def get_account_set_flags(self, data):
    flags_to_enable = []
    flags_to_disable = []

    flag_params = map_request_parameters_to_flag_variables()
    logger.info(f"Mapping of request parameters to flags: {flag_params}")

    non_none_request_parameters = get_account_set_flags_from_request_parameters(self, data)
    logger.info(f"Non-None request parameters: {non_none_request_parameters}")

    for param_name, flag_value in flag_params.items():
        if param_name in non_none_request_parameters:
            flag_state = parse_boolean_param(self, param_name, data)
            logger.info(f"param_name: {param_name}, flag_value: {flag_value}, flag_state: {flag_state}")
            if flag_state:
                flags_to_enable.append(flag_value)
            else:
                flags_to_disable.append(flag_value)

    return flags_to_enable, flags_to_disable


def get_account_objects(account: str):
    account_objects_request = prepare_account_object_with_filter(account, None)
    account_objects_response = get_xrpl_client().request(account_objects_request)

    if "error" in account_objects_response.result:
        logger.error(f"Account {account} not found!")
        return None

    return account_objects_response.result.get('account_objects', [])


def check_check_entries(account_objects):
    check_entries = [entry for entry in account_objects if entry.get('LedgerEntryType') == 'Check']

    if check_entries:
        logger.error(f"Check entries found: {json.dumps(check_entries, indent=2)}")
        return False

    logger.info("No Check entries found.")
    return True


def get_account_reserves():
    try:
        response = get_xrpl_client().request(ServerInfo())

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


def get_account_details(client, wallet_address: str):
    try:
        account_info = prepare_account_data(wallet_address, False)

        response = client.request(account_info)

        logger.debug(XRPL_RESPONSE)
        logger.debug(json.dumps(response.result, indent=4, sort_keys=True))

        print(response.is_successful())

        if response and response.status == 'success':
            result = response.result
            return {
                'result': result,
            }
        else:
            logger.error(f"Failed to retrieve account details. Response: {response.text}")
            engine_result = response.result.get("engine_result")
            if engine_result is None:
                engine_result = 'unknown'

            engine_result_message = response.result.get("engine_result_message",
                                                        "Transaction response was unsuccessful.")
            handle_engine_result(engine_result, engine_result_message)
            return None

    except Exception as e:
        logger.error(f"Error retrieving account details: {str(e)}")
        return None

def account_reserves_response(server_information_response, reserve_base, reserve_inc):
    return JsonResponse({
        'status': 'success',
        'message': 'XRP reserves fetched successfully.',
        'base_reserve': reserve_base,
        'owner_reserve': reserve_inc,
        'result': server_information_response.result
    })


def account_set_tx_response(response, sender_address):
    return JsonResponse({
        'status': 'success',
        'message': 'Successfully updated account settings.',
        'transaction_hash': response['hash'],
        'account': sender_address,
        'result': response
    })


def black_hole_xrp_response(response):
    return JsonResponse({
        'status': 'success',
        'message': 'Account successfully black holed.',
        'result': response.result,
    })


def delete_account_response(tx_response):
    return JsonResponse({
        'status': 'success',
        'message': 'Account successfully black-holed.',
        'tx_response': tx_response.result,
    })


def account_tx_with_pagination_response(paginated_transactions, paginator):
    return JsonResponse({
        "status": "success",
        "message": "Transaction history successfully retrieved.",
        # "transactions": paginated_transactions.object_list,
        "transactions": list(paginated_transactions),
        "page": paginated_transactions.number,
        "total_pages": paginator.num_pages,
        "total_count": paginator.count
    })


def account_delete_tx_response(account_delete_response, payment_response):
    return JsonResponse({
        'status': 'success',
        'message': 'Funds transferred and account deleted successfully.',
        'account_delete_response': account_delete_response.result,
        'payment_response': payment_response.result,
        'payment_response_hash': payment_response.result['hash'],
        'account_delete_response_hash': account_delete_response.result['hash']
    })


def create_wallet_info_response(base_reserve, reserve_increment, account_details):
    return JsonResponse({
        'status': 'success',
        'message': 'Successfully retrieved account information.',
        'reserve': base_reserve,
        'reserve_increment': reserve_increment,
        'result': account_details,
    })


def create_wallet_balance_response(balance_in_xrp, account_details):
    return JsonResponse({
        'status': 'success',
        'message': 'Successfully retrieved account balance.',
        "balance": balance_in_xrp,
        'result': account_details,
    })


def create_account_response(wallet_address, seed, xrp_balance, account_details):
    return JsonResponse({
        'status': 'success',
        'message': 'Successfully created wallet.',
        'account_id': wallet_address,
        'secret': seed,
        'balance': xrp_balance,
        'transaction_hash': account_details['ledger_hash'],
        'previous_transaction_id': account_details['account_data']['PreviousTxnID'],
    })


def create_multiple_account_response(transactions):
    return JsonResponse({
        "status": "success",
        "message": f"{len(transactions)} Wallets created.",
        "transactions": transactions,
    })


def create_account_lines_response(paginated_transactions, paginator):
    return JsonResponse({
        "status": "success",
        "message": "Account Lines successfully retrieved.",
        "trust_lines": list(paginated_transactions),
        "total_account_lines": paginator.count,
        "pages": paginator.num_pages,
        "current_page": paginated_transactions.number,
    })


def create_cancel_offers_response(cancel_offers_transaction_response):
    return JsonResponse({
        'status': 'success',
        'message': 'Successfully cancelled offers.',
        'result': cancel_offers_transaction_response.result,
    })

def account_config_settings(response):
    return JsonResponse({
        "status": "success",
        "message": "Account configuration retrieved successfully.",
        "result": response,
    })

def prepare_account_data(sender_address, black_hole):
    if black_hole:
        return AccountInfo(
            account=sender_address,
        )
    else:
        return AccountInfo(
            account=sender_address,
            ledger_index="validated",
            strict=True,
        )


def prepare_regular_key(wallet_address, black_hole_address):
    return SetRegularKey(
        account=wallet_address,
        regular_key=black_hole_address
    )


def prepare_account_delete(sender_address):
    return AccountDelete(
        account=sender_address,
        destination=sender_address,
        fee="12",
    )


def create_account_delete_transaction(sender_address: str, receiver_address: str, last_ledger_sequence: int):
    return AccountDelete(
        account=sender_address,
        destination=receiver_address,
        last_ledger_sequence=last_ledger_sequence + 200  # Set the custom LastLedgerSequence
    )


def prepare_account_tx_with_pagination(sender_address, marker):
    return AccountTx(
        account=sender_address,
        ledger_index_min=-1,
        ledger_index_max=-1,
        limit=100,
        marker=marker,
    )


def prepare_account_set_enabled_tx(sender_address, flag):
    return AccountSet(
        account=sender_address,
        set_flag=flag,
    )


def prepare_account_set_disabled_tx(sender_address, flag):
    return AccountSet(
        account=sender_address,
        clear_flag=flag,
    )


def prepare_account_lines(wallet_address, marker):
    return AccountLines(
        account=wallet_address,
        limit=100,
        marker=marker,
        ledger_index="validated",
    )


def prepare_account_tx(sender_address):
    return AccountTx(
        account=sender_address,
        limit=100
    )

def prepare_account_tx_for_hash_account(address, marker):
    return AccountTx(
        account=address,
        ledger_index_min=-1,  # Start from the earliest ledger
        ledger_index_max=-1,  # Up to the latest validated ledger
        limit=100,
        marker = marker,
    )

def prepare_account_object_with_filter(account, object_type=None):
    if object_type is None:
        return AccountObjects(
            account=account
        )
    else:
        return AccountObjects(
            account=account,
            type=object_type
        )

