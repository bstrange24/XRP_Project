import json
import logging
import re
from decimal import Decimal

import xrpl
from django.apps import apps
from django.core.cache import cache
from django.http import JsonResponse
from xrpl import XRPLException
from xrpl.clients import JsonRpcClient
from xrpl.core.addresscodec import is_valid_classic_address, is_valid_xaddress
from xrpl.core.keypairs import derive_keypair, derive_classic_address
from xrpl.models import ServerInfo, Payment, AccountInfo, AccountSet, AccountTx, Tx, AccountDelete, TrustSet, \
    IssuedCurrencyAmount, Response
from xrpl.utils import xrp_to_drops, drops_to_xrp

from .constants import BASE_RESERVE, REQUIRE_DESTINATION_TAG_FLAG, DISABLE_MASTER_KEY_FLAG, \
    ENABLE_REGULAR_KEY_FLAG, INVALID_WALLET_IN_REQUEST, XRPL_RESPONSE
from .models import XrplAccountData, XrplPaymentData

logger = logging.getLogger('xrpl_app')


def handle_error(error_message, status_code, function_name):
    """
    This function handles error responses by logging the error, creating a JSON response, and returning it with an appropriate status code.
    - Logs the error message and function exit.
    - Constructs a JSON response with the error message.
    - Sets the HTTP status code based on the error context.
    Parameters:
    - error_message: The details of the error to be logged and returned.
    - status_code: HTTP status code to set for the response.
    - function_name: Name of the function where the error occurred for logging.
    """

    logger.error(error_message)
    logger.error(f"Leaving: {function_name}")
    return JsonResponse(error_message, status=status_code)


def is_valid_transaction_hash(transaction_hash: str) -> bool:
    """
    Check if the provided transaction hash is valid.

    A valid transaction hash is a 64-character string consisting of
    hexadecimal characters (0-9, A-F, or a-f).

    Args:
        transaction_hash (str): The transaction hash to validate.

    Returns:
        bool: True if the transaction hash is valid, False otherwise.
    """
    # Check if the transaction_hash is None
    if transaction_hash is None:
        return False

    # Use a regular expression to validate the transaction hash format
    # The regex pattern checks for exactly 64 hexadecimal characters
    return bool(re.fullmatch(r"^[A-Fa-f0-9]{64}$", transaction_hash))


def validate_xrp_wallet(address):
    """
    Validates whether the provided address is a valid XRP wallet address.

    This function checks if the address is either a valid classic XRP address
    or a valid X-Address format. If the address is valid, it logs the type of
    address and returns True. If the address is invalid, it logs an error and
    returns False.

    Args:
        address (str): The XRP wallet address to validate.

    Returns:
        bool: True if the address is valid (classic or X-Address), False otherwise.
    """
    if is_valid_classic_address(address):
        logger.info(f"Classic Address: {address}")
        return True
    elif is_valid_xaddress(address):
        logger.info(f"X-Address: {address}")
        return True
    else:
        logger.error(f"Invalid Address: {address}")
        return False


def is_valid_xrpl_seed(seed: str) -> bool:
    """
    Validates an XRP Ledger (XRPL) seed.

    A valid XRPL seed must be able to derive a keypair, from which a classic address can be derived,
    and that address must be valid according to the XRPL's rules.

    Args:
        seed (str): The XRPL seed to validate.

    Returns:
        bool: True if the seed is valid, False otherwise.
    """
    try:
        # Attempt to derive a keypair from the seed. If this fails, the seed is invalid.
        public_key, _ = derive_keypair(seed)

        # Derive a classic address from the derived public key.
        classic_address = derive_classic_address(public_key)

        # Validate the resulting classic address according to XRPL rules.
        return is_valid_classic_address(classic_address)

    except XRPLException:
        return False  # The seed was invalid, an exception was raised during the derivation process.


def get_xrpl_client() -> JsonRpcClient:
    """
    Retrieves an XRP Ledger (XRPL) client connected to the specified JSON-RPC server.

    This function fetches the XRPL API configuration from the application settings,
    specifically the JSON-RPC URL, and returns a `JsonRpcClient` object connected to that URL.

    Returns:
        JsonRpcClient: A client object connected to the XRPL JSON-RPC server.

    Raises:
        AppConfigError: If the 'xrpl_api' configuration is not found or is invalid.
    """
    xrpl_config = apps.get_app_config('xrpl_api')
    return JsonRpcClient(xrpl_config.JSON_RPC_URL)


def get_account_reserves():
    """
    Fetches the current reserve requirements from the XRP Ledger.

    This function queries the XRP Ledger server to retrieve the base reserve
    and reserve increment values, which are required for account operations.
    It handles errors gracefully and logs appropriate messages for debugging.

    Returns:
        tuple: A tuple containing (base_reserve, reserve_inc) as integers.
               If the data is unavailable or an error occurs, returns (None, None).

    Example:
        base_reserve, reserve_inc = get_account_reserves()
        if base_reserve and reserve_inc:
            print(f"Base Reserve: {base_reserve}, Reserve Increment: {reserve_inc}")
    """
    try:
        # Request server info from the XRP Ledger using the XRPL client
        response = get_xrpl_client().request(ServerInfo())

        # Extract the 'validated_ledger' object from the server info response
        validated_ledger = response.result.get('info', {}).get('validated_ledger', {})

        # Retrieve the base reserve and reserve increment values from the validated ledger
        base_reserve = validated_ledger.get('reserve_base_xrp')
        reserve_inc = validated_ledger.get('reserve_inc_xrp')

        # Check if either value is missing (None)
        if base_reserve is None or reserve_inc is None:
            logger.error("Reserve data not found in server info.")
            return None, None

        # Convert the values to integers and return them
        return int(base_reserve), int(reserve_inc)

    except Exception as e:
        # Log any exceptions that occur during the process
        logger.error(f"Error fetching server info: {e}")
        return None, None


