import json
import logging
import re
from decimal import Decimal

from django.http import JsonResponse
from xrpl.clients import JsonRpcClient
from xrpl.core.addresscodec import is_valid_classic_address
from xrpl.core.keypairs import derive_keypair, derive_classic_address
from xrpl.models import ServerInfo, Payment
from xrpl.utils import xrp_to_drops

from .constants import JSON_RPC_URL, BASE_RESERVE, REQUIRE_DESTINATION_TAG_FLAG, DISABLE_MASTER_KEY_FLAG, \
    ENABLE_REGULAR_KEY_FLAG, INVALID_WALLET_IN_REQUEST
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


def validate_transaction_hash(transaction_hash):
    """
    Validates an XRP transaction hash:
    - Ensures the hash is not empty and has a length greater than 25 characters.
    - Ensures it is a valid 64-character hex string
    - Returns False if validation fails, otherwise True.
    Parameters:
    - transaction_hash: The transaction hash to validate.
    """

    if not transaction_hash or len(transaction_hash) <= 25 or not bool(
            re.match(r"^[A-Fa-f0-9]{64}$", transaction_hash)):
        return False
    return True


def validate_account_id(wallet_address):
    """
    Validates the format of an XRPL account ID.
    """
    if not wallet_address or not wallet_address.startswith('r') or len(wallet_address) < 25 or len(wallet_address) > 35:
        return False
    return True


def is_valid_xrpl_seed(seed: str) -> bool:
    try:
        # Try deriving a keypair (if it fails, the seed is invalid)
        public_key, _ = derive_keypair(seed)

        # Derive a classic address from the public key
        classic_address = derive_classic_address(public_key)

        # Validate the generated address
        return is_valid_classic_address(classic_address)

    except Exception:
        return False  # Invalid seed


def get_xrpl_client():
    """
    Creates and returns an XRP Ledger JSON-RPC client:
    - Initializes a JsonRpcClient with a predefined URL for communicating with the XRP Ledger.
    """
    return JsonRpcClient(JSON_RPC_URL)


def get_account_reserves():
    """
    Fetches the current reserve requirements from the XRP Ledger:
    - Queries server info to get base reserve and reserve increment for account operations.
    - Logs debug information and errors.
    - Returns reserve values or None if unable to fetch.
    - Handles exceptions gracefully by returning None for both values.
    """

    try:
        # Request network settings (server info) to get the reserve info
        # Create request for server info to fetch reserve data
        response = get_xrpl_client().request(ServerInfo())

        # Extract reserve information from the response
        if response.result and 'info' in response.result:
            logger.debug(json.dumps(response.result, indent=4, sort_keys=True))
            server_info = response.result['info']
            reserve_base = server_info['validated_ledger']['reserve_base_xrp']
            reserve_inc = server_info['validated_ledger']['reserve_inc_xrp']

            if reserve_base is None or reserve_inc is None:
                logger.error("Reserve data not found in server info.")
                return None, None

            return reserve_base, reserve_inc
        else:
            # No response from server
            logger.error("Failed to fetch server info.")
            return None, None

    except Exception as e:
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


def get_request_param(request, key, default=None, convert_func=None, function_name=""):
    """Safely extracts a parameter from request.GET or request.data with optional conversion."""
    try:
        value = request.GET.get(key) or request.data.get(key, default)
        if convert_func and value is not None:
            return convert_func(value)  # Apply conversion function if provided
        return value
    except Exception as e:
        return handle_error({'status': 'failure', 'message': f"Error extracting {key}: {str(e)}"},
                            status_code=500, function_name=function_name)


def extract_request_data(request):
    """Extracts and parses payment details from the request."""
    sender_seed = request.GET.get('sender_seed') or request.data.get('sender_seed')
    receiver_address = request.GET.get('receiver') or request.data.get('receiver')

    try:
        amount_xrp = Decimal(request.GET.get('amount') or request.data.get('amount') or "0")
    except Exception as e:
        raise ValueError(f"Invalid amount format: {str(e)}")

    return sender_seed, receiver_address, amount_xrp


def validate_request_data(sender_seed, receiver_address, amount_xrp):
    """Validates the extracted request data."""
    if not all([sender_seed, receiver_address, amount_xrp]):
        raise ValueError("Missing required parameters.")

    if not is_valid_classic_address(receiver_address):
        raise ValueError(INVALID_WALLET_IN_REQUEST)

    if not is_valid_xrpl_seed(sender_seed):
        raise ValueError("S parameter is invalid")


def fetch_network_fee(client):
    """Fetches the base network fee from the XRPL server."""
    try:
        server_info = client.request(ServerInfo())
        if not server_info:
            raise ValueError("Error initializing server info.")

        raw_fee_xrp = Decimal(server_info.result['info']['validated_ledger']['base_fee_xrp'])
        return xrp_to_drops(raw_fee_xrp)

    except (KeyError, TypeError, AttributeError, ValueError) as e:
        logger.error(f"Failed to fetch network fee: {str(e)}")
        raise ValueError("Failed to fetch network fee. Please try again.")


def create_payment_transaction(sender_address, receiver_address, amount_drops, fee_drops):
    """Creates the XRPL Payment transaction object."""
    return Payment(
        account=sender_address,
        destination=receiver_address,
        amount=amount_drops,
        fee=str(fee_drops),
    )


def process_payment_response(payment_response, sender_address, receiver_address, amount_xrp, fee_drops):
    """Processes the payment response and updates the database."""
    try:
        if not payment_response or not hasattr(payment_response, 'is_successful'):
            raise ValueError("Invalid payment response received.")

        if not payment_response.is_successful():
            error_message = payment_response.result.get("error", "Unknown error")
            return handle_error({'status': 'failure', 'message': f'Payment failed due to: {error_message}'}, 500,
                                'send_payment')

        transaction_hash = payment_response.result.get('hash')
        if not transaction_hash:
            raise ValueError("Transaction hash missing in response.")

        logger.info(f"Payment successful: {transaction_hash}")

        # Save transaction details
        save_transaction(sender_address, receiver_address, amount_xrp, transaction_hash)

        # Update sender and receiver balances
        update_account_balances(sender_address, receiver_address, amount_xrp)

        return JsonResponse({
            'status': 'success',
            'message': 'Payment successfully sent.',
            'transaction_hash': transaction_hash,
            'sender': sender_address,
            'receiver': receiver_address,
            'amount': amount_xrp,
            'fee_drops': fee_drops,
        })

    except (AttributeError, KeyError, TypeError, ValueError) as e:
        logger.error(f"Error processing payment response: {str(e)}")
        return handle_error({'status': 'failure', 'message': f'Internal error: {str(e)}'}, 500, 'send_payment')

    except Exception as e:
        logger.critical(f"Unexpected error in process_payment_response: {str(e)}", exc_info=True)
        return handle_error({'status': 'failure', 'message': f'{str(e)}'}, 500, 'send_payment')


def save_transaction(sender, receiver, amount, transaction_hash):
    """Saves the transaction details to the database."""
    XrplPaymentData.objects.create(
        sender=sender,
        receiver=receiver,
        amount=amount,
        transaction_hash=transaction_hash,
    )


def update_account_balances(sender_address, receiver_address, amount_xrp):
    """Updates the account balances in the database with error handling."""
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

