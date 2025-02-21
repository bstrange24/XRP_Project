from django.core.paginator import Paginator
import logging
import time

from django.views import View
from rest_framework.decorators import api_view
from tenacity import wait_exponential, stop_after_attempt, retry
from xrpl import XRPLException
from xrpl.ledger import get_latest_validated_ledger_sequence
from xrpl.asyncio.clients import XRPLRequestFailureException
from xrpl.models import Fee
from xrpl.transaction import sign, submit_and_wait
from xrpl.utils import XRPRangeException, xrp_to_drops
from xrpl.wallet import Wallet
from xrpl.account import does_account_exist

from .trust_line_util import trust_line_response, create_trust_set_transaction, create_trust_set_response
from ..accounts.account_utils import create_account_lines_response, prepare_account_lines, prepare_account_data
from ..constants import RETRY_BACKOFF, MAX_RETRIES, ENTERING_FUNCTION_LOG, \
    ERROR_INITIALIZING_CLIENT, LEAVING_FUNCTION_LOG, MISSING_REQUEST_PARAMETERS, \
    INVALID_WALLET_IN_REQUEST, ACCOUNT_DOES_NOT_EXIST_ON_THE_LEDGER
from ..errors.error_handling import error_response, process_transaction_error, handle_error_new
from ..offers.account_offers_util import prepare_account_lines_for_offer
from ..utils import get_request_param, get_xrpl_client, total_execution_time_in_millis, validate_xrp_wallet, validate_xrpl_response_data

logger = logging.getLogger('xrpl_app')