def calculate_max_transferable(balance: float) -> int:
    """
    Calculates the maximum amount of XRP that can be transferred, factoring in the base reserve.

    Args:
        balance (float): The current wallet balance in XRP.

    Returns:
        int: Maximum transferable amount in drops.
    """

    max_transferable_xrp = balance - BASE_RESERVE
    return int(xrp_to_drops(max_transferable_xrp)) if max_transferable_xrp > 0 else 0


def build_flags(require_destination_tag, disable_master_key, enable_regular_key):
    """
    This function constructs a flag value for account settings in the XRP Ledger. It:

    - Takes boolean inputs for different account settings:
      - require_destination_tag: If true, forces transactions to this account to include a destination tag.
      - disable_master_key: If true, disables the master key for the account, enhancing security by requiring a regular key for transactions.
      - enable_regular_key: If true, enables a regular key which can be used for signing transactions instead of the master key.

    - Uses bitwise OR operations to combine flag values:
      - Each setting corresponds to a predefined flag constant (assumed to be defined elsewhere as constants).

    - Returns an integer representing the combined state of these flags, which can be used in XRPL transactions like AccountSet.

    Note: The function assumes that constants like REQUIRE_DESTINATION_TAG_FLAG, DISABLE_MASTER_KEY_FLAG, and ENABLE_REGULAR_KEY_FLAG are predefined.
    """

    # Initialize flags to zero; we will use bitwise operations to set specific flags
    flags = 0

    # Set the REQUIRE_DESTINATION_TAG flag if the condition is true
    if require_destination_tag:
        flags |= REQUIRE_DESTINATION_TAG_FLAG

    # Set the DISABLE_MASTER_KEY flag if the condition is true
    if disable_master_key:
        flags |= DISABLE_MASTER_KEY_FLAG

    # Set the ENABLE_REGULAR_KEY flag if the condition is true
    if enable_regular_key:
        flags |= ENABLE_REGULAR_KEY_FLAG

    # Return the combined flags as an integer
    return flags


def get_request_param(request, key, default=None, convert_func=None):
    """
    Retrieves a parameter from an HTTP request.

    This function attempts to fetch a value for the specified key from both GET and POST data in the request.
    If no value is found, it returns a default value. Optionally, it can apply a conversion function to the retrieved value before returning it.

    Args:
        request (HttpRequest): The incoming HTTP request object.
        key (str): The key of the parameter to retrieve.
        default (Any, optional): The default value to return if the parameter is not found. Defaults to None.
        convert_func (Callable[[str], Any], optional): A function to apply to the retrieved value for conversion or validation. Should accept a single string argument and return the converted value.

    Returns:
        Any: The value of the parameter after applying the conversion function, if any, otherwise the original value.

    Examples:
        # Retrieve an integer parameter 'age' from the request
        age = get_request_param(request, 'age', convert_func=int)

        # Retrieve a string parameter 'username' with a default value 'guest'
        username = get_request_param(request, 'username', default='guest')
    """
    value = request.GET.get(key) or request.data.get(key, default)
    if convert_func and value is not None:
        return convert_func(value)  # Apply conversion function if provided
    return value


def extract_request_data(request):
    """
    Extracts and validates data from an HTTP request for processing.

    This function retrieves the following data from the request:
    - `sender_seed`: The seed of the sender (required).
    - `receiver_address`: The address of the receiver (optional).
    - `amount_xrp`: The amount of XRP to transfer (optional, must be a valid decimal).

    Args:
        request: The HTTP request object containing query parameters or JSON data.

    Returns:
        tuple: A tuple containing (sender_seed, receiver_address, amount_xrp).

    Raises:
        ValueError: If `sender_seed` is missing or if `amount_xrp` is in an invalid format.
    """
    # Extract sender_seed from either query parameters or request body
    sender_seed = request.GET.get('sender_seed') or request.data.get('sender_seed')
    if not sender_seed:
        # Raise an error if sender_seed is missing (required field)
        raise ValueError("sender_seed is required")

    # Extract receiver_address from either query parameters or request body
    receiver_address = request.GET.get('receiver') or request.data.get('receiver')

    # Initialize amount_xrp as None (optional field)
    amount_xrp = None

    # Extract amount_str from either query parameters or request body
    amount_str = request.GET.get('amount') or request.data.get('amount')
    if amount_str:
        try:
            # Attempt to convert amount_str to a Decimal
            amount_xrp = Decimal(amount_str)
        except Exception as e:
            # Raise an error if the amount is not a valid decimal
            raise ValueError(f"Invalid amount format: {str(e)}")

    # Return the extracted data as a tuple
    return sender_seed, receiver_address, amount_xrp


def validate_xrpl_response(response: Response, required_keys=None):
    """
    Validates an XRPL response by checking success status, error fields, and required keys.

    Args:
        response (Response): The XRPL response object to validate.
        required_keys (list, optional): A list of keys that must exist in response.result.

    Returns:
        tuple: (bool, dict) where:
            - bool indicates if the response is valid
            - dict contains the result if valid, or error details if invalid
    """
    # Ensure response is an instance of xrpl Response
    if not isinstance(response, Response):
        return False, {"error": "Invalid response object type"}

    # Check if response is successful
    if not response.is_successful():
        return False, {
            "error": response.result.get("error", "Unknown error"),
            "error_code": response.result.get("error_code"),
            "error_message": response.result.get("error_message", "No additional details."),
        }

    # Ensure response.result is a valid dictionary
    if not isinstance(response.result, dict):
        return False, {"error": "Invalid response format. 'result' should be a dictionary."}

    # Validate required keys in response.result
    if required_keys:
        missing_keys = [key for key in required_keys if key not in response.result]
        if missing_keys:
            return False, {"error": f"Missing required fields: {missing_keys}"}

    # Check if ledger index is validated for transaction finality
    if response.result["validated"] == "False":
        return False, {"error": "Transaction is not valid on the ledger."}

    return True, response.result  # Valid response


