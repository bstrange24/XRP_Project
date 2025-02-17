import json
import logging
import time

import xrpl
from django.views import View
from rest_framework.decorators import api_view
from tenacity import retry, wait_exponential, stop_after_attempt
from xrpl import XRPLException
from xrpl.transaction import submit_and_wait
from xrpl.utils import xrp_to_drops
from xrpl.wallet import Wallet
from django.db import transaction

from .payments_util import check_pay_channel_entries, create_payment_transaction, process_payment_response
from ..accounts.account_utils import prepare_account_data, check_check_entries, get_account_reserves, \
    create_account_delete_transaction, account_delete_tx_response
from ..constants import RETRY_BACKOFF, MAX_RETRIES, ENTERING_FUNCTION_LOG, INVALID_WALLET_IN_REQUEST, \
    ERROR_INITIALIZING_CLIENT, ERROR_IN_XRPL_RESPONSE, PAYMENT_IS_UNSUCCESSFUL, LEAVING_FUNCTION_LOG, \
    ERROR_FETCHING_TRANSACTION_STATUS, XRPL_RESPONSE
from ..escrows.escrows_util import check_escrow_entries
from ..ledger.ledger_util import check_account_ledger_entries, check_ripple_state_entries, \
    calculate_last_ledger_sequence
from ..utils import validate_xrp_wallet, extract_request_data, is_valid_xrpl_seed, get_xrpl_client, handle_error, \
    total_execution_time_in_millis, validate_request_data, fetch_network_fee, validate_xrpl_response

logger = logging.getLogger('xrpl_app')

class Payments(View):

    @api_view(['POST'])
    @retry(wait=wait_exponential(multiplier=RETRY_BACKOFF), stop=stop_after_attempt(MAX_RETRIES))
    def send_and_delete_wallet(self, wallet_address):
        start_time = time.time()  # Capture the start time of the function execution.
        function_name = "send_and_delete_wallet"
        logger.info(ENTERING_FUNCTION_LOG.format(function_name))  # Log entering the function.

        try:
            if not wallet_address or not validate_xrp_wallet(wallet_address):
                raise ValueError(INVALID_WALLET_IN_REQUEST)

            sender_seed, _, _ = extract_request_data(self)
            if not is_valid_xrpl_seed(sender_seed):
                raise ValueError('Sender seed is invalid.')

            client = get_xrpl_client()
            if not client:
                raise ValueError(ERROR_INITIALIZING_CLIENT)

            sender_wallet = Wallet.from_seed(sender_seed)

            valid_address, account_objects = check_account_ledger_entries(sender_wallet.classic_address)
            if not valid_address:
                raise ValueError("Wallet not found on ledger. Unable to delete wallet")

            account_info_request = prepare_account_data(sender_wallet.classic_address, False)

            # Check if there are any escrow, payment channels, Ripple state, or check entries
            # that prevent the wallet from being deleted.
            if not check_escrow_entries(account_objects):
                raise ValueError("Wallet has an escrow. Unable to delete wallet")

            if not check_pay_channel_entries(account_objects):
                raise ValueError("Wallet has payment channels. Unable to delete wallet")

            if not check_ripple_state_entries(account_objects):
                raise ValueError("Wallet has Ripple state entries. Unable to delete wallet")

            if not check_check_entries(account_objects):
                raise ValueError("Wallet has check entries. Unable to delete wallet")

            account_info_response = client.request(account_info_request)
            is_valid, result = validate_xrpl_response(account_info_response, required_keys=["validated"])
            if not is_valid:
                raise XRPLException(ERROR_IN_XRPL_RESPONSE)

            # Log the raw response for detailed debugging
            logger.debug(XRPL_RESPONSE)
            logger.debug(json.dumps(result, indent=4, sort_keys=True))

            balance = int(account_info_response.result['account_data']['Balance'])
            base_reserve, reserve_increment = get_account_reserves()
            if base_reserve is None or reserve_increment is None:
                raise ValueError("Failed to retrieve reserve requirements from the XRPL.")

            drops = xrp_to_drops(base_reserve)  # Convert base reserve from XRP to drops.
            transferable_amount = int(balance) - int(drops)  # Calculate the transferable amount.

            if transferable_amount <= 0:
                raise ValueError("Insufficient balance to cover the reserve and fees.")

            # Step 11: Create and submit the payment transaction.
            payment_tx = create_payment_transaction(sender_wallet.classic_address, wallet_address, str(transferable_amount), str(0),True)
            payment_response = submit_and_wait(payment_tx, client, sender_wallet)
            is_valid, payment_response_result = validate_xrpl_response(payment_response, required_keys=["validated"])
            if not is_valid:
                raise XRPLException(ERROR_IN_XRPL_RESPONSE)

            # Log the raw response for detailed debugging
            logger.debug(XRPL_RESPONSE)
            logger.debug(json.dumps(payment_response_result, indent=4, sort_keys=True))

            last_ledger_sequence = calculate_last_ledger_sequence(client, buffer_time=60)

            account_delete_tx = create_account_delete_transaction(sender_wallet.classic_address, wallet_address, last_ledger_sequence)
            account_delete_response = submit_and_wait(account_delete_tx, client, sender_wallet)
            is_valid, account_delete_response_result = validate_xrpl_response(account_delete_response, required_keys=["validated"])
            if not is_valid:
                raise XRPLException(ERROR_IN_XRPL_RESPONSE)

            # Log the raw response for detailed debugging
            logger.debug(XRPL_RESPONSE)
            logger.debug(json.dumps(account_delete_response_result, indent=4, sort_keys=True))

            return account_delete_tx_response(account_delete_response_result, payment_response_result)

        except Exception as e:
            return handle_error({'status': 'failure', 'message': f"{str(e)}"}, status_code=500, function_name=function_name)
        finally:
            logger.info(LEAVING_FUNCTION_LOG.format(function_name, total_execution_time_in_millis(start_time)))

    @api_view(['POST'])
    @retry(wait=wait_exponential(multiplier=RETRY_BACKOFF), stop=stop_after_attempt(MAX_RETRIES))
    def send_payment(self):
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
        start_time = time.time()  # Capture the start time
        function_name = 'send_payment'
        logger.info(ENTERING_FUNCTION_LOG.format(function_name))

        try:
            # Extract and validate request data
            sender_seed, receiver_address, amount_xrp = extract_request_data(self)
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
                payment_transaction = create_payment_transaction(sender_address, receiver_address, amount_drops, str(fee_drops),False)
                payment_response = submit_and_wait(payment_transaction, client, sender_wallet)

                is_valid, result = validate_xrpl_response(payment_response, required_keys=["validated"])
                if not is_valid:
                    raise XRPLException(ERROR_FETCHING_TRANSACTION_STATUS)

                # Handle the transaction response
                return process_payment_response(result, payment_response, sender_address, receiver_address, amount_xrp,
                                                str(fee_drops))

        except (xrpl.XRPLException, Exception) as e:
            # Handle exceptions like XRPL-specific errors, network issues, or unexpected errors
            return handle_error({'status': 'failure', 'message': f"{str(e)}"}, status_code=500,
                                function_name=function_name)

        finally:
            logger.info(LEAVING_FUNCTION_LOG.format(function_name, total_execution_time_in_millis(start_time)))
