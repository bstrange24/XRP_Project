import json
import logging
from decimal import Decimal

import xrpl
from django.core.cache import cache
from django.core.paginator import Paginator
from django.db import transaction
from django.http import JsonResponse
from rest_framework.decorators import api_view
from rest_framework.pagination import PageNumberPagination
from tenacity import retry, wait_exponential, stop_after_attempt
from xrpl.core import addresscodec
from xrpl.core.addresscodec import is_valid_classic_address
from xrpl.models import AccountTx, Tx, AccountDelete, Payment, AccountLines, AccountOffers, ServerInfo, TrustSet
from xrpl.models.requests import AccountInfo
from xrpl.models.requests import Ledger
from xrpl.models.transactions import AccountSet
from xrpl.transaction import sign_and_submit
from xrpl.transaction import submit_and_wait
from xrpl.utils import xrp_to_drops, drops_to_xrp
from xrpl.wallet import Wallet
from xrpl.wallet import generate_faucet_wallet

from .constants import ERROR_INITIALIZING_CLIENT, RETRY_BACKOFF, MAX_RETRIES, PAGINATION_PAGE_SIZE, \
    CACHE_TIMEOUT_FOR_WALLET, CACHE_TIMEOUT, CACHE_TIMEOUT_FOR_SERVER_INFO, ERROR_CREATING_ACCOUNT_INFO_OBJECT, \
    XRPL_RESPONSE, ERROR_IN_XRPL_RESPONSE, INVALID_WALLET_IN_REQUEST, ACCOUNT_IS_REQUIRED, JSON_RPC_URL
from .db_operations import save_account_data_to_databases
from .models import XrplAccountData, XrplPaymentData
from .utils import validate_account_id, get_xrpl_client, handle_error, get_account_reserves, validate_transaction_hash, \
    build_flags, is_valid_xrpl_seed, process_payment_response, create_payment_transaction, fetch_network_fee, \
    extract_request_data, validate_request_data, get_request_param

logger = logging.getLogger('xrpl_app')


class AccountInfoPagination(PageNumberPagination):
    page_size = PAGINATION_PAGE_SIZE


@api_view(['GET'])
@retry(wait=wait_exponential(multiplier=RETRY_BACKOFF), stop=stop_after_attempt(MAX_RETRIES))
def create_account(request):
    """
    This function creates a new XRP account using the XRPL testnet faucet. It:

    - Initializes an XRPL client for ledger interaction.
    - Generates a new wallet with test XRP funds.
    - Converts the wallet address to both classic and X-address formats.
    - Retrieves and logs the new account's information from the ledger.
    - Converts the initial balance from drops to XRP.
    - Saves the account details to a database for persistence.
    - Returns the newly created account details or handles errors if the process fails.
    - Uses retry logic to handle potential network issues.

    Parameters:
    - request: HTTP request object (not used but required by Django's view structure)

    Returns:
    - A JSON response with details of the new account if successful, or an error message if not.
    """

    function_name = 'create_account'
    logger.info(f"Entering: {function_name}")

    try:
        # Initialize the XRPL client for interacting with the ledger
        client = get_xrpl_client()
        if not client:
            return handle_error({'status': 'failure', 'message': ERROR_INITIALIZING_CLIENT},
                                status_code=500,
                                function_name=function_name)

        # Generate a new wallet using the XRPL testnet faucet for testing purposes
        new_wallet = generate_faucet_wallet(client, debug=True)
        if not new_wallet:
            return handle_error({'status': 'failure', 'message': "Error creating new wallet. Wallet is empty"},
                                status_code=500,
                                function_name=function_name)

        # Extract address information from the newly created wallet
        test_account = new_wallet.address
        test_xaddress = addresscodec.classic_address_to_xaddress(test_account, tag=12345, is_test_network=True)

        # Log the classic address and X-address for debugging
        logger.debug(f"Classic address: {test_account}")
        logger.debug(f"X-address: {test_xaddress}")

        # Prepare an AccountInfo request to get details about the new account
        account_info = AccountInfo(
            account=test_account,
            ledger_index="validated",
            strict=True,
        )
        if not account_info:
            return handle_error({'status': 'failure', 'message': ERROR_CREATING_ACCOUNT_INFO_OBJECT},
                                status_code=500,
                                function_name=function_name)

        # Send the AccountInfo request to the XRPL client
        response = client.request(account_info)
        if not response:
            return handle_error({'status': 'failure', 'message': ERROR_IN_XRPL_RESPONSE},
                                status_code=500,
                                function_name=function_name)

        # Log the raw response for detailed debugging
        logger.debug(XRPL_RESPONSE)
        logger.debug(json.dumps(response.result, indent=4, sort_keys=True))

        # Check if the account info response was successful
        if response.status == 'success':
            result = response.result

            # Extract balance information from the response
            balance_drops = result['account_data']['Balance']
            # Convert drops to XRP and round to 2 decimal places
            balance = round(drops_to_xrp(balance_drops), 2)
            ledger_hash = result['ledger_hash']
            previous_transaction_id = result['account_data']['PreviousTxnID']

            # Save the account details to the database
            save_account_data_to_databases(result, balance)

            # Return success response with wallet details
            return JsonResponse({
                'status': 'success',
                'message': 'Successfully created wallet.',
                'account_id': new_wallet.address,
                'secret': new_wallet.seed,
                'balance': balance,
                'transaction_hash': ledger_hash,
                'previous_transaction_id': previous_transaction_id,
            })
        else:
            # Handle the case where the account wasn't successfully funded
            return handle_error(
                {'status': 'failure', 'message': f"Failed to fund account via faucet. Response: {response.text}"},
                status_code=500, function_name=function_name)
    except Exception as e:
        # Catch any exceptions that occurred during account creation
        return handle_error({'status': 'failure', 'message': f"{str(e)}"}, status_code=500,
                            function_name=function_name)
    finally:
        # Ensure the client connection is closed to free up resources
        if 'client' in locals() and hasattr(client, 'close'):
            client.close()


@api_view(['GET'])
@retry(wait=wait_exponential(multiplier=RETRY_BACKOFF), stop=stop_after_attempt(MAX_RETRIES))
def get_wallet_info(request, wallet_address):
    """
    This function retrieves detailed information about an XRP wallet address. It:

    - Validates the wallet address format.
    - Checks for cached data to reduce API calls.
    - If not cached, queries the XRP Ledger for:
      - Account balance (converted from drops to XRP)
      - Account sequence number
      - Base reserve and reserve increment for account operations
    - Logs detailed information about the account for debugging.
    - Caches the fetched wallet info for future requests.
    - Handles errors for invalid addresses, non-existent accounts, and network issues.
    - Uses retry logic to manage potential transient network errors.

    Parameters:
    - request: HTTP request object (not used but required by Django's view structure)
    - wallet_address: The XRP wallet address to query

    Returns:
    - A JSON response with account details if successful, or an error message if not.
    """

    function_name = 'get_wallet_info'
    logger.info(f"Entering: {function_name}")

    # Validate the format of the provided wallet address
    if not validate_account_id(wallet_address):
        return handle_error({'status': 'failure', 'message': INVALID_WALLET_IN_REQUEST},
                            status_code=500,
                            function_name=function_name)

    # Check if wallet information is already in cache to avoid unnecessary API calls
    cache_key = f"get_wallet_info:{wallet_address}"
    cached_data = cache.get(cache_key)
    if cached_data:
        logger.info(f"Cache hit for wallet address: {wallet_address}")
        logger.debug(f"Cached data type: {type(cached_data)} - Value: {cached_data}")
        if isinstance(cached_data, dict):
            return JsonResponse(cached_data)
        else:
            return handle_error({'status': 'failure', 'message': 'Cached data is not a valid dictionary.'},
                                status_code=500,
                                function_name=function_name)

    logger.info(f"Cache missed for wallet address: {wallet_address}")

    try:
        # Initialize XRPL client for making requests
        client = get_xrpl_client()
        if not client:
            return handle_error({'status': 'failure', 'message': ERROR_INITIALIZING_CLIENT},
                                status_code=500,
                                function_name=function_name)

        # Create an AccountInfo request for the given wallet address
        account_info_request = AccountInfo(
            account=wallet_address,
            ledger_index="validated"
        )
        if not account_info_request:
            return handle_error({'status': 'failure', 'message': ERROR_CREATING_ACCOUNT_INFO_OBJECT},
                                status_code=500,
                                function_name=function_name)

        # Send the AccountInfo request to the XRPL
        response = client.request(account_info_request)
        if not response:
            return handle_error({'status': 'failure', 'message': ERROR_IN_XRPL_RESPONSE},
                                status_code=500,
                                function_name=function_name)

        # Check if the request was successful
        if not response.is_successful():
            return handle_error({'status': 'failure', 'message': f'Account not found on XRPL. Response: {response}'},
                                status_code=404,
                                function_name=function_name)

        # Extract result from the response
        result = response.result

        # Log the raw response for detailed debugging
        logger.debug(XRPL_RESPONSE)
        logger.debug(json.dumps(result, indent=4, sort_keys=True))

        # Extract account details from the result
        account_data = result['account_data']
        current_sequence = account_data['Sequence']
        balance_drops = account_data['Balance']

        # Convert balance from drops to XRP and round
        balance = round(drops_to_xrp(balance_drops), 2)

        # Fetch reserve data which is needed for account operations
        base_reserve, reserve_increment = get_account_reserves()
        if base_reserve is None or reserve_increment is None:
            return handle_error({'status': 'failure', 'message': 'Failed to fetch reserve data.'}, status_code=500,
                                function_name=function_name)

        # Log the account details for debugging or monitoring
        logger.info(
            f"Account found: {wallet_address}, Balance: {balance}, Base Reserve: {base_reserve}, Reserve Increment: {reserve_increment}")

        # Prepare the response data structure
        response_data = {
            'status': 'success',
            'message': 'Successfully retrieved account information.',
            'reserve': base_reserve,
            'reserve_increment': reserve_increment,
            'result': result,
        }

        # Cache the response to speed up future requests for this wallet
        cache.set(cache_key, response_data, CACHE_TIMEOUT_FOR_WALLET)

        return JsonResponse(response_data)

    except (xrpl.XRPLException, Exception) as e:
        # Handle exceptions like XRPL errors, network issues, or other unexpected errors
        return handle_error({'status': 'failure', 'message': f"{str(e)}"}, status_code=500,
                            function_name=function_name)
    finally:
        # Ensure that the client connection is closed to free up resources
        if 'client' in locals() and hasattr(client, 'close'):
            client.close()


