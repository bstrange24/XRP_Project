import json
import logging
import time
from datetime import datetime, timedelta

from django.core.paginator import Paginator
from django.views import View
from xrpl import XRPLException
from xrpl.asyncio.clients import XRPLRequestFailureException
from xrpl.transaction import submit_and_wait
from xrpl.utils import datetime_to_ripple_time
from xrpl.wallet import Wallet

from .checks_util import get_checks_response, prepare_check_create, prepare_issued_currency, \
    create_token_check_response, prepare_xrp_check_create, prepare_cash_check, prepare_cash_token_check, \
    prepare_cancel_check, get_checks_for_account, get_checks_pagination_response
from ..accounts.account_utils import prepare_account_object_with_pagination
from ..constants.constants import ENTERING_FUNCTION_LOG, ERROR_INITIALIZING_CLIENT, LEAVING_FUNCTION_LOG, \
    SENDER_SEED_IS_INVALID, MISSING_REQUEST_PARAMETERS
from ..errors.error_handling import process_transaction_error, error_response, handle_error_new
from ..utilities.utilities import get_xrpl_client, total_execution_time_in_millis, validate_xrpl_response_data, \
    is_valid_xrpl_seed

logger = logging.getLogger('xrpl_app')


class GetChecks(View):
    def __init__(self):
        super().__init__()
        self.client = None  # Lazy-loaded client

    def _initialize_client(self):
        """Lazy initialization of the XRPL client."""
        if not self.client:
            self.client = get_xrpl_client()
            if not self.client:
                raise XRPLException(error_response(ERROR_INITIALIZING_CLIENT))

    def post(self, request):
        return self.get_checks(request)

    def get(self, request):
        return self.get_checks(request)

    def get_checks(self, request):
        start_time = time.time()  # Capture the start time to track the execution duration.
        function_name = 'get_checks'
        logger.info(ENTERING_FUNCTION_LOG.format(function_name))  # Log function entry.

        try:
            # Initialize the client if not already initialized
            self._initialize_client()

            data = json.loads(request.body)
            account_seed = data.get("account_seed")

            required_fields = ["account_seed"]
            if not all(field in data for field in required_fields):
                return ValueError(error_response(MISSING_REQUEST_PARAMETERS))

            if not is_valid_xrpl_seed(account_seed):
                raise XRPLException(error_response(SENDER_SEED_IS_INVALID))

            account = Wallet.from_seed(account_seed)
            logger.info(f"Successfully retrieved wallet: {account.classic_address}")

            result, response = get_checks_for_account(self.client, account.classic_address)
            if result:
                return get_checks_response(response, True)
            else:
                return get_checks_response(response, False)

        except (XRPLRequestFailureException, XRPLException, ValueError) as e:
            # Handle error message
            return handle_error_new(e, status_code=500, function_name=function_name)
        except Exception as e:
            # Handle error message
            return handle_error_new(e, status_code=500, function_name=function_name)
        finally:
            logger.info(LEAVING_FUNCTION_LOG.format(function_name, total_execution_time_in_millis(start_time)))


class GetChecksPage(View):
    def __init__(self):
        super().__init__()
        self.client = None

    def _initialize_client(self):
        """Lazy initialization of the XRPL client."""
        if not self.client:
            self.client = get_xrpl_client()
            if not self.client:
                raise XRPLException(error_response(ERROR_INITIALIZING_CLIENT))

    def post(self, request):
        return self.get_checks_with_pagination(request)

    def get(self, request):
        return self.get_checks_with_pagination(request)

    def get_checks_with_pagination(self, request):
        start_time = time.time()  # Capture the start time to track the execution duration.
        function_name = 'get_checks_with_pagination'
        logger.info(ENTERING_FUNCTION_LOG.format(function_name))  # Log function entry.

        try:
            # Initialize the client if not already initialized
            self._initialize_client()

            data = json.loads(request.body)
            account_seed = data.get("account_seed")

            required_fields = ["account_seed"]
            if not all(field in data for field in required_fields):
                return ValueError(error_response(MISSING_REQUEST_PARAMETERS))

            if not is_valid_xrpl_seed(account_seed):
                raise XRPLException(error_response(SENDER_SEED_IS_INVALID))

            account = Wallet.from_seed(account_seed)
            logger.info(f"Successfully retrieved wallet: {account.classic_address}")

            account_check = []
            marker = None

            # Loop to fetch all transactions for the account, using pagination through 'marker'
            while True:
                prepare_account_object_request = prepare_account_object_with_pagination(account.classic_address,
                                                                                        "validated", marker, "check")

                # Send the request to XRPL to get transaction history
                prepare_account_object_response = self.client.request(prepare_account_object_request)

                # Validate client response. Raise exception on error
                if validate_xrpl_response_data(prepare_account_object_response):
                    process_transaction_error(prepare_account_object_response)

                if "account_objects" not in prepare_account_object_response.result:
                    return get_checks_pagination_response(None, None, False)

                account_check.extend(prepare_account_object_response.result["account_objects"])

                # Log the transactions for debugging
                logger.debug(
                    json.dumps(prepare_account_object_response.result["account_objects"], indent=4, sort_keys=True))

                # Check if there are more pages of transactions to fetch
                marker = prepare_account_object_response.result.get("marker")
                if not marker:
                    break

            # Extract pagination parameters from the request
            page = data.get("page", 1)
            page = int(page) if page else 1

            page_size = data.get("page_size", 1)
            page_size = int(page_size) if page_size else 1

            # Paginate the transactions
            paginator = Paginator(account_check, page_size)
            paginated_transactions = paginator.get_page(page)

            # Log successful transaction history fetch
            logger.info(f"Account checks fetched for address: {account}")

            return get_checks_pagination_response(paginated_transactions, paginator, True)

        except (XRPLRequestFailureException, XRPLException, ValueError) as e:
            # Handle error message
            return handle_error_new(e, status_code=500, function_name=function_name)
        except Exception as e:
            # Handle error message
            return handle_error_new(e, status_code=500, function_name=function_name)
        finally:
            logger.info(LEAVING_FUNCTION_LOG.format(function_name, total_execution_time_in_millis(start_time)))