def validate_request_data(sender_seed: str, receiver_address: str, amount_xrp: int) -> None:
    """
    Validates the required parameters for an XRPL transaction.

    Args:
        sender_seed (str): The secret seed of the sender's wallet.
        receiver_address (str): The classic address of the receiver.
        amount_xrp (int): The amount of XRP to send in XRP units.

    Raises:
        ValueError: If any required parameter is missing or if any parameter is invalid.

    This function performs the following validations:
    - Ensures all required parameters are provided.
    - Validates that the receiver's address is a valid classic XRPL address.
    - Validates that the sender's seed is a valid XRPL seed.
    """

    # Check if all required parameters are provided
    if not all([sender_seed, receiver_address, amount_xrp]):
        raise ValueError("Missing required parameters.")

    # Validate the receiver's classic address
    if not is_valid_classic_address(receiver_address):
        raise ValueError(INVALID_WALLET_IN_REQUEST)

    # Validate the sender's secret seed
    if not is_valid_xrpl_seed(sender_seed):
        raise ValueError("Sender seed is invalid.")


def fetch_network_fee(client):
    """
    Fetches the current network fee for XRP transactions from the XRPL server.

    Args:
        client (JsonRpcClient): The client object to communicate with the XRPL server.

    Returns:
        int: The network fee in drops (1 drop = 0.000001 XRP).

    Raises:
        ValueError: If there is an error fetching or processing the network fee.

    This function performs the following steps:
    - Sends a request to the XRPL server for server information.
    - Extracts the base fee from the validated ledger in the response.
    - Converts the extracted base fee from XRP to drops.
    - Returns the converted fee.

    If any error occurs during this process, it logs the error and raises a ValueError with an appropriate message.
    """

    try:
        # Send a request to the XRPL server for server information
        server_info = client.request(ServerInfo())

        # Check if the response is valid
        if not server_info:
            raise ValueError("Error initializing server info.")

        # Extract the base fee from the validated ledger in XRP units
        raw_fee_xrp = Decimal(server_info.result['info']['validated_ledger']['base_fee_xrp'])

        # Convert the base fee from XRP to drops (1 drop = 0.000001 XRP)
        return xrp_to_drops(raw_fee_xrp)

    except (KeyError, TypeError, AttributeError, ValueError) as e:
        # Log the error and raise a ValueError with an appropriate message
        logger.error(f"Failed to fetch network fee: {str(e)}")
        raise ValueError("Failed to fetch network fee. Please try again.")


def process_payment_response(payment_response, sender_address: str, receiver_address: str, amount_xrp: Decimal,
                             fee_drops: int):
    """
    Processes the response from a payment submission to the XRPL network.

    Args:
        payment_response (PaymentResponse): The response object from submitting a payment.
        sender_address (str): The classic address of the sender.
        receiver_address (str): The classic address of the receiver.
        amount_xrp (Decimal): The amount sent in XRP.
        fee_drops (int): The transaction fee in drops.

    Returns:
        dict: A dictionary representing the response to send back to the client.

    This function processes the payment response from the XRPL network, checking its success and handling
    various scenarios such as successful payments, missing data, errors, and internal exceptions.
    """
    try:
        # Check if the payment response was successful
        if not payment_response or not hasattr(payment_response,
                                               'is_successful') or not payment_response.is_successful():
            raise ValueError(f"Payment response was unsuccessfully {payment_response}")

        # Extract the transaction hash from the response
        transaction_hash = payment_response.result.get('hash')
        if not transaction_hash:
            raise ValueError("Transaction hash missing in response.")

        logger.info(f"Payment successful: {transaction_hash}")

        # Save the transaction details
        save_transaction(sender_address, receiver_address, amount_xrp, transaction_hash)

        # Update the balances of both sender and receiver accounts
        update_account_balances(sender_address, receiver_address, amount_xrp)

        # Send a response to indicate successful payment
        return send_payment_response(transaction_hash, sender_address, receiver_address, amount_xrp, fee_drops)
    except (AttributeError, KeyError, TypeError, ValueError) as e:
        # Log critical error and handle it by sending an error response
        logger.critical(f"Unexpected error in process_payment_response: {str(e)}", exc_info=True)
        return handle_error({'status': 'failure', 'message': f'Internal error: {str(e)}'}, 500, 'send_payment')
    except Exception as e:
        # Log critical error and handle it by sending an error response
        logger.critical(f"Unexpected error in process_payment_response: {str(e)}", exc_info=True)
        return handle_error({'status': 'failure', 'message': f'{str(e)}'}, 500, 'send_payment')


def update_account_balances(sender_address: str, receiver_address: str, amount_xrp: Decimal):
    """
    Updates the account balances for both the sender and the receiver after a payment transaction.

    Args:
        sender_address (str): The classic address of the sender.
        receiver_address (str): The classic address of the receiver.
        amount_xrp (Decimal): The amount sent in XRP.

    Raises:
        ValueError: If there is an issue with the balance or if the sender's account does not exist.

    This function updates the balances for both the sender and receiver accounts after a successful payment
    transaction. It checks that the sender has sufficient funds, updates their balance accordingly, fetches
    or creates the receiver's account (if it doesn't already exist), and then updates their balance. If any errors
    occur during this process, appropriate exceptions are raised with descriptive error messages.
    """
    try:
        # Fetch and update sender's account balance
        sender_account = XrplAccountData.objects.get(account=sender_address)
        if sender_account.balance < amount_xrp:
            raise ValueError("Insufficient balance in sender's account.")

        sender_account.balance -= amount_xrp
        sender_account.save()

        # Fetch or create receiver's account and update balance
        receiver_account, created = XrplAccountData.objects.get_or_create(
            account=receiver_address,
            defaults={'balance': amount_xrp}
        )
        if not created:
            receiver_account.balance += amount_xrp
            receiver_account.save()

    except XrplAccountData.DoesNotExist:
        logger.error(f"Sender account {sender_address} not found.")
        raise ValueError("Sender account does not exist.")

    except ValueError as e:
        logger.error(f"ValueError in update_account_balances: {str(e)}")
        raise  # Re-raise for the calling function to handle

    except Exception as e:
        logger.critical(f"Unexpected error updating account balances: {str(e)}", exc_info=True)
        raise ValueError("An unexpected error occurred while updating balances.") from e


