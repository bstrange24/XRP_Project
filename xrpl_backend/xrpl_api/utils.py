from django.http import JsonResponse

import logging
import json
import constants
from xrpl.clients import JsonRpcClient
from xrpl.models import AccountInfo, ServerInfo
from xrpl.wallet import Wallet

logger = logging.getLogger('xrpl_app')

def handle_error(error_message, status_code, function_name):
    """
    Logs an error and returns a JsonResponse with the error message.
    """
    logger.error(error_message)
    logger.error(f"Leaving: {function_name}")
    return JsonResponse({'error': error_message}, status=status_code)

def validate_account_id(wallet_address):
    """
    Validates the format of an XRPL account ID.
    """
    if not wallet_address or not wallet_address.startswith('r') or len(wallet_address) < 25 or len(wallet_address) > 35:
        return False
    return True

def validate_transaction_hash(transaction_hash):
    """
    Validates the format of an XRPL account ID.
    """
    if not transaction_hash or not len(transaction_hash) > 25:
        return False
    return True

def get_xrpl_client():
    """
    Returns a configured JSON-RPC client for the XRPL Testnet.
    """
    return JsonRpcClient(constants.JSON_RPC_URL)

def get_account_reserves():
    """
    Returns the reserves information from the server.
    """
    try:
        # Request network settings (server info) to get the reserve info
        # Create request for server info to fetch reserve data
        response = get_xrpl_client().request(ServerInfo())

        # Extract reserve information from the response
        if response.result and 'info' in response.result:
            logger.debug(json.dumps(response.result, indent=4, sort_keys=True))
            server_info = response.result['info']
            reserve_base = server_info['validated_ledger']['reserve_base_xrp']
            reserve_inc = server_info['validated_ledger']['reserve_inc_xrp']

            if reserve_base is None or reserve_inc is None:
                logger.error("Reserve data not found in server info.")
                return None, None

            return reserve_base, reserve_inc
        else:
            # No response from server
            logger.error("Failed to fetch server info.")
            return None, None

    except Exception as e:
        logger.error(f"Error fetching server info: {e}")
        return None, None

def check_for_none(object, function_name, error_message):
    if not object:
        return handle_error({'status': 'failure', 'message': f"{error_message}"}, status_code=500,
                            function_name=function_name)

# def check_for_none_wallet(wallet,function_name):
#     if not wallet:
#         return handle_error({'status': 'failure', 'message': f"Error creating new wallet. Wallet is empty"}, status_code=500,
#                             function_name=function_name)

# def check_for_none_account_info(acct_info, function_name):
#     if not acct_info:
#         return handle_error({'status': 'failure', 'message': f"Error creating Account Info."}, status_code=500,
#                             function_name=function_name)

# def get_xrpl_client_and_wallet(sender_seed=None):
#     client = get_xrpl_client()  # Centralized client creation
#     if sender_seed:
#         wallet = Wallet.from_seed(sender_seed)
#     else:
#         wallet = None
#     return client, wallet

# def validate_and_get_account(account_id):
#     if not validate_account_id(account_id):
#         return handle_error({'status': 'failure', 'message': 'Invalid address format.'}, status_code=400)
#
#     client = get_xrpl_client()
#     account_info_request = AccountInfo(account=account_id, ledger_index="validated")
#     response = client.request(account_info_request)
#     if not response.is_successful():
#         return handle_error({'status': 'failure', 'message': 'Account not found on XRPL.'}, status_code=404)
#
#     return response.result

# def convert_xrp_balance_to_float(balance):
#     balance = int(balance) / 1000000
#     formatted_balance = round(balance, 2)
#     return str(formatted_balance)