@api_view(['GET'])
@retry(wait=wait_exponential(multiplier=RETRY_BACKOFF), stop=stop_after_attempt(MAX_RETRIES))
def check_wallet_balance(request, wallet_address):
    """
    This function checks the balance of an XRP wallet address. It:

    - Validates the wallet address format.
    - Attempts to retrieve balance from cache first to reduce server load.
    - If not cached, it queries the XRP Ledger for the wallet's balance.
    - Converts the balance from drops (XRPL's smallest unit) to XRP.
    - Caches the result for future requests.
    - Handles errors related to invalid addresses, non-existent accounts, and network issues.
    - Uses retry logic for robustness against temporary network failures.

    Parameters:
    - request: HTTP request object (not used but required by Django's view structure)
    - wallet_address: The XRP wallet address to check

    Returns:
    - A JSON response with the status, message, and balance if successful, or an error message if not.
    """

    function_name = 'check_wallet_balance'
    logger.info(f"Entering: {function_name}")

    # Validate the format of the wallet address to ensure it's correct
    if not validate_account_id(wallet_address):
        return handle_error({'status': 'failure', 'message': INVALID_WALLET_IN_REQUEST},
                            status_code=500,
                            function_name=function_name)

    # Check if the balance information is already cached
    cache_key = f"check_wallet_balance:{wallet_address}"
    cached_data = cache.get(cache_key)
    if cached_data:
        logger.info(f"Cache hit for wallet address: {wallet_address}")
        logger.debug(f"Cached data type: {type(cached_data)} - Value: {cached_data}")
        if isinstance(cached_data, dict):
            return JsonResponse(cached_data)
        else:
            return handle_error({'status': 'failure', 'message': 'Cached data is not a valid dictionary.'},
                                status_code=500,
                                function_name=function_name)

    # Log that there's no cache hit, meaning we need to fetch fresh data
    logger.info(f"Cache missed for wallet address: {wallet_address}")
    logger.info(f"Request received to check balance for address: {wallet_address}")

    try:
        # Initialize the XRPL client to query the ledger
        client = get_xrpl_client()
        if not client:
            return handle_error({'status': 'failure', 'message': ERROR_INITIALIZING_CLIENT},
                                status_code=500,
                                function_name=function_name)

        # Create an AccountInfo request for the wallet's balance
        account_info_request = AccountInfo(
            account=wallet_address
        )
        if not account_info_request:
            return handle_error({'status': 'failure', 'message': ERROR_CREATING_ACCOUNT_INFO_OBJECT},
                                status_code=500,
                                function_name=function_name)

        # Send the request to fetch account information
        response = client.request(account_info_request)
        if not response:
            return handle_error({'status': 'failure', 'message': ERROR_IN_XRPL_RESPONSE},
                                status_code=500,
                                function_name=function_name)

        # Log the raw response for detailed debugging
        logger.debug(XRPL_RESPONSE)
        logger.debug(json.dumps(response.result, indent=4, sort_keys=True))

        # Check if the response from XRPL was successful
        if not response.is_successful():
            return handle_error({'status': 'failure', 'message': f'Account not found on XRPL. Response: {response}'},
                                status_code=404,
                                function_name=function_name)

        # Extract balance from the response. Balance in XRPL is in drops, so convert to XRP
        balance_in_drops = int(response.result["account_data"]["Balance"])
        balance_in_xrp = round(drops_to_xrp(str(balance_in_drops)), 2)

        # Log the successful balance check
        logger.info(f"Balance for address {wallet_address} retrieved successfully: {balance_in_xrp} XRP")

        # Prepare the response data
        response_data = {
            'status': 'success',
            'message': 'Successfully retrieved account balance.',
            "balance": balance_in_xrp,
        }

        # Cache the balance for future queries to reduce network load
        cache.set(cache_key, response_data, CACHE_TIMEOUT)

        return JsonResponse(response_data)

    except (xrpl.XRPLException, Exception) as e:
        # Handle exceptions like network errors or XRPL-specific exceptions
        return handle_error({'status': 'failure', 'message': f"{str(e)}"},
                            status_code=500,
                            function_name=function_name)
    finally:
        # Ensure the client resource is released by closing the connection
        if 'client' in locals() and hasattr(client, 'close'):
            client.close()


@api_view(['GET'])
@retry(wait=wait_exponential(multiplier=RETRY_BACKOFF), stop=stop_after_attempt(MAX_RETRIES))
def account_set(request):
    """
    This function updates the settings of an XRP account. It:

    - Extracts and validates necessary parameters from the HTTP GET request.
    - Uses these parameters to configure account settings like requiring destination tags, disabling the master key, or enabling a regular key.
    - Constructs and submits an AccountSet transaction to modify the account settings on the XRP Ledger.
    - Logs the process for debugging and monitoring.
    - Handles errors related to missing parameters, transaction failures, or network issues.
    - Uses retry logic to ensure reliability against temporary network failures.

    Parameters:
    - request: HTTP request object containing account settings to update.

    Returns:
    - A JSON response indicating success or failure, including transaction details or error messages.
    """

    function_name = 'account_set'
    logger.info(f"Entering: {function_name}")

    # Extract and validate parameters from the request
    sender_seed = get_request_param(request, 'sender_seed', function_name=function_name)

    # sender_seed = request.GET.get('sender_seed')
    # if not sender_seed:
    #     # If sender_seed is missing, return an error immediately
    #     return handle_error({'status': 'failure', 'message': "Missing request parameter."}, status_code=500,
    #                         function_name=function_name)

    # Parse boolean parameters for account settings
    require_destination_tag = request.GET.get('require_destination_tag', 'false').lower() == 'true'
    disable_master_key = request.GET.get('disable_master_key', 'false').lower() == 'true'
    enable_regular_key = request.GET.get('enable_regular_key', 'false').lower() == 'true'

    # Log the settings for debugging or monitoring
    logger.info(
        f"require_destination_tag: {require_destination_tag}, disable_master_key: {disable_master_key}, enable_regular_key: {enable_regular_key}")

    try:
        # Create a wallet from the seed to get the sender's address
        sender_wallet = Wallet.from_seed(sender_seed)
        sender_address = sender_wallet.classic_address

        # Build flags for the AccountSet transaction based on the provided settings
        flags = build_flags(require_destination_tag, disable_master_key, enable_regular_key)

        # Prepare the AccountSet transaction with the calculated flags
        account_set_tx = AccountSet(
            account=sender_address,
            flags=flags
        )
        if account_set_tx is None:
            return handle_error({'status': 'failure', 'message': "Error creating Account Set."}, status_code=500,
                                function_name=function_name)

        # Initialize the XRPL client
        client = get_xrpl_client()
        if not client:
            return handle_error({'status': 'failure', 'message': ERROR_INITIALIZING_CLIENT},
                                status_code=500,
                                function_name=function_name)

        # Submit and wait for the transaction to be included in a ledger
        response = submit_and_wait(account_set_tx, client, sender_wallet)
        if not response:
            return handle_error({'status': 'failure', 'message': "Error submit_and_wait return None."},
                                status_code=500,
                                function_name=function_name)

        # Log the raw response for detailed debugging
        logger.debug(XRPL_RESPONSE)
        logger.debug(json.dumps(response.result, indent=4, sort_keys=True))

        # Check if the transaction was successful
        if response.is_successful():
            logger.info(f"AccountSet transaction successful for account {sender_address}")
            # Prepare success response data
            response_data = {
                'status': 'success',
                'message': 'Successfully updated account settings.',
                'transaction_hash': response.result['hash'],
                'account': sender_address,
                'settings': response.result
            }
            return JsonResponse(response_data)
        else:
            # Return an error if the transaction failed
            return handle_error({'status': 'failure',
                                 'message': f"AccountSet transaction failed for account {sender_address}. Response: {response}"},
                                status_code=500, function_name=function_name)

    except (xrpl.XRPLException, Exception) as e:
        # Handle any exceptions that occur during the process
        return handle_error({'status': 'failure', 'message': f"{str(e)}"},
                            status_code=500, function_name=function_name)
    finally:
        # Ensure the XRPL client connection is closed to free up resources
        if 'client' in locals() and hasattr(client, 'close'):
            client.close()


