import json
import logging

import xrpl
from django.core.cache import cache
from django.core.paginator import Paginator
from django.db import transaction
from django.http import JsonResponse
from rest_framework.decorators import api_view
from rest_framework.pagination import PageNumberPagination
from tenacity import retry, wait_exponential, stop_after_attempt
from xrpl import XRPLException
from django.apps import apps
from xrpl.core import addresscodec
from xrpl.models import AccountLines, AccountOffers, ServerInfo, SetRegularKey, AccountSetAsfFlag, AccountInfo, \
    AccountSet
from xrpl.models.requests import Ledger
from xrpl.transaction import sign_and_submit
from xrpl.transaction import submit_and_wait
from xrpl.utils import xrp_to_drops
from xrpl.wallet import Wallet
from xrpl.wallet import generate_faucet_wallet

from .accounts.account_data import get_account_reserves
from .constants import ERROR_INITIALIZING_CLIENT, RETRY_BACKOFF, MAX_RETRIES, PAGINATION_PAGE_SIZE, \
    CACHE_TIMEOUT_FOR_WALLET, CACHE_TIMEOUT, CACHE_TIMEOUT_FOR_SERVER_INFO, \
    XRPL_RESPONSE, ERROR_IN_XRPL_RESPONSE, INVALID_WALLET_IN_REQUEST, ACCOUNT_IS_REQUIRED, \
    ERROR_FETCHING_TRANSACTION_HISTORY, INVALID_TRANSACTION_HASH, ERROR_FETCHING_TRANSACTION_STATUS, \
    ERROR_INITIALIZING_SERVER_INFO, PAYMENT_IS_UNSUCCESSFUL, ERROR_GETTING_ACCOUNT_INFO, ENTERING_FUNCTION_LOG, \
    LEAVING_FUNCTION_LOG, asfDisableMaster
from .db_operations import save_account_data_to_databases
from .utils import get_xrpl_client, handle_error, \
    build_flags, is_valid_xrpl_seed, get_request_param, validate_xrp_wallet, is_valid_transaction_hash, \
    get_account_details, get_cached_data, \
    parse_boolean_param, prepare_account_set_tx, account_set_tx_response, prepare_account_tx, \
    prepare_account_tx_with_pagination, prepare_tx, \
    account_tx_with_pagination_response, transaction_status_response, extract_request_data, \
    validate_request_data, fetch_network_fee, create_payment_transaction, process_payment_response, \
    prepare_account_data, prepare_account_delete, delete_account_response, create_account_delete_transaction, \
    account_delete_tx_response, server_info_response, account_reserves_response, trust_line_response, \
    create_trust_set_transaction, create_trust_set_response, create_account_response, convert_drops_to_xrp, \
    create_wallet_info_response, create_wallet_balance_response, transaction_history_response, validate_xrpl_response, \
    create_multiple_account_response

logger = logging.getLogger('xrpl_app')


class AccountInfoPagination(PageNumberPagination):
    page_size = PAGINATION_PAGE_SIZE


@api_view(['POST'])
@retry(wait=wait_exponential(multiplier=RETRY_BACKOFF), stop=stop_after_attempt(MAX_RETRIES))
def create_multiple_account(request):
    """
    This function handles the creation of multiple XRPL accounts. It performs the following steps:

    1. Extracts and validates the number of accounts to be created from the request parameters.
    2. Initializes an XRPL client and checks if the initialization is successful.
    3. Iterates over the required number of accounts:
       - Generates a new wallet using the faucet.
       - Retrieves account details for the newly created wallet.
       - Logs account information (classic and X-address).
       - Converts the account balance from drops to XRP.
       - Saves account details to the database.
    4. Returns a response with the created account details.

    Error handling is implemented to catch and log exceptions, ensuring a proper response is returned.
    Logging is used to track function entry, exit, and key processing steps.
    """

    function_name = 'create_multiple_account'
    logger.info(ENTERING_FUNCTION_LOG.format(function_name))  # Log entering the function

    try:
        # Extract and validate parameters from the request
        create_number_of_accounts = get_request_param(request, 'number_of_accounts')

        # Initialize XRPL client. Check if client is successfully initialized. Raise exception if client initialization fails
        client = get_xrpl_client()
        if not client:
            raise XRPLException(ERROR_INITIALIZING_CLIENT)

        transactions = []

        for i in range(int(create_number_of_accounts)):
            # Generate a new wallet using the faucet. Check if new wallet is successfully created. Raise exception if wallet creation fails
            new_wallet = generate_faucet_wallet(client, debug=True)
            if not new_wallet:
                raise XRPLException('Error creating new wallet.')

            # Retrieve account details. Check if account details are successfully retrieved. Raise exception if details retrieval fails
            account_details = get_account_details(client, new_wallet.address)
            if not account_details:
                raise XRPLException('Error retrieving account details.')

            # Log the classic address and X-address
            logger.debug(f"Classic address: {new_wallet.address}")
            logger.debug(
                f"X-address: {addresscodec.classic_address_to_xaddress(new_wallet.address, tag=12345, is_test_network=True)}")

            # Convert balance from drops to XRP
            xrp_balance = convert_drops_to_xrp(account_details['result']['account_data']['Balance'])
            if not xrp_balance:
                raise ValueError("Invalid XRP balance")

            # Save account data to databases
            save_account_data_to_databases(account_details, str(xrp_balance))
            transactions.append(account_details['result']['account_data'])

        logger.debug(f"Wallets created: {transactions}")

        return create_multiple_account_response(transactions)
    except Exception as e:
        # Catch any exceptions that occur during the process. Handle error and return response
        return handle_error({'status': 'failure', 'message': str(e)}, status_code=500, function_name=function_name)
    finally:
        # Log leaving the function regardless of success or failure
        logger.info(LEAVING_FUNCTION_LOG.format(function_name))