class CreateTokenCheck(View):
    def __init__(self):
        super().__init__()
        self.client = None

    def _initialize_client(self):
        """Lazy initialization of the XRPL client."""
        if not self.client:
            self.client = get_xrpl_client()
            if not self.client:
                raise XRPLException(error_response(ERROR_INITIALIZING_CLIENT))

    def post(self, request):
        return self.create_token_check(request)

    def get(self, request):
        return self.create_token_check(request)

    def create_token_check(self, request):
        start_time = time.time()
        function_name = 'create_token_check'
        logger.info(ENTERING_FUNCTION_LOG.format(function_name))

        try:
            # Initialize the client if not already initialized
            self._initialize_client()

            data = json.loads(request.body)
            sender_seed = data.get("sender_seed")
            check_receiver_address = data.get("check_receiver_address")
            token_name = data.get("token_name")
            token_issuer = data.get("token_issuer")
            amount_to_deliver = data.get("amount_to_deliver")
            expiration_days = data.get("expiration_days")

            required_fields = ["sender_seed", "check_receiver_address", "token_name", "token_issuer",
                               "amount_to_deliver", "expiration_days"]
            if not all(field in data for field in required_fields):
                return ValueError(error_response(MISSING_REQUEST_PARAMETERS))

            if not is_valid_xrpl_seed(sender_seed):
                raise XRPLException(error_response(SENDER_SEED_IS_INVALID))

            logger.info(
                f"Check receiver address: {check_receiver_address} Token name: {token_name} Token issuer: {token_issuer} Amount to deliver: {amount_to_deliver} Expiration days: {expiration_days}")

            # Set check to expire after 5 days
            expiry_date = datetime_to_ripple_time(datetime.now() + timedelta(days=float(expiration_days)))

            sender_wallet = Wallet.from_seed(sender_seed)

            issued_currency_amount = prepare_issued_currency(token_name, token_issuer, amount_to_deliver)
            prepare_check_create_txn = prepare_check_create(sender_wallet.address, check_receiver_address,
                                                            issued_currency_amount, expiry_date)

            logger.info("signing and submitting the transaction, awaiting a response")
            prepare_check_create_response = submit_and_wait(prepare_check_create_txn, self.client, sender_wallet)

            if validate_xrpl_response_data(prepare_check_create_response):
                process_transaction_error(prepare_check_create_response)

            print(prepare_check_create_response.result["meta"]["TransactionResult"])
            print(prepare_check_create_response.result["hash"])

            return create_token_check_response(prepare_check_create_response.result)

        except (XRPLRequestFailureException, XRPLException, ValueError) as e:
            # Handle error message
            return handle_error_new(e, status_code=500, function_name=function_name)
        except Exception as e:
            # Handle error message
            return handle_error_new(e, status_code=500, function_name=function_name)
        finally:
            logger.info(LEAVING_FUNCTION_LOG.format(function_name, total_execution_time_in_millis(start_time)))


