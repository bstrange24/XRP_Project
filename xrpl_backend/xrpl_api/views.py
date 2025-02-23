# import json
# import logging
# import time
# from decimal import Decimal
#
# import xrpl
# from django.core.cache import cache
# from django.core.paginator import Paginator
# from django.db import transaction
# from django.http import JsonResponse
# from django.utilities.decorators import sync_and_async_middleware, method_decorator
# from django.views import View
# from django.views.decorators.csrf import csrf_exempt
# from rest_framework.decorators import api_view
# from rest_framework.pagination import PageNumberPagination
# from tenacity import retry, wait_exponential, stop_after_attempt
# from xrpl import XRPLException
# from django.apps import apps
# from xrpl.asyncio.clients import AsyncWebsocketClient
# from xrpl.asyncio.transaction import autofill_and_sign, submit_and_wait
#
# from xrpl.core import addresscodec
# from xrpl.models import AccountLines, ServerInfo, AccountSetAsfFlag, AccountSet, BookOffers, XRP, OfferCreate, \
#     AccountOffers, Fee
# from xrpl.models.requests import Ledger
# from xrpl.transaction import submit_and_wait, submit
# from xrpl.utilities import xrp_to_drops, drops_to_xrp, get_balance_changes
# from xrpl.wallet import Wallet
# from xrpl.wallet import generate_faucet_wallet
#
# from .accounts.account_utils import get_account_reserves, get_account_details, account_set_tx_response, \
#     create_multiple_account_response, create_account_response, create_wallet_info_response, \
#     create_wallet_balance_response, prepare_account_set_tx, prepare_account_tx, prepare_account_tx_with_pagination, \
#     account_tx_with_pagination_response, prepare_account_data, delete_account_response, \
#     create_account_delete_transaction, account_delete_tx_response, account_reserves_response, check_check_entries, \
#     prepare_regular_key, prepare_account_offers, create_account_offers_response, prepare_account_lines, \
#     create_account_lines_response
# from .constants import ERROR_INITIALIZING_CLIENT, RETRY_BACKOFF, MAX_RETRIES, PAGINATION_PAGE_SIZE, \
#     CACHE_TIMEOUT_FOR_WALLET, CACHE_TIMEOUT, CACHE_TIMEOUT_FOR_SERVER_INFO, \
#     XRPL_RESPONSE, ERROR_IN_XRPL_RESPONSE, INVALID_WALLET_IN_REQUEST, ACCOUNT_IS_REQUIRED, \
#     ERROR_FETCHING_TRANSACTION_HISTORY, INVALID_TRANSACTION_HASH, ERROR_FETCHING_TRANSACTION_STATUS, \
#     ERROR_INITIALIZING_SERVER_INFO, PAYMENT_IS_UNSUCCESSFUL, ERROR_GETTING_ACCOUNT_INFO, ENTERING_FUNCTION_LOG, \
#     LEAVING_FUNCTION_LOG, asfDisableMaster, ERROR_FETCHING_ACCOUNT_OFFERS, ERROR_FETCHING_XRP_RESERVES, \
#     RESERVES_NOT_FOUND, MISSING_REQUEST_PARAMETERS
# from .currency.currency_util import create_issued_currency_the_user_wants, create_amount_the_user_wants_to_spend
#
# from .db_operations import save_account_data_to_databases
# from .escrows.escrows_util import check_escrow_entries
# from .payments.payments_util import create_payment_transaction, process_payment_response, check_pay_channel_entries
# from .ledger.ledger_util import ledger_info_response, check_account_ledger_entries, check_ripple_state_entries, \
#     calculate_last_ledger_sequence
# from .transactions.transactions_util import prepare_tx, transaction_status_response, transaction_history_response
# from .trust_lines.trust_line_util import trust_line_response, create_trust_set_transaction, create_trust_set_response
# from .utilities import get_xrpl_client, handle_error, \
#     build_flags, is_valid_xrpl_seed, get_request_param, validate_xrp_wallet, is_valid_transaction_hash, \
#     get_cached_data, parse_boolean_param, extract_request_data, \
#     validate_request_data, fetch_network_fee, convert_drops_to_xrp, \
#     validate_xrpl_response, total_execution_time_in_millis
#
# logger = logging.getLogger('xrpl_app')


# class AccountInfoPagination(PageNumberPagination):
#     page_size = PAGINATION_PAGE_SIZE


# @api_view(['POST'])
# @retry(wait=wait_exponential(multiplier=RETRY_BACKOFF), stop=stop_after_attempt(MAX_RETRIES))
# def create_multiple_accounts(request):
#     """
#     This function handles the creation of multiple XRPL accounts. It performs the following steps:
#
#     1. Extracts and validates the number of accounts to be created from the request parameters.
#     2. Initializes an XRPL client and checks if the initialization is successful.
#     3. Iterates over the required number of accounts:
#        - Generates a new wallet using the faucet.
#        - Retrieves account details for the newly created wallet.
#        - Logs account information (classic and X-address).
#        - Converts the account balance from drops to XRP.
#        - Saves account details to the database.
#     4. Returns a response with the created account details.
#
#     Error handling is implemented to catch and log exceptions, ensuring a proper response is returned.
#     Logging is used to track function entry, exit, and key processing steps.
#     """
#     start_time = time.time()  # Capture the start time
#     function_name = 'create_multiple_accounts'
#     logger.info(ENTERING_FUNCTION_LOG.format(function_name))  # Log entering the function
#
#     try:
#         # Extract and validate parameters from the request
#         create_number_of_accounts = get_request_param(request, 'number_of_accounts')
#
#         # Initialize XRPL client. Check if client is successfully initialized. Raise exception if client initialization fails
#         client = get_xrpl_client()
#         if not client:
#             raise XRPLException(ERROR_INITIALIZING_CLIENT)
#
#         transactions = []
#
#         for i in range(int(create_number_of_accounts)):
#             # Generate a new wallet using the faucet. Check if new wallet is successfully created. Raise exception if wallet creation fails
#             new_wallet = generate_faucet_wallet(client, debug=True)
#             if not new_wallet:
#                 raise XRPLException('Error creating new wallet.')
#
#             # Retrieve account details. Check if account details are successfully retrieved. Raise exception if details retrieval fails
#             account_details = get_account_details(client, new_wallet.address)
#             if not account_details:
#                 raise XRPLException('Error retrieving account details.')
#
#             # Log the classic address and X-address
#             logger.debug(f"Classic address: {new_wallet.address}")
#             logger.debug(
#                 f"X-address: {addresscodec.classic_address_to_xaddress(new_wallet.address, tag=12345, is_test_network=True)}")
#
#             # Convert balance from drops to XRP
#             xrp_balance = convert_drops_to_xrp(account_details['result']['account_data']['Balance'])
#             if not xrp_balance:
#                 raise ValueError("Invalid XRP balance")
#
#             # Save account data to databases
#             save_account_data_to_databases(account_details, str(xrp_balance))
#
#             account_details['result']['account_data']['seed'] = new_wallet.seed
#             account_details['result']['account_data']['private_key'] = new_wallet.private_key
#             account_details['result']['account_data']['public_key'] = new_wallet.public_key
#
#             transactions.append(account_details['result']['account_data'])
#
#         logger.debug(f"Wallets created: {transactions}")
#
#         return create_multiple_account_response(transactions)
#     except Exception as e:
#         # Catch any exceptions that occur during the process. Handle error and return response
#         return handle_error({'status': 'failure', 'message': f"{str(e)}"}, status_code=500, function_name=function_name)
#     finally:
#         # Log leaving the function regardless of success or failure
#         logger.info(LEAVING_FUNCTION_LOG.format(function_name, total_execution_time_in_millis(start_time)))
#
#
# @api_view(['GET'])
# @retry(wait=wait_exponential(multiplier=RETRY_BACKOFF), stop=stop_after_attempt(MAX_RETRIES))
# def create_account(request):
#     """
#     API endpoint to create a new account.
#
#     This function initializes an XRPL client, generates a new wallet using the faucet, retrieves account details,
#     converts the balance to XRP, saves the account data to databases, and returns a response with account information.
#
#     Args:
#         request (Request): The HTTP request object.
#
#     Steps:
#        1. Initialize the XRPL client.
#        2. Generate a new wallet using the XRPL faucet.
#        3. Retrieve the newly created account's details.
#        4. Log the classic address and corresponding X-address.
#        5. Convert balance from drops to XRP.
#        6. Save the account data to the database.
#        7. Return the account information in the response.
#
#     Returns:
#         Response: JSON response containing either the created account details or error information.
#     """
#     start_time = time.time()  # Capture the start time
#     function_name = 'create_account'
#     logger.info(ENTERING_FUNCTION_LOG.format(function_name))  # Log entering the function
#
#     try:
#         # Initialize XRPL client. Check if client is successfully initialized. Raise exception if client initialization fails
#         client = get_xrpl_client()
#         if not client:
#             raise XRPLException(ERROR_INITIALIZING_CLIENT)
#
#         # Generate a new wallet using the faucet. Check if new wallet is successfully created. Raise exception if wallet creation fails
#         new_wallet = generate_faucet_wallet(client, debug=True)
#         if not new_wallet:
#             raise XRPLException('Error creating new wallet.')
#
#         # Retrieve account details. Check if account details are successfully retrieved. Raise exception if details retrieval fails
#         account_details = get_account_details(client, new_wallet.address)
#         if not account_details:
#             raise XRPLException('Error retrieving account details.')
#
#         # Log the classic address and X-address
#         logger.debug(f"Classic address: {new_wallet.address}")
#         logger.debug(
#             f"X-address: {addresscodec.classic_address_to_xaddress(new_wallet.address, tag=12345, is_test_network=True)}")
#
#         # Convert balance from drops to XRP
#         xrp_balance = convert_drops_to_xrp(account_details['result']['account_data']['Balance'])
#         if not xrp_balance:
#             raise ValueError("Invalid XRP balance")
#
#         # Save account data to databases
#         save_account_data_to_databases(account_details, str(xrp_balance))
#
#         # Return response with account information
#         return create_account_response(new_wallet.address, new_wallet.seed, xrp_balance, account_details)
#     except Exception as e:
#         # Catch any exceptions that occur during the process. Handle error and return response
#         return handle_error({'status': 'failure', 'message': f"{str(e)}"}, status_code=500, function_name=function_name)
#
#     finally:
#         # Log leaving the function regardless of success or failure
#         logger.info(LEAVING_FUNCTION_LOG.format(function_name, total_execution_time_in_millis(start_time)))


