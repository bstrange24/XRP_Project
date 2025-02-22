import logging
import time

from django.http import JsonResponse
from django.views import View
from rest_framework.decorators import api_view
from tenacity import wait_exponential, stop_after_attempt, retry
from xrpl import XRPLException
from xrpl.account import does_account_exist
from xrpl.asyncio.wallet import XRPLFaucetException
from xrpl.clients import XRPLRequestFailureException
from xrpl.core import addresscodec
from xrpl.core.addresscodec import XRPLAddressCodecException
from xrpl.transaction import submit_and_wait
from xrpl.utils import XRPRangeException
from xrpl.wallet import generate_faucet_wallet, Wallet

from .account_utils import prepare_account_set_disabled_tx, prepare_account_set_enabled_tx, process_all_flags
from .db_operations.account_db_operations import save_account_data, save_account_configuration_transaction
from ..accounts.account_utils import create_multiple_account_response, \
    create_account_response, create_wallet_info_response, get_account_reserves, create_wallet_balance_response, \
    account_set_tx_response, prepare_account_data, account_config_settings, get_account_set_flags
from ..constants import RETRY_BACKOFF, MAX_RETRIES, ENTERING_FUNCTION_LOG, \
    ERROR_INITIALIZING_CLIENT, LEAVING_FUNCTION_LOG, INVALID_WALLET_IN_REQUEST, \
    ACCOUNT_DOES_NOT_EXIST_ON_THE_LEDGER, ERROR_CREATING_TEST_WALLET, INVALID_XRP_BALANCE, \
    CLASSIC_XRP_ADDRESS, X_XRP_ADDRESS, FAILED_TO_FETCH_RESERVE_DATA, SENDER_SEED_IS_INVALID
from ..errors.error_handling import process_transaction_error, handle_error_new, error_response
from ..transactions.transactions_util import prepare_tx
from ..utils import get_request_param, get_xrpl_client, convert_drops_to_xrp, \
    total_execution_time_in_millis, validate_xrp_wallet, is_valid_xrpl_seed, validate_xrpl_response_data

logger = logging.getLogger('xrpl_app')


