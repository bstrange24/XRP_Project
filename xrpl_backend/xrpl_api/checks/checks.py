import json
import logging
import time

from django.core.paginator import Paginator
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import csrf_exempt
from xrpl import XRPLException
from xrpl.asyncio.clients import XRPLRequestFailureException
from xrpl.transaction import submit_and_wait
from xrpl.wallet import Wallet

from .checks_util import get_checks_response, prepare_check_create, prepare_issued_currency, \
    create_token_check_response, prepare_xrp_check_create, prepare_cash_check, prepare_cash_token_check, \
    prepare_cancel_check, get_checks_for_account, get_checks_pagination_response
from ..accounts.account_utils import prepare_account_object_with_pagination
from ..constants.constants import ENTERING_FUNCTION_LOG, LEAVING_FUNCTION_LOG, \
    SENDER_SEED_IS_INVALID, MISSING_REQUEST_PARAMETERS, INVALID_WALLET_IN_REQUEST
from ..errors.error_handling import process_transaction_error, error_response, handle_error_new, \
    process_unexpected_error
from ..escrows.escrows_util import set_claim_date
from ..utilities.base_xrpl_view import BaseXRPLView
from ..utilities.utilities import total_execution_time_in_millis, validate_xrpl_response_data

logger = logging.getLogger('xrpl_app')


@method_decorator(csrf_exempt, name="dispatch")
class GetChecks(BaseXRPLView):
    def post(self, request):
        return self.get_checks(request)

    def get(self, request):
        return self.get_checks(request)

    def get_checks(self, request):
        start_time = time.time()  # Capture the start time to track the execution duration.
        function_name = 'get_checks'
        logger.info(ENTERING_FUNCTION_LOG.format(function_name))  # Log function entry.

        try:
            self._initialize_client()

            data = json.loads(request.body)
            account_seed = data.get("account_seed")

            if not all([account_seed]):
                raise ValueError(error_response(MISSING_REQUEST_PARAMETERS))

            if not self._is_valid_xrpl_seed(account_seed):
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


@method_decorator(csrf_exempt, name="dispatch")
class GetChecksPage(BaseXRPLView):
    def post(self, request):
        return self.get_checks_with_pagination(request)

    def get(self, request):
        return self.get_checks_with_pagination(request)

    def get_checks_with_pagination(self, request):
        start_time = time.time()  # Capture the start time to track the execution duration.
        function_name = 'get_checks_with_pagination'
        logger.info(ENTERING_FUNCTION_LOG.format(function_name))  # Log function entry.

        try:
            self._initialize_client()

            data = json.loads(request.body)
            account_seed = data.get("account_seed")

            if not all([account_seed]):
                raise ValueError(error_response(MISSING_REQUEST_PARAMETERS))

            if not self._is_valid_xrpl_seed(account_seed):
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

                if "account_objects" not in prepare_account_object_response.result or len(
                        prepare_account_object_response.result['account_objects']) <= 0:
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


@method_decorator(csrf_exempt, name="dispatch")
class CreateTokenCheck(BaseXRPLView):
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
            expiration = data.get("expiration")

            if not all([sender_seed, check_receiver_address, token_name, token_issuer, amount_to_deliver, expiration]):
                raise ValueError(error_response(MISSING_REQUEST_PARAMETERS))

            if not self._is_valid_xrpl_seed(sender_seed):
                raise XRPLException(error_response(SENDER_SEED_IS_INVALID))

            if not self._is_valid_currency_code(token_name):
                raise ValueError(error_response("Invalid currency code"))

            if not self._validate_xrp_wallet(token_issuer):
                raise XRPLException(error_response(INVALID_WALLET_IN_REQUEST))

            if not self._validate_xrp_wallet(check_receiver_address):
                raise XRPLException(error_response(INVALID_WALLET_IN_REQUEST))

            if not self._is_valid_amount(amount_to_deliver):
                raise ValueError(error_response("Invalid cash amount"))

            logger.info(
                f"Check receiver address: {check_receiver_address} Token name: {token_name} Token issuer: {token_issuer} Amount to deliver: {amount_to_deliver} Expiration: {expiration}")

            expiry_date = set_claim_date(expiration)

            sender_wallet = Wallet.from_seed(sender_seed)

            issued_currency_amount = prepare_issued_currency(token_name, token_issuer, amount_to_deliver)
            prepare_check_create_txn = prepare_check_create(sender_wallet.address, check_receiver_address,
                                                            issued_currency_amount, expiry_date)
            try:
                logger.info("signing and submitting the transaction, awaiting a response")
                prepare_check_create_response = submit_and_wait(prepare_check_create_txn, self.client, sender_wallet)
            except XRPLException as e:
                process_unexpected_error(e)

            if validate_xrpl_response_data(prepare_check_create_response):
                process_transaction_error(prepare_check_create_response)

            logger.debug(json.dumps(prepare_check_create_response.result, indent=4, sort_keys=True))

            return create_token_check_response(prepare_check_create_response.result)

        except (XRPLRequestFailureException, XRPLException, ValueError) as e:
            # Handle error message
            return handle_error_new(e, status_code=500, function_name=function_name)
        except Exception as e:
            # Handle error message
            return handle_error_new(e, status_code=500, function_name=function_name)
        finally:
            logger.info(LEAVING_FUNCTION_LOG.format(function_name, total_execution_time_in_millis(start_time)))