# @api_view(['GET'])
# @retry(wait=wait_exponential(multiplier=RETRY_BACKOFF), stop=stop_after_attempt(MAX_RETRIES))
# def get_account_info(request, wallet_address):
#     """
#         Retrieves detailed information about a given XRP wallet.
#
#         Steps:
#         1. Validate the provided wallet address.
#         2. Check if the wallet information is cached to optimize performance.
#         3. If not cached, initialize an XRPL client.
#         4. Retrieve account details from XRPL.
#         5. Extract account balance and convert from drops to XRP.
#         6. Fetch the base reserve and reserve increment for the wallet.
#         7. Cache the wallet data to improve response time for future requests.
#         8. Return the wallet information as a JSON response.
#
#         If an error occurs at any step, an appropriate error response is returned.
#         """
#     start_time = time.time()  # Capture the start time
#     function_name = 'get_wallet_info'
#     logger.info(ENTERING_FUNCTION_LOG.format(function_name))
#
#     # Validate the provided wallet address
#     if not wallet_address or not validate_xrp_wallet(wallet_address):
#         raise XRPLException(INVALID_WALLET_IN_REQUEST)
#
#     # Create a unique cache key for this wallet. Check if data is already cached
#     cache_key = f"get_wallet_info:{wallet_address}"
#     cached_data = get_cached_data(cache_key, wallet_address, function_name)
#     if cached_data:
#         # Return cached data if available
#         return JsonResponse(cached_data)
#
#     try:
#         # Get an instance of the XRPL client
#         client = get_xrpl_client()
#         if not client:
#             # Raise an exception if client initialization fails
#             raise XRPLException(ERROR_INITIALIZING_CLIENT)
#
#         # Fetch account details from the XRPL
#         account_details = get_account_details(client, wallet_address)
#         if not account_details:
#             # Raise an exception if fetching account details fails
#             raise XRPLException(ERROR_GETTING_ACCOUNT_INFO)
#
#         # Extract the actual account data from the response
#         account_data = account_details['result']['account_data']
#
#         # Convert the balance from drops to XRP
#         balance = convert_drops_to_xrp(account_data['Balance'])
#
#         # Retrieve the base reserve and reserve increment
#         base_reserve, reserve_increment = get_account_reserves()
#         if base_reserve is None or reserve_increment is None:
#             # Raise an exception if reserve data retrieval fails
#             raise XRPLException('Failed to fetch reserve data.')
#
#         logger.info(
#             f"Account found: {wallet_address}, Balance: {balance}, Base Reserve: {base_reserve}, Reserve Increment: {reserve_increment}")  # Log the fetched information
#
#         # Cache the response to speed up future requests for this wallet
#         # Store the account data in the cache
#         cache.set(cache_key, account_data, CACHE_TIMEOUT_FOR_WALLET)
#
#         # Return a JSON response with the wallet information
#         return create_wallet_info_response(base_reserve, reserve_increment, account_details)
#
#     except (xrpl.XRPLException, Exception) as e:
#         # Catch any exceptions that occur during the process
#         return handle_error({'status': 'failure', 'message': f"{str(e)}"}, status_code=500, function_name=function_name)
#
#     finally:
#         logger.info(LEAVING_FUNCTION_LOG.format(function_name, total_execution_time_in_millis(start_time)))


# @api_view(['GET'])
# @retry(wait=wait_exponential(multiplier=RETRY_BACKOFF), stop=stop_after_attempt(MAX_RETRIES))
# def check_account_balance(request, wallet_address):
#     """
#     Checks the XRP balance of a given wallet address.
#
#     Steps:
#     1. Validate the provided wallet address.
#     2. Check if the balance information is cached to reduce network load.
#     3. If not cached, initialize an XRPL client to query the ledger.
#     4. Retrieve account details from XRPL and extract the balance.
#     5. Convert the balance from drops to XRP for better readability.
#     6. Cache the balance data to optimize future requests.
#     7. Return the balance information in a JSON response.
#
#     If an error occurs at any step, an appropriate error response is returned.
#     """
#     start_time = time.time()  # Capture the start time
#     function_name = 'check_wallet_balance'
#     logger.info(ENTERING_FUNCTION_LOG.format(function_name))
#
#     # Validate the provided wallet address
#     if not wallet_address or not validate_xrp_wallet(wallet_address):
#         raise XRPLException(INVALID_WALLET_IN_REQUEST)
#
#     # Check if the balance information is already cached
#     cache_key = f"check_wallet_balance:{wallet_address}"
#     cached_data = get_cached_data(cache_key, wallet_address, function_name)
#     if cached_data:
#         # Return cached data if available
#         return JsonResponse(cached_data)
#
#     try:
#         # Initialize the XRPL client to query the ledger
#         client = get_xrpl_client()
#         if not client:
#             raise XRPLException(ERROR_INITIALIZING_CLIENT)
#
#         # Fetch account details from the XRPL
#         account_details = get_account_details(client, wallet_address)
#         if not account_details:
#             # Raise an exception if fetching account details fails
#             raise XRPLException(ERROR_GETTING_ACCOUNT_INFO)
#
#         # Convert the balance from drops to XRP
#         balance_in_xrp = convert_drops_to_xrp(account_details['result']["account_data"]["Balance"])
#
#         # Log the successful balance check
#         logger.info(f"Balance for address {wallet_address} retrieved successfully: {balance_in_xrp} XRP")
#
#         # Cache the balance for future queries to reduce network load
#         cache.set(cache_key, account_details, CACHE_TIMEOUT)
#
#         # Return a JSON response with the wallet information
#         return create_wallet_balance_response(balance_in_xrp)
#
#     except (xrpl.XRPLException, Exception) as e:
#         # Catch any exceptions that occur during the process
#         # Handle error and return a JSON response with an error message
#         return handle_error({'status': 'failure', 'message': f"{str(e)}"}, status_code=500, function_name=function_name)
#     finally:
#         logger.info(LEAVING_FUNCTION_LOG.format(function_name, total_execution_time_in_millis(start_time)))
#
#
# @api_view(['GET'])
# @retry(wait=wait_exponential(multiplier=RETRY_BACKOFF), stop=stop_after_attempt(MAX_RETRIES))
# def config_account(request):
#     """
#     Handles an AccountSet transaction on the XRPL (XRP Ledger).
#
#     Steps:
#     1. Extract and validate request parameters, including sender's seed and account settings.
#     2. Parse boolean parameters for account settings (require destination tag, disable master key, enable regular key).
#     3. Generate the sender's wallet address from the provided seed.
#     4. Construct transaction flags based on the requested settings.
#     5. Prepare an AccountSet transaction using the provided account settings.
#     6. Initialize the XRPL client and verify a successful connection.
#     7. Submit the transaction and wait for it to be processed.
#     8. Log and handle the transaction response.
#     9. Return a JSON response containing the transaction details.
#
#     If an error occurs at any step, an appropriate error response is returned.
#     """
#     start_time = time.time()  # Capture the start time
#     function_name = 'account_set'
#     logger.info(ENTERING_FUNCTION_LOG.format(function_name))
#
#     try:
#         # Extract and validate parameters from the request
#         sender_seed = get_request_param(request, 'sender_seed')
#
#         # Parse boolean parameters for account settings
#         require_destination_tag = parse_boolean_param(request, 'require_destination_tag')
#         disable_master_key = parse_boolean_param(request, 'disable_master_key')
#         enable_regular_key = parse_boolean_param(request, 'enable_regular_key')
#
#         # Log the settings for debugging or monitoring
#         logger.info(
#             f"require_destination_tag: {require_destination_tag}, disable_master_key: {disable_master_key}, enable_regular_key: {enable_regular_key}")
#
#         # Create a wallet from the seed to get the sender's address
#         sender_wallet = Wallet.from_seed(sender_seed)
#         sender_address = sender_wallet.classic_address
#
#         # Build flags for the AccountSet transaction based on the provided settings
#         flags = build_flags(require_destination_tag, disable_master_key, enable_regular_key)
#
#         # Prepare the AccountSet transaction
#         account_set_tx = prepare_account_set_tx(sender_address, flags)
#
#         # Initialize the XRPL client
#         client = get_xrpl_client()
#         if not client:
#             raise XRPLException(ERROR_INITIALIZING_CLIENT)
#
#         # Submit and wait for the transaction to be included in a ledger
#         response = submit_and_wait(account_set_tx, client, sender_wallet)
#         if not response or not response.is_successful():
#             raise XRPLException('Error submit_and_wait return none.')
#
#         # Log the raw response for detailed debugging
#         logger.debug(XRPL_RESPONSE)
#         logger.debug(json.dumps(response.result, indent=4, sort_keys=True))
#
#         # Handle the transaction response
#         return account_set_tx_response(response, sender_address)
#
#     except (xrpl.XRPLException, Exception) as e:
#         # Handle exceptions like XRPL-specific errors, network issues, or unexpected errors
#         return handle_error({'status': 'failure', 'message': f"{str(e)}"}, status_code=500, function_name=function_name)
#     finally:
#         logger.info(LEAVING_FUNCTION_LOG.format(function_name, total_execution_time_in_millis(start_time)))


