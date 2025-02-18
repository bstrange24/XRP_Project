import json
import logging
import time

from django.http import JsonResponse
from django.views import View
from rest_framework.decorators import api_view
from tenacity import retry, wait_exponential, stop_after_attempt
from xrpl import XRPLException
from xrpl.models import ServerInfo, Ledger
from django.core.cache import cache

from ..accounts.account_utils import account_reserves_response
from ..constants import RETRY_BACKOFF, MAX_RETRIES, ENTERING_FUNCTION_LOG, \
    ERROR_INITIALIZING_SERVER_INFO, ERROR_INITIALIZING_CLIENT, ERROR_FETCHING_ACCOUNT_OFFERS, XRPL_RESPONSE, \
    CACHE_TIMEOUT_FOR_SERVER_INFO, LEAVING_FUNCTION_LOG, ERROR_FETCHING_XRP_RESERVES, CACHE_TIMEOUT, \
    ACCOUNT_IS_REQUIRED, RESERVES_NOT_FOUND
from ..errors.error_handling import handle_error
from ..ledger.ledger_util import ledger_info_response
from ..utils import get_cached_data, get_xrpl_client, validate_xrpl_response, \
    total_execution_time_in_millis, get_request_param

logger = logging.getLogger('xrpl_app')


class LedgerInteraction(View):

    @api_view(['GET'])
    @retry(wait=wait_exponential(multiplier=RETRY_BACKOFF), stop=stop_after_attempt(MAX_RETRIES))
    def get_server_info(self):
        """
        Retrieve server information from the XRP Ledger, including details about the server's state and configuration.

        This function performs the following steps:
        1. Checks the cache for previously fetched server information to avoid redundant API calls.
        2. Prepares a request to fetch server information from the XRP Ledger.
        3. Initializes the XRPL client to interact with the XRP Ledger.
        4. Sends the request to the XRP Ledger and validates the response.
        5. Logs the raw response for debugging purposes.
        6. Caches the server information to improve performance on subsequent requests.
        7. Returns the formatted server information.
        8. Handles any exceptions that occur during execution.
        9. Logs the total execution time of the function.

        Args:
            self (HttpRequest): The HTTP request object.

        Returns:
            JsonResponse: A JSON response containing the server information or an error message.
        """
        start_time = time.time()  # Capture the start time to track the execution duration.
        function_name = 'get_server_info'
        logger.info(ENTERING_FUNCTION_LOG.format(function_name))  # Log function entry.

        try:
            # Step 1: Check the cache for previously fetched server information.
            cache_key = "server_info"
            cached_data = get_cached_data(cache_key, 'get_server_info', function_name)
            if cached_data:
                # If cached data is available, return it to avoid redundant API calls.
                return JsonResponse(cached_data)

            # Step 2: Prepare a request to fetch server information from the XRP Ledger.
            server_info_request = ServerInfo()
            if not server_info_request:
                # If the request cannot be initialized, raise an error.
                raise ERROR_INITIALIZING_SERVER_INFO

            # Step 3: Initialize the XRPL client to interact with the XRP Ledger.
            client = get_xrpl_client()
            if not client:
                # If the client is not initialized, raise an error.
                raise ConnectionError(ERROR_INITIALIZING_CLIENT)

            # Step 4: Send the request to the XRP Ledger and validate the response.
            response = client.request(server_info_request)
            is_valid, response = validate_xrpl_response(response, required_keys=["info"])
            if not is_valid:
                raise Exception(response)

            # Step 5: Log the raw response for detailed debugging.
            logger.debug(XRPL_RESPONSE)
            logger.debug(json.dumps(response, indent=4, sort_keys=True))

            # Step 6: Cache the server information to improve performance on subsequent requests.
            cache.set('server_info', response, timeout=CACHE_TIMEOUT_FOR_SERVER_INFO)

            # Step 7: Log the successful fetching of server information.
            logger.info("Successfully fetched ledger information.")

            # Step 8: Return the formatted server information.
            return ledger_info_response(response, 'Server info fetched successfully.')

        except Exception as e:
            # Step 9: Handle any unexpected errors that occur during the process.
            return handle_error({'status': 'failure', 'message': f"{str(e)}"}, status_code=500,
                                function_name=function_name)

        finally:
            # Step 10: Log when the function exits, including the total execution time.
            logger.info(LEAVING_FUNCTION_LOG.format(function_name, total_execution_time_in_millis(start_time)))


    @api_view(['GET'])
    @retry(wait=wait_exponential(multiplier=RETRY_BACKOFF), stop=stop_after_attempt(MAX_RETRIES))
    def get_ledger_info(self):
        """
        Retrieve ledger information from the XRP Ledger based on the provided `ledger_index` or `ledger_hash`.

        This function handles the following steps:
        1. Extracts query parameters (`ledger_index` and `ledger_hash`) from the request.
        2. Checks the cache for previously fetched ledger info to avoid redundant API calls.
        3. Prepares a ledger request based on the provided parameters.
        4. Initializes the XRPL client to interact with the XRP Ledger.
        5. Sends the request to the XRP Ledger and validates the response.
        6. Logs the raw response for debugging purposes.
        7. Formats the response data for the API response.
        8. Caches the formatted response to improve performance on subsequent requests.
        9. Handles any exceptions that occur during execution.
        10. Logs the total execution time of the function.

        Args:
            self (HttpRequest): The HTTP request object containing query parameters.

        Returns:
            JsonResponse: A JSON response containing the ledger information or an error message.
        """
        start_time = time.time()  # Capture the start time of the function execution.
        function_name = 'get_ledger_info'
        logger.info(ENTERING_FUNCTION_LOG.format(function_name))  # Log entering the function.

        try:
            # Step 1: Retrieve the `ledger_index` and `ledger_hash` query parameters from the request.
            ledger_index = get_request_param(self, 'ledger_index')
            ledger_hash = get_request_param(self, 'ledger_hash')

            # Step 2: Check the cache for previously fetched ledger info to avoid redundant API calls.
            cache_key = f"ledger_info_{ledger_index}_{ledger_hash or ''}"
            cached_data = get_cached_data(cache_key, 'get_ledger_info_function', function_name)
            if cached_data:
                return JsonResponse(cached_data)  # Return the cached data if available.

            # Step 3: Prepare the ledger request based on whether a ledger index or ledger hash is provided.
            if ledger_hash:
                ledger_request = Ledger(ledger_hash=ledger_hash)  # Create a Ledger request using the hash.
            else:
                ledger_request = Ledger(ledger_index=ledger_index)  # Create a Ledger request using the index.

            # Step 4: Initialize the XRPL client to make the request to the XRP Ledger.
            client = get_xrpl_client()
            if not client:
                raise ValueError(ERROR_INITIALIZING_CLIENT)  # Raise an error if the client initialization fails.

            # Step 5: Send the request to the XRP Ledger and capture the response.
            response = client.request(ledger_request)
            is_valid, response = validate_xrpl_response(response, required_keys=["validated"])
            if not is_valid:
                raise Exception(response)

            # Log the raw response for detailed debugging and analysis.
            logger.debug(XRPL_RESPONSE)
            logger.debug(json.dumps(response, indent=4, sort_keys=True))

            logger.info(f"Successfully retrieved ledger info for {ledger_index}/{ledger_hash}")

            # Step 7: Format the response data to make it suitable for the response.
            response_data = ledger_info_response(response, 'Ledger information successfully retrieved.')

            # Step 8: Cache the formatted response to improve performance on subsequent requests.
            cache.set(cache_key, response_data, CACHE_TIMEOUT)

            return response_data  # Return the formatted response data.
        except Exception as e:
            # Step 10: Catch any unexpected errors and return a failure response with the error message.
            return handle_error({'status': 'failure', 'message': f"{str(e)}"}, status_code=500,
                                function_name=function_name)

        finally:
            # Step 11: Log the execution time and when the function exits.
            logger.info(LEAVING_FUNCTION_LOG.format(function_name, total_execution_time_in_millis(start_time)))


    @api_view(['GET'])
    @retry(wait=wait_exponential(multiplier=RETRY_BACKOFF), stop=stop_after_attempt(MAX_RETRIES))
    def get_xrp_reserves(self):
        """
        Retrieve XRP reserve information for a given wallet address from the XRP Ledger.

        This function performs the following steps:
        1. Extracts the `wallet_address` query parameter (wallet address) from the request.
        2. Initializes the XRPL client to interact with the XRP Ledger.
        3. Requests server information from the XRP Ledger to fetch reserve details.
        4. Validates the response to ensure it contains the required data.
        5. Extracts the base reserve (`reserve_base_xrp`) and incremental reserve (`reserve_inc_xrp`) from the response.
        6. Logs the raw response for debugging purposes.
        7. Returns the formatted reserve information for the specified wallet address.
        8. Handles any exceptions that occur during execution.
        9. Logs the total execution time of the function.

        Args:
            self (HttpRequest): The HTTP request object containing the `account` query parameter.

        Returns:
            JsonResponse: A JSON response containing the XRP reserve information or an error message.
        """
        start_time = time.time()  # Capture the start time of the function execution.
        function_name = 'get_xrp_reserves'
        logger.info(ENTERING_FUNCTION_LOG.format(function_name))  # Log entering the function.

        try:
            # Step 1: Extract the wallet address from the request query parameters.
            wallet_address = get_request_param(self, 'wallet_address')
            if not wallet_address:
                raise ValueError(ACCOUNT_IS_REQUIRED)  # Raise an error if the wallet address is missing.

            # Step 2: Initialize the XRPL client to interact with the XRP Ledger.
            client = get_xrpl_client()
            if not client:
                raise XRPLException(ERROR_INITIALIZING_CLIENT)  # Raise an error if client initialization fails.

            # Step 3: Request server information from the XRP Ledger to fetch reserve details.
            server_info_request = ServerInfo()
            if not server_info_request:
                raise ERROR_INITIALIZING_SERVER_INFO  # Raise an error if the server info request fails.

            server_information_response = client.request(server_info_request)

            # Step 4: Validate the response to ensure it contains the required data.
            is_valid, response = validate_xrpl_response(server_information_response, required_keys=["info"])
            if not is_valid:
                raise Exception(response)

            # Step 5: Log the raw response for debugging purposes.
            logger.debug(XRPL_RESPONSE)
            logger.debug(json.dumps(server_information_response.result, indent=4, sort_keys=True))

            # Step 6: Extract reserve information from the validated ledger data.
            ledger_info = server_information_response.result.get('info', {}).get('validated_ledger', {})
            reserve_base = ledger_info.get('reserve_base_xrp')  # Base reserve in XRP.
            reserve_inc = ledger_info.get('reserve_inc_xrp')  # Incremental reserve in XRP.

            # Step 7: Ensure that both reserve values are present in the response.
            if reserve_base is None or reserve_inc is None:
                logger.error(f"Reserve info missing in response: {server_information_response.result}")
                raise KeyError(RESERVES_NOT_FOUND)  # Raise an error if reserve information is missing.

            logger.info(f"Successfully fetched XRP reserve information for {wallet_address}.")

            # Step 8: Format and return the reserve information.
            return account_reserves_response(server_information_response, reserve_base, reserve_inc)

        except Exception as e:
            # Step 9: Catch any unexpected errors and return a failure response with the error message.
            return handle_error({'status': 'failure', 'message': f"{str(e)}"}, status_code=500,
                                function_name=function_name)

        finally:
            # Step 10: Log the total execution time and when the function exits.
            logger.info(LEAVING_FUNCTION_LOG.format(function_name, total_execution_time_in_millis(start_time)))
