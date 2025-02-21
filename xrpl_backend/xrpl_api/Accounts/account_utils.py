import json
import logging
from decimal import Decimal
import time
from django.http import JsonResponse
from xrpl.models import ServerInfo, AccountDelete, AccountInfo, AccountTx, AccountSet, AccountObjects, SetRegularKey, AccountLines, AccountSetAsfFlag

from django.db import transaction
from xrpl.transaction import submit_and_wait
from .models.account_models import XrplAccountData
from ..constants import XRPL_RESPONSE
from ..errors.error_handling import handle_engine_result, handle_error_new, process_transaction_error, error_response
from ..transactions.transactions_util import prepare_tx
from ..utils import get_xrpl_client, parse_boolean_param, get_query_param, validate_xrpl_response_data, \
    total_execution_time_in_millis

logger = logging.getLogger('xrpl_app')

def process_all_flags(sender_address, client, sender_wallet, flags_to_enable, all_flags):
    """
    Iterate over all flags and process them individually.
    Returns a list of transaction responses.
    """
    tx_results = []
    for counter, flag in enumerate(all_flags, start=1):
        logger.info("Processing flag %d of %d: %s", counter, len(all_flags), flag.name)
        result = process_flag(sender_address, flag, client, sender_wallet, flags_to_enable)
        tx_results.append(result)
    return tx_results


def process_flag(sender_address, flag, client, sender_wallet, flags_to_enable):
    """
    Process a single flag by preparing, submitting, and validating the AccountSet transaction.
    """
    flag_start_time = time.time()
    if flag in flags_to_enable:
        logger.info("Processing enabled flag: %s", flag.name)
        account_set_tx = prepare_account_set_enabled_tx(sender_address, flag)
    else:
        logger.info("Processing disabled flag: %s", flag.name)
        account_set_tx = prepare_account_set_disabled_tx(sender_address, flag)

    # Submit the transaction and wait for ledger inclusion
    response = submit_and_wait(account_set_tx, client, sender_wallet)
    if validate_xrpl_response_data(response):
        process_transaction_error(response)

    # Request transaction details using the returned hash
    tx_hash = response.result.get("hash")
    if not tx_hash:
        raise ValueError(error_response("Missing transaction hash in response"))

    tx_response = client.request(prepare_tx(tx_hash))
    if validate_xrpl_response_data(tx_response):
        process_transaction_error(tx_response)

    elapsed = total_execution_time_in_millis(flag_start_time)
    logger.info("Processed flag %s in %sms", flag.name, elapsed)
    return tx_response.result

def get_account_set_flags(self):
    flags_to_enable = []
    flags_to_disable = []

    flag_params = map_request_parameters_to_flag_variables()
    logger.info("Mapping of request parameters to flags: %s", flag_params)

    non_none_request_parameters = get_account_set_flags_from_request_parameters(self)
    logger.info("Non-None request parameters: %s", non_none_request_parameters)

    for param_name, flag_value in flag_params.items():
        if param_name in non_none_request_parameters:
            flag_state = parse_boolean_param(self, param_name)
            logger.info(f"param_name: {param_name}, flag_value: {flag_value}, flag_state: {flag_state}")
            if flag_state:
                flags_to_enable.append(flag_value)
            else:
                flags_to_disable.append(flag_value)

    return flags_to_enable, flags_to_disable


def map_request_parameters_to_flag_variables():
    return {
        'asf_account_txn_id': AccountSetAsfFlag.ASF_ACCOUNT_TXN_ID,
        'asf_allow_trustline_clawback': AccountSetAsfFlag.ASF_ALLOW_TRUSTLINE_CLAWBACK,
        'asf_authorized_nftoken_minter': AccountSetAsfFlag.ASF_AUTHORIZED_NFTOKEN_MINTER,
        'asf_default_ripple': AccountSetAsfFlag.ASF_DEFAULT_RIPPLE,
        'asf_deposit_auth': AccountSetAsfFlag.ASF_DEPOSIT_AUTH,
        'asf_disable_master': AccountSetAsfFlag.ASF_DISABLE_MASTER,
        'asf_disable_incoming_check': AccountSetAsfFlag.ASF_DISABLE_INCOMING_CHECK,
        'asf_disable_incoming_nftoken_offer': AccountSetAsfFlag.ASF_DISABLE_INCOMING_NFTOKEN_OFFER,
        'asf_disable_incoming_paychan': AccountSetAsfFlag.ASF_DISABLE_INCOMING_PAYCHAN,
        'asf_disable_incoming_trustline': AccountSetAsfFlag.ASF_DISABLE_INCOMING_TRUSTLINE,
        'asf_disallow_XRP': AccountSetAsfFlag.ASF_DISALLOW_XRP,
        'asf_global_freeze': AccountSetAsfFlag.ASF_GLOBAL_FREEZE,
        'asf_no_freeze': AccountSetAsfFlag.ASF_NO_FREEZE,
        'asf_require_auth': AccountSetAsfFlag.ASF_REQUIRE_AUTH,
        'asf_require_dest': AccountSetAsfFlag.ASF_REQUIRE_DEST,
    }


