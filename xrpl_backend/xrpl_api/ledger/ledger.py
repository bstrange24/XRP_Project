import json
import logging
import time

from django.core.cache import cache
from django.http import JsonResponse
from django.views import View
from tenacity import retry, wait_exponential, stop_after_attempt
from xrpl import XRPLException
from xrpl.account import does_account_exist
from xrpl.asyncio.clients import XRPLRequestFailureException
from xrpl.models import ServerInfo, Ledger

from .db_operations.ledger_db_operations import save_ledger_info, save_server_info
from ..accounts.account_utils import account_reserves_response
from ..constants.constants import RETRY_BACKOFF, MAX_RETRIES, ENTERING_FUNCTION_LOG, \
    ERROR_INITIALIZING_SERVER_INFO, ERROR_INITIALIZING_CLIENT, \
    CACHE_TIMEOUT_FOR_SERVER_INFO, LEAVING_FUNCTION_LOG, \
    INVALID_WALLET_IN_REQUEST, ACCOUNT_DOES_NOT_EXIST_ON_THE_LEDGER
from ..errors.error_handling import process_transaction_error, error_response, handle_error_new
from ..ledger.ledger_util import ledger_info_response
from ..utilities.utilities import get_cached_data, get_xrpl_client, \
    total_execution_time_in_millis, validate_xrpl_response_data, validate_xrp_wallet

logger = logging.getLogger('xrpl_app')


class GetLedgerInfo(View):
    def __init__(self):
        super().__init__()
        self.client = None  # Lazy-loaded client

    def post(self, request, *args, **kwargs):
        return self.get_ledger_info(request)

    def get(self, request, *args, **kwargs):
        return self.get_ledger_info(request)

    def get_ledger_info(self, request):
        start_time = time.time()  # Capture the start time of the function execution.
        function_name = 'get_ledger_info'
        logger.info(ENTERING_FUNCTION_LOG.format(function_name))  # Log entering the function.

        try:
            if not self.client:
                self.client = get_xrpl_client()
            if not self.client:
                raise XRPLException(error_response(ERROR_INITIALIZING_CLIENT))

            # Extract wallet address from request parameters
            data = json.loads(request.body)
            ledger_index = data.get("ledger_index")
            ledger_hash = data.get("ledger_hash")

            if ledger_hash:
                ledger_request = Ledger(ledger_hash=ledger_hash)  # Create a Ledger request using the hash.
            else:
                ledger_request = Ledger(ledger_index=ledger_index)  # Create a Ledger request using the index.

            # Initialize the XRPL client
            client = get_xrpl_client()
            if not client:
                raise XRPLException(error_response(ERROR_INITIALIZING_CLIENT))

            server_info_response = client.request(ledger_request)
            if validate_xrpl_response_data(server_info_response):
                process_transaction_error(server_info_response)

            logger.info(f"Successfully retrieved ledger info for {ledger_index}/{ledger_hash}")

            save_ledger_info(server_info_response.result)
            logger.info(f"Successfully saved {ledger_hash} in the database")

            return ledger_info_response(server_info_response)

        except (XRPLRequestFailureException, XRPLException, ValueError) as e:
            # Handle error message
            return handle_error_new(e, status_code=500, function_name=function_name)
        except Exception as e:
            # Handle error message
            return handle_error_new(e, status_code=500, function_name=function_name)
        finally:
            logger.info(LEAVING_FUNCTION_LOG.format(function_name, total_execution_time_in_millis(start_time)))