@api_view(['GET'])
@retry(wait=wait_exponential(multiplier=RETRY_BACKOFF), stop=stop_after_attempt(MAX_RETRIES))
def create_account(request):
    """
    API endpoint to create a new account.

    This function initializes an XRPL client, generates a new wallet using the faucet, retrieves account details,
    converts the balance to XRP, saves the account data to databases, and returns a response with account information.

    Args:
        request (Request): The HTTP request object.

    Steps:
       1. Initialize the XRPL client.
       2. Generate a new wallet using the XRPL faucet.
       3. Retrieve the newly created account's details.
       4. Log the classic address and corresponding X-address.
       5. Convert balance from drops to XRP.
       6. Save the account data to the database.
       7. Return the account information in the response.

    Returns:
        Response: JSON response containing either the created account details or error information.
    """
    function_name = 'create_account'
    logger.info(ENTERING_FUNCTION_LOG.format(function_name))  # Log entering the function

    try:
        # Initialize XRPL client. Check if client is successfully initialized. Raise exception if client initialization fails
        client = get_xrpl_client()
        if not client:
            raise XRPLException(ERROR_INITIALIZING_CLIENT)

        # Generate a new wallet using the faucet. Check if new wallet is successfully created. Raise exception if wallet creation fails
        new_wallet = generate_faucet_wallet(client, debug=True)
        if not new_wallet:
            raise XRPLException('Error creating new wallet.')

        # Retrieve account details. Check if account details are successfully retrieved. Raise exception if details retrieval fails
        account_details = get_account_details(client, new_wallet.address)
        if not account_details:
            raise XRPLException('Error retrieving account details.')

        # Log the classic address and X-address
        logger.debug(f"Classic address: {new_wallet.address}")
        logger.debug(
            f"X-address: {addresscodec.classic_address_to_xaddress(new_wallet.address, tag=12345, is_test_network=True)}")

        # Convert balance from drops to XRP
        xrp_balance = convert_drops_to_xrp(account_details['result']['account_data']['Balance'])
        if not xrp_balance:
            raise ValueError("Invalid XRP balance")

        # Save account data to databases
        save_account_data_to_databases(account_details, str(xrp_balance))

        # Return response with account information
        return create_account_response(new_wallet.address, new_wallet.seed, xrp_balance, account_details)
    except Exception as e:
        # Catch any exceptions that occur during the process. Handle error and return response
        return handle_error({'status': 'failure', 'message': str(e)}, status_code=500, function_name=function_name)
    finally:
        # Log leaving the function regardless of success or failure
        logger.info(LEAVING_FUNCTION_LOG.format(function_name))


@api_view(['GET'])
@retry(wait=wait_exponential(multiplier=RETRY_BACKOFF), stop=stop_after_attempt(MAX_RETRIES))
def get_wallet_info(request, wallet_address):
    """
        Retrieves detailed information about a given XRP wallet.

        Steps:
        1. Validate the provided wallet address.
        2. Check if the wallet information is cached to optimize performance.
        3. If not cached, initialize an XRPL client.
        4. Retrieve account details from XRPL.
        5. Extract account balance and convert from drops to XRP.
        6. Fetch the base reserve and reserve increment for the wallet.
        7. Cache the wallet data to improve response time for future requests.
        8. Return the wallet information as a JSON response.

        If an error occurs at any step, an appropriate error response is returned.
        """

    function_name = 'get_wallet_info'
    logger.info(ENTERING_FUNCTION_LOG.format(function_name))

    # Validate the provided wallet address
    if not wallet_address or not validate_xrp_wallet(wallet_address):
        raise XRPLException(INVALID_WALLET_IN_REQUEST)

    # Create a unique cache key for this wallet. Check if data is already cached
    cache_key = f"get_wallet_info:{wallet_address}"
    cached_data = get_cached_data(cache_key, wallet_address, function_name)
    if cached_data:
        # Return cached data if available
        return JsonResponse(cached_data)

    try:
        # Get an instance of the XRPL client
        client = get_xrpl_client()
        if not client:
            # Raise an exception if client initialization fails
            raise XRPLException(ERROR_INITIALIZING_CLIENT)

        # Fetch account details from the XRPL
        account_details = get_account_details(client, wallet_address)
        if not account_details:
            # Raise an exception if fetching account details fails
            raise XRPLException(ERROR_GETTING_ACCOUNT_INFO)

        # Extract the actual account data from the response
        account_data = account_details['result']['account_data']

        # Convert the balance from drops to XRP
        balance = convert_drops_to_xrp(account_data['Balance'])

        # Retrieve the base reserve and reserve increment
        base_reserve, reserve_increment = get_account_reserves()
        if base_reserve is None or reserve_increment is None:
            # Raise an exception if reserve data retrieval fails
            raise XRPLException('Failed to fetch reserve data.')

        logger.info(
            f"Account found: {wallet_address}, Balance: {balance}, Base Reserve: {base_reserve}, Reserve Increment: {reserve_increment}")  # Log the fetched information

        # Cache the response to speed up future requests for this wallet
        # Store the account data in the cache
        cache.set(cache_key, account_data, CACHE_TIMEOUT_FOR_WALLET)

        # Return a JSON response with the wallet information
        return create_wallet_info_response(base_reserve, reserve_increment, account_details)

    except (xrpl.XRPLException, Exception) as e:
        # Catch any exceptions that occur during the process
        # Handle error and return a JSON response with an error message
        return handle_error({'status': 'failure', 'message': f"{str(e)}"}, status_code=500, function_name=function_name)

    finally:
        logger.info(LEAVING_FUNCTION_LOG.format(function_name))


