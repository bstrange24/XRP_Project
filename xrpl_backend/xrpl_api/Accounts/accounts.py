import json
import logging
import time

from django.core.paginator import Paginator
from django.utils.decorators import method_decorator
from django.views import View
from django.views.decorators.csrf import csrf_exempt
from xrpl import XRPLException
from xrpl.account import does_account_exist
from xrpl.asyncio.wallet import XRPLFaucetException
from xrpl.clients import XRPLRequestFailureException
from xrpl.core import addresscodec
from xrpl.core.addresscodec import XRPLAddressCodecException
from xrpl.utils import XRPRangeException
from xrpl.wallet import generate_faucet_wallet, Wallet

from .account_utils import process_all_flags, prepare_account_tx_for_hash_account, \
    account_tx_with_pagination_response, prepare_account_object_with_filter
from .db_operations.account_db_operations import save_account_data, save_account_configuration_transaction
from ..accounts.account_utils import create_multiple_account_response, \
    create_account_response, create_wallet_info_response, get_account_reserves, create_wallet_balance_response, \
    account_set_tx_response, prepare_account_data, account_config_settings, get_account_set_flags
from ..constants.constants import ENTERING_FUNCTION_LOG, \
    ERROR_INITIALIZING_CLIENT, LEAVING_FUNCTION_LOG, INVALID_WALLET_IN_REQUEST, \
    ACCOUNT_DOES_NOT_EXIST_ON_THE_LEDGER, ERROR_CREATING_TEST_WALLET, INVALID_XRP_BALANCE, \
    CLASSIC_XRP_ADDRESS, X_XRP_ADDRESS, FAILED_TO_FETCH_RESERVE_DATA, SENDER_SEED_IS_INVALID, \
    MISSING_REQUEST_PARAMETERS, ACCOUNT_OBJECTS_TYPE
from ..errors.error_handling import process_transaction_error, handle_error_new, error_response
from ..transactions.transactions_util import prepare_tx
from ..utilities.utilities import get_xrpl_client, convert_drops_to_xrp, \
    total_execution_time_in_millis, validate_xrp_wallet, is_valid_xrpl_seed, validate_xrpl_response_data

logger = logging.getLogger('xrpl_app')


@method_decorator(csrf_exempt, name="dispatch")
class CreateTestAccount(View):
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
        return self.create_test_account(request)

    def get(self, request, *args, **kwargs):
        return self.create_test_account(request)

    def create_test_account(self, request):
        # Capture the start time
        start_time = time.time()
        function_name = 'create_test_account'
        # Log entering the function
        logger.info(ENTERING_FUNCTION_LOG.format(function_name))

        try:
            # Initialize the client if not already initialized
            self._initialize_client()

            # Generate a new wallet using the faucet. Check if new wallet is successfully created. Raise exception if wallet creation fails
            new_wallet = generate_faucet_wallet(self.client, debug=True)
            if not new_wallet:
                raise XRPLException(error_response(ERROR_CREATING_TEST_WALLET))

            # Prepare account data for the request
            account_info = prepare_account_data(new_wallet.address, False)

            # Send the request to the XRPL client
            account_info_response = self.client.request(account_info)

            # Validate client response. Raise exception on error
            if validate_xrpl_response_data(account_info_response):
                process_transaction_error(account_info_response)

            # Log the classic address and X-address
            logger.debug(f"{CLASSIC_XRP_ADDRESS} {new_wallet.address}")
            logger.debug(
                f"{X_XRP_ADDRESS} {addresscodec.classic_address_to_xaddress(new_wallet.address, tag=12345, is_test_network=True)}")

            # Convert balance from drops to XRP
            xrp_balance = convert_drops_to_xrp(account_info_response.result['account_data']['Balance'])
            logger.debug(f"Xrp balance: {xrp_balance}")

            # Validate balance is greater than 0
            if not xrp_balance or xrp_balance <= 0:
                raise XRPLException(error_response(INVALID_XRP_BALANCE))

            # Save account data to databases
            save_account_data(account_info_response.result, str(xrp_balance))
            logger.debug(f"{CLASSIC_XRP_ADDRESS} save to database")

            print(f"Address: {new_wallet.classic_address} seed: {new_wallet.seed}")

            # Return response with account information
            return create_account_response(new_wallet.address, new_wallet.seed, xrp_balance,
                                           account_info_response.result)

        except (XRPLFaucetException, XRPLRequestFailureException, XRPLException) as e:
            # Handle error message
            return handle_error_new(e, status_code=500, function_name=function_name)
        except Exception as e:
            # Handle error message
            return handle_error_new(e, status_code=500, function_name=function_name)
        finally:
            logger.info(LEAVING_FUNCTION_LOG.format(function_name, total_execution_time_in_millis(start_time)))


