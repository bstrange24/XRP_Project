import logging

from django.views import View
from rest_framework.decorators import api_view
from tenacity import retry, wait_exponential, stop_after_attempt
from xrpl import XRPLException
from xrpl.account import does_account_exist
from xrpl.asyncio.clients import XRPLRequestFailureException
from xrpl.utils import XRPRangeException
from xrpl.wallet import Wallet
from xrpl.models.transactions import Payment
from xrpl.models.requests import Fee
from xrpl.models.amounts import IssuedCurrencyAmount
from xrpl.transaction import sign, submit_and_wait
from xrpl.ledger import get_latest_validated_ledger_sequence
import time

from ..accounts.account_utils import prepare_account_data
from ..constants import RETRY_BACKOFF, MAX_RETRIES, ENTERING_FUNCTION_LOG, \
    MISSING_REQUEST_PARAMETERS, ERROR_INITIALIZING_CLIENT, ACCOUNT_DOES_NOT_EXIST_ON_THE_LEDGER, LEAVING_FUNCTION_LOG
from ..errors.error_handling import error_response, process_transaction_error, handle_error_new
from ..trust_lines.trust_line_util import create_trust_set_response
from ..utils import get_request_param, get_xrpl_client, validate_xrpl_response_data, \
    total_execution_time_in_millis

logger = logging.getLogger('xrpl_app')

