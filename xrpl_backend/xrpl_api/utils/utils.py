import asyncio
import json
import logging
import re
import time
from decimal import Decimal
from typing import Optional

from django.apps import apps
from django.core.cache import cache
from xrpl import XRPLException
from xrpl.asyncio.clients import XRPLRequestFailureException
from xrpl.clients import JsonRpcClient
from xrpl.core.addresscodec import is_valid_classic_address, is_valid_xaddress
from xrpl.core.keypairs import derive_keypair, derive_classic_address
from xrpl.ledger import get_fee
from xrpl.models import Response, AccountSetAsfFlag
from xrpl.utils import xrp_to_drops, drops_to_xrp

from ..constants.constants import BASE_RESERVE, INVALID_WALLET_IN_REQUEST, MISSING_REQUEST_PARAMETERS, ASF_FLAGS
from ..errors.error_handling import handle_error

logger = logging.getLogger('xrpl_app')


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


def get_query_param(params, key):
    try:
        return params.get(key)
    except Exception as e:
        return None


def extract_request_data(request):
    """
    Extracts and validates data from an HTTP request for processing.

    This function retrieves the following data from the request:
    - `sender_seed`: The seed of the sender (required).
    - `receiver_account`: The address of the receiver (optional).
    - `amount_xrp`: The amount of XRP to transfer (optional, must be a valid decimal).

    Args:
        request: The HTTP request object containing query parameters or JSON data.

    Returns:
        tuple: A tuple containing (sender_seed, receiver_account, amount_xrp).

    Raises:
        ValueError: If `sender_seed` is missing or if `amount_xrp` is in an invalid format.
    """
    # Extract sender_seed from either query parameters or request body
    sender_seed = get_request_param(request, 'sender_seed')
    if not sender_seed:
        # Raise an error if sender_seed is missing (required field)
        raise ValueError("sender_seed is required")

    # Extract receiver_account from either query parameters or request body
    receiver_account = get_request_param(request, 'receiver_account')

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
    return sender_seed, receiver_account, amount_xrp


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

    return True, response.result  # Valid response


def validate_xrpl_response_data(response: Optional[Response]) -> bool:
    if response is None or not response.is_successful():
        logger.error("Response is None or not successful")
        return True

    logger.debug(f"response:\n{json.dumps(response.result, indent=4, sort_keys=True)}")
    logger.debug(f"response.is_successful(): {response.is_successful()}")

    result = response.result
    meta_transaction_result = result.get('meta', {}).get('TransactionResult')
    transaction_hash = result.get('hash')

    if meta_transaction_result and transaction_hash:
        logger.debug(f"TransactionResult: {meta_transaction_result} TransactionHash: {transaction_hash}")
        if meta_transaction_result != 'tesSUCCESS':
            logger.error(f"meta_transaction_result is not successful: {meta_transaction_result}")
            return True
    else:
        logger.debug("Meta tag or hash tag is not available")
        return False

    return False


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
    except XRPLRequestFailureException as e:
        logger.error(f"Error fetching transaction fee: {e}")
        return {"status": "failure", "message": str(e)}
    except XRPLException as e:
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


def map_request_parameters_to_flag_variables():
    return {
        flag: getattr(AccountSetAsfFlag, flag.upper()) for flag in ASF_FLAGS
    }


def get_account_set_flags_from_request_parameters(self):
    params = {flag: get_query_param(self.query_params, flag) for flag in ASF_FLAGS}

    # Return only those keys and values where value is not None.
    non_none_request_parameters = {key: value for key, value in params.items() if value is not None}
    return non_none_request_parameters


def get_account_set_flags_for_database_transaction(flags_to_enable):
    enabled_flags = {flag.name for flag in flags_to_enable}

    # Mapping of flag names to database column names
    flag_mapping = {
        'asf_account_txn_id': 'ASF_ACCOUNT_TXN_ID',
        'asf_allow_trustline_clawback': 'ASF_ALLOW_TRUSTLINE_CLAWBACK',
        'asf_authorized_nftoken_minter': 'ASF_AUTHORIZED_NFTOKEN_MINTER',
        'asf_default_ripple': 'ASF_DEFAULT_RIPPLE',
        'asf_deposit_auth': 'ASF_DEPOSIT_AUTH',
        'asf_disable_master': 'ASF_DISABLE_MASTER',
        'asf_disable_incoming_check': 'ASF_DISABLE_INCOMING_CHECK',
        'asf_disable_incoming_nftoken_offer': 'ASF_DISABLE_INCOMING_NFTOKEN_OFFER',
        'asf_disable_incoming_paychan': 'ASF_DISABLE_INCOMING_PAYCHAN',
        'asf_disable_incoming_trustline': 'ASF_DISABLE_INCOMING_TRUSTLINE',
        'asf_disallow_xrp': 'ASF_DISALLOW_XRP',
        'asf_global_freeze': 'ASF_GLOBAL_FREEZE',
        'asf_no_freeze': 'ASF_NO_FREEZE',
        'asf_require_auth': 'ASF_REQUIRE_AUTH',
        'asf_require_dest': 'ASF_REQUIRE_DEST'
    }


    # Print all elements in flag_mapping on the same line
    log_statement = ', '.join(f"{key}: {value}" for key, value in flag_mapping.items())
    logger.info(f"flag_mapping: {log_statement}")

    # Populate the flag_mapping with True or False based on enabled_flags and disabled_flags
    flag_mapping = {key: (flag_mapping[key] in enabled_flags) for key in flag_mapping}

    return flag_mapping