@method_decorator(csrf_exempt, name="dispatch")
class CreateTestAccounts(View):
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
        return self.create_multiple_test_accounts(request)

    def get(self, request, *args, **kwargs):
        return self.create_multiple_test_accounts(request)

    def create_multiple_test_accounts(self, request):
        # Capture the start time
        start_time = time.time()
        function_name = 'create_multiple_accounts'
        # Log entering the function
        logger.info(ENTERING_FUNCTION_LOG.format(function_name))

        try:
            # Initialize the client if not already initialized
            self._initialize_client()

            # Extract wallet address from request parameters
            data = json.loads(request.body)
            create_number_of_accounts = data.get("number_of_accounts")

            transactions = []

            for _ in range(int(create_number_of_accounts)):
                # Generate a new wallet using the faucet. Check if new wallet is successfully created. Raise exception if wallet creation fails
                new_wallet = generate_faucet_wallet(self.client, debug=True)
                if not new_wallet:
                    raise XRPLException(error_response(ERROR_CREATING_TEST_WALLET))

                # Prepare account data for the request
                account_info = prepare_account_data(new_wallet.address, False)

                # Send the request to the XRPL client
                account_info_response = self.client.request(account_info)

                if validate_xrpl_response_data(account_info_response):
                    process_transaction_error(account_info_response)

                # Log the classic address and X-address
                logger.debug(f"{CLASSIC_XRP_ADDRESS} {new_wallet.address}")
                logger.debug(
                    f"{X_XRP_ADDRESS} {addresscodec.classic_address_to_xaddress(new_wallet.address, tag=12345, is_test_network=True)}")

                # Convert balance from drops to XRP
                xrp_balance = convert_drops_to_xrp(account_info_response.result['account_data']['Balance'])
                logger.debug(f"Xrp balance: {xrp_balance}")

                if not xrp_balance or xrp_balance <= 0:
                    raise XRPLException(error_response(INVALID_XRP_BALANCE))

                # Save account data to databases
                save_account_data(account_info_response.result, str(xrp_balance))
                logger.debug(f"{CLASSIC_XRP_ADDRESS} save to database")

                # Accessing the result from the response
                account_info_data = account_info_response.result  # This will give you a dictionary

                # Now you can modify the 'seed'
                account_info_data['account_data']['seed'] = new_wallet.seed
                account_info_data['account_data']['private_key'] = new_wallet.private_key
                account_info_data['account_data']['public_key'] = new_wallet.public_key

                transactions.append(account_info_data)

                print(f"Address: {new_wallet.classic_address} seed: {new_wallet.seed}")

            logger.debug(f"{int(create_number_of_accounts)} Wallets created: {transactions}")

            return create_multiple_account_response(transactions)

        except (XRPLFaucetException, XRPLRequestFailureException, XRPLException) as e:
            # Handle error message
            return handle_error_new(e, status_code=500, function_name=function_name)
        except Exception as e:
            # Handle error message
            return handle_error_new(e, status_code=500, function_name=function_name)
        finally:
            logger.info(LEAVING_FUNCTION_LOG.format(function_name, total_execution_time_in_millis(start_time)))


@method_decorator(csrf_exempt, name="dispatch")
class GetAccountInfo(View):
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
        return self.get_account_info(request)

    def get(self, request, *args, **kwargs):
        return self.get_account_info(request)

    def get_account_info(self, request):
        start_time = time.time()  # Capture the start time
        function_name = 'get_account_info'
        logger.info(ENTERING_FUNCTION_LOG.format(function_name))

        try:
            # Initialize the client if not already initialized
            self._initialize_client()

            # Extract wallet address from request parameters
            data = json.loads(request.body)
            account = data.get("account")

            # Validate the provided wallet address
            if not account or not validate_xrp_wallet(account):
                raise XRPLRequestFailureException(error_response(INVALID_WALLET_IN_REQUEST))

            if not does_account_exist(account, self.client):
                raise XRPLException(error_response(ACCOUNT_DOES_NOT_EXIST_ON_THE_LEDGER.format(account)))

            # Prepare account data for the request
            account_info = prepare_account_data(account, False)

            # Send the request to the XRPL client
            account_info_response = self.client.request(account_info)

            if validate_xrpl_response_data(account_info_response):
                process_transaction_error(account_info_response)

            # Convert the balance from drops to XRP
            xrp_balance = convert_drops_to_xrp(account_info_response.result['account_data']['Balance'])

            # Retrieve the base reserve and reserve increment
            base_reserve, reserve_increment = get_account_reserves()
            if base_reserve is None or reserve_increment is None:
                raise XRPLException(error_response(FAILED_TO_FETCH_RESERVE_DATA.format(account)))

            logger.info(
                f"Account found: {account}, Balance: {xrp_balance}, Base Reserve: {base_reserve}, Reserve Increment: {reserve_increment}")

            return create_wallet_info_response(base_reserve, reserve_increment, account_info_response.result)

        except (XRPLRequestFailureException, XRPLException, XRPRangeException) as e:
            # Handle error message
            return handle_error_new(e, status_code=500, function_name=function_name)
        except Exception as e:
            # Handle error message
            return handle_error_new(e, status_code=500, function_name=function_name)
        finally:
            logger.info(LEAVING_FUNCTION_LOG.format(function_name, total_execution_time_in_millis(start_time)))