@api_view(['GET'])
@retry(wait=wait_exponential(multiplier=RETRY_BACKOFF), stop=stop_after_attempt(MAX_RETRIES))
def get_transaction_history(request, wallet_address, previous_transaction_id):
    """
    This function retrieves the history of a specific transaction for a given XRP wallet address. It:

    - Validates both the wallet address and the transaction hash format.
    - Queries the XRP Ledger for transactions associated with the wallet address.
    - Searches for a transaction matching the provided hash among the fetched transactions.
    - If found, returns the details of that transaction.
    - If not found or if there's an error, it returns appropriate error responses.
    - Utilizes retry logic to manage potential network issues.

    Parameters:
    - request: HTTP request object (not used but required by Django's view structure)
    - wallet_address: The XRP wallet address to check for transactions
    - transaction_hash: The specific transaction hash to look for

    Returns:
    - A JSON response with the transaction details if found, or an error message if not found or if an error occurs.
    """

    function_name = 'get_transaction_history'
    logger.info(f"Entering: {function_name}")

    # Validate the format of the wallet address
    if not validate_account_id(wallet_address):
        return handle_error({'status': 'failure', 'message': INVALID_WALLET_IN_REQUEST},
                            status_code=500,
                            function_name=function_name)

    # Validate the format of the transaction hash
    if not validate_transaction_hash(previous_transaction_id):
        return handle_error({'status': 'failure', 'message': 'Invalid transaction hash.'}, status_code=500,
                            function_name=function_name)

    try:
        # Initialize the XRPL client for querying the ledger
        client = get_xrpl_client()
        if not client:
            return handle_error({'status': 'failure', 'message': ERROR_INITIALIZING_CLIENT},
                                status_code=500,
                                function_name=function_name)

        # Prepare an AccountTx request to fetch transactions for the given account
        account_tx_request = AccountTx(
            account=wallet_address,
            limit=100  # Increase limit to fetch more transactions at once, reducing the need for multiple requests
        )
        if not account_tx_request:
            return handle_error({'status': 'failure', 'message': "Error getting AccountTx."},
                                status_code=500,
                                function_name=function_name)

        # Send the request to XRPL to get transaction history
        response = client.request(account_tx_request)
        if not response:
            return handle_error({'status': 'failure', 'message': ERROR_IN_XRPL_RESPONSE},
                                status_code=500,
                                function_name=function_name)

        # Log the raw response for detailed debugging
        logger.debug(XRPL_RESPONSE)
        logger.debug(json.dumps(response.result, indent=4, sort_keys=True))

        # Check if the response contains any transactions
        if 'transactions' in response.result:
            for transaction in response.result['transactions']:
                # Look for the specific transaction by comparing hash
                if str(transaction['hash']) == previous_transaction_id:  # Match the actual transaction hash
                    logger.debug("Transaction found:")
                    logger.debug(json.dumps(transaction, indent=4, sort_keys=True))

                    # Prepare and return the found transaction
                    response_data = {
                        'status': 'success',
                        'message': 'Transaction history successfully retrieved.',
                        'response': transaction,
                    }
                    return JsonResponse(response_data)

            # If no match is found after checking all transactions
            return handle_error(
                {'status': 'failure', 'message': f'Transaction not found in the recent history. Response: {response}'},
                status_code=404, function_name=function_name)
        else:
            # If the response doesn't contain a 'transactions' key, something went wrong
            return handle_error(
                {'status': 'failure', 'message': f'Error fetching transaction history info. Response: {response}'},
                status_code=500, function_name=function_name)

    except (xrpl.XRPLException, Exception) as e:
        # Handle exceptions like XRPL-specific errors, network issues, or unexpected errors
        return handle_error({'status': 'failure', 'message': f"{str(e)}"},
                            status_code=500, function_name=function_name)
    finally:
        # Ensure client resources are freed by closing the connection
        if 'client' in locals() and hasattr(client, 'close'):
            client.close()


@api_view(['GET'])
@retry(wait=wait_exponential(multiplier=RETRY_BACKOFF), stop=stop_after_attempt(MAX_RETRIES))
def get_transaction_history_with_pagination(request, wallet_address):
    """
    This function retrieves transaction history for a given XRP wallet address with pagination support. It:

    - Validates the wallet address format.
    - Queries the XRP Ledger for all transactions associated with the wallet address, using pagination to handle large sets of transactions.
    - Supports pagination through query parameters for 'page' and 'page_size'.
    - Returns a paginated list of transactions, along with total count and pagination metadata.
    - Uses retry logic to handle potential network issues.

    Parameters:
    - request: HTTP request object containing pagination parameters.
    - wallet_address: The XRP wallet address whose transaction history is to be fetched.

    Returns:
    - A JSON response containing paginated transaction data, or an error message if something goes wrong.
    """

    function_name = 'get_transaction_history_with_pagination'
    logger.info(f"Entering: {function_name}")

    # Validate the wallet address format
    if not validate_account_id(wallet_address):
        return handle_error({'status': 'failure', 'message': INVALID_WALLET_IN_REQUEST},
                            status_code=500,
                            function_name=function_name)

    try:
        # Initialize the XRPL client for querying transactions
        client = get_xrpl_client()
        if not client:
            return handle_error({'status': 'failure', 'message': ERROR_INITIALIZING_CLIENT},
                                status_code=500,
                                function_name=function_name)

        transactions = []
        marker = None

        # Loop to fetch all transactions for the account, using pagination through 'marker'
        while True:
            account_tx_request = AccountTx(
                account=wallet_address,
                ledger_index_min=-1,  # Fetch from the earliest ledger
                ledger_index_max=-1,  # Fetch up to the latest ledger
                limit=100,  # Number of transactions to retrieve per request
                marker=marker,  # Use marker for pagination
            )
            response = client.request(account_tx_request)
            if not response:
                return handle_error({'status': 'failure', 'message': ERROR_IN_XRPL_RESPONSE},
                                    status_code=500,
                                    function_name=function_name)

            # Log the raw response for detailed debugging
            logger.debug(XRPL_RESPONSE)
            logger.debug(json.dumps(response.result, indent=4, sort_keys=True))

            # Add fetched transactions to the list
            if "transactions" not in response.result:
                return handle_error(
                    {'status': 'failure', 'message': 'Error fetching transaction history. Unexpected response format.'},
                    status_code=500, function_name=function_name
                )

            transactions.extend(response.result["transactions"])

            # Log the transactions for debugging
            logger.debug(json.dumps(response.result["transactions"], indent=4, sort_keys=True))

            # Check if there are more pages of transactions to fetch
            marker = response.result.get("marker")
            if not marker:
                break

        # Extract pagination parameters from the request
        page = int(request.GET.get('page', 1))
        page_size = int(request.GET.get('page_size', 10))

        # Paginate the transactions
        paginator = Paginator(transactions, page_size)
        paginated_transactions = paginator.get_page(page)

        # Prepare the response data including pagination information
        data = {
            "status": "success",
            "message": "Transaction history successfully retrieved.",
            "transactions": list(paginated_transactions),
            "total_transactions": paginator.count,
            "pages": paginator.num_pages,
            "current_page": paginated_transactions.number,
        }

        # Log successful transaction history fetch
        logger.info(f"Transaction history fetched for address: {wallet_address}")
        return JsonResponse(data)

    except Exception as e:
        # Handle any exceptions that occur during the process
        return handle_error({'status': 'failure', 'message': f"{str(e)}"},
                            status_code=500, function_name=function_name)
    finally:
        # Ensure the client connection is closed to free resources
        if 'client' in locals() and hasattr(client, 'close'):
            client.close()