class CreateXrpCheck(View):
    def __init__(self):
        super().__init__()
        self.client = None

    def _initialize_client(self):
        """Lazy initialization of the XRPL client."""
        if not self.client:
            self.client = get_xrpl_client()
            if not self.client:
                raise XRPLException(error_response(ERROR_INITIALIZING_CLIENT))

    def post(self, request):
        return self.create_xrp_check(request)

    def get(self, request):
        return self.create_xrp_check(request)

    def create_xrp_check(self, request):
        start_time = time.time()  # Capture the start time of the function execution.
        function_name = 'create_xrp_check'
        logger.info(ENTERING_FUNCTION_LOG.format(function_name))  # Log entering the function.

        try:
            # Initialize the client if not already initialized
            self._initialize_client()

            # Extract wallet address from request parameters
            data = json.loads(request.body)
            sender_seed = data.get("sender_seed")
            check_receiver_address = data.get("check_receiver_address")
            amount_to_deliver = data.get("amount_to_deliver")
            expiration_days = data.get("expiration_days")

            required_fields = ["sender_seed", "check_receiver_address", "amount_to_deliver", "expiration_days"]
            if not all(field in data for field in required_fields):
                return ValueError(error_response(MISSING_REQUEST_PARAMETERS))

            if not is_valid_xrpl_seed(sender_seed):
                raise XRPLException(error_response(SENDER_SEED_IS_INVALID))

            logger.info(
                f"Check receiver address: {check_receiver_address} Amount to deliver: {amount_to_deliver} Expiration days: {expiration_days}")

            # Set check to expire after 5 days
            expiry_date = datetime_to_ripple_time(datetime.now() + timedelta(days=float(expiration_days)))

            sender_wallet = Wallet.from_seed(sender_seed)

            prepare_check_create_txn = prepare_xrp_check_create(sender_wallet.address, check_receiver_address,
                                                                amount_to_deliver, expiry_date)

            logger.info("signing and submitting the transaction, awaiting a response")
            prepare_check_create_response = submit_and_wait(prepare_check_create_txn, self.client, sender_wallet)

            if validate_xrpl_response_data(prepare_check_create_response):
                process_transaction_error(prepare_check_create_response)

            # Print result and transaction hash
            print(prepare_check_create_response.result["meta"]["TransactionResult"])
            print(prepare_check_create_response.result["hash"])

            return create_token_check_response(prepare_check_create_response.result)

        except (XRPLRequestFailureException, XRPLException, ValueError) as e:
            # Handle error message
            return handle_error_new(e, status_code=500, function_name=function_name)
        except Exception as e:
            # Handle error message
            return handle_error_new(e, status_code=500, function_name=function_name)
        finally:
            logger.info(LEAVING_FUNCTION_LOG.format(function_name, total_execution_time_in_millis(start_time)))


class CashTokenCheck(View):
    def __init__(self):
        super().__init__()
        self.client = None

    def _initialize_client(self):
        """Lazy initialization of the XRPL client."""
        if not self.client:
            self.client = get_xrpl_client()
            if not self.client:
                raise XRPLException(error_response(ERROR_INITIALIZING_CLIENT))

    def post(self, request):
        return self.cash_token_check(request)

    def get(self, request):
        return self.cash_token_check(request)

    def cash_token_check(self, request):
        start_time = time.time()
        function_name = 'cash_token_check'
        logger.info(ENTERING_FUNCTION_LOG.format(function_name))

        try:
            # Initialize the client if not already initialized
            self._initialize_client()

            data = json.loads(request.body)
            sender_seed = data.get("sender_seed")
            token_name = data.get("token_name")
            token_issuer = data.get("token_issuer")
            cash_amount = data.get("cash_amount")
            check_id = data.get("check_id")

            required_fields = ["sender_seed", "token_name", "token_issuer", "cash_amount", "check_id"]
            if not all(field in data for field in required_fields):
                return ValueError(error_response(MISSING_REQUEST_PARAMETERS))

            if not is_valid_xrpl_seed(sender_seed):
                raise XRPLException(error_response(SENDER_SEED_IS_INVALID))

            logger.info(f"Token name: {token_name} Token issuer: {token_issuer} Amount to deliver: {cash_amount}")

            sender_wallet = Wallet.from_seed(sender_seed)

            issued_currency_amount = prepare_issued_currency(token_name, token_issuer, cash_amount)
            prepare_check_cash_txn = prepare_cash_token_check(sender_wallet.address, check_id, issued_currency_amount)

            # Autofill, sign, then submit transaction and wait for result
            prepare_check_create_response = submit_and_wait(prepare_check_cash_txn, self.client, sender_wallet)

            # Print result and transaction hash
            print(prepare_check_create_response.result["meta"]["TransactionResult"])
            print(prepare_check_create_response.result["hash"])

            return create_token_check_response(prepare_check_create_response.result)

        except (XRPLRequestFailureException, XRPLException, ValueError) as e:
            # Handle error message
            return handle_error_new(e, status_code=500, function_name=function_name)
        except Exception as e:
            # Handle error message
            return handle_error_new(e, status_code=500, function_name=function_name)
        finally:
            logger.info(LEAVING_FUNCTION_LOG.format(function_name, total_execution_time_in_millis(start_time)))


