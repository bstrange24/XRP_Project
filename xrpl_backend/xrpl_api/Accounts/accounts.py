import json
import logging
import time

from django.views import View
from rest_framework.decorators import api_view
from tenacity import wait_exponential, stop_after_attempt, retry
from xrpl.account import does_account_exist
from xrpl.asyncio.clients import XRPLRequestFailureException
from xrpl.core import addresscodec
from xrpl.models import AccountSet, AccountSetAsfFlag
from xrpl.transaction import submit_and_wait
from xrpl.wallet import generate_faucet_wallet, Wallet
from django.apps import apps

from .account_utils import prepare_account_set_disabled_tx, prepare_account_set_enabled_tx
from ..accounts.account_utils import create_multiple_account_response, \
    create_account_response, create_wallet_info_response, get_account_reserves, create_wallet_balance_response, \
    account_set_tx_response, prepare_account_data, prepare_regular_key, delete_account_response, \
    account_config_settings, get_account_set_flags
from ..constants import RETRY_BACKOFF, MAX_RETRIES, ENTERING_FUNCTION_LOG, \
    ERROR_INITIALIZING_CLIENT, LEAVING_FUNCTION_LOG, INVALID_WALLET_IN_REQUEST, asfDisableMaster, \
    ACCOUNT_DOES_NOT_EXIST_ON_THE_LEDGER
from ..db_operations import save_account_data_to_databases
from ..errors.error_handling import handle_error, process_transaction_error
from ..transactions.transactions_util import prepare_tx
from ..utils import get_request_param, get_xrpl_client, convert_drops_to_xrp, \
    total_execution_time_in_millis, validate_xrp_wallet, \
    extract_request_data, is_valid_xrpl_seed

logger = logging.getLogger('xrpl_app')