@api_view(['GET'])
@retry(wait=wait_exponential(multiplier=RETRY_BACKOFF), stop=stop_after_attempt(MAX_RETRIES))
def check_transaction_status(request, tx_hash):
    """
    This function checks the status of a specific transaction on the XRP Ledger. It:

    - Validates that a transaction hash is provided.
    - Queries the XRP Ledger to fetch details of the transaction.
    - Logs the process for debugging, including the raw response.
    - Returns transaction details if successful or handles errors if the transaction is not found or other issues occur.
    - Uses retry logic to manage potential network issues.

    Parameters:
    - request: HTTP request object (not used but required by Django's view structure)
    - tx_hash: The hash of the transaction whose status is to be checked

    Returns:
    - A JSON response with transaction status details if successful, or an error message if not.
    """

    function_name = 'check_transaction_status'
    logger.info(f"Entering: {function_name}")

    # Ensure the transaction hash is provided
    if not tx_hash:
        return handle_error({'status': 'failure', 'message': "Error transaction hash is None."},
                            status_code=500,
                            function_name=function_name)

    # Check if the transaction hash is valid **BEFORE** calling XRPL
    if not validate_transaction_hash(tx_hash):
        return handle_error({'status': 'failure', 'message': "Invalid transaction hash."},
                            status_code=500,
                            function_name=function_name)

    # Log the start of the transaction status check for debugging purposes
    logger.info(f"Checking transaction status for hash: {tx_hash}")

    try:
        # Initialize the XRPL client for transaction status checks
        client = get_xrpl_client()
        if not client:
            return handle_error({'status': 'failure', 'message': ERROR_INITIALIZING_CLIENT},
                                status_code=500,
                                function_name=function_name)

        # Create a transaction request object to fetch details of the specified transaction
        tx_request = Tx(transaction=tx_hash)
        if not tx_request:
            return handle_error({'status': 'failure', 'message': "Transaction Tx is none."},
                                status_code=500,
                                function_name=function_name)

        # Send the request to the XRPL to get the transaction details
        response = client.request(tx_request)
        if not response.result or "validated" not in response.result:
            return handle_error(
                {'status': 'failure',
                 'message': 'Error while checking transaction status: Unexpected API response format'},
                status_code=500,
                function_name=function_name
            )

        # Log the raw response for detailed debugging
        logger.debug(XRPL_RESPONSE)
        logger.debug(json.dumps(response.result, indent=4, sort_keys=True))

        # Log the raw response for detailed debugging
        logger.info(f"Raw XRPL response for transaction {tx_hash}: {response}")

        # Check if the transaction status was successfully retrieved
        if response.is_successful():
            # Log success for the transaction status check
            logger.info(f"Transaction status retrieved successfully for hash: {tx_hash}")
            # Return the transaction details in JSON format
            return JsonResponse({
                'status': 'success',
                'message': 'Payment successfully sent.',
                'result': response.result,  # Corrected from 'response.result' to 'result'
            })
        else:
            # If the transaction status could not be retrieved, log and handle the failure
            return handle_error(
                {'status': 'failure', 'message': f'Error retrieving transaction status. Response: {response}'},
                status_code=500, function_name=function_name)
    except (xrpl.XRPLException, Exception) as e:
        # Catch any exceptions that occur during the transaction status check
        return handle_error(
            {'status': 'failure', 'message': f"Error while checking transaction status for hash {tx_hash}: {str(e)}"},
            status_code=500, function_name=function_name)
    finally:
        # Ensure the XRPL client is closed to release resources
        if 'client' in locals() and hasattr(client, 'close'):
            client.close()


# @api_view(['POST'])
# @retry(wait=wait_exponential(multiplier=RETRY_BACKOFF), stop=stop_after_attempt(MAX_RETRIES))
# def send_payment(request):
#     """
#     Handles sending an XRP payment from one account to another.
#     """
#     function_name = 'send_payment'
#     logger.info(f"Entering: {function_name}")
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
#                 return handle_error({'status': 'failure', 'message': ERROR_INITIALIZING_CLIENT}, 500, function_name)
#
#             # Create sender wallet
#             sender_wallet = Wallet.from_seed(sender_seed)
#             sender_address = sender_wallet.classic_address
#
#             # Get network fee
#             fee_drops = fetch_network_fee(client)
#
#             # Create and submit the payment transaction
#             payment_transaction = create_payment_transaction(sender_address, receiver_address, amount_drops, fee_drops)
#             payment_response = submit_and_wait(payment_transaction, client, sender_wallet)
#
#             # Handle the transaction response
#             return process_payment_response(payment_response, sender_address, receiver_address, amount_xrp, fee_drops)
#
#     except (xrpl.XRPLException, Exception) as e:
#         return handle_error({'status': 'failure', 'message': str(e)}, 500, function_name)
#
#     finally:
#         # Ensure the client connection is closed
#         if 'client' in locals() and hasattr(client, 'close'):
#             client.close()

@api_view(['POST'])
@retry(wait=wait_exponential(multiplier=RETRY_BACKOFF), stop=stop_after_attempt(MAX_RETRIES))
def send_payment(request):
    """
    This function sends a payment from one XRP account to another. It:

    - Extracts payment details from the request including sender's seed, receiver's address, and amount in XRP.
    - Validates that all necessary parameters are provided.
    - Converts the amount to drops (the smallest unit in XRP Ledger).
    - Uses Django's transaction.atomic() to ensure database operations are atomic.
    - Constructs and submits a Payment transaction to the XRP Ledger.
    - Upon success, it:
      - Logs the transaction hash.
      - Saves payment details to the database.
      - Updates or creates balance entries for sender and receiver in the database.
    - Handles errors related to missing parameters, transaction failures, or network issues.
    - Uses retry logic for robustness against temporary network failures.

    Parameters:
    - request: HTTP request object containing payment details.

    Returns:
    - A JSON response indicating success or failure of the payment, including transaction details or error messages.
    """

    function_name = 'send_payment'
    logger.info(f"Entering: {function_name}")

    # Debugging request data
    logger.debug(f"Request.GET: {request.GET}")
    logger.debug(f"Request.POST: {request.POST}")

    # Extract payment details from the request and handle both query params and request body
    sender_seed = get_request_param(request, 'sender_seed', function_name=function_name)
    receiver_address = get_request_param(request, 'receiver', function_name=function_name)
    amount_xrp = get_request_param(request, 'amount', default="0", convert_func=Decimal, function_name=function_name)

    # Validate that all required parameters are present
    if not all([sender_seed, receiver_address, amount_xrp]):
        return handle_error({'status': 'failure', 'message': 'Missing required parameters.'}, status_code=500,
                            function_name=function_name)

    if not is_valid_classic_address(receiver_address):
        return handle_error({'status': 'failure', 'message': INVALID_WALLET_IN_REQUEST},
                            status_code=500,
                            function_name=function_name)

    if not is_valid_xrpl_seed(sender_seed):
        return handle_error({'status': 'failure', 'message': 'S parameter is invalid'},
                            status_code=500,
                            function_name=function_name)

    # Convert amount from XRP to drops for XRPL transaction
    amount_drops = xrp_to_drops(amount_xrp)

    try:
        # Use Django's transaction to ensure all database operations are atomic
        with transaction.atomic():
            # Initialize the XRPL client.
            client = get_xrpl_client()
            if not client:
                return handle_error({'status': 'failure', 'message': ERROR_INITIALIZING_CLIENT},
                                    status_code=500,
                                    function_name=function_name)

            # Generate wallet from seed for the sender
            sender_wallet = Wallet.from_seed(sender_seed)
            sender_address = sender_wallet.classic_address

            # Fetch the recommended fee from the XRPL
            server_info = client.request(ServerInfo())
            if not server_info:
                return handle_error({'status': 'failure', 'message': "Error initializing server info."},
                                    status_code=500,
                                    function_name=function_name)

            raw_fee_xrp = Decimal(server_info.result['info']['validated_ledger']['base_fee_xrp'])  # Convert to Decimal
            fee_drops = xrp_to_drops(raw_fee_xrp)
            logger.debug(f"Fee from the server: {raw_fee_xrp}")
            logger.debug(f"Fee in drops: {fee_drops}")

            # Construct the Payment transaction
            payment_transaction = Payment(
                account=sender_address,
                destination=receiver_address,
                amount=amount_drops,
                fee=str(fee_drops),
            )

            # Submit the transaction and wait for confirmation
            payment_response = submit_and_wait(payment_transaction, client, sender_wallet)
            if not payment_response.is_successful():
                error_message = payment_response.result.get("error", "Unknown error")  # Extract actual error
                return handle_error({'status': 'failure', 'message': f'Payment failed due to: {error_message}'},
                                    status_code=500,
                                    function_name=function_name)

            # Log the raw response for detailed debugging
            logger.debug(XRPL_RESPONSE)
            logger.debug(json.dumps(payment_response.result, indent=4, sort_keys=True))

            if payment_response.is_successful():
                transaction_hash = payment_response.result['hash']
                logger.info(f"Payment successful: {transaction_hash}")

                # Save the transaction details to the database
                payment = XrplPaymentData(
                    sender=sender_address,
                    receiver=receiver_address,
                    amount=amount_xrp,
                    transaction_hash=transaction_hash,
                )
                payment.save()

                # Update sender's balance in the database
                sender_account = XrplAccountData.objects.get(account=sender_address)
                sender_account.balance -= amount_xrp
                sender_account.save()

                # Check if receiver exists, if not, create with initial balance, otherwise update balance
                receiver_account, created = XrplAccountData.objects.get_or_create(
                    account=receiver_address,
                    defaults={'balance': amount_xrp}
                )
                if not created:
                    receiver_account.balance += amount_xrp
                    receiver_account.save()

                # Return success response with transaction details
                return JsonResponse({
                    'status': 'success',
                    'message': 'Payment successfully sent.',
                    'transaction_hash': transaction_hash,
                    'sender': sender_address,
                    'receiver': receiver_address,
                    'amount': amount_xrp,
                    'fee_drops': fee_drops,
                })
            else:
                # Handle unsuccessful transaction
                return handle_error({'status': 'failure', 'message': f'Payment failed. Response: {payment_response}'},
                                    status_code=500,
                                    function_name=function_name)
    except (xrpl.XRPLException, Exception) as e:
        # Handle exceptions like XRPL errors, network issues, or database errors
        return handle_error({'status': 'failure', 'message': f"{str(e)}"}, status_code=500,
                            function_name=function_name)
    finally:
        # Ensure the client connection is closed to free resources
        if 'client' in locals() and hasattr(client, 'close'):
            client.close()