# @api_view(['GET'])
# @retry(wait=wait_exponential(multiplier=RETRY_BACKOFF), stop=stop_after_attempt(MAX_RETRIES))
# def get_transaction_history(request, wallet_address, previous_transaction_id):
#     """
#     Retrieves the transaction history for a given XRP wallet address and searches for a specific transaction.
#
#     Steps:
#     1. Validate the provided wallet address to ensure it is correctly formatted.
#     2. Validate the transaction hash format to confirm it follows the expected structure.
#     3. Initialize the XRPL client to communicate with the XRP Ledger.
#     4. Prepare an AccountTx request to fetch past transactions related to the wallet.
#     5. Send the request to XRPL and retrieve transaction history.
#     6. Validate the response and check for transactions in the result.
#     7. Iterate through the transactions to find a match with the given transaction hash.
#     8. If a matching transaction is found, return its details.
#     9. If no matching transaction is found or an error occurs, return an appropriate error response.
#
#     If any step fails, an error is logged, and an error response is returned.
#     """
#     start_time = time.time()  # Capture the start time
#     function_name = 'get_transaction_history'
#     logger.info(ENTERING_FUNCTION_LOG.format(function_name))
#
#     try:
#         # Validate the provided wallet address
#         if not wallet_address or not validate_xrp_wallet(wallet_address):
#             raise XRPLException(INVALID_WALLET_IN_REQUEST)
#
#         # Validate the format of the transaction hash
#         if not is_valid_transaction_hash(previous_transaction_id):
#             raise XRPLException(INVALID_TRANSACTION_HASH)
#
#         # Initialize the XRPL client for querying the ledger
#         client = get_xrpl_client()
#         if not client:
#             raise XRPLException(ERROR_INITIALIZING_CLIENT)
#
#         # Prepare an AccountTx request to fetch transactions for the given account
#         account_tx_request = prepare_account_tx(wallet_address)
#
#         # Send the request to XRPL to get transaction history
#         response = client.request(account_tx_request)
#         is_valid, response = validate_xrpl_response(response, required_keys=["validated"])
#         if not is_valid:
#             raise XRPLException(ERROR_FETCHING_TRANSACTION_STATUS)
#
#         # Log the raw response for detailed debugging
#         logger.debug(XRPL_RESPONSE)
#         logger.debug(json.dumps(response, indent=4, sort_keys=True))
#
#         # Check if the response contains any transactions
#         if 'transactions' in response:
#             for transaction_tx in response['transactions']:
#                 # Look for the specific transaction by comparing hash
#                 # Match the actual transaction hash
#                 if str(transaction_tx['hash']) == previous_transaction_id:
#                     logger.debug("Transaction found:")
#                     logger.debug(json.dumps(transaction_tx, indent=4, sort_keys=True))
#
#                     # Prepare and return the found transaction
#                     return transaction_history_response(transaction_tx)
#
#             # If no match is found after checking all transactions
#             raise XRPLException(ERROR_FETCHING_TRANSACTION_HISTORY)
#         else:
#             raise XRPLException(ERROR_FETCHING_TRANSACTION_HISTORY)
#
#     except (xrpl.XRPLException, Exception) as e:
#         # Handle exceptions like XRPL-specific errors, network issues, or unexpected errors
#         return handle_error({'status': 'failure', 'message': f"{str(e)}"}, status_code=500, function_name=function_name)
#     finally:
#         logger.info(LEAVING_FUNCTION_LOG.format(function_name, total_execution_time_in_millis(start_time)))
#
#
# @api_view(['GET'])
# @retry(wait=wait_exponential(multiplier=RETRY_BACKOFF), stop=stop_after_attempt(MAX_RETRIES))
# def get_transaction_history_with_pagination(request, wallet_address):
#     """
#     Retrieves the transaction history for a given XRP wallet address with pagination support.
#
#     Steps:
#     1. Validate the provided wallet address to ensure it is properly formatted.
#     2. Initialize the XRPL client to communicate with the XRP Ledger.
#     3. Fetch transactions in a loop using pagination (via the 'marker' parameter).
#     4. If a response is successful, extract transactions and append them to a list.
#     5. If additional transactions exist (indicated by a 'marker'), continue fetching.
#     6. Extract pagination parameters (page number and page size) from the request.
#     7. Use Django’s Paginator to split transactions into manageable pages.
#     8. Return the paginated transaction history, along with total transaction count and page count.
#
#     If any step fails, an error response is logged and returned.
#     """
#     start_time = time.time()  # Capture the start time
#     function_name = 'get_transaction_history_with_pagination'
#     logger.info(ENTERING_FUNCTION_LOG.format(function_name))
#
#     try:
#         # Validate the provided wallet address
#         if not wallet_address or not validate_xrp_wallet(wallet_address):
#             raise XRPLException(INVALID_WALLET_IN_REQUEST)
#
#         # Initialize the XRPL client for querying transactions
#         client = get_xrpl_client()
#         if not client:
#             raise XRPLException(ERROR_INITIALIZING_CLIENT)
#
#         transactions = []
#         marker = None
#
#         # Loop to fetch all transactions for the account, using pagination through 'marker'
#         while True:
#             account_tx_request = prepare_account_tx_with_pagination(wallet_address, marker)
#
#             # Send the request to XRPL to get transaction history
#             response = client.request(account_tx_request)
#             is_valid, response = validate_xrpl_response(response, required_keys=["validated"])
#             if not is_valid:
#                 raise XRPLException(ERROR_FETCHING_TRANSACTION_STATUS)
#
#             # Log the raw response for detailed debugging
#             logger.debug(XRPL_RESPONSE)
#             logger.debug(json.dumps(response, indent=4, sort_keys=True))
#
#             # Add fetched transactions to the list
#             if "transactions" not in response:
#                 raise XRPLException(ERROR_FETCHING_TRANSACTION_HISTORY)
#
#             transactions.extend(response["transactions"])
#
#             # Log the transactions for debugging
#             logger.debug(json.dumps(response["transactions"], indent=4, sort_keys=True))
#
#             # Check if there are more pages of transactions to fetch
#             marker = response.get("marker")
#             if not marker:
#                 break
#
#         # Extract pagination parameters from the request
#         page = int(request.GET.get('page', 1))
#         page_size = int(request.GET.get('page_size', 10))
#
#         # Paginate the transactions
#         paginator = Paginator(transactions, page_size)
#         paginated_transactions = paginator.get_page(page)
#
#         # Log successful transaction history fetch
#         logger.info(f"Transaction history fetched for address: {wallet_address}")
#         return account_tx_with_pagination_response(paginated_transactions, paginator.count, paginator.num_pages)
#
#     except Exception as e:
#         # Handle any exceptions that occur during the process
#         return handle_error({'status': 'failure', 'message': f"{str(e)}"}, status_code=500, function_name=function_name)
#     finally:
#         logger.info(LEAVING_FUNCTION_LOG.format(function_name, total_execution_time_in_millis(start_time)))
#
#
# @api_view(['GET'])
# @retry(wait=wait_exponential(multiplier=RETRY_BACKOFF), stop=stop_after_attempt(MAX_RETRIES))
# def check_transaction_status(request, tx_hash):
#     """
#     This function checks the status of a given XRPL transaction by its hash. The process involves:
#
#     1. Validating the transaction hash format.
#     2. Initializing an XRPL client to interact with the network.
#     3. Preparing a request to fetch transaction details.
#     4. Sending the request to XRPL and receiving the response.
#     5. Validating the response to ensure it contains necessary transaction details.
#     6. Logging relevant information for debugging and monitoring purposes.
#     7. Returning a formatted response with the transaction status.
#
#     Error handling is implemented to manage XRPL-related errors, network issues, or unexpected failures.
#     Logging is used to trace function entry, exit, and key processing steps.
#     """
#     start_time = time.time()  # Capture the start time
#     function_name = 'check_transaction_status'
#     logger.info(ENTERING_FUNCTION_LOG.format(function_name))
#
#     try:
#         # Validate the format of the transaction hash
#         if not is_valid_transaction_hash(tx_hash):
#             raise XRPLException(INVALID_TRANSACTION_HASH)
#
#         # Log the start of the transaction status check for debugging purposes
#         logger.info(f"Checking transaction status for hash: {tx_hash}")
#
#         # Initialize the XRPL client for transaction status checks
#         client = get_xrpl_client()
#         if not client:
#             raise XRPLException(ERROR_INITIALIZING_CLIENT)
#
#         # Create a transaction request object to fetch details of the specified transaction
#         tx_request = prepare_tx(tx_hash)
#
#         # Send the request to the XRPL to get the transaction details
#         response = client.request(tx_request)
#         is_valid, result = validate_xrpl_response(response, required_keys=["validated"])
#         if not is_valid:
#             raise XRPLException(ERROR_FETCHING_TRANSACTION_STATUS)
#
#         # Log the raw response for detailed debugging
#         logger.debug(XRPL_RESPONSE)
#         logger.debug(json.dumps(result, indent=4, sort_keys=True))
#
#         # Log the raw response for detailed debugging
#         logger.info(f"Raw XRPL response for transaction {tx_hash}: {result}")
#         return transaction_status_response(response, tx_hash)
#
#     except (xrpl.XRPLException, Exception) as e:
#         # Handle exceptions like XRPL-specific errors, network issues, or unexpected errors
#         return handle_error({'status': 'failure', 'message': f"{str(e)}"}, status_code=500, function_name=function_name)
#
#     finally:
#         logger.info(LEAVING_FUNCTION_LOG.format(function_name, total_execution_time_in_millis(start_time)))