class Accounts(View):

    @api_view(['POST'])
    @retry(wait=wait_exponential(multiplier=RETRY_BACKOFF), stop=stop_after_attempt(MAX_RETRIES))
    def create_multiple_accounts(self):
        start_time = time.time()  # Capture the start time
        function_name = 'create_multiple_accounts'
        logger.info(ENTERING_FUNCTION_LOG.format(function_name))  # Log entering the function

        try:
            # Extract and validate parameters from the request
            create_number_of_accounts = get_request_param(self, 'number_of_accounts')

            # Initialize XRPL client. Check if client is successfully initialized. Raise exception if client initialization fails
            client = get_xrpl_client()
            if not client:
                raise Exception(ERROR_INITIALIZING_CLIENT)

            transactions = []

            for _ in range(int(create_number_of_accounts)):
                # Generate a new wallet using the faucet. Check if new wallet is successfully created. Raise exception if wallet creation fails
                new_wallet = generate_faucet_wallet(client, debug=True)
                if not new_wallet:
                    raise Exception('Error creating new wallet.')

                # Prepare account data for the request
                account_info = prepare_account_data(new_wallet.address, False)

                # Send the request to the XRPL client
                account_info_response = client.request(account_info)

                # Log debug information about the response
                logger.debug(f"account_info_response:\n{json.dumps(account_info_response.result, indent=4, sort_keys=True)}")
                logger.info(f"account_info_response is_successful: {account_info_response.is_successful()}")

                if not account_info_response or not account_info_response.is_successful():
                    process_transaction_error(account_info_response)

                # Log the classic address and X-address
                logger.debug(f"Classic address: {new_wallet.address}")
                logger.debug(
                    f"X-address: {addresscodec.classic_address_to_xaddress(new_wallet.address, tag=12345, is_test_network=True)}")

                # Convert balance from drops to XRP
                xrp_balance = convert_drops_to_xrp(account_info_response.result['account_data']['Balance'])
                if not xrp_balance:
                    raise ValueError("Invalid XRP balance")

                # Save account data to databases
                save_account_data_to_databases(account_info_response.result, str(xrp_balance))

                # Accessing the result from the response
                account_info_data = account_info_response.result  # This will give you a dictionary

                # Now you can modify the 'seed'
                account_info_data['account_data']['seed'] = new_wallet.seed
                account_info_data['account_data']['private_key'] = new_wallet.private_key
                account_info_data['account_data']['public_key'] = new_wallet.public_key

                transactions.append(account_info_data)

            logger.debug(f"Wallets created: {transactions}")

            return create_multiple_account_response(transactions)
        except Exception as e:
            # Catch any exceptions that occur during the process. Handle error and return response
            return handle_error({'status': 'failure', 'message': f"{str(e)}"}, status_code=500,
                                function_name=function_name)
        finally:
            # Log leaving the function regardless of success or failure
            logger.info(LEAVING_FUNCTION_LOG.format(function_name, total_execution_time_in_millis(start_time)))


    @api_view(['GET'])
    @retry(wait=wait_exponential(multiplier=RETRY_BACKOFF), stop=stop_after_attempt(MAX_RETRIES))
    def create_account(self):
        start_time = time.time()  # Capture the start time
        function_name = 'create_account'
        logger.info(ENTERING_FUNCTION_LOG.format(function_name))  # Log entering the function

        try:
            # Initialize XRPL client. Check if client is successfully initialized. Raise exception if client initialization fails
            client = get_xrpl_client()
            if not client:
                raise Exception(ERROR_INITIALIZING_CLIENT)

            # Generate a new wallet using the faucet. Check if new wallet is successfully created. Raise exception if wallet creation fails
            new_wallet = generate_faucet_wallet(client, debug=True)
            if not new_wallet:
                raise Exception('Error creating new wallet.')

            # Prepare account data for the request
            account_info = prepare_account_data(new_wallet.address, False)

            # Send the request to the XRPL client
            account_info_response = client.request(account_info)

            # Log debug information about the response
            logger.debug(f"account_info_response:\n{json.dumps(account_info_response.result, indent=4, sort_keys=True)}")
            logger.info(f"account_info_response is_successful: {account_info_response.is_successful()}")

            if not account_info_response or not account_info_response.is_successful():
                process_transaction_error(account_info_response)

            # Log the classic address and X-address
            logger.debug(f"Classic address: {new_wallet.address}")
            logger.debug(
                f"X-address: {addresscodec.classic_address_to_xaddress(new_wallet.address, tag=12345, is_test_network=True)}")

            # Convert balance from drops to XRP
            xrp_balance = convert_drops_to_xrp(account_info_response.result['account_data']['Balance'])
            if not xrp_balance:
                raise ValueError("Invalid XRP balance")

            # Save account data to databases
            save_account_data_to_databases(account_info_response.result, str(xrp_balance))

            # Return response with account information
            return create_account_response(new_wallet.address, new_wallet.seed, xrp_balance,
                                           account_info_response.result)
        except Exception as e:
            # Catch any exceptions that occur during the process. Handle error and return response
            return handle_error({'status': 'failure', 'message': f"{str(e)}"}, status_code=500,
                                function_name=function_name)
        finally:
            # Log leaving the function regardless of success or failure
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
                raise Exception(INVALID_WALLET_IN_REQUEST)

            # Get an instance of the XRPL client
            client = get_xrpl_client()
            if not client:
                # Raise an exception if client initialization fails
                raise Exception(ERROR_INITIALIZING_CLIENT)

            if not does_account_exist(account, client):
                raise XRPLRequestFailureException(
                    {'status': 'failure', 'error_message': ACCOUNT_DOES_NOT_EXIST_ON_THE_LEDGER})

            # Prepare account data for the request
            account_info = prepare_account_data(account, False)

            # Send the request to the XRPL client
            account_info_response = client.request(account_info)

            # Log debug information about the response
            logger.debug(
                f"account_info_response:\n{json.dumps(account_info_response.result, indent=4, sort_keys=True)}")
            logger.info(f"account_info_response is_successful: {account_info_response.is_successful()}")

            if not account_info_response or not account_info_response.is_successful():
                process_transaction_error(account_info_response)

            # Convert the balance from drops to XRP
            balance = convert_drops_to_xrp(account_info_response.result['account_data']['Balance'])

            # Retrieve the base reserve and reserve increment
            base_reserve, reserve_increment = get_account_reserves()
            if base_reserve is None or reserve_increment is None:
                # Raise an exception if reserve data retrieval fails
                raise Exception('Failed to fetch reserve data.')

            logger.info(
                f"Account found: {account}, Balance: {balance}, Base Reserve: {base_reserve}, Reserve Increment: {reserve_increment}")

            # Return a JSON response with the wallet information
            return create_wallet_info_response(base_reserve, reserve_increment, account_info_response.result)

        except Exception as e:
            # Catch any exceptions that occur during the process
            return handle_error({'status': 'failure', 'message': f"{str(e)}"}, status_code=500,
                                function_name=function_name)
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
                raise Exception(INVALID_WALLET_IN_REQUEST)

            # Initialize the XRPL client to query the ledger
            client = get_xrpl_client()
            if not client:
                raise Exception(ERROR_INITIALIZING_CLIENT)

            if not does_account_exist(account, client):
                raise XRPLRequestFailureException({'status': 'failure', 'error_message': ACCOUNT_DOES_NOT_EXIST_ON_THE_LEDGER})

            # Prepare account data for the request
            account_info = prepare_account_data(account, False)

            # Send the request to the XRPL client
            account_info_response = client.request(account_info)

            # Log debug information about the response
            logger.debug(
                f"account_info_response:\n{json.dumps(account_info_response.result, indent=4, sort_keys=True)}")
            logger.info(f"account_info_response is_successful: {account_info_response.is_successful()}")

            if not account_info_response or not account_info_response.is_successful():
                process_transaction_error(account_info_response)

            # Convert the balance from drops to XRP
            balance_in_xrp = convert_drops_to_xrp(account_info_response.result['account_data']['Balance'])

            # Log the successful balance check
            logger.info(f"Balance for address {account} retrieved successfully: {balance_in_xrp} XRP")

            # Return a JSON response with the wallet information
            return create_wallet_balance_response(balance_in_xrp, account_info_response.result)
        except Exception as e:
            # Catch any exceptions that occur during the process
            return handle_error({'status': 'failure', 'message': f"{str(e)}"}, status_code=500, function_name=function_name)
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
                raise Exception(INVALID_WALLET_IN_REQUEST)

            # Initialize the XRPL client
            client = get_xrpl_client()
            if not client:
                raise Exception(ERROR_INITIALIZING_CLIENT)

            if not does_account_exist(account, client):
                raise XRPLRequestFailureException({'status': 'failure', 'error_message': ACCOUNT_DOES_NOT_EXIST_ON_THE_LEDGER})

            # Prepare account data for the request
            account_info = prepare_account_data(account, False)

            # Send the request to the XRPL client
            account_info_response = client.request(account_info)

            # Log debug information about the response
            logger.debug(f"account_info_response:\n{json.dumps(account_info_response.result, indent=4, sort_keys=True)}")
            logger.info(f"account_info_response is_successful: {account_info_response.is_successful()}")

            if not account_info_response or not account_info_response.is_successful():
                process_transaction_error(account_info_response)

            return account_config_settings(account_info_response.result)

        except Exception as e:
            # Handle exceptions like XRPL-specific errors, network issues, or unexpected errors
            return handle_error({'status': 'failure', 'message': f"{str(e)}"}, status_code=500,
                                function_name=function_name)
        finally:
            logger.info(LEAVING_FUNCTION_LOG.format(function_name, total_execution_time_in_millis(start_time)))


    @api_view(['GET'])
    @retry(wait=wait_exponential(multiplier=RETRY_BACKOFF), stop=stop_after_attempt(MAX_RETRIES))
    def config_account(self):
        start_time = time.time()  # Capture the start time
        function_name = 'config_account'
        logger.info(ENTERING_FUNCTION_LOG.format(function_name))

        try:
            # Extract and validate parameters from the request
            sender_seed = get_request_param(self, 'sender_seed')
            if not is_valid_xrpl_seed(sender_seed):
                raise ValueError('Sender seed is invalid.')

            # Initialize the XRPL client
            client = get_xrpl_client()
            if not client:
                raise Exception(ERROR_INITIALIZING_CLIENT)

            # Create a wallet from the seed to get the sender's address
            sender_wallet = Wallet.from_seed(sender_seed)
            sender_address = sender_wallet.classic_address

            # Build flags for the AccountSet transaction based on the provided settings
            flags_to_enable, flags_to_disable = get_account_set_flags(self)
            all_flags = flags_to_enable + flags_to_disable
            logger.info(f"Total Flags being processed: {len(all_flags)}")

            counter = 1

            for flags in all_flags:
                start_time = time.time()  # Capture the start time
                logger.info(f"Processing: {counter} flag")
                if flags in flags_to_enable:
                    # Prepare the AccountSet enabled transaction
                    account_set_tx = prepare_account_set_enabled_tx(sender_address, flags)
                else:
                    # Prepare the AccountSet disable transaction
                    account_set_tx = prepare_account_set_disabled_tx(sender_address, flags)

                # Submit and wait for the transaction to be included in a ledger
                response = submit_and_wait(account_set_tx, client, sender_wallet)

                # Log the raw response for detailed debugging
                logger.debug(f"account_set_tx submit_and_wait:\n{json.dumps(response.result, indent=4, sort_keys=True)}")

                logger.info(f"response.is_successful(): {response.is_successful()}")
                if not response or not response.is_successful() and response.result['meta']['TransactionResult'] == 'tesSUCCESS':
                    process_transaction_error(response)

                # Create a Transaction request to see transaction
                response_result = response.result
                tx_response = client.request(prepare_tx(response_result["hash"]))

                # Log the raw response for detailed debugging
                logger.debug(f"tx_response:\n{json.dumps(tx_response.result, indent=4, sort_keys=True)}")

                logger.info(f"TransactionResult: {response_result["meta"]["TransactionResult"]} TransactionHash: {response_result["hash"]}")

                if response_result["meta"]["TransactionResult"] != 'tesSUCCESS':
                    process_transaction_error(tx_response)

                logger.info(f"Total time for loop: {counter} in ms: {total_execution_time_in_millis(start_time)}")
                counter += 1

            return account_set_tx_response(response_result, sender_address)

        except Exception as e:
            # Handle exceptions like XRPL-specific errors, network issues, or unexpected errors
            return handle_error({'status': 'failure', 'message': f"{str(e)}"}, status_code=500, function_name=function_name)
        finally:
            logger.info(LEAVING_FUNCTION_LOG.format(function_name, total_execution_time_in_millis(start_time)))


    @api_view(['DELETE'])
    @retry(wait=wait_exponential(multiplier=RETRY_BACKOFF), stop=stop_after_attempt(MAX_RETRIES))
    def black_hole_xrp(self, account):
        start_time = time.time()  # Capture the start time
        function_name = 'black_hole_xrp'
        logger.info(ENTERING_FUNCTION_LOG.format(function_name))  # Log entering function

        try:
            # Validate the provided wallet address.
            if not account or not validate_xrp_wallet(account):
                raise Exception(INVALID_WALLET_IN_REQUEST)

            # Extract the sender's seed from the request.
            sender_seed, _, _ = extract_request_data(self)
            if not is_valid_xrpl_seed(sender_seed):
                raise ValueError('Sender seed is invalid.')

            # Initialize the XRPL client for further operations.
            client = get_xrpl_client()
            if not client:
                raise ConnectionError(ERROR_INITIALIZING_CLIENT)

            if not does_account_exist(account, client):
                raise XRPLRequestFailureException({'status': 'failure', 'error_message': ACCOUNT_DOES_NOT_EXIST_ON_THE_LEDGER})

            # Prepare and send request to get the account info from the ledger.
            account_info_request = prepare_account_data(account, True)
            account_info_response = client.request(account_info_request)

            logger.debug(f"account_info_response:\n{json.dumps(account_info_response.result, indent=4, sort_keys=True)}")
            logger.info(f"account_info_response is_successful(): {account_info_response.is_successful()} Validated: {account_info_response.result["validated"]}")

            # Get black hole address from the environment configuration.s
            xrpl_config = apps.get_app_config('xrpl_api')

            # Prepare a transaction to set the account's regular key to the black hole address.
            tx_regular_key = prepare_regular_key(account, xrpl_config.BLACK_HOLE_ADDRESS)

            # Get wallet from the sender's seed and submit the SetRegularKey transaction.
            wallet = Wallet.from_seed(sender_seed)
            submit_tx_regular = submit_and_wait(transaction=tx_regular_key, client=client, wallet=wallet)

            logger.debug(f"submit_tx_regular submit_and_wait:\n{json.dumps(submit_tx_regular.result, indent=4, sort_keys=True)}")
            logger.info(f"submit_tx_regular is_successful(): {submit_tx_regular.is_successful()} Validated: {submit_tx_regular.result["validated"]}")
            logger.info(f"TransactionResult: {submit_tx_regular.result["meta"]["TransactionResult"]} submit_tx_regular: {submit_tx_regular.result["hash"]}")

            if not submit_tx_regular or not submit_tx_regular.is_successful() or submit_tx_regular.result["meta"]["TransactionResult"] != 'tesSUCCESS':
                process_transaction_error(submit_tx_regular)

            tx_response = client.request(prepare_tx(submit_tx_regular.result["hash"]))

            logger.debug(f"tx_response:\n{json.dumps(tx_response.result, indent=4, sort_keys=True)}")
            logger.info(f"tx_response is_successful(): {tx_response.is_successful()} Validated: {tx_response.result["validated"]}")
            logger.info(f"TransactionResult: {tx_response.result["meta"]["TransactionResult"]} tx_response: {tx_response.result["hash"]}")

            if not tx_response.result["validated"]:
                process_transaction_error(tx_response)

            # Prepare a transaction to disable the master key on the account.
            tx_disable_master_key = AccountSet(
                account=account,
                set_flag=AccountSetAsfFlag.ASF_DISABLE_MASTER
            )
            submit_tx_disable = submit_and_wait(transaction=tx_disable_master_key, client=client, wallet=wallet)

            logger.debug(f"submit_tx_disable submit_and_wait:\n{json.dumps(submit_tx_disable.result, indent=4, sort_keys=True)}")
            logger.info(f"submit_tx_disable is_successful(): {submit_tx_disable.is_successful()} Validated: {submit_tx_disable.result["validated"]}")
            logger.info(f"TransactionResult: {submit_tx_disable.result["meta"]["TransactionResult"]} submit_tx_disable: {submit_tx_disable.result["hash"]}")

            if not submit_tx_disable or not submit_tx_disable.is_successful() or submit_tx_disable.result["meta"]["TransactionResult"] != 'tesSUCCESS':
                process_transaction_error(submit_tx_disable)

            tx_response = client.request(prepare_tx(submit_tx_disable.result["hash"]))

            logger.debug(f"tx_response\n{json.dumps(tx_response.result, indent=4, sort_keys=True)}")
            logger.info(f"tx_response is_successful(): {tx_response.is_successful()} Validated: {tx_response.result["validated"]}")
            logger.info(f"TransactionResult: {tx_response.result["meta"]["TransactionResult"]} tx_response: {tx_response.result["hash"]}")

            if not tx_response.result["validated"] or tx_response.result["meta"]["TransactionResult"] != 'tesSUCCESS':
                process_transaction_error(tx_response)

            # Prepare a request to check the account's flags after the transaction.
            get_acc_flag = prepare_account_data(account, True)
            response = client.request(get_acc_flag)

            # Verify if the master key has been successfully disabled.
            if response.result['account_data']['Flags'] & asfDisableMaster:
                logger.info(f"Account {account}'s master key has been disabled, account is black holed.")
            else:
                logger.info(f"Account {account}'s master key is still enabled, account is NOT black holed")

            # Return the response indicating the account status after the operation.
            return delete_account_response(response)

        except Exception as e:
            # Handle exceptions (e.g., XRPL errors, connection issues) and return an error response.
            return handle_error({'status': 'failure', 'message': f"{str(e)}"}, status_code=500, function_name=function_name)
        finally:
            # Log when the function exits.
            logger.info(LEAVING_FUNCTION_LOG.format(function_name, total_execution_time_in_millis(start_time)))