@api_view(['DELETE'])
@retry(wait=wait_exponential(multiplier=RETRY_BACKOFF), stop=stop_after_attempt(MAX_RETRIES))
def delete_account(request, wallet_address):
    """
    This function is designed to delete an XRP account from the ledger. It:

    - Uses the HTTP DELETE method for RESTful compliance.
    - Validates the wallet address format and checks for necessary parameters like sender's seed.
    - Checks if the account's balance is zero before attempting deletion, as an account can only be deleted if it has no balance.
    - If conditions are met, it:
      - Prepares and submits an AccountDelete transaction to the XRP Ledger.
      - Signs the transaction with the provided seed.
      - Returns success or failure information based on the transaction's outcome.
    - Handles errors for invalid addresses, non-zero balance, or other issues during the process.
    - Utilizes retry logic to manage potential network failures.

    Parameters:
    - request: HTTP request object containing the sender's seed for signing.
    - wallet_address: The XRP address of the account to be deleted.

    Returns:
    - A JSON response indicating whether the account was successfully deleted or if an error occurred.
    """

    function_name = 'delete_account'
    logger.info(f"Entering: {function_name}")

    # Validate the provided wallet address format
    if not validate_account_id(wallet_address):
        return handle_error({'status': 'failure', 'message': INVALID_WALLET_IN_REQUEST},
                            status_code=500,
                            function_name=function_name)

    # Extract the sender's seed from the request parameters
    # sender_seed = request.GET.get('sender_seed')
    sender_seed = get_request_param(request, 'sender_seed', function_name=function_name)
    if not sender_seed:
        return handle_error({'status': 'failure', 'message': "Missing required parameters."},
                            status_code=500,
                            function_name=function_name)

    try:
        # Initialize the XRPL client for ledger operations
        client = get_xrpl_client()
        if not client:
            return handle_error({'status': 'failure', 'message': ERROR_INITIALIZING_CLIENT},
                                status_code=500,
                                function_name=function_name)

        # Step 1: Check the wallet balance
        account_info_request = AccountInfo(
            account=wallet_address,
            ledger_index="validated",  # Use the latest validated ledger
            strict=True,
        )
        if not account_info_request:
            return handle_error({'status': 'failure', 'message': ERROR_CREATING_ACCOUNT_INFO_OBJECT},
                                status_code=500,
                                function_name=function_name)

        # Request account information from XRPL
        response = client.request(account_info_request)
        if not response:
            return handle_error({'status': 'failure', 'message': ERROR_IN_XRPL_RESPONSE},
                                status_code=500,
                                function_name=function_name)

        # Log the raw response for detailed debugging
        logger.debug(XRPL_RESPONSE)
        logger.debug(json.dumps(response.result, indent=4, sort_keys=True))

        # Extract balance from the response, converting drops to XRP
        account_data = response.result
        balance = int(account_data['account_data']['Balance']) / 1_000_000  # Convert drops to XRP

        # Check if the balance is zero before proceeding with deletion
        if balance == 0:
            # Step 2: Prepare the AccountDelete transaction
            account_delete_tx = AccountDelete(
                account=wallet_address,
                destination=wallet_address,  # Destination must be the same address for deletion
                fee="12",  # Standard XRP transaction fee
            )
            if not account_delete_tx:
                return handle_error({'status': 'failure', 'message': "Error creating Account Delete."},
                                    status_code=500,
                                    function_name=function_name)

            # Create a wallet object from the sender's seed for signing the transaction
            signer = Wallet(sender_seed, 'False')

            # Step 3: Sign and submit the transaction to the XRPL
            tx_response = sign_and_submit(account_delete_tx, client, signer)
            if not tx_response:
                return handle_error({'status': 'failure', 'message': "Error creating sign_and_submit."},
                                    status_code=500,
                                    function_name=function_name)

            # Check if the transaction was successful
            if tx_response.is_successful():
                return JsonResponse({
                    'status': 'success',
                    'message': 'Account successfully deleted.',
                    'tx_response': tx_response.result,
                })
            else:
                # If transaction failed, return error with details
                return handle_error({'status': 'failure',
                                     'message': f'Error submitting AccountDelete transaction. Response: {response}',
                                     'details': tx_response.result}, status_code=500, function_name=function_name)
        else:
            # If balance is not zero, do not proceed with deletion
            return handle_error({'status': 'failure', 'message': 'Balance is not zero, no action taken.'},
                                status_code=500, function_name=function_name)
    except (xrpl.XRPLException, Exception) as e:
        # Handle exceptions that could occur during account deletion
        return handle_error({'status': 'failure', 'message': f"{str(e)}"},
                            status_code=500, function_name=function_name)
    finally:
        # Ensure the XRPL client is closed to free resources
        if 'client' in locals() and hasattr(client, 'close'):
            client.close()