@api_view(['GET'])
@retry(wait=wait_exponential(multiplier=RETRY_BACKOFF), stop=stop_after_attempt(MAX_RETRIES))
def check_wallet_balance(request, wallet_address):
    """
    Checks the XRP balance of a given wallet address.

    Steps:
    1. Validate the provided wallet address.
    2. Check if the balance information is cached to reduce network load.
    3. If not cached, initialize an XRPL client to query the ledger.
    4. Retrieve account details from XRPL and extract the balance.
    5. Convert the balance from drops to XRP for better readability.
    6. Cache the balance data to optimize future requests.
    7. Return the balance information in a JSON response.

    If an error occurs at any step, an appropriate error response is returned.
    """

    function_name = 'check_wallet_balance'
    logger.info(ENTERING_FUNCTION_LOG.format(function_name))

    # Validate the provided wallet address
    if not wallet_address or not validate_xrp_wallet(wallet_address):
        raise XRPLException(INVALID_WALLET_IN_REQUEST)

    # Check if the balance information is already cached
    cache_key = f"check_wallet_balance:{wallet_address}"
    cached_data = get_cached_data(cache_key, wallet_address, function_name)
    if cached_data:
        # Return cached data if available
        return JsonResponse(cached_data)

    try:
        # Initialize the XRPL client to query the ledger
        client = get_xrpl_client()
        if not client:
            raise XRPLException(ERROR_INITIALIZING_CLIENT)

        # Fetch account details from the XRPL
        account_details = get_account_details(client, wallet_address)
        if not account_details:
            # Raise an exception if fetching account details fails
            raise XRPLException(ERROR_GETTING_ACCOUNT_INFO)

        # Convert the balance from drops to XRP
        balance_in_xrp = convert_drops_to_xrp(account_details['result']["account_data"]["Balance"])

        # Log the successful balance check
        logger.info(f"Balance for address {wallet_address} retrieved successfully: {balance_in_xrp} XRP")

        # Cache the balance for future queries to reduce network load
        cache.set(cache_key, account_details, CACHE_TIMEOUT)

        # Return a JSON response with the wallet information
        return create_wallet_balance_response(balance_in_xrp)

    except (xrpl.XRPLException, Exception) as e:
        # Catch any exceptions that occur during the process
        # Handle error and return a JSON response with an error message
        return handle_error({'status': 'failure', 'message': f"{str(e)}"}, status_code=500, function_name=function_name)
    finally:
        logger.info(LEAVING_FUNCTION_LOG.format(function_name))


@api_view(['GET'])
@retry(wait=wait_exponential(multiplier=RETRY_BACKOFF), stop=stop_after_attempt(MAX_RETRIES))
def account_set(request):
    """
    Handles an AccountSet transaction on the XRPL (XRP Ledger).

    Steps:
    1. Extract and validate request parameters, including sender's seed and account settings.
    2. Parse boolean parameters for account settings (require destination tag, disable master key, enable regular key).
    3. Generate the sender's wallet address from the provided seed.
    4. Construct transaction flags based on the requested settings.
    5. Prepare an AccountSet transaction using the provided account settings.
    6. Initialize the XRPL client and verify a successful connection.
    7. Submit the transaction and wait for it to be processed.
    8. Log and handle the transaction response.
    9. Return a JSON response containing the transaction details.

    If an error occurs at any step, an appropriate error response is returned.
    """

    function_name = 'account_set'
    logger.info(ENTERING_FUNCTION_LOG.format(function_name))

    try:
        # Extract and validate parameters from the request
        sender_seed = get_request_param(request, 'sender_seed')

        # Parse boolean parameters for account settings
        require_destination_tag = parse_boolean_param(request, 'require_destination_tag')
        disable_master_key = parse_boolean_param(request, 'disable_master_key')
        enable_regular_key = parse_boolean_param(request, 'enable_regular_key')

        # Log the settings for debugging or monitoring
        logger.info(
            f"require_destination_tag: {require_destination_tag}, disable_master_key: {disable_master_key}, enable_regular_key: {enable_regular_key}")

        # Create a wallet from the seed to get the sender's address
        sender_wallet = Wallet.from_seed(sender_seed)
        sender_address = sender_wallet.classic_address

        # Build flags for the AccountSet transaction based on the provided settings
        flags = build_flags(require_destination_tag, disable_master_key, enable_regular_key)

        # Prepare the AccountSet transaction
        account_set_tx = prepare_account_set_tx(sender_address, flags)

        # Initialize the XRPL client
        client = get_xrpl_client()
        if not client:
            raise XRPLException(ERROR_INITIALIZING_CLIENT)

        # Submit and wait for the transaction to be included in a ledger
        response = submit_and_wait(account_set_tx, client, sender_wallet)
        if not response or not response.is_successful():
            raise XRPLException('Error submit_and_wait return none.')

        # Log the raw response for detailed debugging
        logger.debug(XRPL_RESPONSE)
        logger.debug(json.dumps(response.result, indent=4, sort_keys=True))

        # Handle the transaction response
        return account_set_tx_response(response, sender_address)

    except (xrpl.XRPLException, Exception) as e:
        # Handle exceptions like XRPL-specific errors, network issues, or unexpected errors
        return handle_error({'status': 'failure', 'message': f"{str(e)}"},
                            status_code=500, function_name=function_name)
    finally:
        logger.info(LEAVING_FUNCTION_LOG.format(function_name))


