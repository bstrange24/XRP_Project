import datetime
import json
import logging
import time

from django.core.paginator import Paginator
from django.views import View
from xrpl import XRPLException
from xrpl.account import does_account_exist
from xrpl.asyncio.clients import XRPLRequestFailureException
from xrpl.transaction import submit_and_wait
from xrpl.wallet import Wallet

from .oracle_util import prepare_get_oracle_data, process_oracle_price_data_results, get_oracle_data_response, \
    prepare_create_oracle_data, prepare_create_oracle_set_data, create_oracle_data, prepare_oracle_delete_data, \
    create_oracle_delete_data, prepare_get_oracle_data_with_pagination, oracles_with_pagination_response
from ..constants.constants import ENTERING_FUNCTION_LOG, ERROR_INITIALIZING_CLIENT, LEAVING_FUNCTION_LOG, \
    INVALID_WALLET_IN_REQUEST, ACCOUNT_DOES_NOT_EXIST_ON_THE_LEDGER, SENDER_SEED_IS_INVALID, MISSING_REQUEST_PARAMETERS
from ..errors.error_handling import error_response, handle_error_new, process_transaction_error
from ..utilities.utilities import get_xrpl_client, total_execution_time_in_millis, validate_xrp_wallet, \
    is_valid_xrpl_seed, validate_xrpl_response_data

logger = logging.getLogger('xrpl_app')


class GetPriceOracle(View):
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
        return self.get_price_oracle(request)

    def get(self, request):
        return self.get_price_oracle(request)

    def get_price_oracle(self, request):
        start_time = time.time()  # Capture the start time to track the execution duration.
        function_name = 'get_price_oracle'
        logger.info(ENTERING_FUNCTION_LOG.format(function_name))  # Log function entry.

        try:
            # Initialize the client if not already initialized
            self._initialize_client()

            data = json.loads(request.body)
            oracle_creator_account = data.get("oracle_creator_account")

            logger.info(f"Oracle creator: {oracle_creator_account}")

            # Validate the provided wallet address
            if not oracle_creator_account or not validate_xrp_wallet(oracle_creator_account):
                raise XRPLRequestFailureException(error_response(INVALID_WALLET_IN_REQUEST))

            if not does_account_exist(oracle_creator_account, self.client):
                raise XRPLException(error_response(ACCOUNT_DOES_NOT_EXIST_ON_THE_LEDGER.format(oracle_creator_account)))

            oracles = []
            marker = None

            while True:
                # prepare_get_oracle_data_request = prepare_get_oracle_data(oracle_creator_account)

                # if process_oracle_price_data_results(get_oracle_price_data_result):
                #     return get_oracle_data_response(get_oracle_price_data_result, True)
                # else:
                #     return get_oracle_data_response(get_oracle_price_data_result, False)

                prepare_get_oracle_data_request = prepare_get_oracle_data_with_pagination(oracle_creator_account, marker)

                prepare_get_oracle_data_response = self.client.request(prepare_get_oracle_data_request)

                # Validate client response. Raise exception on error
                if validate_xrpl_response_data(prepare_get_oracle_data_response):
                    process_transaction_error(prepare_get_oracle_data_response)

                get_oracle_price_data_result = prepare_get_oracle_data_response.result

                if not "account_objects" in get_oracle_price_data_result or len(get_oracle_price_data_result["account_objects"]) <= 0:
                    return get_oracle_data_response(get_oracle_price_data_result, False)

                oracles.append(get_oracle_price_data_result["account_objects"])

                # Log the account_objects for debugging
                logger.debug(json.dumps(get_oracle_price_data_result["account_objects"], indent=4, sort_keys=True))

                # Check if there are more pages of account_objects to fetch
                marker = get_oracle_price_data_result.get("marker")
                if not marker:
                    break

            # Extract pagination parameters from the request
            page = data.get("page", 1)
            page = int(page) if page else 1

            page_size = data.get("page_size", 1)
            page_size = int(page_size) if page_size else 1

            # Paginate the transactions
            paginator = Paginator(oracles, page_size)
            paginated_transactions = paginator.get_page(page)

            # Log successful transaction history fetch
            logger.info(f"Transaction history fetched for address: {oracle_creator_account}")

            return oracles_with_pagination_response(paginated_transactions, paginator)

        except (XRPLRequestFailureException, XRPLException, ValueError) as e:
            # Handle error message
            return handle_error_new(e, status_code=500, function_name=function_name)
        except Exception as e:
            # Handle error message
            return handle_error_new(e, status_code=500, function_name=function_name)
        finally:
            logger.info(LEAVING_FUNCTION_LOG.format(function_name, total_execution_time_in_millis(start_time)))