@api_view(['POST'])
@retry(wait=wait_exponential(multiplier=RETRY_BACKOFF), stop=stop_after_attempt(MAX_RETRIES))
def send_and_delete_wallet(request, destination_address):
    """
       Sends the maximum amount of XRP from the sender's wallet, including the reserve,
       to the destination wallet, and deletes the sender's wallet.

       Workflow:
       1. Calculate the transferable XRP by subtracting the base reserve from the sender's total balance.
       2. Create and submit a Payment transaction to transfer the calculated amount to the destination address.
       3. Create and submit an AccountDelete transaction to delete the sender's wallet and send the reserve balance to the destination address.
       4. Handle any errors or exceptions that might occur during the process.

       Parameters:
           request: HTTP request object containing the sender's seed for signing.
           destination_address (str): The wallet address to receive the funds and account deletion.

       Returns:
           JsonResponse: A JSON response containing the transaction results or any error details.

       Note:
           - The destination wallet must exist on the XRPL for the AccountDelete transaction to succeed.
           - This function assumes that the sending wallet has enough XRP to cover the network fees and base reserve.
           - Both transactions (Payment and AccountDelete) are submitted sequentially.

       Raises:
           ValueError: If the sender's wallet balance is insufficient to cover the reserve and fees.
           xrpl.clients.XRPLRequestFailureException: If the XRPL client encounters an error during request submission.
       """

    function_name = "send_and_delete_wallet"
    logger.info(f"Entering: {function_name}")

    # Validate the provided wallet address format
    if not validate_account_id(destination_address):
        return handle_error({'status': 'failure', 'message': INVALID_WALLET_IN_REQUEST},
                            status_code=500,
                            function_name=function_name)

    # Extract the sender's seed from the request parameters
    # sender_seed = request.GET.get('sender_seed')
    sender_seed = get_request_param(request, 'sender_seed', function_name=function_name)

    if not sender_seed:
        return handle_error({'status': 'failure', 'message': "Missing required parameters."},
                            status_code=500,
                            function_name=function_name)

    try:
        # Initialize the XRPL client for ledger operations
        client = get_xrpl_client()
        if not client:
            return handle_error({'status': 'failure', 'message': ERROR_INITIALIZING_CLIENT},
                                status_code=500,
                                function_name=function_name)

        # Create sender wallet
        sender_wallet = Wallet.from_seed(sender_seed)

        # Fetch account information for the sender wallet
        account_info_request = AccountInfo(
            account=sender_wallet.classic_address,
            ledger_index="validated"
        )
        if not account_info_request:
            return handle_error({'status': 'failure', 'message': ERROR_CREATING_ACCOUNT_INFO_OBJECT},
                                status_code=500,
                                function_name=function_name)

        # Request account information from XRPL
        account_info_response = client.request(account_info_request)
        if not account_info_response:
            return handle_error({'status': 'failure', 'message': ERROR_IN_XRPL_RESPONSE},
                                status_code=500,
                                function_name=function_name)

        # Check if the response from XRPL was successful
        if not account_info_response.is_successful():
            return handle_error(
                {'status': 'failure', 'message': f'Account not found on XRPL. Response: {account_info_response}'},
                status_code=404,
                function_name=function_name)

        # Extract the sender's balance and reserve requirements
        balance = int(account_info_response.result['account_data']['Balance'])
        base_reserve, reserve_increment = get_account_reserves()
        if base_reserve is None or reserve_increment is None:
            raise ValueError("Failed to retrieve reserve requirements from the XRPL.")

        # Calculate the transferable amount (balance minus the base reserve)
        transferable_amount = balance - xrp_to_drops(int(base_reserve))

        if transferable_amount <= 0:
            raise ValueError("Insufficient balance to cover the reserve and fees.")

        # Step 1: Send the transferable amount to the destination address
        payment_tx = Payment(
            account=sender_wallet.classic_address,
            destination=destination_address,
            amount=str(transferable_amount)  # Must be in drops
        )
        payment_response = submit_and_wait(payment_tx, client, sender_wallet)

        if not payment_response.is_successful():
            error_message = payment_response.result.get("error", "Unknown error")  # Extract actual error message
            return handle_error({'status': 'failure', 'message': f'Payment failed due to: {error_message}'},
                                status_code=500,
                                function_name=function_name)

        # Step 2: Delete the sender's account
        account_delete_tx = AccountDelete(
            account=sender_wallet.classic_address,
            destination=destination_address
        )
        account_delete_response = submit_and_wait(account_delete_tx, client, sender_wallet)

        if not account_delete_response.is_successful():
            raise ValueError(f"AccountDelete transaction failed: {account_delete_response.result}")

        return JsonResponse({
            'status': 'success',
            'message': 'Funds transferred and account deleted successfully.',
            'payment_tx_hash': payment_response.result['hash'],
            'account_delete_tx_hash': account_delete_response.result['hash']
        })
    except Exception as e:
        return JsonResponse({"status": "failure", "message": f"An error occurred: {str(e)}"}, status=500)


@api_view(['GET'])
@retry(wait=wait_exponential(multiplier=RETRY_BACKOFF), stop=stop_after_attempt(MAX_RETRIES))
def get_ledger_info(request):
    """
    This function retrieves information about a specific ledger from the XRP Ledger. It:

    - Accepts either a ledger index or hash to fetch specific ledger details.
    - Checks for cached data first to reduce load on the XRPL server.
    - If not cached, it queries the XRP Ledger for ledger information.
    - Caches the result for future requests to speed up subsequent calls.
    - Handles errors if the ledger cannot be retrieved or if parameters are missing.
    - Uses retry logic for robustness against temporary network issues.

    Parameters:
    - request: HTTP request object containing optional 'ledger_index' or 'ledger_hash' parameters.

    Returns:
    - A JSON response with ledger details if successful or an error message if not.
    """

    function_name = 'get_ledger_info'
    logger.info(f"Entering: {function_name}")

    try:
        # Retrieve ledger index or hash from query parameters
        ledger_index = request.GET.get('ledger_index', 'validated')  # Default to 'validated' if not specified
        ledger_hash = request.GET.get('ledger_hash', None)

        # Attempt to fetch from cache before making an API call
        cache_key = f"ledger_info_{ledger_index}_{ledger_hash or ''}"
        cached_response = cache.get(cache_key)

        if cached_response:
            # Log cache hit and return cached data
            logger.info(f"Returning cached ledger info for {ledger_index}/{ledger_hash}")
            return JsonResponse(cached_response)

        # Prepare the Ledger request based on whether hash or index is provided
        if ledger_hash:
            ledger_request = Ledger(ledger_hash=ledger_hash)
        else:
            ledger_request = Ledger(ledger_index=ledger_index)

        # Initialize and use the XRPL client to fetch ledger information
        client = get_xrpl_client()
        if not client:
            return handle_error({'status': 'failure', 'message': ERROR_INITIALIZING_CLIENT},
                                status_code=500,
                                function_name=function_name)

        response = client.request(ledger_request)
        if not response:
            return handle_error({'status': 'failure', 'message': ERROR_IN_XRPL_RESPONSE},
                                status_code=500,
                                function_name=function_name)

        # Log the raw response for detailed debugging
        logger.debug(XRPL_RESPONSE)
        logger.debug(json.dumps(response.result, indent=4, sort_keys=True))

        # Check if the ledger request was successful
        if response.is_successful():
            ledger_info = response.result
            logger.info(f"Successfully retrieved ledger info for {ledger_index}/{ledger_hash}")

            # Format the response data
            response_data = {
                'status': 'success',
                'message': 'Ledger information successfully retrieved.',
                'ledger_info': ledger_info,
            }

            # Cache the response to reduce future server load
            cache.set(cache_key, response_data, CACHE_TIMEOUT)

            return JsonResponse(response_data)
        else:
            # Log error and return failure response if the request wasn't successful
            logger.error(f"Failed to retrieve ledger info: {response.result}")
            return JsonResponse({
                'status': 'failure',
                'message': 'Error retrieving ledger info.',
                'error_details': response.result,
            }, status=500)
    except Exception as e:
        # Catch any unexpected errors and return them in the response
        return JsonResponse({'status': 'failure', 'message': f"Error fetching ledger info: {e}"}, status=500)
    finally:
        # Ensure the client connection is closed if it was opened
        if 'client' in locals() and hasattr(client, 'close'):
            client.close()


