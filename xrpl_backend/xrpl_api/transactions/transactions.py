import json
import logging
import time

from django.core.paginator import Paginator
from django.utils.decorators import method_decorator
from django.views import View
from django.views.decorators.csrf import csrf_exempt
from rest_framework.decorators import api_view
from tenacity import wait_exponential, stop_after_attempt, retry
from xrpl import XRPLException
from xrpl.account import does_account_exist
from xrpl.asyncio.clients import XRPLRequestFailureException
from xrpl.utils import XRPRangeException

from .db_operations.transaction_db_operations import save_transaction_history
from .transactions_util import prepare_tx, transaction_status_response
from ..accounts.account_utils import prepare_account_tx_with_pagination, \
    account_tx_with_pagination_response
from ..constants.constants import ENTERING_FUNCTION_LOG, \
    ERROR_INITIALIZING_CLIENT, LEAVING_FUNCTION_LOG, INVALID_WALLET_IN_REQUEST, ERROR_FETCHING_TRANSACTION_HISTORY, \
    INVALID_TRANSACTION_HASH, \
    ACCOUNT_DOES_NOT_EXIST_ON_THE_LEDGER
from ..errors.error_handling import process_transaction_error, handle_error_new, error_response
from ..utilities.utilities import get_xrpl_client, total_execution_time_in_millis, validate_xrp_wallet, is_valid_transaction_hash, \
    validate_xrpl_response_data

logger = logging.getLogger('xrpl_app')

@method_decorator(csrf_exempt, name="dispatch")
class GetTransactionHistory(View):
    def __init__(self):
        super().__init__()
        self.client = None  # Lazy-loaded client

    def _initialize_client(self):
        """Lazy initialization of the XRPL client."""
        if not self.client:
            self.client = get_xrpl_client()
            if not self.client:
                raise XRPLException(error_response(ERROR_INITIALIZING_CLIENT))

    def post(self, request, *args, **kwargs):
        return self.get_transaction_history_with_pagination(request)

    def get(self, request, *args, **kwargs):
        return self.get_transaction_history_with_pagination(request)

    def get_transaction_history_with_pagination(self, request):
        start_time = time.time()  # Capture the start time
        function_name = 'get_transaction_history_with_pagination'
        logger.info(ENTERING_FUNCTION_LOG.format(function_name))

        try:
            # Initialize the client if not already initialized
            self._initialize_client()

            # Extract wallet address from request parameters
            data = json.loads(request.body)
            account = data.get("account")

            # Validate the provided wallet address
            if not account or not validate_xrp_wallet(account):
                raise XRPLException(error_response(INVALID_WALLET_IN_REQUEST))

            # Initialize XRPL client. Check if client is successfully initialized. Raise exception if client initialization fails
            client = get_xrpl_client()
            if not client:
                raise XRPLException(error_response(ERROR_INITIALIZING_CLIENT))

            if not does_account_exist(account, client):
                raise XRPLException(error_response(ACCOUNT_DOES_NOT_EXIST_ON_THE_LEDGER.format(account)))

            transactions = []
            marker = None

            # Loop to fetch all transactions for the account, using pagination through 'marker'
            while True:
                account_tx_request = prepare_account_tx_with_pagination(account, marker)

                # Send the request to XRPL to get transaction history
                account_tx_response = client.request(account_tx_request)

                # Validate client response. Raise exception on error
                if validate_xrpl_response_data(account_tx_response):
                    process_transaction_error(account_tx_response)

                # Add fetched transactions to the list
                if "transactions" not in account_tx_response.result:
                    raise XRPLException(ERROR_FETCHING_TRANSACTION_HISTORY)

                transactions.extend(account_tx_response.result["transactions"])

                # Log the transactions for debugging
                logger.debug(json.dumps(account_tx_response.result["transactions"], indent=4, sort_keys=True))

                # Check if there are more pages of transactions to fetch
                marker = account_tx_response.result.get("marker")
                if not marker:
                    break

            # Extract pagination parameters from the request
            page = data.get("page", 1)
            page = int(page) if page else 1

            page_size = data.get("page_size", 1)
            page_size = int(page_size) if page_size else 1

            # Paginate the transactions
            paginator = Paginator(transactions, page_size)
            paginated_transactions = paginator.get_page(page)

            # Log successful transaction history fetch
            logger.info(f"Transaction history fetched for address: {account}")

            if paginated_transactions:
                # Here we assume save_transaction_history will record info based on the last transaction
                save_transaction_history(paginated_transactions[-1])

            return account_tx_with_pagination_response(paginated_transactions, paginator)

        except (XRPLRequestFailureException, XRPLException, XRPRangeException) as e:
            # Handle error message
            return handle_error_new(e, status_code=500, function_name=function_name)
        except Exception as e:
            # Handle error message
            return handle_error_new(e, status_code=500, function_name=function_name)
        finally:
            logger.info(LEAVING_FUNCTION_LOG.format(function_name, total_execution_time_in_millis(start_time)))

@method_decorator(csrf_exempt, name="dispatch")
class GetTransactionStatus(View):
    def __init__(self):
        super().__init__()
        self.client = None  # Lazy-loaded client

    def _initialize_client(self):
        """Lazy initialization of the XRPL client."""
        if not self.client:
            self.client = get_xrpl_client()
            if not self.client:
                raise XRPLException(error_response(ERROR_INITIALIZING_CLIENT))

    def post(self, request, *args, **kwargs):
        return self.check_transaction_status(request)

    def get(self, request, *args, **kwargs):
        return self.check_transaction_status(request)

    def check_transaction_status(self, request):
        # Capture the start time
        start_time = time.time()
        function_name = 'check_transaction_status'
        # Log entering the function
        logger.info(ENTERING_FUNCTION_LOG.format(function_name))

        try:
            # Initialize the client if not already initialized
            self._initialize_client()

            # Extract wallet address from request parameters
            data = json.loads(request.body)
            tx_hash = data.get("tx_hash")

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
            tx_response = client.request(tx_request)

            # Validate client response. Raise exception on error
            if validate_xrpl_response_data(tx_response):
                process_transaction_error(tx_response)

            logger.info(f"Raw XRPL response for transaction {tx_hash}: {tx_response}")

            if tx_response:
                save_transaction_history(tx_response.result)

            return transaction_status_response(tx_response)

        except (XRPLRequestFailureException, XRPLException, XRPRangeException) as e:
            # Handle error message
            return handle_error_new(e, status_code=500, function_name=function_name)
        except Exception as e:
            # Handle error message
            return handle_error_new(e, status_code=500, function_name=function_name)
        finally:
            logger.info(LEAVING_FUNCTION_LOG.format(function_name, total_execution_time_in_millis(start_time)))