@method_decorator(csrf_exempt, name="dispatch")
class CreateXrpCheck(BaseXRPLView):
    def post(self, request):
        return self.create_xrp_check(request)

    def get(self, request):
        return self.create_xrp_check(request)

    def create_xrp_check(self, request):
        start_time = time.time()  # Capture the start time of the function execution.
        function_name = 'create_xrp_check'
        logger.info(ENTERING_FUNCTION_LOG.format(function_name))  # Log entering the function.

        try:
            self._initialize_client()

            data = json.loads(request.body)
            sender_seed = data.get("sender_seed")
            check_receiver_address = data.get("check_receiver_address")
            amount_to_deliver = data.get("amount_to_deliver")
            expiration = data.get("expiration")

            if not all([sender_seed, check_receiver_address, amount_to_deliver, expiration]):
                raise ValueError(error_response(MISSING_REQUEST_PARAMETERS))

            if not self._is_valid_xrpl_seed(sender_seed):
                raise XRPLException(error_response(SENDER_SEED_IS_INVALID))

            if not self._validate_xrp_wallet(check_receiver_address):
                raise XRPLException(error_response(INVALID_WALLET_IN_REQUEST))

            if not self._is_valid_xrp_amount(amount_to_deliver):
                raise ValueError(error_response("Invalid XRP amount"))

            logger.info(
                f"Check receiver address: {check_receiver_address} Amount to deliver: {amount_to_deliver} Expiration: {expiration}")

            expiry_date = set_claim_date(expiration)

            sender_wallet = Wallet.from_seed(sender_seed)

            prepare_check_create_txn = prepare_xrp_check_create(sender_wallet.address, check_receiver_address,
                                                                amount_to_deliver, expiry_date)
            try:
                logger.info("signing and submitting the transaction, awaiting a response")
                prepare_check_create_response = submit_and_wait(prepare_check_create_txn, self.client, sender_wallet)
            except XRPLException as e:
                process_unexpected_error(e)

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


@method_decorator(csrf_exempt, name="dispatch")
class CashTokenCheck(BaseXRPLView):
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

            if not all([sender_seed, token_name, token_issuer, cash_amount, check_id]):
                raise ValueError(error_response(MISSING_REQUEST_PARAMETERS))

            if not self._is_valid_xrpl_seed(sender_seed):
                raise XRPLException(error_response(SENDER_SEED_IS_INVALID))

            if not self._is_valid_currency_code(token_name):
                raise ValueError(error_response("Invalid currency code"))

            if not self._validate_xrp_wallet(token_issuer):
                raise XRPLException(error_response(INVALID_WALLET_IN_REQUEST))

            if not self._is_valid_amount(cash_amount):
                raise ValueError(error_response("Invalid cash amount"))

            logger.info(
                f"Token name: {token_name} Token issuer: {token_issuer} Amount to deliver: {cash_amount} Check ID: {check_id}")

            sender_wallet = Wallet.from_seed(sender_seed)

            issued_currency_amount = prepare_issued_currency(token_name, token_issuer, cash_amount)
            prepare_check_cash_txn = prepare_cash_token_check(sender_wallet.address, check_id, issued_currency_amount)

            try:
                logger.info("signing and submitting the transaction, awaiting a response")
                prepare_check_create_response = submit_and_wait(prepare_check_cash_txn, self.client, sender_wallet)
            except XRPLException as e:
                process_unexpected_error(e)

            # Validate client response. Raise exception on error
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


@method_decorator(csrf_exempt, name="dispatch")
class CashXrpCheck(BaseXRPLView):
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

            if not all([sender_seed, check_id, cash_amount]):
                raise ValueError(error_response(MISSING_REQUEST_PARAMETERS))

            if not self._is_valid_xrpl_seed(sender_seed):
                raise XRPLException(error_response(SENDER_SEED_IS_INVALID))

            if not self._is_valid_xrp_amount(cash_amount):
                raise ValueError(error_response("Invalid XRP amount"))

            logger.info(f"Check Id: {check_id} Cash amount: {cash_amount}")

            sender_wallet = Wallet.from_seed(sender_seed)

            prepare_check_cash_txn = prepare_cash_check(sender_wallet.address, check_id, cash_amount)

            try:
                logger.info("signing and submitting the transaction, awaiting a response")
                prepare_check_create_response = submit_and_wait(prepare_check_cash_txn, self.client, sender_wallet)
            except XRPLException as e:
                process_unexpected_error(e)

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


@method_decorator(csrf_exempt, name="dispatch")
class CancelCheck(BaseXRPLView):
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

            if not all([account_seed, check_id]):
                raise ValueError(error_response(MISSING_REQUEST_PARAMETERS))

            if not self._is_valid_xrpl_seed(account_seed):
                raise XRPLException(error_response(SENDER_SEED_IS_INVALID))

            sender_wallet = Wallet.from_seed(account_seed)
            logger.info(f"Successfully retrieved wallet: {sender_wallet.classic_address}")

            result, response = get_checks_for_account(self.client, sender_wallet.classic_address)
            if not result:
                return get_checks_response(response, False)

            prepare_check_cancel_txn = prepare_cancel_check(sender_wallet.address, check_id)

            try:
                logger.info("signing and submitting the transaction, awaiting a response")
                prepare_check_cancel_response = submit_and_wait(prepare_check_cancel_txn, self.client, sender_wallet)
            except XRPLException as e:
                process_unexpected_error(e)

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
