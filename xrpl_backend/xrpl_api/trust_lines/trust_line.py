from django.core.paginator import Paginator
import json
import logging
import time

import xrpl
from django.views import View
from rest_framework.decorators import api_view
from tenacity import wait_exponential, stop_after_attempt, retry
from xrpl import XRPLException
from xrpl.models import AccountLines, Fee, IssuedCurrencyAmount, TrustSet
from xrpl.transaction import submit
from xrpl.wallet import Wallet

from .trust_line_util import trust_line_response, create_trust_set_transaction, create_trust_set_response, \
    wait_for_validation
from ..accounts.account_utils import create_account_lines_response, prepare_account_lines, \
    prepare_account_lines_for_offer, prepare_account_data
from ..constants import RETRY_BACKOFF, MAX_RETRIES, ENTERING_FUNCTION_LOG, \
    ERROR_INITIALIZING_CLIENT, LEAVING_FUNCTION_LOG, XRPL_RESPONSE, MISSING_REQUEST_PARAMETERS
from ..errors.error_handling import handle_engine_result, handle_error
from ..utils import get_request_param, get_xrpl_client, total_execution_time_in_millis, validate_xrpl_response

logger = logging.getLogger('xrpl_app')


class TrustLine(View):

    @api_view(['GET'])
    @retry(wait=wait_exponential(multiplier=RETRY_BACKOFF), stop=stop_after_attempt(MAX_RETRIES))
    def get_account_trust_lines(self):
        """
        This function handles fetching trust lines for a specific wallet address from the XRPL network.
        It supports pagination to handle large numbers of trust lines.

        The function starts by extracting the wallet address from the request. It then initializes an
        XRPL client to make requests to the XRP ledger and fetch the account lines for the specified
        wallet address. To handle potentially large datasets, pagination is implemented through the
        use of markers, allowing the function to fetch account lines in multiple pages if necessary.

        The account lines are fetched in a loop until all available lines are retrieved. Each page of
        trust lines is added to a list, which is then paginated using Django's Paginator class to
        return a specific subset of results based on the `page` and `page_size` query parameters.

        If any errors occur during the process (such as invalid wallet address or failed request),
        they are caught and handled gracefully, with appropriate error messages returned to the client.
        Finally, the total execution time of the function is logged for performance monitoring.

        Steps:
        1. Extract the wallet address from the request parameters.
        2. Initialize the XRPL client to communicate with the XRP ledger.
        3. Fetch account lines using a loop to handle pagination, continuing until all lines are retrieved.
        4. Paginate the resulting account lines list based on the `page` and `page_size` parameters.
        5. Return the paginated result to the client.
        6. Handle any errors that may arise during the process.
        7. Log the total execution time for monitoring.

        Args:
            self (Request): The HTTP request object, containing query parameters such as `wallet_address`, `page`, and `page_size`.

        Returns:
            Response: A paginated response containing the trust lines for the given wallet address.
        """
        # Capture the start time to calculate the total execution time
        start_time = time.time()
        function_name = 'get_account_trust_lines'
        logger.info(ENTERING_FUNCTION_LOG.format(function_name))

        try:
            # Extract wallet address from request parameters
            # The wallet address is required to fetch account lines. If not provided, raise an error.
            account = get_request_param(self, 'account')
            if not account:
                raise ValueError("Account is required.")

            # Initialize the XRPL client to interact with the XRPL network.
            # If the client can't be initialized, raise an exception.
            client = get_xrpl_client()
            if not client:
                raise ConnectionError("Failed to initialize XRPL client.")

            account_lines = []  # Initialize an empty list to store account lines
            marker = None  # Initialize the marker to manage pagination

            # Loop to fetch all account lines for the account, using pagination via 'marker'
            while True:
                # Prepare the account lines request with the current marker (for pagination)
                account_lines_request = prepare_account_lines(account, marker)

                # Send the request to XRPL to fetch account lines
                response1 = client.request(account_lines_request)

                # Validate the response to ensure it contains the expected fields
                is_valid, response = validate_xrpl_response(response1, required_keys=["validated"])
                if not is_valid:
                    raise Exception(response)

                # Handle the engine result
                engine_result = response1.result.get("engine_result")
                engine_result_message = response1.result.get("engine_result_message", "No additional details")
                handle_engine_result(engine_result, engine_result_message)

                # Log the raw response for debugging purposes
                logger.debug(XRPL_RESPONSE)
                logger.debug(json.dumps(response, indent=4, sort_keys=True))

                # Check if the "lines" field exists in the response. If not, raise an error.
                if "lines" not in response:
                    raise Exception('Account lines not found')

                # Add the fetched account lines to the account_lines list
                account_lines.extend(response["lines"])

                # Log the account lines for further debugging
                logger.debug(json.dumps(response, indent=4, sort_keys=True))

                # Check if there are more pages of account lines to fetch using the 'marker' field.
                # If 'marker' is not present, break the loop, as we have fetched all pages.
                marker = response.get("marker")
                if not marker:
                    break

            # Extract pagination parameters from the request for paginating the response
            page = int(self.GET.get('page', 1))  # Default to page 1 if no page is specified
            page_size = int(
                self.GET.get('page_size', 10))  # Default to 10 items per page if no page_size is specified

            # Paginate the account lines using Django's Paginator
            paginator = Paginator(account_lines, page_size)
            paginated_transactions = paginator.get_page(page)

            # Log that the account lines have been successfully fetched
            logger.info(f"Account Lines fetched for address: {account}")

            # Return the paginated response to the client
            return create_account_lines_response(paginated_transactions, paginator)

        except Exception as e:
            # Handle any exceptions by logging the error and returning a failure response
            return handle_error({'status': 'failure', 'message': f"{str(e)}"}, status_code=500,
                                function_name=function_name)

        finally:
            # Log the total execution time of the function for monitoring purposes
            logger.info(LEAVING_FUNCTION_LOG.format(function_name, total_execution_time_in_millis(start_time)))

    #### Need new error handling
    ####
    @api_view(['GET'])
    @retry(wait=wait_exponential(multiplier=RETRY_BACKOFF), stop=stop_after_attempt(MAX_RETRIES))
    def get_trust_line(self):
        """
        This function retrieves the trust lines for a specific wallet address on the XRP Ledger (XRPL).
        It uses the XRPL client to make a request for account lines (trust lines) associated with the given wallet address.

        The function performs the following steps:
        1. Extracts the wallet address from the request parameters.
        2. Initializes the XRPL client and prepares an AccountLines request.
        3. Sends the request to the XRPL network to fetch the trust lines for the wallet address.
        4. Validates the response to ensure the data is valid and contains the necessary fields.
        5. Logs the response for debugging purposes.
        6. Extracts and returns the trust lines from the response.
        7. Handles any errors gracefully by logging and returning a failure response.

        If there is an issue with the client or the response, the function raises appropriate exceptions
        and logs detailed information for troubleshooting.

        Args:
            self (Request): The HTTP request object containing the wallet address.

        Returns:
            Response: A JSON response containing the trust lines for the given wallet address.
        """

        # Capture the start time to calculate the total execution time
        start_time = time.time()
        function_name = 'get_trust_line'
        logger.info(ENTERING_FUNCTION_LOG.format(function_name))

        try:
            # Extract wallet address from request parameters
            # The wallet address is essential to fetch the trust lines for the specified account.
            account = get_request_param(self, 'account')
            if not account:
                raise ValueError("Account is required.")

            # Prepare an AccountLines request to retrieve trust lines for the account.
            # The request will be sent to the XRPL network to fetch the trust lines for the specified wallet address.
            account_lines_request = prepare_account_lines_for_offer(account)
            # account_lines_request = AccountLines(account=account)

            # Initialize the XRPL client to communicate with the XRP ledger and fetch the required information.
            # If the client can't be initialized, raise an exception.
            client = get_xrpl_client()
            if not client:
                raise ConnectionError(ERROR_INITIALIZING_CLIENT)

            # Send the AccountLines request to the XRPL network.
            # The response contains the trust lines for the wallet address.
            response1 = client.request(account_lines_request)
            is_valid, response = validate_xrpl_response(response1, required_keys=["validated"])
            if not is_valid:
                raise Exception(response)

            # Handle the engine result
            engine_result = response1.result.get("engine_result")
            engine_result_message = response1.result.get("engine_result_message", "No additional details")
            handle_engine_result(engine_result, engine_result_message)

            # Log the raw response for debugging purposes.
            # This helps in analyzing the response content and troubleshooting issues.
            logger.debug(XRPL_RESPONSE)
            logger.debug(json.dumps(response, indent=4, sort_keys=True))

            # Extract trust lines from the response.
            # If no trust lines are found, an empty list is returned.
            trust_lines = response.get('lines', [])
            logger.info(f"Successfully fetched trust lines for account {account}. Trust lines: {trust_lines}")

            # Return the trust lines in a structured response.
            return trust_line_response(response)

        except Exception as e:
            # Handle any unexpected errors during the process.
            # Log the error and return a failure response with the exception details.
            return handle_error({'status': 'failure', 'message': f"{str(e)}"}, status_code=500,
                                function_name=function_name)

        finally:
            # Log the total execution time of the function to monitor performance.
            logger.info(LEAVING_FUNCTION_LOG.format(function_name, total_execution_time_in_millis(start_time)))

    #### Need new error handling
    ####
    @api_view(['POST'])
    @retry(wait=wait_exponential(multiplier=RETRY_BACKOFF), stop=stop_after_attempt(MAX_RETRIES))
    def set_trust_line(self):
        # Capture the start time to calculate the total execution time of the function
        start_time = time.time()
        function_name = 'set_trust_line'
        logger.info(ENTERING_FUNCTION_LOG.format(function_name))

        try:
            # Extract the parameters from the request data.
            # These parameters are necessary to create and submit a TrustSet transaction.
            sender_seed = get_request_param(self, 'sender_seed')
            account = get_request_param(self, 'account')
            currency = get_request_param(self, 'currency')
            limit = get_request_param(self, 'limit')

            # If any of the required parameters are missing, raise an error.
            if not sender_seed or not account or not currency or not limit:
                raise ValueError(MISSING_REQUEST_PARAMETERS)

            # Log the received parameters for debugging and verification.
            logger.info(
                f"Received parameters - sender_seed: {sender_seed}, wallet_address: {account}, currency: {currency}, limit: {limit}")

            # If the currency is XRP, convert the limit into drops (the smallest unit of XRP).
            limit_drops = xrpl.utils.xrp_to_drops(limit) if currency == "XRP" else limit
            logger.info(f"Converted limit: {limit_drops}")

            # Initialize the XRPL client to interact with the XRP ledger.
            # If the client cannot be initialized, raise an exception.
            client = get_xrpl_client()
            if not client:
                raise ConnectionError(ERROR_INITIALIZING_CLIENT)

            # Create the sender's wallet from the provided seed. This is used to sign transactions.
            sender_wallet = Wallet.from_seed(sender_seed)
            logger.info(f"Sender wallet created: {sender_wallet.classic_address}")

            # Fetch the current sequence number for the sender's account.
            # The sequence number is required for submitting a transaction on the XRP Ledger.
            account_info = client.request(xrpl.models.requests.AccountInfo(account=sender_wallet.classic_address))
            if not account_info or not account_info.result:
                raise ValueError('Unable to fetch account info')

            sequence_number = account_info.result['account_data']['Sequence']
            logger.info(f"Fetched sequence number: {sequence_number}")

            # Fetch the current network fee to include in the transaction.
            # The network fee is used to pay for processing the transaction.
            response1 = client.request(Fee())
            is_valid, response = validate_xrpl_response(response1, required_keys=["drops"])
            if not is_valid:
                raise Exception(response)

            logger.info(f"Trust lines response1: {response1}")
            logger.info(f"Trust lines response: {response}")

            # Extract the minimum fee from the response.
            fee = response['drops']['minimum_fee']
            logger.info(f"Fetched network fee: {fee}")

            # Create a TrustSet transaction with the extracted parameters, including the fee and sequence number.
            trust_set_tx = create_trust_set_transaction(currency, limit_drops, account,
                                                        sender_wallet.classic_address, sequence_number, fee)
            logger.info(f"Created TrustSet transaction: {trust_set_tx}")

            # Sign the transaction with the sender's wallet.
            signed_tx = xrpl.transaction.sign(trust_set_tx, sender_wallet)
            logger.info(f"Signed transaction: {signed_tx}")

            # Submit the signed transaction to the XRPL network.
            response1 = submit(signed_tx, client)
            is_valid, response = validate_xrpl_response(response1, required_keys=["tx_json"])
            if not is_valid:
                raise Exception(response)

            # is_successful, message = check_engine_result(response1, "meta")
            # if not is_successful:
            #     raise Exception(message)

            logger.info(f"Trust lines response: {response}")

            tx_hash = response['tx_json']['hash']
            validated_tx_response = wait_for_validation(client, tx_hash)

            # is_successful, message = check_engine_result(response1, "meta")
            # if not is_successful:
            #     raise Exception(message)

            if not validated_tx_response or not validated_tx_response.result.get('validated'):
                raise Exception("Transaction not validated in time")

            # Log the success and return the response to indicate that the trust line was set successfully.
            logger.info(f"Transaction validated in ledger: {validated_tx_response.result['ledger_index']}")
            logger.info(f"Trust line set successfully for account {account}")
            return create_trust_set_response(response, account, currency, limit)

        except Exception as e:
            # Handle any exceptions by logging the error and returning a failure response.
            return handle_error({'status': 'failure', 'message': f"{str(e)}"}, status_code=500,
                                function_name=function_name)

        finally:
            # Log the total execution time for performance monitoring purposes.
            logger.info(LEAVING_FUNCTION_LOG.format(function_name, total_execution_time_in_millis(start_time)))

    #### Need new error handling
    ####
    @api_view(['POST'])
    @retry(wait=wait_exponential(multiplier=RETRY_BACKOFF), stop=stop_after_attempt(MAX_RETRIES))
    def remove_trust_line(self):
        # Capture the start time to calculate the total execution time of the function
        start_time = time.time()
        function_name = 'remove_trust_line'
        logger.info(ENTERING_FUNCTION_LOG.format(function_name))

        try:
            # Extract the parameters from the request data.
            # These parameters are necessary to create and submit a TrustSet transaction.
            sender_seed = get_request_param(self, 'sender_seed')
            account = get_request_param(self, 'account')
            currency_code = get_request_param(self, 'currency_code')
            issuer = get_request_param(self, 'issuer')

            # If any of the required parameters are missing, raise an error.
            if not sender_seed or not account or not currency_code or not issuer:
                raise ValueError(MISSING_REQUEST_PARAMETERS)

            # Log the received parameters for debugging and verification.
            logger.info(
                f"Received parameters - sender_seed: {sender_seed}, wallet_address: {account}, currency: {currency_code}, issuer: {issuer}")

            # Initialize the XRPL client to interact with the XRP ledger.
            # If the client cannot be initialized, raise an exception.
            client = get_xrpl_client()
            if not client:
                raise ConnectionError(ERROR_INITIALIZING_CLIENT)

            # Load the wallet using the secret key
            sender_wallet = Wallet.from_secret(sender_seed)
            # Fetch account info to get the current sequence number
            account_info = client.request(prepare_account_data(account, False))
            is_valid, response = validate_xrpl_response(account_info, required_keys=["account_data"])
            if not is_valid:
                raise Exception(response)

            sequence = account_info.result["account_data"]["Sequence"]

            # Fetch the current fee from the XRPL network
            fee_info = client.request(Fee())
            is_valid, response = validate_xrpl_response(fee_info, required_keys=["drops"])
            if not is_valid:
                raise Exception(response)

            fee = fee_info.result["drops"]["open_ledger_fee"]

            # Create a TrustSet transaction to remove the trust line by setting the limit to 0
            trust_set_tx = TrustSet(
                account=account,
                limit_amount=IssuedCurrencyAmount(
                    currency=currency_code,
                    issuer=issuer,
                    value=int(0)
                ),
                sequence=sequence,
                fee=fee,
            )

            # Sign the transaction with the sender's wallet.
            signed_tx = xrpl.transaction.sign(trust_set_tx, sender_wallet)
            logger.info(f"Signed transaction: {signed_tx}")

            # Submit the signed transaction to the XRPL network.
            response = submit(signed_tx, client)

            # Check the transaction response
            if response.is_successful():
                logger.info(f"Trust line for {currency_code} removed successfully.")
            else:
                logger.error(f"Error: {response.result['error']}, Message: {response.result.get('error_message', 'No additional details')}")

            # Handle the engine result
            engine_result = response.result.get("engine_result")
            engine_result_message = response.result.get("engine_result_message", "No additional details")
            handle_engine_result(engine_result, engine_result_message)

            is_valid, response = validate_xrpl_response(response, required_keys=["tx_json"])
            if not is_valid:
                raise Exception(response)

            return create_trust_set_response(response, account, currency_code, 'NOT THIS')

        except Exception as e:
            # Handle any exceptions by logging the error and returning a failure response.
            return handle_error({'status': 'failure', 'message': f"{str(e)}"}, status_code=500, function_name=function_name)
        finally:
            # Log the total execution time for performance monitoring purposes.
            logger.info(LEAVING_FUNCTION_LOG.format(function_name, total_execution_time_in_millis(start_time)))