@api_view(['GET'])
@retry(wait=wait_exponential(multiplier=RETRY_BACKOFF), stop=stop_after_attempt(MAX_RETRIES))
def get_transaction_history(request, wallet_address, previous_transaction_id):
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
            raise XRPLException(ERROR_FETCHING_TRANSACTION_STATUS)

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
        return handle_error({'status': 'failure', 'message': f"{str(e)}"},
                            status_code=500, function_name=function_name)
    finally:
        logger.info(LEAVING_FUNCTION_LOG.format(function_name))


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
                raise XRPLException(ERROR_FETCHING_TRANSACTION_STATUS)

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
        return handle_error({'status': 'failure', 'message': f"{str(e)}"},
                            status_code=500, function_name=function_name)
    finally:
        logger.info(LEAVING_FUNCTION_LOG.format(function_name))


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
            raise XRPLException(ERROR_FETCHING_TRANSACTION_STATUS)

        # Log the raw response for detailed debugging
        logger.debug(XRPL_RESPONSE)
        logger.debug(json.dumps(result, indent=4, sort_keys=True))

        # Log the raw response for detailed debugging
        logger.info(f"Raw XRPL response for transaction {tx_hash}: {result}")
        return transaction_status_response(response, tx_hash)

    except (xrpl.XRPLException, Exception) as e:
        # Handle exceptions like XRPL-specific errors, network issues, or unexpected errors
        return handle_error({'status': 'failure', 'message': f"{str(e)}"},
                            status_code=500, function_name=function_name)
    finally:
        logger.info(LEAVING_FUNCTION_LOG.format(function_name))


@api_view(['POST'])
@retry(wait=wait_exponential(multiplier=RETRY_BACKOFF), stop=stop_after_attempt(MAX_RETRIES))
def send_payment(request):
    """
    Processes a payment transaction on the XRPL (XRP Ledger).

    This function performs the following steps:
    1. Extracts and validates the request data, ensuring sender seed, receiver address, and amount are correct.
    2. Converts the XRP amount to drops (the smallest unit of XRP).
    3. Uses a database transaction to ensure atomicity, preventing partial updates in case of failures.
    4. Initializes an XRPL client to interact with the XRP Ledger.
    5. Creates a sender wallet from the provided seed and retrieves the sender's address.
    6. Fetches the current network fee to include in the transaction.
    7. Constructs and submits a payment transaction to the XRPL.
    8. Validates the transaction response to ensure it has been processed successfully.
    9. Handles and processes the response, updating necessary records or triggering additional actions.
    10. Implements error handling to catch XRPL-specific errors, network issues, or unexpected failures.

    If an error occurs at any stage, a detailed failure response is logged and returned.
    """

    function_name = 'send_payment'
    logger.info(ENTERING_FUNCTION_LOG.format(function_name))

    try:
        # Extract and validate request data
        sender_seed, receiver_address, amount_xrp = extract_request_data(request)
        validate_request_data(sender_seed, receiver_address, amount_xrp)

        # Convert amount to drops
        amount_drops = xrp_to_drops(amount_xrp)

        with transaction.atomic():
            # Initialize XRPL client
            client = get_xrpl_client()
            if not client:
                raise ConnectionError(ERROR_INITIALIZING_CLIENT)

            # Create sender wallet
            sender_wallet = Wallet.from_seed(sender_seed)
            sender_address = sender_wallet.classic_address

            # Get network fee
            fee_drops = fetch_network_fee(client)

            # Create and submit the payment transaction
            payment_transaction = create_payment_transaction(sender_address, receiver_address, amount_drops, fee_drops, False)
            payment_response = submit_and_wait(payment_transaction, client, sender_wallet)

            is_valid, result = validate_xrpl_response(payment_response, required_keys=["validated"])
            if not is_valid:
                raise XRPLException(ERROR_FETCHING_TRANSACTION_STATUS)

            # Handle the transaction response
            return process_payment_response(payment_response, sender_address, receiver_address, amount_xrp, fee_drops)

    except (xrpl.XRPLException, Exception) as e:
        # Handle exceptions like XRPL-specific errors, network issues, or unexpected errors
        return handle_error({'status': 'failure', 'message': str(e)}, 500, function_name)

    finally:
        logger.info(LEAVING_FUNCTION_LOG.format(function_name))