# @api_view(['POST'])
# @retry(wait=wait_exponential(multiplier=RETRY_BACKOFF), stop=stop_after_attempt(MAX_RETRIES))
# def send_payment(request):
#     """
#     Processes a payment transaction on the XRPL (XRP Ledger).
#
#     This function performs the following steps:
#     1. Extracts and validates the request data, ensuring sender seed, receiver address, and amount are correct.
#     2. Converts the XRP amount to drops (the smallest unit of XRP).
#     3. Uses a database transaction to ensure atomicity, preventing partial updates in case of failures.
#     4. Initializes an XRPL client to interact with the XRP Ledger.
#     5. Creates a sender wallet from the provided seed and retrieves the sender's address.
#     6. Fetches the current network fee to include in the transaction.
#     7. Constructs and submits a payment transaction to the XRPL.
#     8. Validates the transaction response to ensure it has been processed successfully.
#     9. Handles and processes the response, updating necessary records or triggering additional actions.
#     10. Implements error handling to catch XRPL-specific errors, network issues, or unexpected failures.
#
#     If an error occurs at any stage, a detailed failure response is logged and returned.
#     """
#     start_time = time.time()  # Capture the start time
#     function_name = 'send_payment'
#     logger.info(ENTERING_FUNCTION_LOG.format(function_name))
#
#     try:
#         # Extract and validate request data
#         sender_seed, receiver_address, amount_xrp = extract_request_data(request)
#         validate_request_data(sender_seed, receiver_address, amount_xrp)
#
#         # Convert amount to drops
#         amount_drops = xrp_to_drops(amount_xrp)
#
#         with transaction.atomic():
#             # Initialize XRPL client
#             client = get_xrpl_client()
#             if not client:
#                 raise ConnectionError(ERROR_INITIALIZING_CLIENT)
#
#             # Create sender wallet
#             sender_wallet = Wallet.from_seed(sender_seed)
#             sender_address = sender_wallet.classic_address
#
#             # Get network fee
#             fee_drops = fetch_network_fee(client)
#
#             # Create and submit the payment transaction
#             payment_transaction = create_payment_transaction(sender_address, receiver_address, amount_drops, fee_drops,
#                                                              False)
#             payment_response = submit_and_wait(payment_transaction, client, sender_wallet)
#
#             is_valid, result = validate_xrpl_response(payment_response, required_keys=["validated"])
#             if not is_valid:
#                 raise XRPLException(ERROR_FETCHING_TRANSACTION_STATUS)
#
#             # Handle the transaction response
#             return process_payment_response(payment_response, sender_address, receiver_address, amount_xrp, fee_drops)
#
#     except (xrpl.XRPLException, Exception) as e:
#         # Handle exceptions like XRPL-specific errors, network issues, or unexpected errors
#         return handle_error({'status': 'failure', 'message': f"{str(e)}"}, status_code=500, function_name=function_name)
#
#     finally:
#         logger.info(LEAVING_FUNCTION_LOG.format(function_name, total_execution_time_in_millis(start_time)))


# @api_view(['DELETE'])
# @retry(wait=wait_exponential(multiplier=RETRY_BACKOFF), stop=stop_after_attempt(MAX_RETRIES))
# def black_hole_xrp(request, wallet_address):
#     """
#     Function to perform the 'black hole' operation on an XRP account. This involves:
#     - Setting the account's regular key to a black hole address.
#     - Disabling the master key, making the account inaccessible.
#     """
#     start_time = time.time()  # Capture the start time
#     function_name = 'black_hole_xrp'
#     logger.info(ENTERING_FUNCTION_LOG.format(function_name))  # Log entering function
#
#     try:
#         # Validate the provided wallet address.
#         if not wallet_address or not validate_xrp_wallet(wallet_address):
#             raise XRPLException(INVALID_WALLET_IN_REQUEST)
#
#         # Extract the sender's seed from the request.
#         sender_seed, _, _ = extract_request_data(request)
#         if not is_valid_xrpl_seed(sender_seed):
#             raise ValueError('Sender seed is invalid.')
#
#         # Initialize the XRPL client for further operations.
#         client = get_xrpl_client()
#         if not client:
#             raise ConnectionError(ERROR_INITIALIZING_CLIENT)
#
#         # Prepare and send request to get the account info from the ledger.
#         account_info_request = prepare_account_data(wallet_address, True)
#         response = client.request(account_info_request)
#
#         # Validate the response from the account info request.
#         is_valid, response = validate_xrpl_response(response, required_keys=["validated"])
#         if not is_valid:
#             raise XRPLException(ERROR_FETCHING_TRANSACTION_STATUS)
#
#         # Log the raw response for debugging.
#         logger.debug(XRPL_RESPONSE)
#         logger.debug(json.dumps(response, indent=4, sort_keys=True))
#
#         # Get black hole address from the environment configuration.s
#         xrpl_config = apps.get_app_config('xrpl_api')
#
#         # Prepare a transaction to set the account's regular key to the black hole address.
#         tx_regular_key = prepare_regular_key(wallet_address, xrpl_config.BLACK_HOLE_ADDRESS)
#
#         # Get wallet from the sender's seed and submit the SetRegularKey transaction.
#         wallet = Wallet.from_seed(sender_seed)
#         submit_tx_regular = submit_and_wait(transaction=tx_regular_key, client=client, wallet=wallet)
#         submit_tx_regular = submit_tx_regular.result
#
#         # Log the result of the SetRegularKey transaction.
#         logger.info("Submitted a SetRegularKey tx.")
#         logger.info(f"Result: {submit_tx_regular['meta']['TransactionResult']}")
#         logger.info(f"Tx content: {submit_tx_regular}")
#
#         # Prepare a transaction to disable the master key on the account.
#         tx_disable_master_key = AccountSet(
#             account=wallet_address,
#             set_flag=AccountSetAsfFlag.ASF_DISABLE_MASTER
#         )
#
#         # Submit the transaction to disable the master key.
#         submit_tx_disable = submit_and_wait(transaction=tx_disable_master_key, client=client, wallet=wallet)
#         submit_tx_disable = submit_tx_disable.result
#
#         # Log the result of the DisableMasterKey transaction.
#         logger.info("Submitted a DisableMasterKey tx.")
#         logger.info(f"Result: {submit_tx_disable['meta']['TransactionResult']}")
#         logger.info(f"Tx content: {submit_tx_disable}")
#
#         # Prepare a request to check the account's flags after the transaction.
#         get_acc_flag = prepare_account_data(wallet_address, True)
#         response = client.request(get_acc_flag)
#
#         # Verify if the master key has been successfully disabled.
#         if response.result['account_data']['Flags'] & asfDisableMaster:
#             logger.info(f"Account {wallet_address}'s master key has been disabled, account is black holed.")
#         else:
#             logger.info(f"Account {wallet_address}'s master key is still enabled, account is NOT black holed")
#
#         # Return the response indicating the account status after the operation.
#         return delete_account_response(response)
#
#     except (xrpl.XRPLException, Exception) as e:
#         # Handle exceptions (e.g., XRPL errors, connection issues) and return an error response.
#         return handle_error({'status': 'failure', 'message': f"{str(e)}"}, status_code=500, function_name=function_name)
#     finally:
#         # Log when the function exits.
#         logger.info(LEAVING_FUNCTION_LOG.format(function_name, total_execution_time_in_millis(start_time)))