def get_account_details(client, wallet_address: str):
    """
    Retrieves details for a specified XRP Ledger (XRPL) wallet address using an XRPL client.

    Args:
        client: An XRPL client instance capable of making requests to the XRPL network.
        wallet_address (str): The classic address of the wallet whose details are desired.

    Returns:
        dict or None: A dictionary containing the account details if successful, or None if there was an error.

    This function prepares a request to retrieve account details for a given wallet address and sends it
    using the provided XRPL client. It logs debug information about the response and checks if the request
    was successful. If so, it returns the account details in a dictionary format. Otherwise, it logs an error
    and returns None.
    """
    try:
        # Prepare account data for the request
        account_info = prepare_account_data(wallet_address)

        # Send the request to the XRPL client
        response = client.request(account_info)

        # Log debug information about the response
        logger.debug(XRPL_RESPONSE)
        logger.debug(json.dumps(response.result, indent=4, sort_keys=True))

        # Check if the response status is 'success'
        if response and response.status == 'success':
            result = response.result
            return {
                'result': result,
            }
        else:
            logger.error(f"Failed to retrieve account details. Response: {response.text}")
            return None

    except Exception as e:
        # Log any exceptions that occur during the request
        logger.error(f"Error retrieving account details: {str(e)}")
        return None


# def get_account_info_with_cache(client, wallet_address):
#     cache_key = f"get_wallet_info:{wallet_address}"
#     cached_data = cache.get(cache_key)
#     if cached_data:
#         logger.info(f"Cache hit for wallet address: {wallet_address}")
#         return cached_data
#
#     try:
#         response = get_account_details(client, wallet_address)
#         if not response:
#             raise xrpl.XRPLException(ERROR_IN_XRPL_RESPONSE)
#
#         account_info = response['result']
#         cache.set(cache_key, account_info, CACHE_TIMEOUT_FOR_WALLET)
#         return account_info
#
#     except Exception as e:
#         logger.error(f"Failed to fetch account info: {e}")
#         raise e
#
#

# def convert_balance_to_xrp1(balance_drops):
#     try:
#         return round(drops_to_xrp(balance_drops), 2)
#     except Exception as e:
#         logger.error(f"Error converting balance to XRP: {str(e)}")
#         return None


# def set_cache_balance(wallet_address, response_data):
#     cache_key = f"balance:{wallet_address}"
#     cache.set(cache_key, response_data, CACHE_TIMEOUT)


# def update_cache(wallet_address, balance):
#     cache[wallet_address] = balance


def convert_drops_to_xrp(balance_drops: str):
    """
    Converts a balance from drops to XRP.

    Args:
        balance_drops (str): The balance amount in drops.

    Returns:
        float: The converted balance in XRP, rounded to 2 decimal places.
    """
    # Convert the balance from drops to XRP
    return round(drops_to_xrp(balance_drops), 2)


def get_cached_data(cache_key, wallet_address, function_name):
    """
    Retrieves data from cache using a specified key.

    Args:
        cache_key (str): The key used to store and retrieve data in the cache.
        wallet_address (str): The wallet address associated with the cached data.
        function_name (str): The name of the function calling this method for logging purposes.

    Returns:
        dict or None: The cached data if successful, otherwise None. Logs relevant information based on whether
                      a cache hit or miss occurred and handles errors appropriately.

    This function attempts to retrieve data from the cache using a provided key. If the cache hit is successful,
    it logs an informational message indicating a cache hit and returns the cached data if it's a dictionary.
    If the cached data is not a valid dictionary, it logs an error and raises an appropriate exception. If the cache
    miss occurs, it logs an informational message indicating a cache miss and returns None.
    """
    # Attempt to retrieve cached data using the provided key
    cached_data = cache.get(cache_key)

    if cached_data:
        # Log information if the cache hit is successful
        logger.info(f"Cache hit for wallet address: {wallet_address}")

        # Log details about the cached data
        logger.debug(f"Cached data type: {type(cached_data)} - Value: {cached_data}")

        # Check if the cached data is a dictionary
        if isinstance(cached_data, dict):
            return cached_data
        else:
            # Handle error if the cached data is not a valid dictionary
            handle_error({'status': 'failure', 'message': 'Cached data is not a valid dictionary.'},
                         status_code=500,
                         function_name=function_name)
            return None

    # Log information if the cache miss occurs
    logger.info(f"Cache missed for wallet address: {wallet_address}")

    return None


def parse_boolean_param(request, param_name, default="false"):
    """
    Parses a boolean parameter from an HTTP request.

    Args:
        request: The HTTP request object containing the parameters.
        param_name (str): The name of the parameter to be parsed as a boolean.
        default (str): The default value to use if the parameter is not present. Defaults to "false".

    Returns:
        bool: True if the parameter value indicates a true state, False otherwise.

    This function retrieves the specified parameter from an HTTP request and attempts to parse it as a boolean.
    It uses the `get_request_param` function to fetch the parameter value, converting it to lowercase for case-insensitive comparison.
    The function returns True if the parameter's value is in the set ["true", "1", "yes"], otherwise it returns False.
    If the parameter is not present, it uses the provided default value and proceeds with the parsing.
    """
    # Retrieve the parameter value from the request, using the specified default if not present
    value = get_request_param(request, param_name, default=default).lower()

    # Check if the parsed value indicates a true state
    return value in ["true", "1", "yes"]