class Currency(View):

    @api_view(['POST'])
    @retry(wait=wait_exponential(multiplier=RETRY_BACKOFF), stop=stop_after_attempt(MAX_RETRIES))
    def send_cross_currency_payment(self):
        # Set Up Trust Lines: Ensure both sender and receiver have trust lines to their respective issuers.
        # Create Offers: Add liquidity to the order books (e.g., USD/XRP and XRP/EUR).
        # Test the Payment: Retry the cross-currency payment with sufficient paths.

        # Step 1: Verify Trust Lines
        # Sender: Must trust source_issuer (e.g., rUSDissuer) for USD with a limit >= send_max (e.g., 12 USD) and have a balance >= send_max.
        # Receiver: Must trust destination_issuer (e.g., rEURissuer) for EUR with a limit >= amount (e.g., 10 EUR).
        # Use your set_trust_line function if these aren’t set
        #
        # Step 2: Create Liquidity with Offer
        # Step 3: Retry the Payment
        start_time = time.time()
        function_name = 'send_cross_currency_payment'
        logger.info(ENTERING_FUNCTION_LOG.format(function_name))

        try:
            # Extract parameters from the request
            sender_seed = get_request_param(self, 'sender_seed')  # Sender’s wallet seed
            destination_address = get_request_param(self, 'destination_address')  # Receiver’s address
            source_currency = get_request_param(self, 'source_currency')  # e.g., "USD"
            source_issuer = get_request_param(self, 'source_issuer')  # e.g., rUSDissuer
            destination_currency = get_request_param(self, 'destination_currency')  # e.g., "EUR"
            destination_issuer = get_request_param(self, 'destination_issuer')  # e.g., rEURissuer
            amount_to_deliver = get_request_param(self, 'amount_to_deliver')  # Amount to deliver (e.g., "10" EUR)
            max_to_spend = get_request_param(self, 'max_to_spend')  # Max to spend (e.g., "12" USD)

            if not all([sender_seed, destination_address, source_currency, source_issuer,
                        destination_currency, destination_issuer, amount_to_deliver, max_to_spend]):
                raise ValueError(MISSING_REQUEST_PARAMETERS)

            logger.info(f"Received parameters - sender_seed: {sender_seed}, destination: {destination_address}, "
                        f"source_currency: {source_currency}, source_issuer: {source_issuer}, "
                        f"destination_currency: {destination_currency}, destination_issuer: {destination_issuer}, "
                        f"amount_to_deliver: {amount_to_deliver}, max_to_spend: {max_to_spend}")

            # Initialize XRPL client
            client = get_xrpl_client()  # Assumes this returns a JsonRpcClient
            if not client:
                raise XRPLException(error_response(ERROR_INITIALIZING_CLIENT))

            # Verify accounts exist
            if not does_account_exist(destination_address, client):
                raise XRPLException(error_response(ACCOUNT_DOES_NOT_EXIST_ON_THE_LEDGER.format(destination_address)))
            if not does_account_exist(source_issuer, client):
                raise XRPLException(error_response(ACCOUNT_DOES_NOT_EXIST_ON_THE_LEDGER.format(source_issuer)))
            if not does_account_exist(destination_issuer, client):
                raise XRPLException(error_response(ACCOUNT_DOES_NOT_EXIST_ON_THE_LEDGER.format(destination_issuer)))

            # Load sender wallet
            sender_wallet = Wallet.from_seed(sender_seed)
            logger.info(f"Sender wallet: {sender_wallet.classic_address}")

            # Fetch sequence number for sender
            account_info_response = client.request(prepare_account_data(sender_wallet.classic_address, False))
            if validate_xrpl_response_data(account_info_response):
                process_transaction_error(account_info_response)

            sequence_number = account_info_response.result["account_data"]["Sequence"]
            logger.info(f"Fetched sequence number: {sequence_number}")

            # Fetch network fee
            fee_response = client.request(Fee())
            if validate_xrpl_response_data(fee_response):
                process_transaction_error(fee_response)

            fee = fee_response.result["drops"]["open_ledger_fee"]
            logger.info(f"Fetched network fee: {fee}")

            # Get current ledger for LastLedgerSequence
            current_ledger = get_latest_validated_ledger_sequence(client)
            logger.info(f"Current ledger: {current_ledger}")

            # Create cross-currency Payment transaction
            payment_tx = Payment(
                account=sender_wallet.classic_address,
                destination=destination_address,
                amount=IssuedCurrencyAmount(
                    currency=destination_currency,
                    value=amount_to_deliver,  # Amount to deliver (e.g., "10" EUR)
                    issuer=destination_issuer
                ),
                send_max=IssuedCurrencyAmount(
                    currency=source_currency,
                    value=max_to_spend,  # Max to spend (e.g., "12" USD)
                    issuer=source_issuer
                ),
                sequence=sequence_number,
                fee=fee,
                last_ledger_sequence=current_ledger + 200  # Larger buffer for your setup
            )

            # Sign the transaction
            signed_tx = sign(payment_tx, sender_wallet)
            logger.info(f"Signed transaction: {signed_tx}")

            print(f"LastLedgerSequence: {payment_tx.last_ledger_sequence}")
            print(f"Time before submission: {time.time()}")
            validated_tx_response = submit_and_wait(payment_tx, client, sender_wallet)
            print(f"Time after submission: {time.time()}")

            if validate_xrpl_response_data(validated_tx_response):
                if validated_tx_response.result.get('engine_result') == 'tecPATH_DRY':
                    raise XRPLException("Transaction failed: No path found with sufficient liquidity (tecPATH_DRY). "
                                        "Ensure order books have offers for conversion (e.g., USD/XRP, XRP/EUR).")
                process_transaction_error(validated_tx_response)

            tx_hash = validated_tx_response.result['hash']
            logger.info(f"Transaction validated with hash: {tx_hash}")
            logger.info(f"Transaction validated in ledger: {validated_tx_response.result['ledger_index']}")
            logger.info(f"Cross-currency payment sent: {amount_to_deliver} {destination_currency} to {destination_address}")

            # Return response (adjust based on your create_trust_set_response)
            return create_trust_set_response(validated_tx_response, destination_address, destination_currency, amount_to_deliver)

        except (XRPLRequestFailureException, XRPLException, XRPRangeException) as e:
            return handle_error_new(e, status_code=500, function_name=function_name)
        except Exception as e:
            return handle_error_new(e, status_code=500, function_name=function_name)
        finally:
            logger.info(LEAVING_FUNCTION_LOG.format(function_name, total_execution_time_in_millis(start_time)))