#
# @api_view(['POST'])
# @retry(wait=wait_exponential(multiplier=RETRY_BACKOFF), stop=stop_after_attempt(MAX_RETRIES))
# def send_and_delete_wallet(request, wallet_address):
#     """
#     Handles the process of sending XRP from a wallet and then deleting the wallet.
#     The function validates the wallet, checks for any associated ledger entries,
#     processes a payment, and deletes the wallet from the ledger.
#
#     Args:
#     - request: The HTTP request object that contains the data for the operation.
#     - wallet_address: The address of the wallet to be processed.
#
#     Returns:
#     - JsonResponse with transaction status.
#     """
#     start_time = time.time()  # Capture the start time of the function execution.
#     function_name = "send_and_delete_wallet"
#     logger.info(ENTERING_FUNCTION_LOG.format(function_name))  # Log entering the function.
#
#     try:
#         # Step 1: Validate the provided wallet address format.
#         if not wallet_address or not validate_xrp_wallet(wallet_address):
#             raise ValueError(INVALID_WALLET_IN_REQUEST)
#
#         # Step 2: Extract sender seed from the request data.
#         sender_seed, _, _ = extract_request_data(request)
#         if not is_valid_xrpl_seed(sender_seed):
#             raise ValueError('Sender seed is invalid.')
#
#         # Step 3: Initialize the XRPL client.
#         client = get_xrpl_client()
#         if not client:
#             raise ValueError(ERROR_INITIALIZING_CLIENT)
#
#         # Step 4: Prepare the sender wallet using the extracted seed.
#         sender_wallet = Wallet.from_seed(sender_seed)
#
#         # Step 5: Prepare the request to fetch account data for the sender.
#         account_info_request = prepare_account_data(sender_wallet.classic_address, False)
#
#         # Step 6: Check if the wallet is present in the ledger and has valid ledger entries.
#         valid_address, account_objects = check_account_ledger_entries(sender_wallet.classic_address)
#         if not valid_address:
#             raise ValueError("Wallet not found on ledger. Unable to delete wallet")
#
#         # Step 7: Check if there are any escrow, payment channels, Ripple state, or check entries
#         # that prevent the wallet from being deleted.
#         if not check_escrow_entries(account_objects):
#             raise ValueError("Wallet has an escrow. Unable to delete wallet")
#
#         if not check_pay_channel_entries(account_objects):
#             raise ValueError("Wallet has payment channels. Unable to delete wallet")
#
#         if not check_ripple_state_entries(account_objects):
#             raise ValueError("Wallet has Ripple state entries. Unable to delete wallet")
#
#         if not check_check_entries(account_objects):
#             raise ValueError("Wallet has check entries. Unable to delete wallet")
#
#         # Step 8: Fetch account information and validate response.
#         account_info_response = client.request(account_info_request)
#         if not account_info_response or not account_info_response.is_successful():
#             raise ValueError(ERROR_IN_XRPL_RESPONSE)
#
#         # Step 9: Get the balance of the sender's account.
#         balance = int(account_info_response.result['account_data']['Balance'])
#         base_reserve, reserve_increment = get_account_reserves()
#         if base_reserve is None or reserve_increment is None:
#             raise ValueError("Failed to retrieve reserve requirements from the XRPL.")
#
#         drops = xrp_to_drops(base_reserve)  # Convert base reserve from XRP to drops.
#         transferable_amount = int(balance) - int(drops)  # Calculate the transferable amount.
#
#         # Step 10: Check if there is enough balance to cover the transaction fees.
#         if transferable_amount <= 0:
#             raise ValueError("Insufficient balance to cover the reserve and fees.")
#
#         # Step 11: Create and submit the payment transaction.
#         payment_tx = create_payment_transaction(sender_wallet.classic_address, wallet_address, transferable_amount, 0,
#                                                 True)
#         payment_response = submit_and_wait(payment_tx, client, sender_wallet)
#
#         if not payment_response or not payment_response.is_successful():
#             raise ValueError(PAYMENT_IS_UNSUCCESSFUL)
#
#         # Step 12: Calculate the appropriate LastLedgerSequence for the account delete transaction.
#         last_ledger_sequence = calculate_last_ledger_sequence(client, buffer_time=60)
#
#         # Step 13: Create and submit the account delete transaction.
#         account_delete_tx = create_account_delete_transaction(sender_wallet.classic_address, wallet_address,
#                                                               last_ledger_sequence)
#         account_delete_response = submit_and_wait(account_delete_tx, client, sender_wallet)
#
#         if not account_delete_response or not account_delete_response.is_successful():
#             raise ValueError("Account delete transaction failed.")
#
#         # Step 14: Return the response containing the hashes of the payment and account delete transactions.
#         return account_delete_tx_response(payment_response.result['hash'], account_delete_response.result['hash'])
#
#     except Exception as e:
#         # Step 15: Handle any exceptions that occurred during the process.
#         return handle_error({'status': 'failure', 'message': f"{str(e)}"}, status_code=500, function_name=function_name)
#
#     finally:
#         # Step 16: Log when the function exits, including the total execution time.
#         logger.info(LEAVING_FUNCTION_LOG.format(function_name, total_execution_time_in_millis(start_time)))


# @api_view(['GET'])
# @retry(wait=wait_exponential(multiplier=RETRY_BACKOFF), stop=stop_after_attempt(MAX_RETRIES))
# def get_ledger_info(request):
#     """
#     Retrieve ledger information from the XRP Ledger based on the provided `ledger_index` or `ledger_hash`.
#
#     This function handles the following steps:
#     1. Extracts query parameters (`ledger_index` and `ledger_hash`) from the request.
#     2. Checks the cache for previously fetched ledger info to avoid redundant API calls.
#     3. Prepares a ledger request based on the provided parameters.
#     4. Initializes the XRPL client to interact with the XRP Ledger.
#     5. Sends the request to the XRP Ledger and validates the response.
#     6. Logs the raw response for debugging purposes.
#     7. Formats the response data for the API response.
#     8. Caches the formatted response to improve performance on subsequent requests.
#     9. Handles any exceptions that occur during execution.
#     10. Logs the total execution time of the function.
#
#     Args:
#         request (HttpRequest): The HTTP request object containing query parameters.
#
#     Returns:
#         JsonResponse: A JSON response containing the ledger information or an error message.
#     """
#     start_time = time.time()  # Capture the start time of the function execution.
#     function_name = 'get_ledger_info'
#     logger.info(ENTERING_FUNCTION_LOG.format(function_name))  # Log entering the function.
#
#     try:
#         # Step 1: Retrieve the `ledger_index` and `ledger_hash` query parameters from the request.
#         ledger_index = get_request_param(request, 'ledger_index')
#         ledger_hash = get_request_param(request, 'ledger_hash')
#
#         # Step 2: Check the cache for previously fetched ledger info to avoid redundant API calls.
#         cache_key = f"ledger_info_{ledger_index}_{ledger_hash or ''}"
#         cached_data = get_cached_data(cache_key, 'get_ledger_info_function', function_name)
#         if cached_data:
#             return JsonResponse(cached_data)  # Return the cached data if available.
#
#         # Step 3: Prepare the ledger request based on whether a ledger index or ledger hash is provided.
#         if ledger_hash:
#             ledger_request = Ledger(ledger_hash=ledger_hash)  # Create a Ledger request using the hash.
#         else:
#             ledger_request = Ledger(ledger_index=ledger_index)  # Create a Ledger request using the index.
#
#         # Step 4: Initialize the XRPL client to make the request to the XRP Ledger.
#         client = get_xrpl_client()
#         if not client:
#             raise ValueError(ERROR_INITIALIZING_CLIENT)  # Raise an error if the client initialization fails.
#
#         # Step 5: Send the request to the XRP Ledger and capture the response.
#         response = client.request(ledger_request)
#         is_valid, response = validate_xrpl_response(response, required_keys=["validated"])
#
#         # If the response is not valid, raise an exception to indicate an issue.
#         if not is_valid:
#             raise XRPLException(ERROR_FETCHING_XRP_RESERVES)
#
#         # Log the raw response for detailed debugging and analysis.
#         logger.debug(XRPL_RESPONSE)
#         logger.debug(json.dumps(response, indent=4, sort_keys=True))
#
#         logger.info(f"Successfully retrieved ledger info for {ledger_index}/{ledger_hash}")
#
#         # Step 7: Format the response data to make it suitable for the response.
#         response_data = ledger_info_response(response, 'Ledger information successfully retrieved.')
#
#         # Step 8: Cache the formatted response to improve performance on subsequent requests.
#         cache.set(cache_key, response_data, CACHE_TIMEOUT)
#
#         return response_data  # Return the formatted response data.
#     except Exception as e:
#         # Step 10: Catch any unexpected errors and return a failure response with the error message.
#         return handle_error({'status': 'failure', 'message': f"{str(e)}"}, status_code=500, function_name=function_name)
#
#     finally:
#         # Step 11: Log the execution time and when the function exits.
#         logger.info(LEAVING_FUNCTION_LOG.format(function_name, total_execution_time_in_millis(start_time)))