class GetServerInfo(View):
    def __init__(self):
        super().__init__()
        self.client = None  # Lazy-loaded client

    def post(self, request, *args, **kwargs):
        return self.get_server_info(request)

    def get(self, request, *args, **kwargs):
        return self.get_server_info(request)

    def get_server_info(self, request):
        start_time = time.time()  # Capture the start time to track the execution duration.
        function_name = 'get_server_info'
        logger.info(ENTERING_FUNCTION_LOG.format(function_name))  # Log function entry.

        try:
            if not self.client:
                self.client = get_xrpl_client()
            if not self.client:
                raise XRPLException(error_response(ERROR_INITIALIZING_CLIENT))

            cache_key = "server_info"
            cached_data = get_cached_data(cache_key, 'get_server_info', function_name)
            if cached_data:
                return JsonResponse(cached_data)

            server_info_request = ServerInfo()
            if not server_info_request:
                raise XRPLException(error_response(ERROR_INITIALIZING_SERVER_INFO))

            # Initialize the XRPL client for further operations.
            client = get_xrpl_client()
            if not client:
                raise XRPLException(error_response(ERROR_INITIALIZING_CLIENT))

            server_info_response = client.request(server_info_request)
            if validate_xrpl_response_data(server_info_response):
                process_transaction_error(server_info_response)

            cache.set('server_info', server_info_response, timeout=CACHE_TIMEOUT_FOR_SERVER_INFO)

            logger.info("Successfully fetched ledger information.")

            save_server_info(server_info_response.result)
            logger.info(f"Successfully saved server info in the database")

            return ledger_info_response(server_info_response)

        except (XRPLRequestFailureException, XRPLException, ValueError) as e:
            # Handle error message
            return handle_error_new(e, status_code=500, function_name=function_name)
        except Exception as e:
            # Handle error message
            return handle_error_new(e, status_code=500, function_name=function_name)
        finally:
            logger.info(LEAVING_FUNCTION_LOG.format(function_name, total_execution_time_in_millis(start_time)))


class GetXrpReserves(View):
    def __init__(self):
        super().__init__()
        self.client = None  # Lazy-loaded client

    def post(self, request, *args, **kwargs):
        return self.get_xrp_reserves(request)

    def get(self, request, *args, **kwargs):
        return self.get_xrp_reserves(request)

    @retry(wait=wait_exponential(multiplier=RETRY_BACKOFF), stop=stop_after_attempt(MAX_RETRIES))
    def get_xrp_reserves(self, request):
        start_time = time.time()  # Capture the start time of the function execution.
        function_name = 'get_xrp_reserves'
        logger.info(ENTERING_FUNCTION_LOG.format(function_name))  # Log entering the function.

        try:
            if not self.client:
                self.client = get_xrpl_client()
            if not self.client:
                raise XRPLException(error_response(ERROR_INITIALIZING_CLIENT))

            data = json.loads(request.body)
            account = data.get("account")

            # Validate the provided wallet address
            if not account or not validate_xrp_wallet(account):
                raise XRPLRequestFailureException(error_response(INVALID_WALLET_IN_REQUEST))

            # Get an instance of the XRPL client
            client = get_xrpl_client()
            if not client:
                raise XRPLException(error_response(ERROR_INITIALIZING_CLIENT))

            if not does_account_exist(account, client):
                raise XRPLException(error_response(ACCOUNT_DOES_NOT_EXIST_ON_THE_LEDGER.format(account)))

            server_info_request = ServerInfo()
            if not server_info_request:
                raise XRPLException(error_response(ERROR_INITIALIZING_SERVER_INFO))

            server_information_response = client.request(server_info_request)

            if validate_xrpl_response_data(server_information_response):
                process_transaction_error(server_information_response)

            ledger_info = server_information_response.result.get('info', {}).get('validated_ledger', {})
            reserve_base = ledger_info.get('reserve_base_xrp')  # Base reserve in XRP.
            reserve_inc = ledger_info.get('reserve_inc_xrp')  # Incremental reserve in XRP.

            if reserve_base is None or reserve_inc is None:
                logger.error(f"Reserve info missing in response: {server_information_response.result}")
                raise KeyError(error_response(INVALID_WALLET_IN_REQUEST))

            logger.info(f"Successfully fetched XRP reserve information for {account}.")

            return account_reserves_response(server_information_response, reserve_base, reserve_inc)

        except (XRPLRequestFailureException, XRPLException, ValueError) as e:
            # Handle error message
            return handle_error_new(e, status_code=500, function_name=function_name)
        except Exception as e:
            # Handle error message
            return handle_error_new(e, status_code=500, function_name=function_name)
        finally:
            logger.info(LEAVING_FUNCTION_LOG.format(function_name, total_execution_time_in_millis(start_time)))