@api_view(['DELETE'])
@retry(wait=wait_exponential(multiplier=RETRY_BACKOFF), stop=stop_after_attempt(MAX_RETRIES))
def delete_account(request, wallet_address):
    """
        Deletes an XRP account by setting its regular key to a black hole address and disabling the master key.

        This function validates the wallet address and sender's seed, then constructs and submits a SetRegularKey
        transaction to set the regular key of the account to a black hole address. Afterward, an AccountSet transaction
        is created to disable the master key, effectively blackholing the account.

        The account will only be deleted if the XRP balance is zero. If the balance is non-zero, an exception is raised.

        Args:
            request (HttpRequest): The HTTP request object containing parameters.
            wallet_address (str): The address of the wallet to be deleted.

        Raises:
            XRPLException: If the wallet address is invalid, the balance is non-zero, or any other XRPL-related issue occurs.
            ValueError: If the sender seed is invalid.

        Returns:
            Response: A JSON response indicating the success or failure of the delete operation.
        """

    function_name = 'delete_account'
    logger.info(ENTERING_FUNCTION_LOG.format(function_name))

    try:
        # Validate the provided wallet address format
        if not wallet_address or not validate_xrp_wallet(wallet_address):
            raise XRPLException(INVALID_WALLET_IN_REQUEST)

        # Extract the sender's seed from the request parameters
        sender_seed, _, _  = extract_request_data(request)
        if not is_valid_xrpl_seed(sender_seed):
            raise ValueError('Sender seed is invalid.')

        # Initialize the XRPL client for ledger operations
        client = get_xrpl_client()
        if not client:
            raise ConnectionError(ERROR_INITIALIZING_CLIENT)

        # Prepare account data
        account_info_request = prepare_account_data(wallet_address)

        # Request account information from XRPL
        response = client.request(account_info_request)
        is_valid, response = validate_xrpl_response(response, required_keys=["validated"])
        if not is_valid:
            raise XRPLException(ERROR_FETCHING_TRANSACTION_STATUS)

        # Log the raw response for detailed debugging
        logger.debug(XRPL_RESPONSE)
        logger.debug(json.dumps(response, indent=4, sort_keys=True))

        # # Extract balance from the response, converting drops to XRP
        account_data = response
        balance = int(account_data['account_data']['Balance']) / 1_000_000  # Convert drops to XRP

        # Check if the balance is zero before proceeding with deletion
        balance = 0
        if balance == 0:
            xrpl_config = apps.get_app_config('xrpl_api')
            # Construct SetRegularKey transaction
            tx_regulary_key = SetRegularKey(
                account=wallet_address,
                regular_key=xrpl_config.BLACK_HOLE_ADDRESS
            )

            wallet = Wallet.from_seed(sender_seed)

            # Sign and submit the transaction
            submit_tx_regular = submit_and_wait(transaction=tx_regulary_key, client=client, wallet=wallet)
            submit_tx_regular = submit_tx_regular.result
            logger.info("Submitted a SetRegularKey tx.")
            logger.info(f"Result: {submit_tx_regular['meta']['TransactionResult']}")
            logger.info(f"Tx content: {submit_tx_regular}")


            # Construct AccountSet transaction w/ asfDisableMaster flag
            # This permanently blackholes an account!
            tx_disable_master_key = AccountSet(
                account=wallet_address,
                set_flag=AccountSetAsfFlag.ASF_DISABLE_MASTER
            )

            # Sign and submit the transaction
            submit_tx_disable = submit_and_wait(transaction=tx_disable_master_key, client=client, wallet=wallet)
            submit_tx_disable = submit_tx_disable.result
            logger.info("Submitted a DisableMasterKey tx.")
            logger.info(f"Result: {submit_tx_disable['meta']['TransactionResult']}")
            logger.info(f"Tx content: {submit_tx_disable}")

            # Verify Account Settings
            get_acc_flag = AccountInfo(
                account=wallet_address
            )
            response = client.request(get_acc_flag)

            if response.result['account_data']['Flags'] & asfDisableMaster:
                logger.info(f"Account {wallet_address}'s master key has been disabled, account is blackholed.")
            else:
                logger.info(f"Account {wallet_address}'s master key is still enabled, account is NOT blackholed")

            return delete_account_response(response)
        else:
            raise XRPLException('XRP balance is not zero. Unable to delete wallet.')
    except (xrpl.XRPLException, Exception) as e:
        # Handle exceptions like XRPL-specific errors, network issues, or unexpected errors
        return handle_error({'status': 'failure', 'message': f"{str(e)}"},
                            status_code=500, function_name=function_name)
    finally:
        logger.info(LEAVING_FUNCTION_LOG.format(function_name))


@api_view(['POST'])
@retry(wait=wait_exponential(multiplier=RETRY_BACKOFF), stop=stop_after_attempt(MAX_RETRIES))
def send_and_delete_wallet(request, wallet_address):
    function_name = "send_and_delete_wallet"
    logger.info(ENTERING_FUNCTION_LOG.format(function_name))

    try:
        if not wallet_address or not validate_xrp_wallet(wallet_address):
            raise ValueError(INVALID_WALLET_IN_REQUEST)

        sender_seed, _, _ = extract_request_data(request)
        if not is_valid_xrpl_seed(sender_seed):
            raise ValueError('Sender seed is invalid.')

        client = get_xrpl_client()
        if not client:
            raise ValueError(ERROR_INITIALIZING_CLIENT)

        sender_wallet = Wallet.from_seed(sender_seed)
        account_info_request = prepare_account_data(sender_wallet.classic_address)

        account_info_response = client.request(account_info_request)
        if not account_info_response or not account_info_response.is_successful():
            raise ValueError(ERROR_IN_XRPL_RESPONSE)

        balance = int(account_info_response.result['account_data']['Balance'])
        base_reserve, reserve_increment = get_account_reserves()
        if base_reserve is None or reserve_increment is None:
            raise ValueError("Failed to retrieve reserve requirements from the XRPL.")

        drops = xrp_to_drops(base_reserve)
        transferable_amount = int(balance) - int(drops)

        if transferable_amount <= 0:
            raise ValueError("Insufficient balance to cover the reserve and fees.")

        payment_tx = create_payment_transaction(sender_wallet.classic_address, wallet_address, transferable_amount, 0,
                                                True)
        payment_response = submit_and_wait(payment_tx, client, sender_wallet)

        if not payment_response or not payment_response.is_successful():
            raise ValueError(PAYMENT_IS_UNSUCCESSFUL)

        account_delete_tx = create_account_delete_transaction(sender_wallet.classic_address, wallet_address)
        account_delete_response = submit_and_wait(account_delete_tx, client, sender_wallet)

        if not account_delete_response or not account_delete_response.is_successful():
            raise ValueError("Account delete transaction failed.")

        return account_delete_tx_response(payment_response.result['hash'], account_delete_response.result['hash'])
    except Exception as e:
        return JsonResponse({"status": "failure", "message": f"{str(e)}"}, status=500)
    finally:
        logger.info(LEAVING_FUNCTION_LOG.format(function_name))