def prepare_account_set_tx(sender_address, flags):
    """
    Prepares an AccountSet transaction for the XRPL.

    Args:
        sender_address (str): The address of the account sending the transaction.
        flags (int): A bitmask representing the flags to be set in the transaction.

    Returns:
        xrpl.models.transactions.AccountSet: An AccountSet transaction object with the specified parameters.

    This function constructs an AccountSet transaction for the XRPL, which is used to modify various settings and properties of an account.
    It takes two arguments: `sender_address`, which is the address of the account sending the transaction, and `flags`, which is a bitmask
    representing the flags to be set in the transaction. The function returns an `AccountSet` object configured with these parameters.
    """
    # Prepare and return an AccountSet transaction object
    return AccountSet(
        account=sender_address,
        flags=flags
    )


def prepare_account_tx(sender_address):
    """
    Prepares an `AccountTx` request object to fetch transactions for a given sender address.

    This function creates and returns an `AccountTx` object configured to retrieve
    the transaction history for the specified sender address. The limit is set to 100
    to fetch more transactions in a single request, reducing the need for multiple
    API calls.

    Args:
        sender_address (str): The XRP Ledger address of the sender whose transactions
                              are to be fetched.

    Returns:
        AccountTx: A configured `AccountTx` object ready to be used in a request.

    Example:
        account_tx_request = prepare_account_tx("rExampleAddress123")
        response = xrpl_client.request(account_tx_request)
    """
    return AccountTx(
        account=sender_address,
        limit=100  # Increase limit to fetch more transactions at once, reducing the need for multiple requests
    )


def prepare_account_data(sender_address):
    """
    Prepares an `AccountInfo` request object to fetch account data for a given sender address.

    This function creates and returns an `AccountInfo` object configured to retrieve
    the latest validated account information for the specified sender address. The
    request is set to use the latest validated ledger and enforces strict validation
    to ensure the address is in the correct format.

    Args:
        sender_address (str): The XRP Ledger address of the sender whose account data
                             is to be fetched.

    Returns:
        AccountInfo: A configured `AccountInfo` object ready to be used in a request.

    Example:
        account_info_request = prepare_account_data("rExampleAddress123")
        response = xrpl_client.request(account_info_request)
    """
    return AccountInfo(
        account=sender_address,
        ledger_index="validated",  # Use the latest validated ledger
        strict=True,  # Enforce strict validation of the address format
    )


def prepare_account_delete(sender_address):
    """
    Prepares an AccountDelete transaction for the XRPL.

    Args:
        sender_address (str): The address of the account to be deleted.

    Returns:
        xrpl.models.transactions.AccountDelete: An AccountDelete transaction object with the specified parameters.

    This function constructs an AccountDelete transaction for the XRPL, which is used to delete an account.
    It takes one argument: `sender_address`, which is the address of the account that will be deleted.
    The function returns an `AccountDelete` object configured with this parameter. Note that the destination
    field in AccountDelete must match the sender's address, and a transaction fee is specified.
    """
    # Prepare and return an AccountDelete transaction object
    return AccountDelete(
        account=sender_address,
        destination=sender_address,
        fee="12",
    )


def prepare_account_tx_with_pagination(sender_address, marker):
    """
    Prepares an AccountTx transaction for the XRPL with pagination parameters.

    Args:
        sender_address (str): The address of the account to query transactions for.
        marker (any): A marker value used for pagination to retrieve the next set of transactions.

    Returns:
        xrpl.models.transactions.AccountTx: An AccountTx transaction object configured with the specified parameters.

    This function constructs an AccountTx transaction for the XRPL, which is used to retrieve transactions associated with a specific account.
    It takes two arguments: `sender_address`, which is the address of the account whose transactions are being queried, and `marker`,
    which is a marker value used for pagination. The function returns an `AccountTx` object configured with these parameters:
    - `ledger_index_min` and `ledger_index_max` set to `-1` indicate that all ledgers should be considered.
    - `limit` set to `100` specifies the maximum number of transactions to return in a single response.
    - `marker` is used for pagination, allowing retrieval of subsequent pages of transactions.
    """
    # Prepare and return an AccountTx transaction object with pagination parameters
    return AccountTx(
        account=sender_address,
        ledger_index_min=-1,
        ledger_index_max=-1,
        limit=100,
        marker=marker,
    )


def prepare_tx(tx_hash):
    """
    Prepares a `Tx` request object to fetch details of a specific transaction.

    This function creates and returns a `Tx` object configured to retrieve
    the details of a transaction identified by its transaction hash. The
    transaction hash is used to query the XRP Ledger for the corresponding
    transaction data.

    Args:
        tx_hash (str): The transaction hash (ID) of the transaction to fetch.

    Returns:
        Tx: A configured `Tx` object ready to be used in a request.

    Example:
        tx_request = prepare_tx("ABC123TransactionHashXYZ")
        response = xrpl_client.request(tx_request)
    """
    return Tx(transaction=tx_hash)


