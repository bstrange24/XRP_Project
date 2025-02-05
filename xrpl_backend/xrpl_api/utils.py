from django.http import JsonResponse
import logging

from xrpl.clients import JsonRpcClient

logger = logging.getLogger(__name__)
JSON_RPC_URL = "https://s.altnet.rippletest.net:51234/"

def handle_error(error_message, status_code=500):
    """
    Logs an error and returns a JsonResponse with the error message.
    """
    logger.error(error_message)
    return JsonResponse({'error': error_message}, status=status_code)

def validate_account_id(account_id):
    """
    Validates the format of an XRPL account ID.
    """
    if not account_id.startswith("r") or len(account_id) < 25 or len(account_id) > 35:
        return False
    return True

def get_xrpl_client():
    """
    Returns a configured JSON-RPC client for the XRPL Testnet.
    """
    return JsonRpcClient(JSON_RPC_URL)