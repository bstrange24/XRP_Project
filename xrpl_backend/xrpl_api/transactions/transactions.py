from django.core.paginator import Paginator
import json
import logging
import time

import xrpl
from django.views import View
from rest_framework.decorators import api_view
from tenacity import wait_exponential, stop_after_attempt, retry
from xrpl import XRPLException

from .transactions_util import transaction_history_response, prepare_tx, transaction_status_response
from ..accounts.account_utils import prepare_account_tx, prepare_account_tx_with_pagination, \
    account_tx_with_pagination_response
from ..constants import RETRY_BACKOFF, MAX_RETRIES, ENTERING_FUNCTION_LOG, \
    ERROR_INITIALIZING_CLIENT, LEAVING_FUNCTION_LOG, XRPL_RESPONSE, ERROR_FETCHING_TRANSACTION_STATUS, \
    INVALID_WALLET_IN_REQUEST, ERROR_FETCHING_TRANSACTION_HISTORY, INVALID_TRANSACTION_HASH
from ..utils import get_xrpl_client, handle_error, total_execution_time_in_millis, \
    validate_xrpl_response, validate_xrp_wallet, is_valid_transaction_hash

logger = logging.getLogger('xrpl_app')


class Transactions(View):

    @api_view(['GET'])
    @retry(wait=wait_exponential(multiplier=RETRY_BACKOFF), stop=stop_after_attempt(MAX_RETRIES))
    def get_transaction_history(self, wallet_address, previous_transaction_id):
        """
        Retrieves the transaction history for a given XRP wallet address and searches for a specific transaction.

        Steps:
        1. Validate the provided wallet address to ensure it is correctly formatted.
        2. Validate the transaction hash format to confirm it follows the expected structure.
        3. Initialize the XRPL client to communicate with the XRP Ledger.
        4. Prepare an AccountTx request to fetch past transactions related to the wallet.
        5. Send the request to XRPL and retrieve transaction history.
        6. Validate the response and check for transactions in the result.
        7. Iterate through the transactions to find a match with the given transaction hash.
        8. If a matching transaction is found, return its details.
        9. If no matching transaction is found or an error occurs, return an appropriate error response.

        If any step fails, an error is logged, and an error response is returned.
        """
        start_time = time.time()  # Capture the start time
        function_name = 'get_transaction_history'
        logger.info(ENTERING_FUNCTION_LOG.format(function_name))

        try:
            # Validate the provided wallet address
            if not wallet_address or not validate_xrp_wallet(wallet_address):
                raise XRPLException(INVALID_WALLET_IN_REQUEST)

            # Validate the format of the transaction hash
            if not is_valid_transaction_hash(previous_transaction_id):
                raise XRPLException(INVALID_TRANSACTION_HASH)

            # Initialize the XRPL client for querying the ledger
            client = get_xrpl_client()
            if not client:
                raise XRPLException(ERROR_INITIALIZING_CLIENT)

            # Prepare an AccountTx request to fetch transactions for the given account
            account_tx_request = prepare_account_tx(wallet_address)

            # Send the request to XRPL to get transaction history
            response = client.request(account_tx_request)
            is_valid, response = validate_xrpl_response(response, required_keys=["validated"])
            if not is_valid:
                raise Exception(response)

            # Log the raw response for detailed debugging
            logger.debug(XRPL_RESPONSE)
            logger.debug(json.dumps(response, indent=4, sort_keys=True))

            # Check if the response contains any transactions
            if 'transactions' in response:
                for transaction_tx in response['transactions']:
                    # Look for the specific transaction by comparing hash
                    # Match the actual transaction hash
                    if str(transaction_tx['hash']) == previous_transaction_id:
                        logger.debug("Transaction found:")
                        logger.debug(json.dumps(transaction_tx, indent=4, sort_keys=True))

                        # Prepare and return the found transaction
                        return transaction_history_response(transaction_tx)

                # If no match is found after checking all transactions
                raise XRPLException(ERROR_FETCHING_TRANSACTION_HISTORY)
            else:
                raise XRPLException(ERROR_FETCHING_TRANSACTION_HISTORY)

        except (xrpl.XRPLException, Exception) as e:
            # Handle exceptions like XRPL-specific errors, network issues, or unexpected errors
            return handle_error({'status': 'failure', 'message': f"{str(e)}"}, status_code=500,
                                function_name=function_name)
        finally:
            logger.info(LEAVING_FUNCTION_LOG.format(function_name, total_execution_time_in_millis(start_time)))

    @api_view(['GET'])
    @retry(wait=wait_exponential(multiplier=RETRY_BACKOFF), stop=stop_after_attempt(MAX_RETRIES))
    def get_transaction_history_with_pagination(request, wallet_address):
        """
        Retrieves the transaction history for a given XRP wallet address with pagination support.

        Steps:
        1. Validate the provided wallet address to ensure it is properly formatted.
        2. Initialize the XRPL client to communicate with the XRP Ledger.
        3. Fetch transactions in a loop using pagination (via the 'marker' parameter).
        4. If a response is successful, extract transactions and append them to a list.
        5. If additional transactions exist (indicated by a 'marker'), continue fetching.
        6. Extract pagination parameters (page number and page size) from the request.
        7. Use Django’s Paginator to split transactions into manageable pages.
        8. Return the paginated transaction history, along with total transaction count and page count.

        If any step fails, an error response is logged and returned.
        """
        start_time = time.time()  # Capture the start time
        function_name = 'get_transaction_history_with_pagination'
        logger.info(ENTERING_FUNCTION_LOG.format(function_name))

        try:
            # Validate the provided wallet address
            if not wallet_address or not validate_xrp_wallet(wallet_address):
                raise XRPLException(INVALID_WALLET_IN_REQUEST)

            # Initialize the XRPL client for querying transactions
            client = get_xrpl_client()
            if not client:
                raise XRPLException(ERROR_INITIALIZING_CLIENT)

            transactions = []
            marker = None

            # Loop to fetch all transactions for the account, using pagination through 'marker'
            while True:
                account_tx_request = prepare_account_tx_with_pagination(wallet_address, marker)

                # Send the request to XRPL to get transaction history
                response = client.request(account_tx_request)
                is_valid, response = validate_xrpl_response(response, required_keys=["validated"])
                if not is_valid:
                    raise Exception(response)

                # Log the raw response for detailed debugging
                logger.debug(XRPL_RESPONSE)
                logger.debug(json.dumps(response, indent=4, sort_keys=True))

                # Add fetched transactions to the list
                if "transactions" not in response:
                    raise XRPLException(ERROR_FETCHING_TRANSACTION_HISTORY)

                transactions.extend(response["transactions"])

                # Log the transactions for debugging
                logger.debug(json.dumps(response["transactions"], indent=4, sort_keys=True))

                # Check if there are more pages of transactions to fetch
                marker = response.get("marker")
                if not marker:
                    break

            # Extract pagination parameters from the request
            page = int(request.GET.get('page', 1))
            page_size = int(request.GET.get('page_size', 10))

            # Paginate the transactions
            paginator = Paginator(transactions, page_size)
            paginated_transactions = paginator.get_page(page)

            # Log successful transaction history fetch
            logger.info(f"Transaction history fetched for address: {wallet_address}")
            return account_tx_with_pagination_response(paginated_transactions, paginator.count, paginator.num_pages)

        except Exception as e:
            # Handle any exceptions that occur during the process
            return handle_error({'status': 'failure', 'message': f"{str(e)}"}, status_code=500,
                                function_name=function_name)
        finally:
            logger.info(LEAVING_FUNCTION_LOG.format(function_name, total_execution_time_in_millis(start_time)))

    @api_view(['GET'])
    @retry(wait=wait_exponential(multiplier=RETRY_BACKOFF), stop=stop_after_attempt(MAX_RETRIES))
    def check_transaction_status(request, tx_hash):
        """
        This function checks the status of a given XRPL transaction by its hash. The process involves:

        1. Validating the transaction hash format.
        2. Initializing an XRPL client to interact with the network.
        3. Preparing a request to fetch transaction details.
        4. Sending the request to XRPL and receiving the response.
        5. Validating the response to ensure it contains necessary transaction details.
        6. Logging relevant information for debugging and monitoring purposes.
        7. Returning a formatted response with the transaction status.

        Error handling is implemented to manage XRPL-related errors, network issues, or unexpected failures.
        Logging is used to trace function entry, exit, and key processing steps.
        """
        start_time = time.time()  # Capture the start time
        function_name = 'check_transaction_status'
        logger.info(ENTERING_FUNCTION_LOG.format(function_name))

        try:
            # Validate the format of the transaction hash
            if not is_valid_transaction_hash(tx_hash):
                raise XRPLException(INVALID_TRANSACTION_HASH)

            # Log the start of the transaction status check for debugging purposes
            logger.info(f"Checking transaction status for hash: {tx_hash}")

            # Initialize the XRPL client for transaction status checks
            client = get_xrpl_client()
            if not client:
                raise XRPLException(ERROR_INITIALIZING_CLIENT)

            # Create a transaction request object to fetch details of the specified transaction
            tx_request = prepare_tx(tx_hash)

            # Send the request to the XRPL to get the transaction details
            response = client.request(tx_request)
            is_valid, result = validate_xrpl_response(response, required_keys=["validated"])
            if not is_valid:
                raise Exception(result)

            # Log the raw response for detailed debugging
            logger.debug(XRPL_RESPONSE)
            logger.debug(json.dumps(result, indent=4, sort_keys=True))

            # Log the raw response for detailed debugging
            logger.info(f"Raw XRPL response for transaction {tx_hash}: {result}")
            return transaction_status_response(response, tx_hash)

        except (xrpl.XRPLException, Exception) as e:
            # Handle exceptions like XRPL-specific errors, network issues, or unexpected errors
            return handle_error({'status': 'failure', 'message': f"{str(e)}"}, status_code=500,
                                function_name=function_name)

        finally:
            logger.info(LEAVING_FUNCTION_LOG.format(function_name, total_execution_time_in_millis(start_time)))