def create_payment_transaction(sender_address: str, receiver_address: str, amount_drops: int, fee_drops: int,
                               send_and_delete_wallet: bool) -> Payment:
    """
    Creates a Payment transaction object for transferring funds between two addresses.

    This function constructs a Payment transaction based on the provided parameters. Depending on the
    `send_and_delete_wallet` flag, the transaction may or may not include a fee. This is useful in scenarios
    where the sender's wallet is to be deleted after the transaction (e.g., for account deletion workflows).

    Parameters:
    - sender_address (str): The address of the sender initiating the payment.
    - receiver_address (str): The address of the receiver receiving the payment.
    - amount_drops (int): The amount to send, specified in drops (the smallest unit of the currency).
    - fee_drops (int): The transaction fee, specified in drops. Only applied if `send_and_delete_wallet` is False.
    - send_and_delete_wallet (bool): A flag indicating whether the sender's wallet will be deleted after the transaction.
                                     If True, the fee is omitted from the transaction.

    Returns:
    - Payment: A Payment object representing the transaction, configured based on the provided parameters.
    """
    if send_and_delete_wallet:
        # Create a Payment transaction without a fee (used when the sender's wallet will be deleted)
        return Payment(
            account=sender_address,
            destination=receiver_address,
            amount=str(amount_drops)  # Amount must be passed as a string
        )
    else:
        # Create a Payment transaction with a fee (standard use case)
        return Payment(
            account=sender_address,
            destination=receiver_address,
            amount=str(amount_drops),
            fee=str(fee_drops),  # Fee must be passed as a string
        )


def create_account_delete_transaction(sender_address: str, receiver_address: str):
    """
    Creates a transaction to delete an account on the XRP Ledger.

    Args:
        sender_address (str): The address of the account that will send the transaction.
        receiver_address (str): The address of the account that will be deleted.

    Returns:
        AccountDelete: An AccountDelete object representing the created transaction.

    This function constructs a transaction to delete an account on the XRP Ledger. It takes two arguments:
    - `sender_address`: The address of the account that will send the transaction.
    - `receiver_address`: The address of the account that will be deleted.

    The function returns an AccountDelete object representing the created transaction.

    Note: Before executing this transaction, you must sign it with the appropriate private key and submit it to the XRP Ledger using a suitable library or API.
    """
    # Construct an AccountDelete operation
    return AccountDelete(
        account=sender_address,
        destination=receiver_address
    )


def create_trust_set_transaction(currency, limit_drops, wallet_address, sender_wallet, sequence_number, fee):
    """
    Creates a TrustSet transaction for setting a trust line on the XRPL.

    Args:
        currency (str): The currency code for the trust line (e.g., 'USD').
        limit_drops (str): The limit for the trust line in drops (1 drop = 0.000001 XRP).
        wallet_address (str): The address of the wallet that is setting the trust line.
        sender_wallet (Wallet): The wallet object representing the sender.
        sequence_number (int): The current sequence number of the sender's account.
        fee (str): The transaction fee in drops.

    Returns:
        TrustSet: A TrustSet transaction object ready to be submitted to the XRPL.
    """
    return TrustSet(
        account=sender_wallet,  # Set the sender wallet as the account for the transaction
        limit_amount=IssuedCurrencyAmount(  # Properly instantiate IssuedCurrencyAmount
            currency=currency,  # The currency code for the trust line
            value=str(limit_drops),  # Ensure the value is a string
            issuer=wallet_address,  # The issuer of the trust line
        ),
        sequence=sequence_number,  # Add the sequence number here
        fee=fee,  # Add the fee here
    )


def create_trust_set_response(response, account, currency, limit):
    """
    Creates a JSON response for successful trust line set operations.

    Args:
        response (xrpl.models.response.Response): The response object from the XRPL transaction.
        account (str): The address of the account that had the trust line set.
        currency (str): The currency code for the trust line.
        limit (str): The limit for the trust line in drops.

    Returns:
        JsonResponse: A Django JsonResponse containing the success message and transaction details.
    """
    # Create a JSON response with success status, message, and transaction details
    return JsonResponse({
        'status': 'success',  # Indicate that the operation was successful
        'message': 'Trust line set successfully.',  # Provide a success message
        'result': response.result,  # Include the result from the XRPL transaction
        'account': account,  # Include the account address that had the trust line set
        'currency': currency,  # Include the currency code for the trust line
        'limit': limit,  # Include the limit for the trust line in drops
    })


def create_wallet_info_response(base_reserve, reserve_increment, account_details):
    """
    Creates and returns a JSON response containing wallet information including base reserve, reserve increment, and account details.

    Args:
        base_reserve (float): The base reserve amount for the wallet.
        reserve_increment (float): The incremental reserve amount for the wallet.
        account_details (dict): Detailed account information from the XRPL.

    Returns:
        JsonResponse: A JSON response object with the wallet information.
    """
    return JsonResponse({
        'status': 'success',
        'message': 'Successfully retrieved account information.',
        'reserve': base_reserve,
        'reserve_increment': reserve_increment,
        'result': account_details,
    })


def create_wallet_balance_response(balance_in_xrp):
    """
    Creates and returns a JSON response containing the wallet balance in XRP.

    Args:
        balance_in_xrp (float): The balance of the wallet in XRP.

    Returns:
        JsonResponse: A JSON response object with the balance information.
    """
    return JsonResponse({
        'status': 'success',
        'message': 'Successfully retrieved account balance.',
        "balance": balance_in_xrp,
    })


def create_account_response(wallet_address, seed, xrp_balance, account_details):
    """
    Creates and returns a JSON response containing details of a newly created wallet.

    Args:
        wallet_address (str): The address of the newly created wallet.
        seed (str): The secret seed for the wallet.
        xrp_balance (float): The initial XRP balance of the wallet.
        account_details (dict): Detailed account information from the XRPL.

    Returns:
        JsonResponse: A JSON response object with the wallet creation details.
    """
    return JsonResponse({
        'status': 'success',
        'message': 'Successfully created wallet.',
        'account_id': wallet_address,
        'secret': seed,
        'balance': xrp_balance,
        'transaction_hash': account_details['result']['ledger_hash'],
        'previous_transaction_id': account_details['result']['account_data']['PreviousTxnID'],
    })