@api_view(['GET'])
@retry(wait=wait_exponential(multiplier=RETRY_BACKOFF), stop=stop_after_attempt(MAX_RETRIES))
def get_ledger_info(request):
    function_name = 'get_ledger_info'
    logger.info(ENTERING_FUNCTION_LOG.format(function_name))

    try:
        # Retrieve ledger index or hash from query parameters
        ledger_index = get_request_param(request, 'ledger_index')
        ledger_hash = get_request_param(request, 'ledger_hash')

        # Attempt to fetch from cache before making an API call
        cache_key = f"ledger_info_{ledger_index}_{ledger_hash or ''}"
        cached_data = get_cached_data(cache_key, 'get_ledger_info_function', function_name)
        if cached_data:
            return JsonResponse(cached_data)

        # Prepare the Ledger request based on whether hash or index is provided
        if ledger_hash:
            ledger_request = Ledger(ledger_hash=ledger_hash)
        else:
            ledger_request = Ledger(ledger_index=ledger_index)

        # Initialize and use the XRPL client to fetch ledger information
        client = get_xrpl_client()
        if not client:
            raise ValueError(ERROR_INITIALIZING_CLIENT)

        response = client.request(ledger_request)

        # Check if the ledger request was successful
        if response and response.is_successful():
            # Log the raw response for detailed debugging
            logger.debug(XRPL_RESPONSE)
            logger.debug(json.dumps(response.result, indent=4, sort_keys=True))

            logger.info(f"Successfully retrieved ledger info for {ledger_index}/{ledger_hash}")

            # Format the response data
            response_data = server_info_response(response)

            # Cache the response to reduce future server load
            cache.set(cache_key, response_data, CACHE_TIMEOUT)

            return response_data
        else:
            # Log error and return failure response if the request wasn't successful
            logger.error(f"Failed to retrieve ledger info: {response.result}")
            raise ValueError('Error retrieving ledger info.')
    except Exception as e:
        # Catch any unexpected errors and return them in the response

        return JsonResponse({'status': 'failure', 'message': f"Error fetching ledger info: {e}"}, status=500)
    finally:
        logger.info(LEAVING_FUNCTION_LOG.format(function_name))


@api_view(['GET'])
@retry(wait=wait_exponential(multiplier=RETRY_BACKOFF), stop=stop_after_attempt(MAX_RETRIES))
def get_xrp_reserves(request):
    function_name = 'get_xrp_reserves'
    logger.info(ENTERING_FUNCTION_LOG.format(function_name))

    try:
        # Extract wallet address
        wallet_address = get_request_param(request, 'account')
        if not wallet_address:
            raise ValueError(ACCOUNT_IS_REQUIRED)

        # Initialize XRPL client
        client = get_xrpl_client()
        if not client:
            raise XRPLException(ERROR_INITIALIZING_CLIENT)

        # Request server info
        server_info_request = ServerInfo()
        if not server_info_request:
            raise ERROR_INITIALIZING_SERVER_INFO

        server_information_response = client.request(server_info_request)

        if not server_information_response or not server_information_response.is_successful():
            logger.error(f"Failed to fetch server info: {server_information_response.result}")
            raise RuntimeError("Error fetching server information.")

        # Log raw response for debugging
        logger.debug(XRPL_RESPONSE)
        logger.debug(json.dumps(server_information_response.result, indent=4, sort_keys=True))

        # Extract reserve information
        ledger_info = server_information_response.result.get('info', {}).get('validated_ledger', {})
        reserve_base = ledger_info.get('reserve_base_xrp')
        reserve_inc = ledger_info.get('reserve_inc_xrp')

        if reserve_base is None or reserve_inc is None:
            logger.error(f"Reserve info missing in response: {server_information_response.result}")
            raise KeyError("Error fetching reserve information. Reserves not found.")

        logger.info(f"Successfully fetched XRP reserve information for {wallet_address}.")
        return account_reserves_response(server_information_response, reserve_base, reserve_inc)

    except Exception as e:
        logger.error(f"Error fetching XRP reserves: {str(e)}")
        return JsonResponse({'status': 'failure', 'message': f"Error fetching XRP reserves: {e}"}, status=500)

    finally:
        logger.info(LEAVING_FUNCTION_LOG.format(function_name))