# @api_view(['GET'])
# @retry(wait=wait_exponential(multiplier=RETRY_BACKOFF), stop=stop_after_attempt(MAX_RETRIES))
# def get_xrp_reserves(request):
#     """
#     Retrieve XRP reserve information for a given wallet address from the XRP Ledger.
#
#     This function performs the following steps:
#     1. Extracts the `wallet_address` query parameter (wallet address) from the request.
#     2. Initializes the XRPL client to interact with the XRP Ledger.
#     3. Requests server information from the XRP Ledger to fetch reserve details.
#     4. Validates the response to ensure it contains the required data.
#     5. Extracts the base reserve (`reserve_base_xrp`) and incremental reserve (`reserve_inc_xrp`) from the response.
#     6. Logs the raw response for debugging purposes.
#     7. Returns the formatted reserve information for the specified wallet address.
#     8. Handles any exceptions that occur during execution.
#     9. Logs the total execution time of the function.
#
#     Args:
#         request (HttpRequest): The HTTP request object containing the `account` query parameter.
#
#     Returns:
#         JsonResponse: A JSON response containing the XRP reserve information or an error message.
#     """
#     start_time = time.time()  # Capture the start time of the function execution.
#     function_name = 'get_xrp_reserves'
#     logger.info(ENTERING_FUNCTION_LOG.format(function_name))  # Log entering the function.
#
#     try:
#         # Step 1: Extract the wallet address from the request query parameters.
#         wallet_address = get_request_param(request, 'wallet_address')
#         if not wallet_address:
#             raise ValueError(ACCOUNT_IS_REQUIRED)  # Raise an error if the wallet address is missing.
#
#         # Step 2: Initialize the XRPL client to interact with the XRP Ledger.
#         client = get_xrpl_client()
#         if not client:
#             raise XRPLException(ERROR_INITIALIZING_CLIENT)  # Raise an error if client initialization fails.
#
#         # Step 3: Request server information from the XRP Ledger to fetch reserve details.
#         server_info_request = ServerInfo()
#         if not server_info_request:
#             raise ERROR_INITIALIZING_SERVER_INFO  # Raise an error if the server info request fails.
#
#         server_information_response = client.request(server_info_request)
#
#         # Step 4: Validate the response to ensure it contains the required data.
#         is_valid, response = validate_xrpl_response(server_information_response, required_keys=["info"])
#         if not is_valid:
#             raise XRPLException(ERROR_FETCHING_XRP_RESERVES)  # Raise an error if the response is invalid.
#
#         # Step 5: Log the raw response for debugging purposes.
#         logger.debug(XRPL_RESPONSE)
#         logger.debug(json.dumps(server_information_response.result, indent=4, sort_keys=True))
#
#         # Step 6: Extract reserve information from the validated ledger data.
#         ledger_info = server_information_response.result.get('info', {}).get('validated_ledger', {})
#         reserve_base = ledger_info.get('reserve_base_xrp')  # Base reserve in XRP.
#         reserve_inc = ledger_info.get('reserve_inc_xrp')  # Incremental reserve in XRP.
#
#         # Step 7: Ensure that both reserve values are present in the response.
#         if reserve_base is None or reserve_inc is None:
#             logger.error(f"Reserve info missing in response: {server_information_response.result}")
#             raise KeyError(RESERVES_NOT_FOUND)  # Raise an error if reserve information is missing.
#
#         logger.info(f"Successfully fetched XRP reserve information for {wallet_address}.")
#
#         # Step 8: Format and return the reserve information.
#         return account_reserves_response(server_information_response, reserve_base, reserve_inc)
#
#     except Exception as e:
#         # Step 9: Catch any unexpected errors and return a failure response with the error message.
#         return handle_error({'status': 'failure', 'message': f"{str(e)}"}, status_code=500, function_name=function_name)
#
#     finally:
#         # Step 10: Log the total execution time and when the function exits.
#         logger.info(LEAVING_FUNCTION_LOG.format(function_name, total_execution_time_in_millis(start_time)))


# @api_view(['GET'])
# @retry(wait=wait_exponential(multiplier=RETRY_BACKOFF), stop=stop_after_attempt(MAX_RETRIES))
# def get_server_info(request):
#     """
#     Retrieve server information from the XRP Ledger, including details about the server's state and configuration.
#
#     This function performs the following steps:
#     1. Checks the cache for previously fetched server information to avoid redundant API calls.
#     2. Prepares a request to fetch server information from the XRP Ledger.
#     3. Initializes the XRPL client to interact with the XRP Ledger.
#     4. Sends the request to the XRP Ledger and validates the response.
#     5. Logs the raw response for debugging purposes.
#     6. Caches the server information to improve performance on subsequent requests.
#     7. Returns the formatted server information.
#     8. Handles any exceptions that occur during execution.
#     9. Logs the total execution time of the function.
#
#     Args:
#         request (HttpRequest): The HTTP request object.
#
#     Returns:
#         JsonResponse: A JSON response containing the server information or an error message.
#     """
#     start_time = time.time()  # Capture the start time to track the execution duration.
#     function_name = 'get_server_info'
#     logger.info(ENTERING_FUNCTION_LOG.format(function_name))  # Log function entry.
#
#     try:
#         # Step 1: Check the cache for previously fetched server information.
#         cache_key = "server_info"
#         cached_data = get_cached_data(cache_key, 'get_server_info', function_name)
#         if cached_data:
#             # If cached data is available, return it to avoid redundant API calls.
#             return JsonResponse(cached_data)
#
#         # Step 2: Prepare a request to fetch server information from the XRP Ledger.
#         server_info_request = ServerInfo()
#         if not server_info_request:
#             # If the request cannot be initialized, raise an error.
#             raise ERROR_INITIALIZING_SERVER_INFO
#
#         # Step 3: Initialize the XRPL client to interact with the XRP Ledger.
#         client = get_xrpl_client()
#         if not client:
#             # If the client is not initialized, raise an error.
#             raise ConnectionError(ERROR_INITIALIZING_CLIENT)
#
#         # Step 4: Send the request to the XRP Ledger and validate the response.
#         response = client.request(server_info_request)
#         is_valid, response = validate_xrpl_response(response, required_keys=["info"])
#         if not is_valid:
#             # If the response is not valid, raise an exception to indicate an issue.
#             raise XRPLException(ERROR_FETCHING_ACCOUNT_OFFERS)
#
#         # Step 5: Log the raw response for detailed debugging.
#         logger.debug(XRPL_RESPONSE)
#         logger.debug(json.dumps(response, indent=4, sort_keys=True))
#
#         # Step 6: Cache the server information to improve performance on subsequent requests.
#         cache.set('server_info', response, timeout=CACHE_TIMEOUT_FOR_SERVER_INFO)
#
#         # Step 7: Log the successful fetching of server information.
#         logger.info("Successfully fetched ledger information.")
#
#         # Step 8: Return the formatted server information.
#         return ledger_info_response(response, 'Server info fetched successfully.')
#
#     except Exception as e:
#         # Step 9: Handle any unexpected errors that occur during the process.
#         return handle_error({'status': 'failure', 'message': f"{str(e)}"}, status_code=500, function_name=function_name)
#
#     finally:
#         # Step 10: Log when the function exits, including the total execution time.
#         logger.info(LEAVING_FUNCTION_LOG.format(function_name, total_execution_time_in_millis(start_time)))


