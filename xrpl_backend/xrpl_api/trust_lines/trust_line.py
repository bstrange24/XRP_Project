from django.core.paginator import Paginator
import json
import logging
import time

import xrpl
from django.views import View
from rest_framework.decorators import api_view
from tenacity import wait_exponential, stop_after_attempt, retry
from xrpl import XRPLException
from xrpl.models import AccountLines, Fee
from xrpl.transaction import submit
from xrpl.wallet import Wallet

from .trust_line_util import trust_line_response, create_trust_set_transaction, create_trust_set_response
from ..accounts.account_utils import create_account_lines_response, prepare_account_lines
from ..constants import RETRY_BACKOFF, MAX_RETRIES, ENTERING_FUNCTION_LOG, \
    ERROR_INITIALIZING_CLIENT, LEAVING_FUNCTION_LOG, XRPL_RESPONSE, ERROR_FETCHING_TRANSACTION_STATUS, \
    MISSING_REQUEST_PARAMETERS
from ..utils import get_request_param, get_xrpl_client, handle_error, total_execution_time_in_millis, \
    validate_xrpl_response

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
            wallet_address = get_request_param(self, 'wallet_address')
            if not wallet_address:
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
                account_lines_request = prepare_account_lines(wallet_address, marker)

                # Send the request to XRPL to fetch account lines
                response = client.request(account_lines_request)

                # Validate the response to ensure it contains the expected fields
                is_valid, response = validate_xrpl_response(response, required_keys=["validated"])
                if not is_valid:
                    raise XRPLException(ERROR_FETCHING_TRANSACTION_STATUS)

                # Log the raw response for debugging purposes
                logger.debug(XRPL_RESPONSE)
                logger.debug(json.dumps(response, indent=4, sort_keys=True))

                # Check if the "lines" field exists in the response. If not, raise an error.
                if "lines" not in response:
                    raise XRPLException('Account lines not found')

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
            logger.info(f"Account Lines fetched for address: {wallet_address}")

            # Return the paginated response to the client
            return create_account_lines_response(paginated_transactions, paginator)

        except Exception as e:
            # Handle any exceptions by logging the error and returning a failure response
            return handle_error({'status': 'failure', 'message': f"{str(e)}"}, status_code=500,
                                function_name=function_name)

        finally:
            # Log the total execution time of the function for monitoring purposes
            logger.info(LEAVING_FUNCTION_LOG.format(function_name, total_execution_time_in_millis(start_time)))

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
            wallet_address = get_request_param(self, 'wallet_address')
            if not wallet_address:
                raise ValueError("Account is required.")

            # Prepare an AccountLines request to retrieve trust lines for the account.
            # The request will be sent to the XRPL network to fetch the trust lines for the specified wallet address.
            account_lines_request = AccountLines(account=wallet_address)

            # Initialize the XRPL client to communicate with the XRP ledger and fetch the required information.
            # If the client can't be initialized, raise an exception.
            client = get_xrpl_client()
            if not client:
                raise ConnectionError(ERROR_INITIALIZING_CLIENT)

            # Send the AccountLines request to the XRPL network.
            # The response contains the trust lines for the wallet address.
            response = client.request(account_lines_request)

            # Validate the response to ensure it contains the expected fields.
            # If the response is not valid, log the error and raise an exception.
            is_valid, response = validate_xrpl_response(response, required_keys=["validated"])
            if not is_valid:
                logger.error(f"Failed to fetch trust lines for {wallet_address}: {response}")
                raise XRPLException('Error fetching trust lines.')

            # Log the raw response for debugging purposes.
            # This helps in analyzing the response content and troubleshooting issues.
            logger.debug(XRPL_RESPONSE)
            logger.debug(json.dumps(response, indent=4, sort_keys=True))

            # Extract trust lines from the response.
            # If no trust lines are found, an empty list is returned.
            trust_lines = response.get('lines', [])
            logger.info(f"Successfully fetched trust lines for account {wallet_address}. Trust lines: {trust_lines}")

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

    @api_view(['POST'])
    @retry(wait=wait_exponential(multiplier=RETRY_BACKOFF), stop=stop_after_attempt(MAX_RETRIES))
    def set_trust_line(self):
        """
        This function is responsible for setting a trust line for a specific wallet address on the XRP Ledger (XRPL).
        The trust line defines the amount of a certain currency that an account is willing to accept from another account.

        The function performs the following actions:
        1. Extracts the required parameters (sender seed, wallet address, currency, and limit) from the request data.
        2. Converts the limit to drops if the currency is XRP.
        3. Initializes the XRPL client to communicate with the XRP Ledger.
        4. Creates a wallet from the sender's seed.
        5. Fetches the current sequence number for the sender's account.
        6. Retrieves the current network fee.
        7. Constructs a TrustSet transaction with the necessary details.
        8. Signs the transaction using the sender's wallet.
        9. Submits the signed transaction to the XRPL network.
        10. Returns a success response if the transaction is successfully processed.

        If any errors occur during the process, they are caught, logged, and a failure response is returned.

        Args:
            self (Request): The HTTP request object containing parameters like sender_seed, wallet_address, currency, and limit.

        Returns:
            Response: A JSON response indicating whether the trust line was successfully set.
        """

        # Capture the start time to calculate the total execution time of the function
        start_time = time.time()
        function_name = 'set_trust_line'
        logger.info(ENTERING_FUNCTION_LOG.format(function_name))

        try:
            # Extract the parameters from the request data.
            # These parameters are necessary to create and submit a TrustSet transaction.
            sender_seed = get_request_param(self, 'sender_seed')
            wallet_address = get_request_param(self, 'wallet_address')
            currency = get_request_param(self, 'currency')
            limit = get_request_param(self, 'limit')

            # If any of the required parameters are missing, raise an error.
            if not sender_seed or not wallet_address or not currency or not limit:
                raise ValueError(MISSING_REQUEST_PARAMETERS)

            # Log the received parameters for debugging and verification.
            logger.info(
                f"Received parameters - sender_seed: {sender_seed}, wallet_address: {wallet_address}, currency: {currency}, limit: {limit}")

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
            response = client.request(Fee())
            is_valid, response = validate_xrpl_response(response, required_keys=["drops"])
            if not is_valid:
                logger.error(f"Failed to fetch fees for {wallet_address}: {response}")
                raise XRPLException('Error fetching fees.')

            logger.info(f"Trust lines response: {response}")

            # Extract the minimum fee from the response.
            fee = response['drops']['minimum_fee']
            logger.info(f"Fetched network fee: {fee}")

            # Create a TrustSet transaction with the extracted parameters, including the fee and sequence number.
            trust_set_tx = create_trust_set_transaction(currency, limit_drops, wallet_address,
                                                        sender_wallet.classic_address, sequence_number, fee)
            logger.info(f"Created TrustSet transaction: {trust_set_tx}")

            # Sign the transaction with the sender's wallet.
            signed_tx = xrpl.transaction.sign(trust_set_tx, sender_wallet)
            logger.info(f"Signed transaction: {signed_tx}")

            # Submit the signed transaction to the XRPL network.
            response = submit(signed_tx, client)
            is_valid, response = validate_xrpl_response(response, required_keys=["tx_json"])
            if not is_valid:
                logger.error(f"Failed to fetch fees for {wallet_address}: {response}")
                raise XRPLException('Error fetching fees.')

            logger.info(f"Trust lines response: {response}")

            # Log the success and return the response to indicate that the trust line was set successfully.
            logger.info(f"Trust line set successfully for account {wallet_address}")
            return create_trust_set_response(response, wallet_address, currency, limit)

        except Exception as e:
            # Handle any exceptions by logging the error and returning a failure response.
            return handle_error({'status': 'failure', 'message': f"{str(e)}"}, status_code=500,
                                function_name=function_name)

        finally:
            # Log the total execution time for performance monitoring purposes.
            logger.info(LEAVING_FUNCTION_LOG.format(function_name, total_execution_time_in_millis(start_time)))