class CreatePriceOracle(View):
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
        return self.create_price_get_oracle(request)

    def get(self, request):
        return self.create_price_get_oracle(request)

    def create_price_get_oracle(self, request):
        start_time = time.time()
        function_name = 'create_price_get_oracle'
        logger.info(ENTERING_FUNCTION_LOG.format(function_name))

        try:
            # Initialize the client if not already initialized
            self._initialize_client()

            data = json.loads(request.body)
            account_seed = data.get("account_seed")
            oracle_document_id = data.get("oracle_document_id")
            provider = data.get("provider")
            uri = data.get("uri")
            asset_class_type = data.get("asset_class_type")
            base_asset = data.get("base_asset")
            quote_asset = data.get("quote_asset")
            price = data.get("price")
            scale_value = data.get("scale_value")

            logger.info(f"Document Id: {oracle_document_id} Provider: {provider} URI: {uri} Asset class type: {asset_class_type}")
            logger.info(f"Base Asset: {base_asset} Quote price: {quote_asset} Price: {price} Scale value: {scale_value}")

            required_fields = ["account_seed", "oracle_document_id", "provider", "uri", "asset_class_type", "base_asset", "quote_asset", "price", "scale_value"]
            if not all(field in data for field in required_fields):
                return ValueError(error_response(MISSING_REQUEST_PARAMETERS))

            if not is_valid_xrpl_seed(account_seed):
                raise XRPLException(error_response(SENDER_SEED_IS_INVALID))

            # Verify all lists have the same length
            if not (len(base_asset) == len(quote_asset) == len(price) == len(scale_value)):
                raise ValueError(error_response("All lists must have the same number of elements"))

            if len(base_asset) > 10:
                raise ValueError(error_response("Lists cannot have more than 10 elements"))

            oracle_creator = Wallet.from_seed(account_seed)

            last_update_time = int(datetime.datetime.now().timestamp())

            price_data_array = []

            # Loop over the lists using their indices
            for i in range(len(base_asset)):
                # Create a PriceData dictionary for each set of values
                price_data = prepare_create_oracle_data(base_asset[i], quote_asset[i], price[i], scale_value[i])
                # Append the PriceData object to the array
                price_data_array.append(price_data)

            logger.info("PriceData Array")
            for item in price_data_array:
                logger.info(f"Item: {item}")

            oracle_set = prepare_create_oracle_set_data(oracle_creator.address, oracle_document_id, provider, uri,
                                                        last_update_time, asset_class_type, price_data_array)

            logger.info("signing and submitting transaction, awaiting response")
            oracle_set_txn_response = submit_and_wait(oracle_set, self.client, oracle_creator)

            if validate_xrpl_response_data(oracle_set_txn_response):
                process_transaction_error(oracle_set_txn_response)

            # print the result and transaction hash
            logger.info(oracle_set_txn_response.result["meta"]["TransactionResult"])
            logger.info(oracle_set_txn_response.result["hash"])

            return create_oracle_data(oracle_set_txn_response.result)

        except (XRPLRequestFailureException, XRPLException, ValueError) as e:
            # Handle error message
            return handle_error_new(e, status_code=500, function_name=function_name)
        except Exception as e:
            # Handle error message
            return handle_error_new(e, status_code=500, function_name=function_name)
        finally:
            logger.info(LEAVING_FUNCTION_LOG.format(function_name, total_execution_time_in_millis(start_time)))


class DeletePriceOracles(View):
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
        return self.delete_price_oracle(request)

    def get(self, request):
        return self.delete_price_oracle(request)

    def delete_price_oracle(self, request):
        start_time = time.time()  # Capture the start time of the function execution.
        function_name = 'delete_price_oracle'
        logger.info(ENTERING_FUNCTION_LOG.format(function_name))  # Log entering the function.

        try:
            # Initialize the client if not already initialized
            self._initialize_client()

            # Extract wallet address from request parameters
            data = json.loads(request.body)
            account_seed = data.get("account_seed")
            oracle_document_id = data.get("oracle_document_id")

            logger.info(f"Document Id: {oracle_document_id}")

            required_fields = ["account_seed", "oracle_document_id"]
            if not all(field in data for field in required_fields):
                return ValueError(error_response(MISSING_REQUEST_PARAMETERS))

            if not is_valid_xrpl_seed(account_seed):
                raise XRPLException(error_response(SENDER_SEED_IS_INVALID))

            oracle_creator = Wallet.from_seed(account_seed)

            prepare_get_oracle_data_request = prepare_get_oracle_data(oracle_creator.classic_address)
            prepare_get_oracle_data_response = self.client.request(prepare_get_oracle_data_request)

            get_oracle_price_data_result = prepare_get_oracle_data_response.result

            if not process_oracle_price_data_results(get_oracle_price_data_result):
                return get_oracle_data_response(get_oracle_price_data_result, False)

            oracle_set = prepare_oracle_delete_data(oracle_creator.address, int(oracle_document_id))

            logger.info("signing and submitting transaction, awaiting response")
            oracle_set_txn_response = submit_and_wait(oracle_set, self.client, oracle_creator)

            if validate_xrpl_response_data(oracle_set_txn_response):
                process_transaction_error(oracle_set_txn_response)

            # print the result and transaction hash
            logger.info(oracle_set_txn_response.result["meta"]["TransactionResult"])
            logger.info(oracle_set_txn_response.result["hash"])

            # check if the transaction was successful
            if oracle_set_txn_response.result["meta"]["TransactionResult"] == "tesSUCCESS":
                logger.info("oracle deleted successfully")

            return create_oracle_delete_data(oracle_set_txn_response.result)

        except (XRPLRequestFailureException, XRPLException, ValueError) as e:
            # Handle error message
            return handle_error_new(e, status_code=500, function_name=function_name)
        except Exception as e:
            # Handle error message
            return handle_error_new(e, status_code=500, function_name=function_name)
        finally:
            logger.info(LEAVING_FUNCTION_LOG.format(function_name, total_execution_time_in_millis(start_time)))