def account_delete_tx_response(payment_response_hash, account_delete_response_hash):
    """
    Constructs a JSON response for the successful transfer of funds and deletion of an account.

    Args:
        payment_response_hash (str): The hash of the transaction that transferred funds.
        account_delete_response_hash (str): The hash of the transaction that deleted the account.

    Returns:
        JsonResponse: A Django JsonResponse object containing details of both transactions.

    This function prepares a JSON response indicating that funds have been successfully transferred and an account has been deleted.
    It takes two arguments:
    - `payment_response_hash`: The hash of the transaction that transferred funds.
    - `account_delete_response_hash`: The hash of the transaction that deleted the account.

    The function returns a Django JsonResponse object with keys for 'status', 'message', 'payment_tx_hash', and 'account_delete_tx_hash'.
    - 'status' indicates the outcome of the operations ('success').
    - 'message' provides a brief description of the operation result.
    - 'payment_tx_hash' contains the hash of the transaction that transferred funds.
    - 'account_delete_tx_hash' contains the hash of the transaction that deleted the account.

    This allows for a consistent format to inform clients about whether the operations were successfully completed and provide additional details if needed.
    """
    # Prepare and return a JSON response indicating successful transfer of funds and deletion of an account
    return JsonResponse({
        'status': 'success',
        'message': 'Funds transferred and account deleted successfully.',
        'payment_tx_hash': payment_response_hash,
        'account_delete_tx_hash': account_delete_response_hash
    })


def account_tx_with_pagination_response(paginated_transactions, count, num_pages):
    """
    Constructs a response dictionary for the account transaction history with pagination information.

    Args:
        paginated_transactions (xrpl.models.transactions.AccountTx): A paginated list of transactions.
        count (int): The total number of transactions retrieved.
        num_pages (int): The total number of pages available for pagination.

    Returns:
        JsonResponse: A JsonResponse containing the response data including transactions, counts, and pagination details.

    This function prepares a response dictionary that encapsulates the results of retrieving an account's transaction history with pagination support.
    It takes three arguments:
    - `paginated_transactions`: The paginated list of transactions retrieved from the XRPL.
    - `count`: The total number of transactions available for the given account.
    - `num_pages`: The total number of pages available for pagination.

    The function returns a dictionary with keys for status, message, transactions, total_transactions, pages, and current_page,
    providing a structured format to display the transaction history along with pagination information.
    """
    # Prepare and return a response dictionary containing transaction data and pagination details
    return JsonResponse({
        "status": "success",
        "message": "Transaction history successfully retrieved.",
        "transactions": list(paginated_transactions),
        "total_transactions": count,
        "pages": num_pages,
        "current_page": paginated_transactions.number,
    })


def delete_account_response(tx_response):
    """
    Constructs a JSON response for the deletion of an account.

    Args:
        tx_response (xrpl.models.transactions.TransactionResponse): The transaction response from the XRPL client.

    Returns:
        JsonResponse: A Django JsonResponse object containing the result of the account deletion.

    This function prepares a JSON response for the deletion of an account, including the status and message of the operation.
    It takes one argument:
    - `tx_response`: The transaction response from the XRPL client, which contains details about the deletion process.

    The function returns a Django JsonResponse object with keys for 'status', 'message', and 'tx_response'.
    - 'status' indicates the outcome of the operation ('success' or an error message).
    - 'message' provides a brief description of the operation result.
    - 'tx_response' contains the actual response from the XRPL client regarding the transaction.

    This allows for a consistent format to inform clients about whether the account deletion was successful and provide additional details if needed.
    """
    # Prepare and return a JSON response for the account deletion
    return JsonResponse({
        'status': 'success',
        'message': 'Account successfully deleted.',
        'tx_response': tx_response.result,
    })


def transaction_status_response(response, tx_hash):
    """
    Constructs a JSON response for the status of a transaction.

    Args:
        response (xrpl.models.response.Response): The response from the XRPL client containing transaction details.
        tx_hash (str): The hash of the transaction whose status is being retrieved.

    Returns:
        JsonResponse: A Django JsonResponse object containing the result of the transaction status retrieval.

    This function prepares a JSON response for retrieving the status of a specific transaction, including the status and message of the operation.
    It takes two arguments:
    - `response`: The response from the XRPL client, which contains details about the transaction.
    - `tx_hash`: The hash of the transaction whose status is being retrieved.

    The function returns a Django JsonResponse object with keys for 'status', 'message', and 'result'.
    - 'status' indicates the outcome of the operation ('success' or an error message).
    - 'message' provides a brief description of the operation result.
    - 'result' contains the actual response from the XRPL client regarding the transaction status.

    This allows for a consistent format to inform clients about whether the transaction status was successfully retrieved and provide additional details if needed.
    """
    # Log successful retrieval of transaction status
    logger.info(f"Transaction status retrieved successfully for hash: {tx_hash}")

    # Prepare and return a JSON response for the transaction status
    return JsonResponse({
        'status': 'success',
        'message': 'Payment successfully sent.',
        'result': response.result,  # Corrected from 'response.result' to 'result'
    })


def server_info_response(response):
    """
    Generates a JSON response containing the status, message, and ledger information.

    This function takes a response object, typically containing ledger information,
    and formats it into a JSON response with a success status and a descriptive message.

    Parameters:
    - response: An object containing the result of a ledger information retrieval operation.

    Returns:
    - JsonResponse: A JSON response with the following structure:
        {
            'status': 'success',
            'message': 'Ledger information successfully retrieved.',
            'ledger_info': response.result
        }
    """
    return JsonResponse({
        'status': 'success',
        'message': 'Ledger information successfully retrieved.',
        'ledger_info': response.result
    })