@api_view(['GET'])
@retry(wait=wait_exponential(multiplier=RETRY_BACKOFF), stop=stop_after_attempt(MAX_RETRIES))
def get_xrp_reserves(request):
    """
    This function retrieves the XRP reserve requirements for an account from the XRP Ledger server. It:

    - Checks for the presence of an account address in the request parameters.
    - Queries the XRP Ledger for server information which includes reserve details.
    - Extracts and returns the base reserve and the increment for each owned object.
    - Logs the process for debugging or monitoring.
    - Handles errors if the account address is missing, if the server info cannot be retrieved, or if the reserve data is not available.
    - Uses retry logic to manage potential network issues.

    Parameters:
    - request: HTTP request object containing the 'account' parameter.

    Returns:
    - A JSON response with the reserve information if successful, or an error message if not.
    """

    function_name = 'get_xrp_reserves'
    logger.info(f"Entering: {function_name}")

    try:
        # Extract the account address from the request parameters
        wallet_address = request.GET.get('account')
        if not wallet_address:
            return JsonResponse({
                'status': 'failure',
                'message': ACCOUNT_IS_REQUIRED
            }, status=500)

        # Initialize and use the XRPL client to fetch ledger information
        client = get_xrpl_client()
        if not client:
            return handle_error({'status': 'failure', 'message': ERROR_INITIALIZING_CLIENT},
                                status_code=500,
                                function_name=function_name)

        # Create a ServerInfo request to get ledger server details
        server_info_request = ServerInfo()
        if not server_info_request:
            return handle_error({'status': 'failure', 'message': "Server info is none."},
                                status_code=500,
                                function_name=function_name)

        # Send the server info request to XRPL
        server_info_response = client.request(server_info_request)
        if not server_info_response:
            return handle_error({'status': 'failure', 'message': ERROR_IN_XRPL_RESPONSE},
                                status_code=500,
                                function_name=function_name)

        # Log the raw response for detailed debugging
        logger.debug(XRPL_RESPONSE)
        logger.debug(json.dumps(server_info_response.result, indent=4, sort_keys=True))

        # Check if the server info was successfully retrieved
        if server_info_response.is_successful():
            # Extract reserve information from the server's validated ledger
            reserve_base = server_info_response.result['info']['validated_ledger']['reserve_base_xrp']
            reserve_inc = server_info_response.result['info']['validated_ledger']['reserve_inc_xrp']

            if reserve_base is not None and reserve_inc is not None:
                logger.info(f"Successfully fetched XRP reserve information for {wallet_address}.")

                # Format the response with the fetched reserve values
                response_data = {
                    'status': 'success',
                    'message': 'XRP reserves fetched successfully.',
                    'base_reserve': reserve_base,
                    'owner_reserve': reserve_inc,
                }
                return JsonResponse(response_data)
            else:
                # If reserves are not found in the response, log error and return failure
                logger.error(f"Reserve info not found in server response: {server_info_response.result}")
                return JsonResponse({
                    'status': 'failure',
                    'message': 'Error fetching reserve information. Reserves not found.',
                }, status=500)
        else:
            # If server info request failed, log the error and return appropriate failure response
            logger.error(f"Failed to fetch server info: {server_info_response.result}")
            return JsonResponse({
                'status': 'failure',
                'message': 'Error fetching server information.',
                'error_details': server_info_response.result,
            }, status=500)
    except Exception as e:
        # Handle any unexpected errors during the process
        return JsonResponse({'status': 'failure', 'message': f"Error fetching XRP reserves: {e}"}, status=500)
    finally:
        # Ensure the client connection is closed if it was opened
        if 'client' in locals() and hasattr(client, 'close'):
            client.close()


@api_view(['GET'])
@retry(wait=wait_exponential(multiplier=RETRY_BACKOFF), stop=stop_after_attempt(MAX_RETRIES))
def get_account_trust_lines(request):
    """
    This function fetches all trust lines for a specified XRP account. Trust lines represent the relationship between accounts for non-XRP assets. It:

    - Requires an account address as a parameter.
    - Queries the XRP Ledger for trust lines associated with the given account.
    - Returns the list of trust lines if successful.
    - Logs the process for debugging or monitoring.
    - Handles errors for missing account addresses, failed requests, or unexpected exceptions.
    - Uses retry logic to manage potential network issues.

    Parameters:
    - request: HTTP request object containing the 'account' parameter.

    Returns:
    - A JSON response with the list of trust lines if successful, or an error message if not.
    """

    function_name = 'get_account_trust_lines'
    logger.info(f"Entering: {function_name}")

    try:
        # Extract the account address from the request parameters
        wallet_address = request.GET.get('account')
        if not wallet_address:
            return JsonResponse({
                'status': 'failure',
                'message': ACCOUNT_IS_REQUIRED
            }, status=500)

        # Prepare an AccountLines request to retrieve trust lines for the account
        account_lines_request = AccountLines(account=wallet_address)

        # Initialize and use the XRPL client to fetch ledger information
        client = get_xrpl_client()
        if not client:
            return handle_error({'status': 'failure', 'message': ERROR_INITIALIZING_CLIENT},
                                status_code=500,
                                function_name=function_name)

        response = client.request(account_lines_request)
        if not response:
            return handle_error({'status': 'failure', 'message': ERROR_IN_XRPL_RESPONSE},
                                status_code=500,
                                function_name=function_name)

        # Log the raw response for detailed debugging
        logger.debug(XRPL_RESPONSE)
        logger.debug(json.dumps(response.result, indent=4, sort_keys=True))

        # Check if the trust line request was successful
        if response.is_successful():
            # Extract the trust lines from the response
            trust_lines = response.result.get("lines", [])
            logger.info(f"Successfully fetched trust lines for account {wallet_address}.")

            # Prepare and return the response with the trust lines
            return JsonResponse({
                'status': 'success',
                'message': 'Trust lines fetched successfully.',
                'trust_lines': trust_lines
            })
        else:
            # If the request failed, log the error and return a failure response
            logger.error(f"Failed to fetch trust lines for account {wallet_address}: {response.result}")
            return JsonResponse({
                'status': 'failure',
                'message': 'Error fetching trust lines.',
                'error_details': response.result
            }, status=500)

    except Exception as e:
        # Handle any unexpected errors that occur during the process
        return JsonResponse({'status': 'failure', 'message': f"Error fetching trust lines: {e}"}, status=500)
    finally:
        # Ensure the client connection is closed if it was opened
        if 'client' in locals() and hasattr(client, 'close'):
            client.close()


@api_view(['GET'])
@retry(wait=wait_exponential(multiplier=RETRY_BACKOFF), stop=stop_after_attempt(MAX_RETRIES))
def get_account_offers(request):
    """
    This function retrieves all active offers (buy or sell orders) for a specified XRP account. It:

    - Requires an account address as a parameter to query.
    - Communicates with the XRP Ledger to fetch current offers related to that account.
    - Returns these offers if the request is successful.
    - Logs the process for debugging or monitoring.
    - Manages errors for missing account addresses, failed API calls, or unexpected exceptions.
    - Implements retry logic to handle potential network errors.

    Parameters:
    - request: HTTP request object containing the 'account' parameter.

    Returns:
    - A JSON response containing the list of offers if successful, or an error message if not.
    """

    function_name = 'get_account_offers'
    logger.info(f"Entering: {function_name}")

    try:
        # Extract the account address from the request parameters
        wallet_address = request.GET.get('account')
        if not wallet_address:
            return JsonResponse({
                'status': 'failure',
                'message': ACCOUNT_IS_REQUIRED
            }, status=500)

        # Prepare an AccountOffers request to retrieve offers for the account
        account_offers_request = AccountOffers(account=wallet_address)

        # Initialize and use the XRPL client to fetch ledger information
        client = get_xrpl_client()
        if not client:
            return handle_error({'status': 'failure', 'message': ERROR_INITIALIZING_CLIENT},
                                status_code=500,
                                function_name=function_name)

        response = client.request(account_offers_request)
        if not response:
            return handle_error({'status': 'failure', 'message': ERROR_IN_XRPL_RESPONSE},
                                status_code=500,
                                function_name=function_name)

        # Log the raw response for detailed debugging
        logger.debug(XRPL_RESPONSE)
        logger.debug(json.dumps(response.result, indent=4, sort_keys=True))

        # Check if the offers request was successful
        if response.is_successful():
            # Extract the offers from the response
            offers = response.result.get("offers", [])
            logger.info(f"Successfully fetched offers for account {wallet_address}.")

            # Prepare and return the response with the offers
            return JsonResponse({
                'status': 'success',
                'message': 'Offers fetched successfully.',
                'offers': offers
            })
        else:
            # If the request failed, log the error and return a failure response
            logger.error(f"Failed to fetch offers for account {wallet_address}: {response.result}")
            return JsonResponse({
                'status': 'failure',
                'message': 'Error fetching offers.',
                'error_details': response.result
            }, status=500)

    except Exception as e:
        # Handle any unexpected errors that occur during the process
        return JsonResponse({'status': 'failure', 'message': f"Error fetching offers: {e}"}, status=500)
    finally:
        # Ensure the client connection is closed if it was opened
        if 'client' in locals() and hasattr(client, 'close'):
            client.close()


