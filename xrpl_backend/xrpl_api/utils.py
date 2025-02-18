import asyncio
import logging
import re
import time
from decimal import Decimal

from django.apps import apps
from django.core.cache import cache
from django.http import JsonResponse
from xrpl import XRPLException
from xrpl.asyncio.transaction import submit_and_wait
from xrpl.clients import JsonRpcClient
from xrpl.core.addresscodec import is_valid_classic_address, is_valid_xaddress
from xrpl.core.keypairs import derive_keypair, derive_classic_address
from xrpl.ledger import get_fee
from xrpl.models import Response
from xrpl.utils import xrp_to_drops, drops_to_xrp

from .constants import BASE_RESERVE, REQUIRE_DESTINATION_TAG_FLAG, DISABLE_MASTER_KEY_FLAG, \
    ENABLE_REGULAR_KEY_FLAG, INVALID_WALLET_IN_REQUEST, MISSING_REQUEST_PARAMETERS
from .errors.error_handling import handle_engine_result, handle_error

logger = logging.getLogger('xrpl_app')


# def handle_error(error_message, status_code, function_name):
#     """
#     This function handles error responses by logging the error, creating a JSON response, and returning it with an appropriate status code.
#     - Logs the error message and function exit.
#     - Constructs a JSON response with the error message.
#     - Sets the HTTP status code based on the error context.
#     Parameters:
#     - error_message: The details of the error to be logged and returned.
#     - status_code: HTTP status code to set for the response.
#     - function_name: Name of the function where the error occurred for logging.
#     """
#
#     logger.error(error_message)
#     logger.error(f"Leaving: {function_name}")
#     return JsonResponse(error_message, status=status_code)

# def check_engine_result(response):
#     try:
#         # Convert the response to a dictionary
#         response_dict = response.result
#
#         # Check if the 'meta' field is present in the response
#         meta_key = 'engine_result'
#         if meta_key not in response_dict:
#             return True, "Missing 'engine_result' key."
#
#         # Get the 'engine_result' from the metadata
#         engine_result = response_dict[meta_key]
#
#         if engine_result == "tesSUCCESS":
#             return True, "Transaction was successful!"
#         else:
#             # Handle the engine result
#             engine_result = response.get("engine_result")
#             engine_result_message = response.get("engine_result_message", "No additional details")
#             handle_engine_result(engine_result, engine_result_message)
#             # return False, f"Transaction failed: {engine_result}"
#
#     except AttributeError as e:
#         # Handle cases where the response does not have a `.result` attribute
#         return False, f"Unexpected error: {e}"
#     except KeyError as e:
#         # Handle cases where expected keys are missing in the response
#         return False, f"Key not found: {e}"


# def check_transaction_response(response, key):
#     try:
#         # Ensure response.result is a valid dictionary
#         if not isinstance(response, dict):
#             return False, f"Invalid response format. 'result' should be a dictionary {response}"
#
#         # Check if the 'meta' field is present in the response
#         if key not in response:
#             return True, f"Missing {key} key."
#
#         # Get the 'engine_result' from the metadata
#         engine_result = response[key].get('TransactionResult', None)
#
#         if engine_result == "tesSUCCESS":
#             return True, "Transaction was successful!"
#         else:
#             # Handle the engine result
#             engine_result = response.get("engine_result")
#             engine_result_message = response.get("engine_result_message", "No additional details")
#             handle_engine_result(engine_result, engine_result_message)
#
#     except AttributeError as e:
#         # Handle cases where the response does not have a `.result` attribute
#         return False, f"Unexpected error: {e}"
#     except KeyError as e:
#         # Handle cases where expected keys are missing in the response
#         return False, f"Key not found: {e}"

# def check_engine_result(response):
#
#     try:
#         response = response.result
#         if response["engine_result"] == "tesSUCCESS":
#             return True, "Transaction was successful!"
#         else:
#             # Handle the engine result
#             engine_result = response.get("engine_result")
#             engine_result_message = response.get("engine_result_message", "No additional details")
#             handle_engine_result(engine_result, engine_result_message)
#     except Exception as e:
#         print(f"HERE: {e}")
#         return None, "No engine_result available for this transaction."