def get_account_set_flags_from_request_parameters(self):
    params = {
        'asf_account_txn_id': get_query_param(self.query_params, 'asf_account_txn_id'),
        'asf_allow_trustline_clawback': get_query_param(self.query_params, 'asf_allow_trustline_clawback'),
        'asf_authorized_nftoken_minter': get_query_param(self.query_params, 'asf_authorized_nftoken_minter'),
        'asf_default_ripple': get_query_param(self.query_params, 'asf_default_ripple'),
        'asf_deposit_auth': get_query_param(self.query_params, 'asf_deposit_auth'),
        'asf_disable_master': get_query_param(self.query_params, 'asf_disable_master'),
        'asf_disable_incoming_check': get_query_param(self.query_params, 'asf_disable_incoming_check'),
        'asf_disable_incoming_nftoken_offer': get_query_param(self.query_params, 'asf_disable_incoming_nftoken_offer'),
        'asf_disable_incoming_paychan': get_query_param(self.query_params, 'asf_disable_incoming_paychan'),
        'asf_disable_incoming_trustline': get_query_param(self.query_params, 'asf_disable_incoming_trustline'),
        'asf_disallow_XRP': get_query_param(self.query_params, 'asf_disallow_XRP'),
        'asf_global_freeze': get_query_param(self.query_params, 'asf_global_freeze'),
        'asf_no_freeze': get_query_param(self.query_params, 'asf_no_freeze'),
        'asf_require_auth': get_query_param(self.query_params, 'asf_require_auth'),
        'asf_require_dest': get_query_param(self.query_params, 'asf_require_dest')
    }

    # Return only those keys and values where value is not None.
    non_none_request_parameters = {key: value for key, value in params.items() if value is not None}
    return non_none_request_parameters


def get_account_objects(account: str):
    account_objects_request = AccountObjects(account=account)
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


def update_sender_account_balances(sender_address: str, amount_xrp: Decimal):
    try:
        with transaction.atomic():  # Ensures the update is committed
            sender_account = XrplAccountData.objects.select_for_update().get(account=sender_address)

            if amount_xrp <= 0:
                logger.warning(f"Skipping update: amount_xrp={amount_xrp}")
                return

            sender_account.balance -= amount_xrp
            sender_account.save(update_fields=["balance"])  # Force update

    except XrplAccountData.DoesNotExist as e:
        # Handle error message
        return handle_error_new(e, status_code=500, function_name='update_sender_account_balances')
    except Exception as e:
        # Handle error message
        return handle_error_new(e, status_code=500, function_name='update_sender_account_balances')


def update_receiver_account_balances(receiver_address: str, amount_xrp: Decimal):
    try:
        with transaction.atomic():
            receiver_account = XrplAccountData.objects.get(account=receiver_address)

            if amount_xrp <= 0:
                logger.warning(f"Skipping update: amount_xrp={amount_xrp}")
                return

            receiver_account.balance += amount_xrp
            receiver_account.save()

    except XrplAccountData.DoesNotExist as e:
        # Handle error message
        return handle_error_new(e, status_code=500, function_name='update_receiver_account_balances')
    except Exception as e:
        # Handle error message
        return handle_error_new(e, status_code=500, function_name='update_receiver_account_balances')


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


def account_tx_with_pagination_response(paginated_transactions, count, num_pages):
    return JsonResponse({
        "status": "success",
        "message": "Transaction history successfully retrieved.",
        "transactions": list(paginated_transactions),
        "total_transactions": count,
        "pages": num_pages,
        "current_page": paginated_transactions.number,
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


def create_account_delete_transaction(sender_address: str, receiver_address: str, last_ledger_sequence: str):
    return AccountDelete(
        account=sender_address,
        destination=receiver_address,
        last_ledger_sequence=int(last_ledger_sequence)  # Set the custom LastLedgerSequence
    )


def create_account_lines_response(paginated_transactions, paginator):
    return JsonResponse({
        "status": "success",
        "message": "Account Lines successfully retrieved.",
        "trust_lines": list(paginated_transactions),
        "total_account_lines": paginator.count,
        "pages": paginator.num_pages,
        "current_page": paginated_transactions.number,
    })


def account_config_settings(response):
    return JsonResponse({
        "status": "success",
        "message": "Account configuration retrieved successfully.",
        "result": response,
    })


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
        limit=100  # Increase limit to fetch more transactions at once, reducing the need for multiple requests
    )