@api_view(['GET'])
@retry(wait=wait_exponential(multiplier=RETRY_BACKOFF), stop=stop_after_attempt(MAX_RETRIES))
def get_server_info(request):
    """
    This function retrieves and returns information about the XRP Ledger server. It:

    - Checks for cached server information to minimize server queries.
    - If not cached, it queries the XRP Ledger for current server details such as version, peer count, etc.
    - Caches the server info for future requests to reduce network load.
    - Logs the process for monitoring and debugging.
    - Handles errors if the server info cannot be retrieved or if there are unexpected issues.
    - Utilizes retry logic to manage potential network failures.

    Parameters:
    - request: HTTP request object (not used directly but required for Django's view structure).

    Returns:
    - A JSON response with server details if successful, or an error message if not.
    """

    function_name = 'get_server_info'
    logger.info(f"Entering: {function_name}")

    try:
        # First, check if server information is already cached to reduce load on the server
        cached_server_info = cache.get('server_info')

        if cached_server_info:
            logger.info("Returning cached server information.")
            return JsonResponse({
                'status': 'success',
                'message': 'Server info fetched from cache.',
                'server_info': cached_server_info
            })

        # If not cached, prepare a ServerInfo request to fetch current server status
        server_info_request = ServerInfo()

        # Initialize and use the XRPL client to fetch ledger information
        client = get_xrpl_client()
        if not client:
            return handle_error({'status': 'failure', 'message': ERROR_INITIALIZING_CLIENT},
                                status_code=500,
                                function_name=function_name)

        response = client.request(server_info_request)
        if not response:
            return handle_error({'status': 'failure', 'message': ERROR_IN_XRPL_RESPONSE},
                                status_code=500,
                                function_name=function_name)

        # Log the raw response for detailed debugging
        logger.debug(XRPL_RESPONSE)
        logger.debug(json.dumps(response.result, indent=4, sort_keys=True))

        # Check if the server info request was successful
        if response.is_successful():
            # Extract server information from the response
            server_info = response.result

            # Cache the server information for future requests to reduce server load
            cache.set('server_info', server_info, timeout=CACHE_TIMEOUT_FOR_SERVER_INFO)

            logger.info("Successfully fetched server information.")
            return JsonResponse({
                'status': 'success',
                'message': 'Server info fetched successfully.',
                'server_info': server_info
            })
        else:
            # If request failed, log the error and return a failure response
            logger.error(f"Failed to fetch server info: {response.result}")
            return JsonResponse({
                'status': 'failure',
                'message': 'Error fetching server information.',
                'error_details': response.result
            }, status=500)
    except Exception as e:
        # Handle any unexpected errors during the process
        return JsonResponse({'status': 'failure', 'message': f"Error fetching server info: {e}"}, status=500)
    finally:
        # Ensure the client connection is closed if it was opened
        if 'client' in locals() and hasattr(client, 'close'):
            client.close()


@api_view(['GET'])
@retry(wait=wait_exponential(multiplier=RETRY_BACKOFF), stop=stop_after_attempt(MAX_RETRIES))
def get_trust_line(request):
    """
    This function retrieves trust lines for a specified XRP account. Trust lines are necessary for holding non-XRP assets in the XRP Ledger. It:

    - Requires the wallet address as a parameter to query.
    - Queries the XRP Ledger for trust lines associated with the given account.
    - Returns these trust lines if the request is successful.
    - Logs the process for debugging or monitoring purposes.
    - Manages errors if the wallet address is missing, if the request fails, or if unexpected exceptions occur.
    - Utilizes retry logic to deal with potential network issues.

    Parameters:
    - request: HTTP request object containing the 'wallet_address' parameter.

    Returns:
    - A JSON response with the trust lines if successful, or an error message if not.
    """

    function_name = 'get_trust_line'
    logger.info(f"Entering: {function_name}")

    # Extract the wallet address from the request parameters
    wallet_address = request.GET.get('wallet_address')
    if not wallet_address:
        return JsonResponse({
            'status': 'failure',
            'message': 'wallet_address parameter is required.'
        }, status=500)

    try:
        # Prepare an AccountLines request to retrieve trust lines for the account
        account_lines_request = AccountLines(account=wallet_address)

        # Initialize and use the XRPL client to fetch ledger information
        client = get_xrpl_client()
        if not client:
            return handle_error({'status': 'failure', 'message': ERROR_INITIALIZING_CLIENT},
                                status_code=500,
                                function_name=function_name)

        response = client.request(account_lines_request)
        if not response:
            return handle_error({'status': 'failure', 'message': ERROR_IN_XRPL_RESPONSE},
                                status_code=500,
                                function_name=function_name)

        # Log the raw response for detailed debugging
        logger.debug(XRPL_RESPONSE)
        logger.debug(json.dumps(response.result, indent=4, sort_keys=True))

        # Check if the trust line request was successful
        if response.is_successful():
            # Extract trust lines from the response
            trust_lines = response.result.get('lines', [])
            logger.info(f"Successfully fetched trust lines for account {wallet_address}.")
            return JsonResponse({
                'status': 'success',
                'message': 'Trust lines fetched successfully.',
                'trust_lines': trust_lines
            })
        else:
            # If the request failed, log the error and return a failure response
            logger.error(f"Failed to fetch trust lines for account {wallet_address}: {response.result}")
            return JsonResponse({
                'status': 'failure',
                'message': 'Error fetching trust lines.',
                'error_details': response.result
            }, status=500)
    except Exception as e:
        # Handle any unexpected errors that occur during the process
        return JsonResponse({'status': 'failure', 'message': f"Error fetching trust lines: {e}"}, status=500)
    finally:
        # Ensure the client connection is closed if it was opened
        if 'client' in locals() and hasattr(client, 'close'):
            client.close()


@api_view(['POST'])
@retry(wait=wait_exponential(multiplier=RETRY_BACKOFF), stop=stop_after_attempt(MAX_RETRIES))
def set_trust_line(request):
    """
    This function sets a new trust line for an XRP account, which is necessary for holding or trading non-XRP assets. It:

    - Accepts POST requests with parameters for setting up a trust line including sender's seed, account, currency, and limit.
    - Validates all required parameters are present.
    - Converts the limit amount to drops if dealing with XRP.
    - Constructs a TrustSet transaction to establish or modify the trust line.
    - Signs the transaction with the sender's seed.
    - Submits the transaction to the XRP Ledger.
    - Returns the transaction hash on success or handles errors if the transaction fails or parameters are missing.
    - Uses retry logic for robustness against network issues.

    Parameters:
    - request: HTTP request object containing trust line details in POST data.

    Returns:
    - A JSON response indicating success or failure of the trust line setup, including transaction details or error messages.
    """

    function_name = 'set_trust_line'
    logger.info(f"Entering: {function_name}")

    try:
        # Extract parameters from the request data
        sender_seed = get_request_param(request, 'sender_seed', function_name=function_name) # Sender seed the trust line for
        account = get_request_param(request, 'account', function_name=function_name) # Account to set the trust line for
        currency = get_request_param(request, 'currency', function_name=function_name) # Currency for trust line (e.g., 'USD')
        limit = get_request_param(request, 'limit', function_name=function_name)  # Trust line limit

        # Validate that all required parameters are provided
        if not sender_seed or not account or not currency or not limit:
            return JsonResponse({'status': 'failure', 'message': 'Missing required parameters'}, status=500)

        # Convert the limit to drops if the currency is XRP, as XRP amounts are in drops on XRPL
        limit_drops = xrpl.utils.xrp_to_drops(limit) if currency == "XRP" else limit

        # Prepare the TrustSet transaction for setting the trust line
        trust_set_tx = TrustSet(
            account=account,
            limit_amount={'currency': currency, 'value': str(limit_drops), 'issuer': account},
        )
        if not trust_set_tx:
            return handle_error({'status': 'failure', 'message': "Error creating TrustSet."},
                                status_code=500,
                                function_name=function_name)

        # Initialize the XRPL client for transaction submission
        client = get_xrpl_client()
        if not client:
            return handle_error({'status': 'failure', 'message': ERROR_INITIALIZING_CLIENT},
                                status_code=500,
                                function_name=function_name)

        # Create a wallet from the sender's seed to sign the transaction
        sender_wallet = Wallet.from_seed(sender_seed)
        signed_tx = xrpl.transaction.sign_transaction(trust_set_tx, sender_wallet)

        # Submit the signed transaction to the XRPL
        response = client.submit(signed_tx)
        if not response:
            return handle_error({'status': 'failure', 'message': "Error submitting TrustSet transaction."},
                                status_code=500,
                                function_name=function_name)

        # Check if the transaction submission was successful
        if response.is_successful():
            logger.info(f"Trust line set successfully for account {account}")
            return JsonResponse({
                'status': 'success',
                'message': 'Trust line set successfully.',
                'transaction_hash': response.result['hash'],
                'account': account,
                'currency': currency,
                'limit': limit,
            })
        else:
            # If transaction failed, return an error response
            return JsonResponse({'status': 'failure', 'message': 'Error setting trust line.'}, status=500)
    except Exception as e:
        # Handle any exceptions that might occur during the process
        return JsonResponse({'status': 'failure', 'message': f"Error setting trust line: {str(e)}"}, status=500)
    finally:
        # Ensure the client connection is closed to free resources
        if 'client' in locals() and hasattr(client, 'close'):
            client.close()