@api_view(['GET'])
@retry(wait=wait_exponential(multiplier=RETRY_BACKOFF), stop=stop_after_attempt(MAX_RETRIES))
def get_account_offers(request):
    function_name = 'get_account_offers'
    logger.info(ENTERING_FUNCTION_LOG.format(function_name))

    try:
        wallet_address = get_request_param(request, 'account')
        if not wallet_address:
            raise ValueError(ACCOUNT_IS_REQUIRED)

        client = get_xrpl_client()
        if not client:
            raise ConnectionError(ERROR_INITIALIZING_CLIENT)

        account_offers_request = AccountOffers(account=wallet_address)

        response = client.request(account_offers_request)

        if response and response.is_successful():
            # Log the raw response for detailed debugging
            logger.debug(XRPL_RESPONSE)
            logger.debug(json.dumps(response.result, indent=4, sort_keys=True))

            # Extract the offers from the response
            # offers = response.result.get("offers", [])
            logger.info(f"Successfully fetched offers for account {wallet_address}.")

            # Prepare and return the response with the offers
            return JsonResponse({
                'status': 'success',
                'message': 'Offers fetched successfully.',
                'result': response.result,
            })
        else:
            # If the request failed, log the error and return a failure response
            logger.error(f"Failed to fetch offers for account {wallet_address}: {response.result}")
            raise ConnectionError(ERROR_IN_XRPL_RESPONSE)

    except Exception as e:
        # Handle any unexpected errors that occur during the process
        return JsonResponse({'status': 'failure', 'message': f"Error fetching offers: {e}"}, status=500)
    finally:
        logger.info(LEAVING_FUNCTION_LOG.format(function_name))


@api_view(['GET'])
@retry(wait=wait_exponential(multiplier=RETRY_BACKOFF), stop=stop_after_attempt(MAX_RETRIES))
def get_server_info(request):
    function_name = 'get_server_info'
    logger.info(ENTERING_FUNCTION_LOG.format(function_name))

    try:
        cache_key = "server_info"
        cached_data = get_cached_data(cache_key, 'get_server_info', function_name)
        if cached_data:
            return JsonResponse(cached_data)

        server_info_request = ServerInfo()
        if not server_info_request:
            raise ERROR_INITIALIZING_SERVER_INFO

        # Initialize and use the XRPL client to fetch ledger information
        client = get_xrpl_client()
        if not client:
            raise ConnectionError(ERROR_INITIALIZING_CLIENT)

        response = client.request(server_info_request)
        if response and response.is_successful():
            # Log the raw response for detailed debugging
            logger.debug(XRPL_RESPONSE)
            logger.debug(json.dumps(response.result, indent=4, sort_keys=True))

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
            raise ConnectionError(ERROR_IN_XRPL_RESPONSE)

    except Exception as e:
        # Handle any unexpected errors during the process
        return JsonResponse({'status': 'failure', 'message': f"Error fetching server info: {e}"}, status=500)
    finally:
        logger.info(LEAVING_FUNCTION_LOG.format(function_name))


@api_view(['GET'])
@retry(wait=wait_exponential(multiplier=RETRY_BACKOFF), stop=stop_after_attempt(MAX_RETRIES))
def get_account_trust_lines(request):
    function_name = 'get_account_trust_lines'
    logger.info(ENTERING_FUNCTION_LOG.format(function_name))

    client = None  # Initialize client variable for cleanup in `finally`

    try:
        # Extract wallet address from request parameters
        wallet_address = get_request_param(request, 'wallet_address')
        if not wallet_address:
            raise ValueError("Account is required.")

        # Create an AccountLines request
        account_lines_request = AccountLines(account=wallet_address)

        # Initialize XRPL client
        client = get_xrpl_client()
        if not client:
            raise ConnectionError("Failed to initialize XRPL client.")

        # Send request for trust lines
        response = client.request(account_lines_request)

        if not response or not response.is_successful():
            logger.error(f"Failed to fetch trust lines for {wallet_address}: {response.result}")
            raise ConnectionError("Error fetching trust lines.")

        # Log raw response for debugging
        logger.debug(XRPL_RESPONSE)
        logger.debug(json.dumps(response.result, indent=4, sort_keys=True))

        # Extract trust lines
        trust_lines = response.result.get("lines", [])
        logger.info(f"Successfully fetched {len(trust_lines)} trust lines for account {wallet_address}.")

        return trust_line_response(response)

    except Exception as e:
        logger.error(f"Error fetching trust lines for {wallet_address}: {e}")
        return JsonResponse({'status': 'failure', 'message': f"Error fetching trust lines: {e}"}, status=500)

    finally:
        if client and hasattr(client, 'close'):
            client.close()  # Ensure client connection is properly closed
        logger.info(LEAVING_FUNCTION_LOG.format(function_name))


@api_view(['GET'])
@retry(wait=wait_exponential(multiplier=RETRY_BACKOFF), stop=stop_after_attempt(MAX_RETRIES))
def get_trust_line(request):
    function_name = 'get_trust_line'
    logger.info(ENTERING_FUNCTION_LOG.format(function_name))

    try:
        # Extract wallet address from request parameters
        wallet_address = get_request_param(request, 'wallet_address')
        if not wallet_address:
            raise ValueError("Account is required.")

        # Prepare an AccountLines request to retrieve trust lines for the account
        account_lines_request = AccountLines(account=wallet_address)

        # Initialize and use the XRPL client to fetch ledger information
        client = get_xrpl_client()
        if not client:
            raise ConnectionError(ERROR_INITIALIZING_CLIENT)

        response = client.request(account_lines_request)
        if not response or not response.is_successful():
            logger.error(f"Failed to fetch trust lines for {wallet_address}: {response.result}")
            raise ConnectionError("Error fetching trust lines.")

        # Log the raw response for detailed debugging
        logger.debug(XRPL_RESPONSE)
        logger.debug(json.dumps(response.result, indent=4, sort_keys=True))

        # Extract trust lines from the response
        trust_lines = response.result.get('lines', [])
        logger.info(f"Successfully fetched trust lines for account {wallet_address}.")
        return trust_line_response(response, trust_lines)

    except Exception as e:
        # Handle any unexpected errors that occur during the process
        return JsonResponse({'status': 'failure', 'message': f"Error fetching trust lines: {e}"}, status=500)
    finally:
        logger.info(LEAVING_FUNCTION_LOG.format(function_name))