@method_decorator(csrf_exempt, name="dispatch")
class GetAccountInfoFromHash(View):
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
        return self.get_account_info_from_hash(request)

    def get(self, request, *args, **kwargs):
        return self.get_account_info_from_hash(request)

    def get_account_info_from_hash(self, request):
        start_time = time.time()  # Capture the start time
        function_name = 'get_account_info_from_hash'
        logger.info(ENTERING_FUNCTION_LOG.format(function_name))

        try:
            # Initialize the client if not already initialized
            self._initialize_client()

            # Extract wallet address from request parameters
            data = json.loads(request.body)
            tx_hash = data.get("tx_hash")
            get_account_objects = data.get("get_account_objects")
            get_all_tx_for_account = data.get("get_all_tx_for_account")
            filter_account_object = data.get("filter_account_object")

            if not all([tx_hash, get_account_objects, get_all_tx_for_account]):
                raise ValueError(error_response(MISSING_REQUEST_PARAMETERS))

            if get_account_objects == 'True' and get_all_tx_for_account == 'True':
                raise ValueError(
                    error_response('Getting all transactions and account object at the same time is not supported.'))

            # Check if value is in the list using 'in'
            if filter_account_object in ACCOUNT_OBJECTS_TYPE:
                print(f"{filter_account_object} is a valid account object type!")
            else:
                print(f"{filter_account_object} is not in the list. Defaulting to no object type")
                filter_account_object = None

            transactions = []
            marker = None

            tx_hash_request = prepare_tx(tx_hash)
            tx_response = self.client.request(tx_hash_request)
            account = tx_response.result['tx_json']["Account"]  # The account that initiated the transaction
            logger.info(f"Account associated with hash {tx_hash}: {account}")

            if get_account_objects == 'True':
                # Loop to fetch all transactions for the account, using pagination through 'marker'
                while True:
                    account_objects_request = prepare_account_object_with_filter(account, filter_account_object)
                    account_objects_response = self.client.request(account_objects_request)
                    logger.info("Account Objects (Escrows, Offers, etc.):")
                    if account_objects_response.result["account_objects"]:
                        logger.debug(f"Account Objects: {account_objects_response.result["account_objects"]}")
                    else:
                        logger.info("No account objects found.")

                    transactions.extend(account_objects_response.result["account_objects"])
                    logger.debug(
                        json.dumps(account_objects_response.result["account_objects"], indent=4, sort_keys=True))

                    # Check if there are more pages of transactions to fetch
                    marker = account_objects_response.result.get("marker")
                    if not marker:
                        break
            else:
                # Loop to fetch all transactions for the account, using pagination through 'marker'
                while True:
                    # Get transaction history (payments, etc.)
                    account_tx_request = prepare_account_tx_for_hash_account(account, marker)
                    account_tx_response = self.client.request(account_tx_request)
                    transactions.extend(account_tx_response.result["transactions"])
                    logger.debug(json.dumps(account_tx_response.result["transactions"], indent=4, sort_keys=True))

                    if account_tx_response.result["transactions"]:
                        for tx in account_tx_response.result["transactions"]:
                            logger.debug(
                                f"Tx Hash: {tx['hash']}, Type: {tx['tx_json']['TransactionType']}, Result: {tx['meta']['TransactionResult']}")
                    else:
                        logger.info("No transactions found.")

                    # Check if there are more pages of transactions to fetch
                    marker = account_tx_response.result.get("marker")
                    if not marker:
                        break

            # Extract pagination parameters from the request
            page = self.request.GET.get('page', 1)
            page = int(page) if page else 1

            page_size = self.request.GET.get('page_size', 10)
            page_size = int(page_size) if page_size else 1

            # Paginate the transactions
            paginator = Paginator(transactions, page_size)
            paginated_transactions = paginator.get_page(page)

            # Log successful transaction history fetch
            logger.info(f"Transaction history fetched for address: {account}")
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
class GetAccountBalance(View):
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
        return self.check_account_balance(request)

    def get(self, request, *args, **kwargs):
        return self.check_account_balance(request)

    def check_account_balance(self, request):
        start_time = time.time()  # Capture the start time
        function_name = 'check_wallet_balance'
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

            if not does_account_exist(account, self.client):
                raise XRPLException(error_response(ACCOUNT_DOES_NOT_EXIST_ON_THE_LEDGER.format(account)))

            # Prepare account data for the request
            account_info = prepare_account_data(account, False)

            # Send the request to the XRPL client
            account_info_response = self.client.request(account_info)

            if validate_xrpl_response_data(account_info_response):
                process_transaction_error(account_info_response)

            # Convert the balance from drops to XRP
            balance_in_xrp = convert_drops_to_xrp(account_info_response.result['account_data']['Balance'])
            logger.info(f"Balance for address {account} retrieved successfully: {balance_in_xrp} XRP")

            # Return a JSON response with the wallet information
            return create_wallet_balance_response(balance_in_xrp, account_info_response.result)

        except (XRPLRequestFailureException, XRPLException, XRPRangeException) as e:
            # Handle error message
            return handle_error_new(e, status_code=500, function_name=function_name)
        except Exception as e:
            # Handle error message
            return handle_error_new(e, status_code=500, function_name=function_name)
        finally:
            logger.info(LEAVING_FUNCTION_LOG.format(function_name, total_execution_time_in_millis(start_time)))