# @api_view(['GET'])
# @retry(wait=wait_exponential(multiplier=RETRY_BACKOFF), stop=stop_after_attempt(MAX_RETRIES))
# def get_account_offers(request):
#     """
#     Retrieve account offers (open orders) for a given wallet address from the XRP Ledger.
#
#     This function performs the following steps:
#     1. Extracts the `wallet_address` query parameter from the request.
#     2. Initializes the XRPL client to interact with the XRP Ledger.
#     3. Prepares and sends a request to fetch account offers for the specified wallet address.
#     4. Validates the response to ensure it contains the required data.
#     5. Logs the raw response for debugging purposes.
#     6. Extracts the offers from the response data.
#     7. Logs the number of offers found or if no offers are present.
#     8. Returns the formatted response containing the account offers.
#     9. Handles any exceptions that occur during execution.
#     10. Logs the total execution time of the function.
#
#     Args:
#         request (HttpRequest): The HTTP request object containing the `wallet_address` query parameter.
#
#     Returns:
#         JsonResponse: A JSON response containing the account offers or an error message.
#     """
#     start_time = time.time()  # Capture the start time to track the execution duration.
#     function_name = 'get_account_offers'
#     logger.info(ENTERING_FUNCTION_LOG.format(function_name))  # Log function entry.
#
#     try:
#         # Step 1: Retrieve the wallet address from the query parameters in the request.
#         wallet_address = get_request_param(request, 'wallet_address')
#         if not wallet_address:
#             # If wallet address is missing, raise an error and return failure.
#             raise ValueError(ACCOUNT_IS_REQUIRED)
#
#         # Step 2: Initialize the XRPL client to interact with the XRPL network.
#         client = get_xrpl_client()
#         if not client:
#             # If the client is not initialized, raise an error and return failure.
#             raise ConnectionError(ERROR_INITIALIZING_CLIENT)
#
#         # Step 3: Prepare the request for fetching account offers using the wallet address.
#         account_offers_request = prepare_account_offers(wallet_address)
#         # Send the request to the XRPL client to get the account offers.
#         response = client.request(account_offers_request)
#
#         # Step 4: Validate the response from XRPL to ensure it's successful and contains expected data.
#         is_valid, response = validate_xrpl_response(response, required_keys=["validated"])
#         if not is_valid:
#             # If the response is not valid, raise an exception to indicate an issue.
#             raise XRPLException(ERROR_FETCHING_ACCOUNT_OFFERS)
#
#         # Step 5: Log the raw response for debugging purposes (useful for detailed inspection).
#         logger.debug(XRPL_RESPONSE)
#         logger.debug(json.dumps(response, indent=4, sort_keys=True))
#
#         # Step 6: Extract the offers from the response data.
#         offers = response.get("offers", [])
#
#         # Step 7: Log the number of offers found and return the response with the offer data.
#         if offers:
#             # If offers are found, log how many were found.
#             logger.info(f"Found {len(offers)} offers for wallet {wallet_address}.")
#         else:
#             # If no offers are found, log this information.
#             logger.info(f"No offers found for wallet {wallet_address}.")
#
#         # Step 8: Log the successful fetching of offers for the account.
#         logger.info(f"Successfully fetched offers for account {wallet_address}.")
#
#         # Step 9: Prepare and return the response containing the offers.
#         return create_account_offers_response(response, offers)
#
#     except Exception as e:
#         # Step 10: Handle unexpected errors that might occur during the execution.
#         return handle_error({'status': 'failure', 'message': f"{str(e)}"}, status_code=500, function_name=function_name)
#
#     finally:
#         # Step 11: Log when the function exits, including the total execution time.
#         logger.info(LEAVING_FUNCTION_LOG.format(function_name, total_execution_time_in_millis(start_time)))