# def check_transaction_response(response):
#     try:
#         response = response.result
#         # Check if the 'meta' field is present
#         if 'meta' in response:
#             # Get the 'engine_result' field from the 'meta'
#             engine_result = response['meta'].get('TransactionResult', None)
#
#             if engine_result == "tesSUCCESS":
#                 return True, "Transaction was successful!"
#             else:
#                 return False, f"Transaction failed: {engine_result}"
#         else:
#             return None, "No metadata available for this transaction."
#     except XRPLException:
#         return None, "No metadata available for this transaction."



def total_execution_time_in_millis(start_time):
    end_time = time.time()  # Capture the end time
    return int((end_time - start_time) * 1000)  # Convert seconds to milliseconds


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
    # Check if the transaction_hash matches the regex pattern
    return bool(re.match(r"^[A-Fa-f0-9]{64}$", transaction_hash))


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
    Retrieves an XRP Ledger (XRPL) client connected to the specified JSON-RPC ledger.

    This function fetches the XRPL API configuration from the application settings,
    specifically the JSON-RPC URL, and returns a `JsonRpcClient` object connected to that URL.

    Returns:
        JsonRpcClient: A client object connected to the XRPL JSON-RPC ledger.

    Raises:
        AppConfigError: If the 'xrpl_api' configuration is not found or is invalid.
    """
    xrpl_config = apps.get_app_config('xrpl_api')
    return JsonRpcClient(xrpl_config.JSON_RPC_URL)


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
    sender_seed = get_request_param(request, 'sender_seed')
    if not sender_seed:
        # Raise an error if sender_seed is missing (required field)
        raise ValueError("sender_seed is required")

    # Extract receiver_address from either query parameters or request body
    receiver_address = get_request_param(request, 'receiver')

    # Initialize amount_xrp as None (optional field)
    amount_xrp = None

    # Extract amount_str from either query parameters or request body
    amount_str = get_request_param(request, 'amount')
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
    # Ensure response is an instance of xrpl Response
    if not isinstance(response, Response):
        return False, f"Invalid response object type"

    # Check if response is successful
    if not response.is_successful():
        return False, {
            "error": response.result.get("error", "Unknown error"),
            "error_code": response.result.get("error_code"),
            "error_message": response.result.get("error_message", "No additional details."),
        }

    # Ensure response.result is a valid dictionary
    if not isinstance(response.result, dict):
        return False, f"Invalid response format. 'result' should be a dictionary {response}"

    if not response and response.status != 'success':
        return False, f"Response status is unsuccessful {response}"

    # Validate required keys in response.result
    if required_keys:
        missing_keys = [key for key in required_keys if key not in response.result]
        if missing_keys:
            return False, f"Missing required fields: {missing_keys} in response"

    # Check if "info" is present and has a value
    if response.result.get("info"):
        return True, response.result

    # Check if "validated" is present and is False
    # if not response.result.get("validated"):
    #     return False, f"Transaction is not valid on the ledger {response.result}"

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
        raise ValueError(MISSING_REQUEST_PARAMETERS)

    # Validate the receiver's classic address
    if not is_valid_classic_address(receiver_address):
        raise ValueError(INVALID_WALLET_IN_REQUEST)

    # Validate the sender's secret seed
    if not is_valid_xrpl_seed(sender_seed):
        raise ValueError("Sender seed is invalid.")


async def fetch_network_fee(client):
    try:
        # Run the synchronous get_fee function in a separate thread
        fee = await asyncio.to_thread(get_fee, client)
        logger.info(f"Network fee in drops: {fee}")
        return fee
    except Exception as e:
        logger.error(f"Error fetching transaction fee: {e}")
        return {"status": "failure", "message": str(e)}


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