@method_decorator(csrf_exempt, name="dispatch")
class GetAccountConfiguration(View):
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
        return self.get_account_config(request)

    def get(self, request, *args, **kwargs):
        return self.get_account_config(request)

    def get_account_config(self, request):
        start_time = time.time()  # Capture the start time
        function_name = 'get_account_config'
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

            if not does_account_exist(account, self.client):
                raise XRPLException(error_response(ACCOUNT_DOES_NOT_EXIST_ON_THE_LEDGER.format(account)))

            logger.info(f"Getting account config for {account} ")

            # Prepare account data for the request
            account_info = prepare_account_data(account, False)

            # Send the request to the XRPL client
            account_info_response = self.client.request(account_info)

            if validate_xrpl_response_data(account_info_response):
                process_transaction_error(account_info_response)

            logger.info(f"Retrieved account config for {account} ")

            return account_config_settings(account_info_response.result)

        except (XRPLRequestFailureException, XRPLException, XRPLAddressCodecException, ValueError) as e:
            # Handle error message
            return handle_error_new(e, status_code=500, function_name=function_name)
        except Exception as e:
            # Handle error message
            return handle_error_new(e, status_code=500, function_name=function_name)
        finally:
            logger.info(LEAVING_FUNCTION_LOG.format(function_name, total_execution_time_in_millis(start_time)))


@method_decorator(csrf_exempt, name="dispatch")
class UpdateAccountConfiguration(View):
    def __init__(self):
        super().__init__()
        self.client = None  # Lazy-loaded client

    def _initialize_client(self):
        """Lazy initialization of the XRPL client."""
        if not self.client:
            self.client = get_xrpl_client()
            if not self.client:
                raise XRPLException(error_response(ERROR_INITIALIZING_CLIENT))

    def put(self, request, *args, **kwargs):
        return self.update_account_config(request)

    def update_account_config(self, request):
        overall_start_time = time.time()
        function_name = 'update_account_config'
        logger.info(ENTERING_FUNCTION_LOG.format(function_name))

        try:
            # Initialize the client if not already initialized
            self._initialize_client()

            # Extract wallet address from request parameters
            data = json.loads(request.body)
            wallet_seed = data.get("wallet_seed")

            # Validate and extract request parameters
            if not is_valid_xrpl_seed(wallet_seed):
                raise XRPLException(error_response(SENDER_SEED_IS_INVALID))

            sender_wallet = Wallet.from_seed(wallet_seed)
            sender_address = sender_wallet.classic_address
            logger.info(f"Processing account config for {sender_address}")

            # Get flags from request (enabled and disabled)
            flags_to_enable, flags_to_disable = get_account_set_flags(self, data)
            all_flags = flags_to_enable + flags_to_disable
            logger.info(f"Total Flags being processed: {len(all_flags)}")

            # Process each flag and collect the transaction responses.
            tx_responses = process_all_flags(sender_address, self.client, sender_wallet, flags_to_enable, all_flags)

            # Save account transaction info (if needed)
            if tx_responses:
                # Here we assume save_account_transaction will record info based on the last transaction
                save_account_configuration_transaction(tx_responses[-1], flags_to_enable)

            return account_set_tx_response(tx_responses[-1], sender_address)

        except (XRPLRequestFailureException, XRPLException, XRPLAddressCodecException, ValueError) as e:
            return handle_error_new(e, status_code=500, function_name=function_name)
        except Exception as e:
            return handle_error_new(e, status_code=500, function_name=function_name)
        finally:
            elapsed = total_execution_time_in_millis(overall_start_time)
            logger.info(LEAVING_FUNCTION_LOG.format(function_name, elapsed))