# @api_view(['GET'])
# @retry(wait=wait_exponential(multiplier=RETRY_BACKOFF), stop=stop_after_attempt(MAX_RETRIES))
# def get_account_trust_lines(request):
#     """
#     This function handles fetching trust lines for a specific wallet address from the XRPL network.
#     It supports pagination to handle large numbers of trust lines.
#
#     The function starts by extracting the wallet address from the request. It then initializes an
#     XRPL client to make requests to the XRP ledger and fetch the account lines for the specified
#     wallet address. To handle potentially large datasets, pagination is implemented through the
#     use of markers, allowing the function to fetch account lines in multiple pages if necessary.
#
#     The account lines are fetched in a loop until all available lines are retrieved. Each page of
#     trust lines is added to a list, which is then paginated using Django's Paginator class to
#     return a specific subset of results based on the `page` and `page_size` query parameters.
#
#     If any errors occur during the process (such as invalid wallet address or failed request),
#     they are caught and handled gracefully, with appropriate error messages returned to the client.
#     Finally, the total execution time of the function is logged for performance monitoring.
#
#     Steps:
#     1. Extract the wallet address from the request parameters.
#     2. Initialize the XRPL client to communicate with the XRP ledger.
#     3. Fetch account lines using a loop to handle pagination, continuing until all lines are retrieved.
#     4. Paginate the resulting account lines list based on the `page` and `page_size` parameters.
#     5. Return the paginated result to the client.
#     6. Handle any errors that may arise during the process.
#     7. Log the total execution time for monitoring.
#
#     Args:
#         request (Request): The HTTP request object, containing query parameters such as `wallet_address`, `page`, and `page_size`.
#
#     Returns:
#         Response: A paginated response containing the trust lines for the given wallet address.
#     """
#     # Capture the start time to calculate the total execution time
#     start_time = time.time()
#     function_name = 'get_account_trust_lines'
#     logger.info(ENTERING_FUNCTION_LOG.format(function_name))
#
#     try:
#         # Extract wallet address from request parameters
#         # The wallet address is required to fetch account lines. If not provided, raise an error.
#         wallet_address = get_request_param(request, 'wallet_address')
#         if not wallet_address:
#             raise ValueError("Account is required.")
#
#         # Initialize the XRPL client to interact with the XRPL network.
#         # If the client can't be initialized, raise an exception.
#         client = get_xrpl_client()
#         if not client:
#             raise ConnectionError("Failed to initialize XRPL client.")
#
#         account_lines = []  # Initialize an empty list to store account lines
#         marker = None  # Initialize the marker to manage pagination
#
#         # Loop to fetch all account lines for the account, using pagination via 'marker'
#         while True:
#             # Prepare the account lines request with the current marker (for pagination)
#             account_lines_request = prepare_account_lines(wallet_address, marker)
#
#             # Send the request to XRPL to fetch account lines
#             response = client.request(account_lines_request)
#
#             # Validate the response to ensure it contains the expected fields
#             is_valid, response = validate_xrpl_response(response, required_keys=["validated"])
#             if not is_valid:
#                 raise XRPLException(ERROR_FETCHING_TRANSACTION_STATUS)
#
#             # Log the raw response for debugging purposes
#             logger.debug(XRPL_RESPONSE)
#             logger.debug(json.dumps(response, indent=4, sort_keys=True))
#
#             # Check if the "lines" field exists in the response. If not, raise an error.
#             if "lines" not in response:
#                 raise XRPLException('Account lines not found')
#
#             # Add the fetched account lines to the account_lines list
#             account_lines.extend(response["lines"])
#
#             # Log the account lines for further debugging
#             logger.debug(json.dumps(response, indent=4, sort_keys=True))
#
#             # Check if there are more pages of account lines to fetch using the 'marker' field.
#             # If 'marker' is not present, break the loop, as we have fetched all pages.
#             marker = response.get("marker")
#             if not marker:
#                 break
#
#         # Extract pagination parameters from the request for paginating the response
#         page = int(request.GET.get('page', 1))  # Default to page 1 if no page is specified
#         page_size = int(request.GET.get('page_size', 10))  # Default to 10 items per page if no page_size is specified
#
#         # Paginate the account lines using Django's Paginator
#         paginator = Paginator(account_lines, page_size)
#         paginated_transactions = paginator.get_page(page)
#
#         # Log that the account lines have been successfully fetched
#         logger.info(f"Account Lines fetched for address: {wallet_address}")
#
#         # Return the paginated response to the client
#         return create_account_lines_response(paginated_transactions, paginator)
#
#     except Exception as e:
#         # Handle any exceptions by logging the error and returning a failure response
#         return handle_error({'status': 'failure', 'message': f"{str(e)}"}, status_code=500, function_name=function_name)
#
#     finally:
#         # Log the total execution time of the function for monitoring purposes
#         logger.info(LEAVING_FUNCTION_LOG.format(function_name, total_execution_time_in_millis(start_time)))
#
#
# @api_view(['GET'])
# @retry(wait=wait_exponential(multiplier=RETRY_BACKOFF), stop=stop_after_attempt(MAX_RETRIES))
# def get_trust_line(request):
#     """
#     This function retrieves the trust lines for a specific wallet address on the XRP Ledger (XRPL).
#     It uses the XRPL client to make a request for account lines (trust lines) associated with the given wallet address.
#
#     The function performs the following steps:
#     1. Extracts the wallet address from the request parameters.
#     2. Initializes the XRPL client and prepares an AccountLines request.
#     3. Sends the request to the XRPL network to fetch the trust lines for the wallet address.
#     4. Validates the response to ensure the data is valid and contains the necessary fields.
#     5. Logs the response for debugging purposes.
#     6. Extracts and returns the trust lines from the response.
#     7. Handles any errors gracefully by logging and returning a failure response.
#
#     If there is an issue with the client or the response, the function raises appropriate exceptions
#     and logs detailed information for troubleshooting.
#
#     Args:
#         request (Request): The HTTP request object containing the wallet address.
#
#     Returns:
#         Response: A JSON response containing the trust lines for the given wallet address.
#     """
#
#     # Capture the start time to calculate the total execution time
#     start_time = time.time()
#     function_name = 'get_trust_line'
#     logger.info(ENTERING_FUNCTION_LOG.format(function_name))
#
#     try:
#         # Extract wallet address from request parameters
#         # The wallet address is essential to fetch the trust lines for the specified account.
#         wallet_address = get_request_param(request, 'wallet_address')
#         if not wallet_address:
#             raise ValueError("Account is required.")
#
#         # Prepare an AccountLines request to retrieve trust lines for the account.
#         # The request will be sent to the XRPL network to fetch the trust lines for the specified wallet address.
#         account_lines_request = AccountLines(account=wallet_address)
#
#         # Initialize the XRPL client to communicate with the XRP ledger and fetch the required information.
#         # If the client can't be initialized, raise an exception.
#         client = get_xrpl_client()
#         if not client:
#             raise ConnectionError(ERROR_INITIALIZING_CLIENT)
#
#         # Send the AccountLines request to the XRPL network.
#         # The response contains the trust lines for the wallet address.
#         response = client.request(account_lines_request)
#
#         # Validate the response to ensure it contains the expected fields.
#         # If the response is not valid, log the error and raise an exception.
#         is_valid, response = validate_xrpl_response(response, required_keys=["validated"])
#         if not is_valid:
#             logger.error(f"Failed to fetch trust lines for {wallet_address}: {response}")
#             raise XRPLException('Error fetching trust lines.')
#
#         # Log the raw response for debugging purposes.
#         # This helps in analyzing the response content and troubleshooting issues.
#         logger.debug(XRPL_RESPONSE)
#         logger.debug(json.dumps(response, indent=4, sort_keys=True))
#
#         # Extract trust lines from the response.
#         # If no trust lines are found, an empty list is returned.
#         trust_lines = response.get('lines', [])
#         logger.info(f"Successfully fetched trust lines for account {wallet_address}. Trust lines: {trust_lines}")
#
#         # Return the trust lines in a structured response.
#         return trust_line_response(response)
#
#     except Exception as e:
#         # Handle any unexpected errors during the process.
#         # Log the error and return a failure response with the exception details.
#         return handle_error({'status': 'failure', 'message': f"{str(e)}"}, status_code=500, function_name=function_name)
#
#     finally:
#         # Log the total execution time of the function to monitor performance.
#         logger.info(LEAVING_FUNCTION_LOG.format(function_name, total_execution_time_in_millis(start_time)))
#
#
# @api_view(['POST'])
# @retry(wait=wait_exponential(multiplier=RETRY_BACKOFF), stop=stop_after_attempt(MAX_RETRIES))
# def set_trust_line(request):
#     """
#     This function is responsible for setting a trust line for a specific wallet address on the XRP Ledger (XRPL).
#     The trust line defines the amount of a certain currency that an account is willing to accept from another account.
#
#     The function performs the following actions:
#     1. Extracts the required parameters (sender seed, wallet address, currency, and limit) from the request data.
#     2. Converts the limit to drops if the currency is XRP.
#     3. Initializes the XRPL client to communicate with the XRP Ledger.
#     4. Creates a wallet from the sender's seed.
#     5. Fetches the current sequence number for the sender's account.
#     6. Retrieves the current network fee.
#     7. Constructs a TrustSet transaction with the necessary details.
#     8. Signs the transaction using the sender's wallet.
#     9. Submits the signed transaction to the XRPL network.
#     10. Returns a success response if the transaction is successfully processed.
#
#     If any errors occur during the process, they are caught, logged, and a failure response is returned.
#
#     Args:
#         request (Request): The HTTP request object containing parameters like sender_seed, wallet_address, currency, and limit.
#
#     Returns:
#         Response: A JSON response indicating whether the trust line was successfully set.
#     """
#
#     # Capture the start time to calculate the total execution time of the function
#     start_time = time.time()
#     function_name = 'set_trust_line'
#     logger.info(ENTERING_FUNCTION_LOG.format(function_name))
#
#     try:
#         # Extract the parameters from the request data.
#         # These parameters are necessary to create and submit a TrustSet transaction.
#         sender_seed = get_request_param(request, 'sender_seed')
#         wallet_address = get_request_param(request, 'wallet_address')
#         currency = get_request_param(request, 'currency')
#         limit = get_request_param(request, 'limit')
#
#         # If any of the required parameters are missing, raise an error.
#         if not sender_seed or not wallet_address or not currency or not limit:
#             raise ValueError(MISSING_REQUEST_PARAMETERS)
#
#         # Log the received parameters for debugging and verification.
#         logger.info(
#             f"Received parameters - sender_seed: {sender_seed}, wallet_address: {wallet_address}, currency: {currency}, limit: {limit}")
#
#         # If the currency is XRP, convert the limit into drops (the smallest unit of XRP).
#         limit_drops = xrpl.utilities.xrp_to_drops(limit) if currency == "XRP" else limit
#         logger.info(f"Converted limit: {limit_drops}")
#
#         # Initialize the XRPL client to interact with the XRP ledger.
#         # If the client cannot be initialized, raise an exception.
#         client = get_xrpl_client()
#         if not client:
#             raise ConnectionError(ERROR_INITIALIZING_CLIENT)
#
#         # Create the sender's wallet from the provided seed. This is used to sign transactions.
#         sender_wallet = Wallet.from_seed(sender_seed)
#         logger.info(f"Sender wallet created: {sender_wallet.classic_address}")
#
#         # Fetch the current sequence number for the sender's account.
#         # The sequence number is required for submitting a transaction on the XRP Ledger.
#         account_info = client.request(xrpl.models.requests.AccountInfo(account=sender_wallet.classic_address))
#         if not account_info or not account_info.result:
#             raise ValueError('Unable to fetch account info')
#
#         sequence_number = account_info.result['account_data']['Sequence']
#         logger.info(f"Fetched sequence number: {sequence_number}")
#
#         # Fetch the current network fee to include in the transaction.
#         # The network fee is used to pay for processing the transaction.
#         response = client.request(Fee())
#         is_valid, response = validate_xrpl_response(response, required_keys=["drops"])
#         if not is_valid:
#             logger.error(f"Failed to fetch fees for {wallet_address}: {response}")
#             raise XRPLException('Error fetching fees.')
#
#         logger.info(f"Trust lines response: {response}")
#
#         # Extract the minimum fee from the response.
#         fee = response['drops']['minimum_fee']
#         logger.info(f"Fetched network fee: {fee}")
#
#         # Create a TrustSet transaction with the extracted parameters, including the fee and sequence number.
#         trust_set_tx = create_trust_set_transaction(currency, limit_drops, wallet_address,
#                                                     sender_wallet.classic_address, sequence_number, fee)
#         logger.info(f"Created TrustSet transaction: {trust_set_tx}")
#
#         # Sign the transaction with the sender's wallet.
#         signed_tx = xrpl.transaction.sign(trust_set_tx, sender_wallet)
#         logger.info(f"Signed transaction: {signed_tx}")
#
#         # Submit the signed transaction to the XRPL network.
#         response = submit(signed_tx, client)
#         is_valid, response = validate_xrpl_response(response, required_keys=["tx_json"])
#         if not is_valid:
#             logger.error(f"Failed to fetch fees for {wallet_address}: {response}")
#             raise XRPLException('Error fetching fees.')
#
#         logger.info(f"Trust lines response: {response}")
#
#         # Log the success and return the response to indicate that the trust line was set successfully.
#         logger.info(f"Trust line set successfully for account {wallet_address}")
#         return create_trust_set_response(response, wallet_address, currency, limit)
#
#     except Exception as e:
#         # Handle any exceptions by logging the error and returning a failure response.
#         return handle_error({'status': 'failure', 'message': f"{str(e)}"}, status_code=500, function_name=function_name)
#
#     finally:
#         # Log the total execution time for performance monitoring purposes.
#         logger.info(LEAVING_FUNCTION_LOG.format(function_name, total_execution_time_in_millis(start_time)))