@api_view(['POST'])
@retry(wait=wait_exponential(multiplier=RETRY_BACKOFF), stop=stop_after_attempt(MAX_RETRIES))
def set_trust_line(request):
    function_name = 'set_trust_line'
    logger.info(ENTERING_FUNCTION_LOG.format(function_name))

    try:
        # Extract parameters from the request data
        sender_seed = get_request_param(request, 'sender_seed')
        wallet_address = get_request_param(request, 'wallet_address')
        currency = get_request_param(request, 'currency')
        limit = get_request_param(request, 'limit')

        # Log the received parameters
        logger.info(
            f"Received parameters - sender_seed: {sender_seed}, wallet_address: {wallet_address}, currency: {currency}, limit: {limit}")

        # Validate that all required parameters are provided
        if not sender_seed or not wallet_address or not currency or not limit:
            error_message = 'Missing required parameters'
            logger.error(error_message)
            return JsonResponse({'status': 'failure', 'message': error_message}, status=400)

        # Convert the limit to drops if the currency is XRP
        limit_drops = xrpl.utils.xrp_to_drops(limit) if currency == "XRP" else limit
        logger.info(f"Converted limit: {limit_drops}")

        # Initialize the XRPL client
        client = get_xrpl_client()
        if not client:
            error_message = 'Failed to initialize XRPL client'
            logger.error(error_message)
            return JsonResponse({'status': 'failure', 'message': error_message}, status=500)

        # Create a wallet from the sender's seed
        try:
            sender_wallet = Wallet.from_seed(sender_seed)
            logger.info(f"Sender wallet created: {sender_wallet.classic_address}")
        except Exception as e:
            error_message = f"Error creating sender wallet: {str(e)}"
            logger.error(error_message)
            return JsonResponse({'status': 'failure', 'message': error_message}, status=500)

        # Fetch the current sequence number for the sender's account
        try:
            account_info = client.request(xrpl.models.requests.AccountInfo(account=sender_wallet.classic_address))
            if not account_info or not account_info.result:
                error_message = 'Unable to fetch account info'
                logger.error(error_message)
                return JsonResponse({'status': 'failure', 'message': error_message}, status=500)

            sequence_number = account_info.result['account_data']['Sequence']
            logger.info(f"Fetched sequence number: {sequence_number}")
        except Exception as e:
            error_message = f"Error fetching account info: {str(e)}"
            logger.error(error_message)
            return JsonResponse({'status': 'failure', 'message': error_message}, status=500)

        # Fetch the current network fee
        try:
            fee_response = client.request(xrpl.models.requests.Fee())
            fee = fee_response.result['drops']['minimum_fee']
            logger.info(f"Fetched network fee: {fee}")
        except Exception as e:
            error_message = f"Error fetching network fee: {str(e)}"
            logger.error(error_message)
            return JsonResponse({'status': 'failure', 'message': error_message}, status=500)

        # Prepare the TrustSet transaction
        try:
            trust_set_tx = create_trust_set_transaction(currency, limit_drops, wallet_address,
                                                        sender_wallet.classic_address, sequence_number, fee)
            logger.info(f"Created TrustSet transaction: {trust_set_tx}")
        except Exception as e:
            error_message = f"Error creating TrustSet transaction: {str(e)}"
            logger.error(error_message)
            return JsonResponse({'status': 'failure', 'message': error_message}, status=500)

        # Sign the transaction
        try:
            signed_tx = xrpl.transaction.sign(trust_set_tx, sender_wallet)
            logger.info(f"Signed transaction: {signed_tx}")
        except Exception as e:
            error_message = f"Error signing transaction: {str(e)}"
            logger.error(error_message)
            return JsonResponse({'status': 'failure', 'message': error_message}, status=500)

        # Submit the signed transaction
        try:
            response = xrpl.transaction.submit(signed_tx, client)
            logger.info(f"Transaction response: {response}")
            if not response or not response.is_successful():
                error_message = 'Error submitting TrustSet transaction'
                logger.error(error_message)
                return JsonResponse({'status': 'failure', 'message': error_message}, status=500)

            # Log and return successful response
            logger.info(f"Trust line set successfully for account {wallet_address}")
            return create_trust_set_response(response, wallet_address, currency, limit)

        except Exception as e:
            error_message = f"Error submitting transaction: {str(e)}"
            logger.error(error_message)
            return JsonResponse({'status': 'failure', 'message': error_message}, status=500)

    except Exception as e:
        error_message = f"Unexpected error: {str(e)}"
        logger.error(error_message)
        return JsonResponse({'status': 'failure', 'message': error_message}, status=500)

    finally:
        logger.info(LEAVING_FUNCTION_LOG.format(function_name))