def account_reserves_response(server_information_response, reserve_base, reserve_inc):
    """
    Creates a JSON response for successfully fetching XRP reserves.

    Args:
        server_information_response (xrpl.models.response.Response): The response object from the XRPL server information query.
        reserve_base (int): The base reserve amount in drops.
        reserve_inc (int): The incremental reserve amount per account in drops.

    Returns:
        JsonResponse: A Django JsonResponse containing the success message and reserve details.
    """
    # Create a JSON response with success status, message, and reserve details
    return JsonResponse({
        'status': 'success',  # Indicate that the operation was successful
        'message': 'XRP reserves fetched successfully.',  # Provide a success message
        'base_reserve': reserve_base,  # Include the base reserve amount in drops
        'owner_reserve': reserve_inc,  # Include the incremental reserve amount per account in drops
        'result': server_information_response.result  # Include the result from the XRPL server information query
    })


def trust_line_response(response):
    """
    Creates a JSON response for successfully fetching trust lines.

    Args:
        response (xrpl.models.response.Response): The response object from the XRPL transaction to fetch trust lines.

    Returns:
        JsonResponse: A Django JsonResponse containing the success message and fetched trust line details.
    """
    # Create a JSON response with success status, message, and fetched trust line details
    return JsonResponse({
        'status': 'success',  # Indicate that the operation was successful
        'message': 'Trust lines fetched successfully.',  # Provide a success message
        'results': response.result  # Include the results from the XRPL transaction
    })


def account_set_tx_response(response, sender_address):
    """
    Constructs a JSON response for an AccountSet transaction.

    Args:
        response (xrpl.models.response.Response): The response from the XRPL client containing details of the transaction.
        sender_address (str): The address of the account that sent the AccountSet transaction.

    Returns:
        JsonResponse: A Django JsonResponse object containing the result of the AccountSet transaction.

    This function prepares a JSON response for an AccountSet transaction, including the status and message of the operation.
    It takes two arguments:
    - `response`: The response from the XRPL client, which contains details about the transaction.
    - `sender_address`: The address of the account that sent the AccountSet transaction.

    The function returns a Django JsonResponse object with keys for 'status', 'message', 'transaction_hash', 'account', and 'result'.
    - 'status' indicates the outcome of the operation ('success' or an error message).
    - 'message' provides a brief description of the operation result.
    - 'transaction_hash' contains the hash of the transaction.
    - 'account' contains the address of the sender's account.
    - 'result' contains the actual response from the XRPL client regarding the transaction.

    This allows for a consistent format to inform clients about whether the AccountSet transaction was successful and provide additional details if needed.
    """
    # Log successful completion of the AccountSet transaction
    logger.info(f"AccountSet transaction successful for account {sender_address}")

    # Prepare and return a JSON response for the AccountSet transaction
    return JsonResponse({
        'status': 'success',
        'message': 'Successfully updated account settings.',
        'transaction_hash': response.result['hash'],  # Corrected from 'response.result' to 'response.result["hash"]'
        'account': sender_address,
        'result': response.result
    })


def transaction_history_response(transaction_tx):
    # Prepare and return a JSON response for the transaction history
    return JsonResponse({
        'status': 'success',
        'message': 'Transaction history successfully retrieved.',
        'response': transaction_tx,
    })


def send_payment_response(transaction_hash, sender_address, receiver_address, amount_xrp, fee_drops):
    """
    Constructs a JSON response for a successfully sent payment.

    Args:
        transaction_hash (str): The hash of the transaction that was sent.
        sender_address (str): The address of the account sending the payment.
        receiver_address (str): The address of the account receiving the payment.
        amount_xrp (float): The amount of XRP being sent in dollars.
        fee_drops (int): The fee for the transaction in drops.

    Returns:
        JsonResponse: A Django JsonResponse object containing details of the payment transaction.

    This function prepares a JSON response indicating that a payment has been successfully sent.
    It takes five arguments:
    - `transaction_hash`: The hash of the transaction that was sent.
    - `sender_address`: The address of the account sending the payment.
    - `receiver_address`: The address of the account receiving the payment.
    - `amount_xrp`: The amount of XRP being sent in dollars.
    - `fee_drops`: The fee for the transaction in drops.

    The function returns a Django JsonResponse object with keys for 'status', 'message', 'transaction_hash', 'sender', 'receiver', 'amount', and 'fee_drops'.
    - 'status' indicates the outcome of the operation ('success').
    - 'message' provides a brief description of the operation result.
    - 'transaction_hash' contains the hash of the transaction that was sent.
    - 'sender' contains the address of the account sending the payment.
    - 'receiver' contains the address of the account receiving the payment.
    - 'amount' contains the amount of XRP being sent in dollars.
    - 'fee_drops' contains the fee for the transaction in drops.

    This allows for a consistent format to inform clients about whether the payment was successfully sent and provide additional details if needed.
    """
    # Prepare and return a JSON response indicating successful payment
    return JsonResponse({
        'status': 'success',
        'message': 'Payment successfully sent.',
        'transaction_hash': transaction_hash,
        'sender': sender_address,
        'receiver': receiver_address,
        'amount': amount_xrp,
        'fee_drops': fee_drops,
    })


def save_transaction(sender: str, receiver: str, amount: Decimal, transaction_hash: str):
    """
    Saves a payment transaction record to the database.

    Args:
        sender (str): The classic address of the sender.
        receiver (str): The classic address of the receiver.
        amount (Decimal): The amount sent in XRP.
        transaction_hash (str): The hash of the transaction on the XRPL network.

    This function creates a new record in the XrplPaymentData model to store information about a payment
    transaction, including details such as sender, receiver, amount, and transaction hash. If there is an error
    during this process, it will raise a DatabaseError.
    """
    XrplPaymentData.objects.create(
        sender=sender,
        receiver=receiver,
        amount=amount,
        transaction_hash=transaction_hash,
    )