class Accounts(View):

    @api_view(['GET'])
    @retry(wait=wait_exponential(multiplier=RETRY_BACKOFF), stop=stop_after_attempt(MAX_RETRIES))
    def create_test_account(self):
        # Capture the start time
        start_time = time.time()
        function_name = 'create_test_account'
        # Log entering the function
        logger.info(ENTERING_FUNCTION_LOG.format(function_name))

        try:
            # Initialize XRPL client. Check if client is successfully initialized. Raise exception if client initialization fails
            client = get_xrpl_client()
            if not client:
                raise XRPLException(error_response(ERROR_INITIALIZING_CLIENT))

            # Generate a new wallet using the faucet. Check if new wallet is successfully created. Raise exception if wallet creation fails
            new_wallet = generate_faucet_wallet(client, debug=True)
            if not new_wallet:
                raise XRPLException(error_response(ERROR_CREATING_TEST_WALLET))

            # Prepare account data for the request
            account_info = prepare_account_data(new_wallet.address, False)

            # Send the request to the XRPL client
            account_info_response = client.request(account_info)

            # Validate client response. Raise exception on error
            if validate_xrpl_response_data(account_info_response):
                process_transaction_error(account_info_response)

            # Log the classic address and X-address
            logger.debug(f"{CLASSIC_XRP_ADDRESS} {new_wallet.address}")
            logger.debug(f"{X_XRP_ADDRESS} {addresscodec.classic_address_to_xaddress(new_wallet.address, tag=12345, is_test_network=True)}")

            # Convert balance from drops to XRP
            xrp_balance = convert_drops_to_xrp(account_info_response.result['account_data']['Balance'])
            logger.debug(f"Xrp balance: {xrp_balance}")

            # Validate balance is greater than 0
            if not xrp_balance or xrp_balance <= 0:
                raise XRPLException(error_response(INVALID_XRP_BALANCE))

            # Save account data to databases
            save_account_data(account_info_response.result, str(xrp_balance))
            logger.debug(f"{CLASSIC_XRP_ADDRESS} save to database")

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

    @api_view(['POST'])
    @retry(wait=wait_exponential(multiplier=RETRY_BACKOFF), stop=stop_after_attempt(MAX_RETRIES))
    def create_multiple_test_accounts(self):
        # Capture the start time
        start_time = time.time()
        function_name = 'create_multiple_accounts'
        # Log entering the function
        logger.info(ENTERING_FUNCTION_LOG.format(function_name))

        try:
            # Extract and validate parameters from the request
            create_number_of_accounts = get_request_param(self, 'number_of_accounts')

            # Initialize XRPL client. Check if client is successfully initialized. Raise exception if client initialization fails
            client = get_xrpl_client()
            if not client:
                raise XRPLException(error_response(ERROR_INITIALIZING_CLIENT))

            transactions = []

            for _ in range(int(create_number_of_accounts)):
                # Generate a new wallet using the faucet. Check if new wallet is successfully created. Raise exception if wallet creation fails
                new_wallet = generate_faucet_wallet(client, debug=True)
                if not new_wallet:
                    raise XRPLException(error_response(ERROR_CREATING_TEST_WALLET))

                # Prepare account data for the request
                account_info = prepare_account_data(new_wallet.address, False)

                # Send the request to the XRPL client
                account_info_response = client.request(account_info)

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

    @api_view(['GET'])
    @retry(wait=wait_exponential(multiplier=RETRY_BACKOFF), stop=stop_after_attempt(MAX_RETRIES))
    def get_account_info(self, account):
        start_time = time.time()  # Capture the start time
        function_name = 'get_wallet_info'
        logger.info(ENTERING_FUNCTION_LOG.format(function_name))

        try:
            # Validate the provided wallet address
            if not account or not validate_xrp_wallet(account):
                raise XRPLRequestFailureException(error_response(INVALID_WALLET_IN_REQUEST))

            # Get an instance of the XRPL client
            client = get_xrpl_client()
            if not client:
                raise XRPLException(error_response(ERROR_INITIALIZING_CLIENT))

            if not does_account_exist(account, client):
                raise XRPLException(error_response(ACCOUNT_DOES_NOT_EXIST_ON_THE_LEDGER.format(account)))

            # Prepare account data for the request
            account_info = prepare_account_data(account, False)

            # Send the request to the XRPL client
            account_info_response = client.request(account_info)

            if validate_xrpl_response_data(account_info_response):
                process_transaction_error(account_info_response)

            # Convert the balance from drops to XRP
            xrp_balance = convert_drops_to_xrp(account_info_response.result['account_data']['Balance'])

            # Retrieve the base reserve and reserve increment
            base_reserve, reserve_increment = get_account_reserves()
            if base_reserve is None or reserve_increment is None:
                raise XRPLException(error_response(FAILED_TO_FETCH_RESERVE_DATA.format(account)))

            logger.info(f"Account found: {account}, Balance: {xrp_balance}, Base Reserve: {base_reserve}, Reserve Increment: {reserve_increment}")

            return create_wallet_info_response(base_reserve, reserve_increment, account_info_response.result)

        except (XRPLRequestFailureException, XRPLException, XRPRangeException) as e:
            # Handle error message
            return handle_error_new(e, status_code=500, function_name=function_name)
        except Exception as e:
            # Handle error message
            return handle_error_new(e, status_code=500, function_name=function_name)
        finally:
            logger.info(LEAVING_FUNCTION_LOG.format(function_name, total_execution_time_in_millis(start_time)))

    @api_view(['GET'])
    @retry(wait=wait_exponential(multiplier=RETRY_BACKOFF), stop=stop_after_attempt(MAX_RETRIES))
    def check_account_balance(self, account):
        start_time = time.time()  # Capture the start time
        function_name = 'check_wallet_balance'
        logger.info(ENTERING_FUNCTION_LOG.format(function_name))

        try:
            # Validate the provided wallet address
            if not account or not validate_xrp_wallet(account):
                raise XRPLException(error_response(INVALID_WALLET_IN_REQUEST))

            # Initialize the XRPL client to query the ledger
            client = get_xrpl_client()
            if not client:
                raise XRPLException(error_response(ERROR_INITIALIZING_CLIENT))

            if not does_account_exist(account, client):
                raise XRPLException(error_response(ACCOUNT_DOES_NOT_EXIST_ON_THE_LEDGER.format(account)))

            # Prepare account data for the request
            account_info = prepare_account_data(account, False)

            # Send the request to the XRPL client
            account_info_response = client.request(account_info)

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

    @api_view(['GET'])
    @retry(wait=wait_exponential(multiplier=RETRY_BACKOFF), stop=stop_after_attempt(MAX_RETRIES))
    def get_account_config(self, account):
        start_time = time.time()  # Capture the start time
        function_name = 'get_account_config'
        logger.info(ENTERING_FUNCTION_LOG.format(function_name))

        try:
            # Validate the provided wallet address
            if not account or not validate_xrp_wallet(account):
                raise XRPLException(error_response(INVALID_WALLET_IN_REQUEST))

            # Initialize the XRPL client
            client = get_xrpl_client()
            if not client:
                raise XRPLException(error_response(ERROR_INITIALIZING_CLIENT))

            if not does_account_exist(account, client):
                raise XRPLException(error_response(ACCOUNT_DOES_NOT_EXIST_ON_THE_LEDGER.format(account)))

            logger.info(f"Getting account config for {account} ")

            # Prepare account data for the request
            account_info = prepare_account_data(account, False)

            # Send the request to the XRPL client
            account_info_response = client.request(account_info)

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

    @api_view(['GET'])
    @retry(wait=wait_exponential(multiplier=RETRY_BACKOFF), stop=stop_after_attempt(MAX_RETRIES))
    def update_account_config(self):
        overall_start_time = time.time()
        function_name = 'update_account_config'
        logger.info(ENTERING_FUNCTION_LOG.format(function_name))

        try:
            # Validate and extract request parameters
            sender_seed = get_request_param(self, 'sender_seed')
            if not is_valid_xrpl_seed(sender_seed):
                raise XRPLException(error_response(SENDER_SEED_IS_INVALID))

            # Initialize XRPL client and wallet
            client = get_xrpl_client()
            if not client:
                raise XRPLException(error_response(ERROR_INITIALIZING_CLIENT))

            sender_wallet = Wallet.from_seed(sender_seed)
            sender_address = sender_wallet.classic_address
            logger.info(f"Processing account config for {sender_address}")

            # Get flags from request (enabled and disabled)
            flags_to_enable, flags_to_disable = get_account_set_flags(self)
            all_flags = flags_to_enable + flags_to_disable
            logger.info(f"Total Flags being processed: {len(all_flags)}")

            # Process each flag and collect the transaction responses.
            tx_responses = process_all_flags(sender_address, client, sender_wallet, flags_to_enable, all_flags)

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