class TrustLine(View):

    @api_view(['GET'])
    @retry(wait=wait_exponential(multiplier=RETRY_BACKOFF), stop=stop_after_attempt(MAX_RETRIES))
    def get_account_trust_lines(self):
        # Capture the start time to calculate the total execution time
        start_time = time.time()
        function_name = 'get_account_trust_lines'
        logger.info(ENTERING_FUNCTION_LOG.format(function_name))

        try:
            # Extract wallet address from request parameters
            account = get_request_param(self, 'account')
            # Validate the provided wallet address
            if not account or not validate_xrp_wallet(account):
                raise XRPLRequestFailureException(error_response(INVALID_WALLET_IN_REQUEST))

            # Get an instance of the XRPL client
            client = get_xrpl_client()
            if not client:
                raise XRPLException(error_response(ERROR_INITIALIZING_CLIENT))

            if not does_account_exist(account, client):
                raise XRPLException(error_response(ACCOUNT_DOES_NOT_EXIST_ON_THE_LEDGER.format(account)))

            account_lines = []  # Initialize an empty list to store account lines
            marker = None  # Initialize the marker to manage pagination

            # Loop to fetch all account lines for the account, using pagination via 'marker'
            while True:
                # Prepare the account lines request with the current marker (for pagination)
                account_lines_info = prepare_account_lines(account, marker)

                # Send the request to XRPL to fetch account lines
                account_lines_response = client.request(account_lines_info)

                if validate_xrpl_response_data(account_lines_response):
                    process_transaction_error(account_lines_response)

                # Check if the "lines" field exists in the response. If not, raise an error.
                if "lines" not in account_lines_response.result:
                    raise XRPLException('Account lines not found')

                # Add the fetched account lines to the account_lines list
                account_lines.extend(account_lines_response.result["lines"])

                # Check if there are more pages of account lines to fetch using the 'marker' field.
                # If 'marker' is not present, break the loop, as we have fetched all pages.
                marker = account_lines_response.result.get('marker')
                if not marker:
                    break

            # Extract pagination parameters from the request for paginating the response
            # Default to page 1 if no page is specified
            page = int(self.GET.get('page', 1))
            # Default to 10 items per page if no page_size is specified
            page_size = int(self.GET.get('page_size', 10))

            # Paginate the account lines using Django's Paginator
            paginator = Paginator(account_lines, page_size)
            paginated_transactions = paginator.get_page(page)

            # Log that the account lines have been successfully fetched
            logger.info(f"Account Lines fetched for address: {account}")

            # Return the paginated response to the client
            return create_account_lines_response(paginated_transactions, paginator)

        except (XRPLRequestFailureException, XRPLException, XRPRangeException) as e:
            # Handle error message
            return handle_error_new(e, status_code=500, function_name=function_name)
        except Exception as e:
            # Handle error message
            return handle_error_new(e, status_code=500, function_name=function_name)
        finally:
            logger.info(LEAVING_FUNCTION_LOG.format(function_name, total_execution_time_in_millis(start_time)))

    @api_view(['GET'])
    @retry(wait=wait_exponential(multiplier=RETRY_BACKOFF), stop=stop_after_attempt(MAX_RETRIES))
    def get_trust_line(self):
        # Capture the start time to calculate the total execution time
        start_time = time.time()
        function_name = 'get_trust_line'
        logger.info(ENTERING_FUNCTION_LOG.format(function_name))

        try:
            # Extract wallet address from request parameters
            account = get_request_param(self, 'account')
            # Validate the provided wallet address
            if not account or not validate_xrp_wallet(account):
                raise XRPLRequestFailureException(error_response(INVALID_WALLET_IN_REQUEST))

            # Get an instance of the XRPL client
            client = get_xrpl_client()
            if not client:
                raise XRPLException(error_response(ERROR_INITIALIZING_CLIENT))

            if not does_account_exist(account, client):
                raise XRPLException(error_response(ACCOUNT_DOES_NOT_EXIST_ON_THE_LEDGER.format(account)))

            # Prepare an AccountLines request to retrieve trust lines for the account.
            account_lines_info = prepare_account_lines_for_offer(account)

            # Send the AccountLines request to the XRPL network.
            # The response contains the trust lines for the wallet address.
            account_lines_info_response = client.request(account_lines_info)

            if validate_xrpl_response_data(account_lines_info_response):
                process_transaction_error(account_lines_info_response)

            # Check if the "lines" field exists in the response. If not, raise an error.
            if "lines" not in account_lines_info_response.result:
                raise XRPLException('Account lines not found')

            # Extract trust lines from the response.
            # If no trust lines are found, an empty list is returned.
            trust_lines = account_lines_info_response.result.get('lines', [])
            logger.info(f"Successfully fetched trust lines for account {account}. Trust lines: {trust_lines}")

            # Return the trust lines in a structured response.
            return trust_line_response(account_lines_info_response)

        except (XRPLRequestFailureException, XRPLException, XRPRangeException) as e:
            # Handle error message
            return handle_error_new(e, status_code=500, function_name=function_name)
        except Exception as e:
            # Handle error message
            return handle_error_new(e, status_code=500, function_name=function_name)
        finally:
            logger.info(LEAVING_FUNCTION_LOG.format(function_name, total_execution_time_in_millis(start_time)))

    @api_view(['POST'])
    @retry(wait=wait_exponential(multiplier=RETRY_BACKOFF), stop=stop_after_attempt(MAX_RETRIES))
    def set_trust_line(self):
        start_time = time.time()
        function_name = 'set_trust_line'
        logger.info(ENTERING_FUNCTION_LOG.format(function_name))

        try:
            # Extract the parameters from the request data.
            # These parameters are necessary to create and submit a TrustSet transaction.
            sender_seed = get_request_param(self, 'sender_seed')
            issuer = get_request_param(self, 'issuer')
            currency = get_request_param(self, 'currency')
            limit = get_request_param(self, 'limit')

            # If any of the required parameters are missing, raise an error.
            if not all([sender_seed, issuer, currency, limit]):
                XRPLException(error_response(MISSING_REQUEST_PARAMETERS))

            # Log the received parameters for debugging and verification.
            logger.debug(f"Received parameters - sender_seed: {sender_seed}, wallet_address: {issuer}, currency: {currency}, limit: {limit}")

            # Initialize XRPL client. Check if client is successfully initialized. Raise exception if client initialization fails
            client = get_xrpl_client()
            if not client:
                raise XRPLException(error_response(ERROR_INITIALIZING_CLIENT))

            if not does_account_exist(issuer, client):
                raise XRPLException(error_response(ACCOUNT_DOES_NOT_EXIST_ON_THE_LEDGER.format(issuer)))

            # If the currency is XRP, convert the limit into drops (the smallest unit of XRP).
            limit_drops = xrp_to_drops(limit) if currency == "XRP" else limit
            logger.info(f"Converted limit: {limit_drops}")

            # Create the sender's wallet from the provided seed. This is used to sign transactions.
            sender_wallet = Wallet.from_seed(sender_seed)
            logger.info(f"Sender wallet created: {sender_wallet.classic_address}")

            # Fetch the current sequence number for the sender's account.
            # The sequence number is required for submitting a transaction on the XRP Ledger.
            account_info = prepare_account_data(sender_wallet.classic_address, False)

            # Send the request to the XRPL client
            account_info_response = client.request(account_info)

            # Validate client response. Raise exception on error
            if validate_xrpl_response_data(account_info_response):
                process_transaction_error(account_info_response)

            sequence_number = account_info_response.result['account_data']['Sequence']
            logger.info(f"Fetched sequence number: {sequence_number}")

            # Fetch the current network fee to include in the transaction.
            # The network fee is used to pay for processing the transaction.
            fee_response = client.request(Fee())
            if validate_xrpl_response_data(fee_response):
                process_transaction_error(fee_response)

            logger.info(f"Fee response: {fee_response}")

            # Extract the minimum fee from the response.
            fee = fee_response.result['drops']['base_fee']
            logger.info(f"Fetched network fee: {fee}")

            # Get current ledger for LastLedgerSequence
            current_ledger = get_latest_validated_ledger_sequence(client)

            # Create a TrustSet transaction with the extracted parameters, including the fee and sequence number.
            trust_set_tx = create_trust_set_transaction(currency, limit_drops, issuer, sender_wallet.classic_address, sequence_number, fee, current_ledger)

            # Sign the transaction with the sender's wallet.
            signed_tx_response = sign(trust_set_tx, sender_wallet)
            logger.info(f"Signed transaction: {signed_tx_response}")

            validated_tx_response = submit_and_wait(trust_set_tx, client, sender_wallet)
            if validate_xrpl_response_data(validated_tx_response):
                process_transaction_error(validated_tx_response)

            tx_hash = validated_tx_response.result['hash']
            logger.info(f"Transaction validated with hash: {tx_hash}")
            logger.info(f"Transaction validated in ledger: {validated_tx_response.result['ledger_index']}")
            logger.info(f"Trust line created: {validated_tx_response.result}")
            logger.info(f"Trust line set successfully for account {issuer}")
            return create_trust_set_response(validated_tx_response, issuer, currency, limit)

        except (XRPLRequestFailureException, XRPLException, XRPRangeException) as e:
            # Handle error message
            return handle_error_new(e, status_code=500, function_name=function_name)
        except Exception as e:
            # Handle error message
            return handle_error_new(e, status_code=500, function_name=function_name)
        finally:
            logger.info(LEAVING_FUNCTION_LOG.format(function_name, total_execution_time_in_millis(start_time)))

    @api_view(['POST'])
    @retry(wait=wait_exponential(multiplier=RETRY_BACKOFF), stop=stop_after_attempt(MAX_RETRIES))
    def remove_trust_line(self):
        # Capture the start time to calculate the total execution time of the function
        start_time = time.time()
        function_name = 'remove_trust_line'
        logger.info(ENTERING_FUNCTION_LOG.format(function_name))

        try:
            # Extract the parameters from the request data.
            # These parameters are necessary to create and submit a TrustSet transaction.
            sender_seed = get_request_param(self, 'sender_seed')
            currency_code = get_request_param(self, 'currency_code')
            issuer = get_request_param(self, 'issuer')

            # If any of the required parameters are missing, raise an error.
            if not all([sender_seed, currency_code, issuer]):
                raise ValueError(MISSING_REQUEST_PARAMETERS)

            # Log the received parameters for debugging and verification.
            logger.info(f"Received parameters - sender_seed: {sender_seed}, currency: {currency_code}, issuer: {issuer}")

            # Initialize XRPL client. Check if client is successfully initialized. Raise exception if client initialization fails
            client = get_xrpl_client()
            if not client:
                raise XRPLException(error_response(ERROR_INITIALIZING_CLIENT))

            if not does_account_exist(issuer, client):
                raise XRPLException(error_response(ACCOUNT_DOES_NOT_EXIST_ON_THE_LEDGER.format(issuer)))

            # Load the wallet using the secret key
            sender_wallet = Wallet.from_secret(sender_seed)
            logger.info(f"Sender wallet: {sender_wallet.classic_address}")

            account_info_response = client.request(prepare_account_data(sender_wallet.classic_address, False))
            if validate_xrpl_response_data(account_info_response):
                process_transaction_error(account_info_response)

            sequence_number = account_info_response.result["account_data"]["Sequence"]
            logger.info(f"Fetched sequence number: {sequence_number}")

            # Fetch the current fee from the XRPL network
            fee_response = client.request(Fee())
            if validate_xrpl_response_data(fee_response):
                process_transaction_error(fee_response)

            fee = fee_response.result["drops"]["open_ledger_fee"]

            # Get current ledger for LastLedgerSequence
            current_ledger = get_latest_validated_ledger_sequence(client)
            logger.info(f"Current ledger: {current_ledger}")

            trust_set_tx = create_trust_set_transaction(currency_code, str(0), issuer, sender_wallet.classic_address,
                                                        sequence_number, fee, current_ledger)

            # Sign the transaction with the sender's wallet.
            signed_tx_response = sign(trust_set_tx, sender_wallet)
            logger.info(f"Signed transaction: {signed_tx_response}")
            logger.info(f"LastLedgerSequence: {trust_set_tx.last_ledger_sequence}")

            submit_and_wait_start_time = int((time.time()) * 1000)
            logger.info(f"Time before submission: {submit_and_wait_start_time}")

            validated_tx_response = submit_and_wait(trust_set_tx, client, sender_wallet)

            submit_and_wait_end_time = int((time.time()) * 1000)
            logger.info(f"Time after submission: {submit_and_wait_end_time - submit_and_wait_start_time}")

            if validate_xrpl_response_data(validated_tx_response):
                process_transaction_error(validated_tx_response)

            tx_hash = validated_tx_response.result['hash']
            logger.info(f"Transaction validated with hash: {tx_hash}")
            logger.info(f"Transaction validated in ledger: {validated_tx_response.result['ledger_index']}")
            logger.info(f"Trust line set successfully for account {issuer}")
            return create_trust_set_response(validated_tx_response, issuer, currency_code, 'NOT THIS')

        except (XRPLRequestFailureException, XRPLException, XRPRangeException) as e:
            # Handle error message
            return handle_error_new(e, status_code=500, function_name=function_name)
        except Exception as e:
            # Handle error message
            return handle_error_new(e, status_code=500, function_name=function_name)
        finally:
            logger.info(LEAVING_FUNCTION_LOG.format(function_name, total_execution_time_in_millis(start_time)))