class CashXrpCheck(View):
    def __init__(self):
        super().__init__()
        self.client = None

    def _initialize_client(self):
        """Lazy initialization of the XRPL client."""
        if not self.client:
            self.client = get_xrpl_client()
            if not self.client:
                raise XRPLException(error_response(ERROR_INITIALIZING_CLIENT))

    def post(self, request):
        return self.cash_xrp_check(request)

    def get(self, request):
        return self.cash_xrp_check(request)

    def cash_xrp_check(self, request):
        start_time = time.time()  # Capture the start time of the function execution.
        function_name = 'cash_xrp_check'
        logger.info(ENTERING_FUNCTION_LOG.format(function_name))  # Log entering the function.

        try:
            # Initialize the client if not already initialized
            self._initialize_client()

            # Extract wallet address from request parameters
            data = json.loads(request.body)
            sender_seed = data.get("sender_seed")
            check_id = data.get("check_id")
            cash_amount = data.get("cash_amount")

            required_fields = ["sender_seed", "check_id", "cash_amount"]
            if not all(field in data for field in required_fields):
                return ValueError(error_response(MISSING_REQUEST_PARAMETERS))

            if not is_valid_xrpl_seed(sender_seed):
                raise XRPLException(error_response(SENDER_SEED_IS_INVALID))

            logger.info(f"Check Id: {check_id} Cash amount: {cash_amount}")

            sender_wallet = Wallet.from_seed(sender_seed)

            prepare_check_cash_txn = prepare_cash_check(sender_wallet.address, check_id, cash_amount)
            prepare_check_create_response = submit_and_wait(prepare_check_cash_txn, self.client, sender_wallet)

            if validate_xrpl_response_data(prepare_check_create_response):
                process_transaction_error(prepare_check_create_response)

            # Print result and transaction hash
            print(prepare_check_create_response.result["meta"]["TransactionResult"])
            print(prepare_check_create_response.result["hash"])

            return create_token_check_response(prepare_check_create_response.result)

        except (XRPLRequestFailureException, XRPLException, ValueError) as e:
            # Handle error message
            return handle_error_new(e, status_code=500, function_name=function_name)
        except Exception as e:
            # Handle error message
            return handle_error_new(e, status_code=500, function_name=function_name)
        finally:
            logger.info(LEAVING_FUNCTION_LOG.format(function_name, total_execution_time_in_millis(start_time)))


class CancelCheck(View):
    def __init__(self):
        super().__init__()
        self.client = None  # Lazy-loaded client

    def _initialize_client(self):
        """Lazy initialization of the XRPL client."""
        if not self.client:
            self.client = get_xrpl_client()
            if not self.client:
                raise XRPLException(error_response(ERROR_INITIALIZING_CLIENT))

    def post(self, request):
        return self.cancel_check(request)

    def get(self, request):
        return self.cancel_check(request)

    def cancel_check(self, request):
        start_time = time.time()  # Capture the start time to track the execution duration.
        function_name = 'cancel_check'
        logger.info(ENTERING_FUNCTION_LOG.format(function_name))  # Log function entry.

        try:
            # Initialize the client if not already initialized
            self._initialize_client()

            data = json.loads(request.body)
            account_seed = data.get("account_seed")
            check_id = data.get("check_id")

            required_fields = ["account_seed", "check_id"]
            if not all(field in data for field in required_fields):
                return ValueError(error_response(MISSING_REQUEST_PARAMETERS))

            if not is_valid_xrpl_seed(account_seed):
                raise XRPLException(error_response(SENDER_SEED_IS_INVALID))

            sender_wallet = Wallet.from_seed(account_seed)
            logger.info(f"Successfully retrieved wallet: {sender_wallet.classic_address}")

            result, response = get_checks_for_account(self.client, sender_wallet.classic_address)
            if not result:
                return get_checks_response(response, False)

            prepare_check_cancel_txn = prepare_cancel_check(sender_wallet.address, check_id)
            prepare_check_cancel_response = submit_and_wait(prepare_check_cancel_txn, self.client, sender_wallet)

            if validate_xrpl_response_data(prepare_check_cancel_response):
                process_transaction_error(prepare_check_cancel_response)

            # Print result and transaction hash
            print(prepare_check_cancel_response.result["meta"]["TransactionResult"])
            print(prepare_check_cancel_response.result["hash"])

            return create_token_check_response(prepare_check_cancel_response.result)

        except (XRPLRequestFailureException, XRPLException, ValueError) as e:
            # Handle error message
            return handle_error_new(e, status_code=500, function_name=function_name)
        except Exception as e:
            # Handle error message
            return handle_error_new(e, status_code=500, function_name=function_name)
        finally:
            logger.info(LEAVING_FUNCTION_LOG.format(function_name, total_execution_time_in_millis(start_time)))
