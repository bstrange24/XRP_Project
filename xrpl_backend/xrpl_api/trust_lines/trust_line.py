import json

from django.core.paginator import Paginator
import logging
import time

from django.utils.decorators import method_decorator
from django.views import View
from django.views.decorators.csrf import csrf_exempt
from tenacity import wait_exponential, stop_after_attempt, retry
from xrpl import XRPLException
from xrpl.ledger import get_latest_validated_ledger_sequence
from xrpl.asyncio.clients import XRPLRequestFailureException
from xrpl.models import Fee
from xrpl.transaction import submit_and_wait
from xrpl.utils import XRPRangeException, xrp_to_drops
from xrpl.wallet import Wallet
from xrpl.account import does_account_exist, get_balance

from .trust_line_util import create_trust_set_transaction, create_trust_set_response
from ..accounts.account_utils import create_account_lines_response, prepare_account_lines, prepare_account_data, \
    get_account_reserves
from ..constants.constants import ENTERING_FUNCTION_LOG, \
    ERROR_INITIALIZING_CLIENT, LEAVING_FUNCTION_LOG, MISSING_REQUEST_PARAMETERS, \
    INVALID_WALLET_IN_REQUEST, ACCOUNT_DOES_NOT_EXIST_ON_THE_LEDGER, FAILED_TO_FETCH_RESERVE_DATA, RETRY_BACKOFF, \
    MAX_RETRIES
from ..errors.error_handling import error_response, process_transaction_error, handle_error_new, \
    process_unexpected_error
from ..offers.account_offers.account_offers_util import prepare_account_lines_for_offer, prepare_account_offers
from ..utilities.utilities import get_xrpl_client, total_execution_time_in_millis, validate_xrp_wallet, \
    validate_xrpl_response_data, count_xrp_received

logger = logging.getLogger('xrpl_app')

@method_decorator(csrf_exempt, name="dispatch")
class GetAccountTrustLines(View):
    def __init__(self):
        super().__init__()
        self.client = None  # Lazy-loaded client

    def _initialize_client(self):
        """Lazy initialization of the XRPL client."""
        if not self.client:
            self.client = get_xrpl_client()
            if not self.client:
                raise XRPLException(error_response(ERROR_INITIALIZING_CLIENT))

    def post(self, request):
        return self.get_account_trust_lines(request)

    def get(self, request):
        return self.get_account_trust_lines(request)

    @retry(wait=wait_exponential(multiplier=RETRY_BACKOFF), stop=stop_after_attempt(MAX_RETRIES))
    def get_account_trust_lines(self, request):
        # Capture the start time to calculate the total execution time
        start_time = time.time()
        function_name = 'get_account_trust_lines'
        logger.info(ENTERING_FUNCTION_LOG.format(function_name))

        try:
            # Initialize the client if not already initialized
            self._initialize_client()

            # Extract wallet address from request parameters
            data = json.loads(request.body)
            account = data.get("account")

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

                count_xrp_received(account_lines_response.result, account)

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

            # Extract pagination parameters from the request
            page = data.get("page", 1)
            page = int(page) if page else 1

            page_size = data.get("page_size", 1)
            page_size = int(page_size) if page_size else 1

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

@method_decorator(csrf_exempt, name="dispatch")
class SetTrustLines(View):
    def __init__(self):
        super().__init__()
        self.client = None  # Lazy-loaded client

    def _initialize_client(self):
        """Lazy initialization of the XRPL client."""
        if not self.client:
            self.client = get_xrpl_client()
            if not self.client:
                raise XRPLException(error_response(ERROR_INITIALIZING_CLIENT))

    def post(self, request):
        return self.set_trust_line(request)

    def get(self, request):
        return self.set_trust_line(request)

    @retry(wait=wait_exponential(multiplier=RETRY_BACKOFF), stop=stop_after_attempt(MAX_RETRIES))
    def set_trust_line(self, request):
        start_time = time.time()
        function_name = 'set_trust_line'
        logger.info(ENTERING_FUNCTION_LOG.format(function_name))

        try:
            # Initialize the client if not already initialized
            self._initialize_client()

            # Extract the parameters from the request data.
            data = json.loads(request.body)
            sender_seed = data.get("sender_seed")
            issuer_address = data.get("issuer_address")
            currency_code = data.get("currency_code")
            limit = data.get("limit")

            # If any of the required parameters are missing, raise an error.
            if not all([sender_seed, issuer_address, currency_code, limit]):
                ValueError(error_response(MISSING_REQUEST_PARAMETERS))

            # Log the received parameters for debugging and verification.
            logger.debug(f"Parameters: issuer={issuer_address}, currency={currency_code}, limit={limit}")

            # Initialize XRPL client. Check if client is successfully initialized. Raise exception if client initialization fails
            client = get_xrpl_client()
            if not client:
                raise XRPLException(error_response(ERROR_INITIALIZING_CLIENT))

            if not does_account_exist(issuer_address, client):
                raise XRPLException(error_response(ACCOUNT_DOES_NOT_EXIST_ON_THE_LEDGER.format(issuer_address)))

            # If the currency is XRP, convert the limit into drops (the smallest unit of XRP).
            limit_drops = xrp_to_drops(limit) if currency_code == "XRP" else limit
            logger.info(f"Converted limit: {limit_drops}")

            # Create the sender's wallet from the provided seed. This is used to sign transactions.
            sender_wallet = Wallet.from_seed(sender_seed)
            sender_wallet_balance = get_balance(sender_wallet.classic_address, client)
            issuer_wallet_balance = get_balance(issuer_address, client)
            logger.info(
                f"Sender wallet retrieved: {sender_wallet.classic_address} Sender Address Balance: {sender_wallet_balance} Issuer Address Balance: {issuer_wallet_balance}")

            # Check balance
            base_reserve, reserve_increment = get_account_reserves()
            if base_reserve is None or reserve_increment is None:
                raise XRPLException(error_response(FAILED_TO_FETCH_RESERVE_DATA.format(sender_wallet.classic_address)))

            min_balance = base_reserve + reserve_increment  # For 1 trustline
            logger.info(
                f" Base Reserve: {base_reserve}, Reserve Increment: {reserve_increment}, Minimum reserve: {min_balance}")

            if float(sender_wallet_balance) < min_balance:
                raise XRPLException(f"Insufficient XRP for trustline reserve (need {min_balance} XRP)")

            # Create trust line from
            sender_wallet_account_info = prepare_account_data(sender_wallet.classic_address, False)
            sender_wallet_account_info_response = client.request(sender_wallet_account_info)

            # Validate client response. Raise exception on error
            if validate_xrpl_response_data(sender_wallet_account_info_response):
                process_transaction_error(sender_wallet_account_info_response)

            # Fetch sequence
            sequence_number = sender_wallet_account_info_response.result['account_data']['Sequence']
            logger.info(f"Fetched sequence number: {sequence_number}")

            # Fetch the current network fee to include in the transaction.
            # The network fee is used to pay for processing the transaction.
            fee_response = client.request(Fee())
            if validate_xrpl_response_data(fee_response):
                process_transaction_error(fee_response)

            logger.debug(f"Fee response: {fee_response}")

            # Extract the minimum fee from the response.
            fee = fee_response.result['drops']['open_ledger_fee']
            logger.info(f"Fetched network fee: {fee}")

            # Get current ledger for LastLedgerSequence
            current_ledger = get_latest_validated_ledger_sequence(client)

            # Create a TrustSet transaction with the extracted parameters, including the fee and sequence number.
            trust_set_tx = create_trust_set_transaction(currency_code, limit_drops, issuer_address,
                                                        sender_wallet.classic_address, sequence_number, fee,
                                                        current_ledger)

            try:
                logger.info("signing and submitting the transaction, awaiting a response")
                validated_tx_response = submit_and_wait(trust_set_tx, client, sender_wallet)
            except XRPLException as e:
                process_unexpected_error(e)

            if validate_xrpl_response_data(validated_tx_response):
                process_transaction_error(validated_tx_response)

            count_xrp_received(validated_tx_response.result, issuer_address)

            tx_hash = validated_tx_response.result['hash']
            logger.info(
                f"Transaction validated with hash: {tx_hash} in ledger: {validated_tx_response.result['ledger_index']}")
            logger.info(f"Trust line created: {validated_tx_response.result} for account {issuer_address}")
            logger.info(f"Sender Address Balance: {get_balance(sender_wallet.classic_address, client)}")
            logger.info(f"Issuer Address Balance: {get_balance(issuer_address, client)}")

            return create_trust_set_response(validated_tx_response, issuer_address, currency_code, limit)

        except (XRPLRequestFailureException, XRPLException, XRPRangeException) as e:
            # Handle error message
            return handle_error_new(e, status_code=500, function_name=function_name)
        except Exception as e:
            if "Fee value" in str(e):
                return handle_error_new("Fee too high, try again later", status_code=500, function_name=function_name)
            else:
                return handle_error_new(e, status_code=500, function_name=function_name)
        finally:
            logger.info(LEAVING_FUNCTION_LOG.format(function_name, total_execution_time_in_millis(start_time)))

@method_decorator(csrf_exempt, name="dispatch")
class RemoveTrustLine(View):
    def __init__(self):
        super().__init__()
        self.client = None  # Lazy-loaded client

    def _initialize_client(self):
        """Lazy initialization of the XRPL client."""
        if not self.client:
            self.client = get_xrpl_client()
            if not self.client:
                raise XRPLException(error_response(ERROR_INITIALIZING_CLIENT))

    def post(self, request):
        return self.remove_trust_line(request)

    def get(self, request):
        return self.remove_trust_line(request)

    @retry(wait=wait_exponential(multiplier=RETRY_BACKOFF), stop=stop_after_attempt(MAX_RETRIES))
    def remove_trust_line(self, request):
        # Capture the start time to calculate the total execution time of the function
        start_time = time.time()
        function_name = 'remove_trust_line'
        logger.info(ENTERING_FUNCTION_LOG.format(function_name))

        try:
            # Initialize the client if not already initialized
            self._initialize_client()

            # Extract the parameters from the request data.
            data = json.loads(request.body)
            sender_seed = data.get("sender_seed")
            currency_code = data.get("currency_code")
            issuer_address = data.get("issuer_address")

            # If any of the required parameters are missing, raise an error.
            if not all([sender_seed, currency_code, issuer_address]):
                raise ValueError(error_response(MISSING_REQUEST_PARAMETERS))

            # Log the received parameters for debugging and verification.
            logger.info(f"Received parameters: currency: {currency_code}, issuer: {issuer_address}")

            # Initialize XRPL client. Check if client is successfully initialized. Raise exception if client initialization fails
            client = get_xrpl_client()
            if not client:
                raise XRPLException(error_response(ERROR_INITIALIZING_CLIENT))

            if not does_account_exist(issuer_address, client):
                raise XRPLException(error_response(ACCOUNT_DOES_NOT_EXIST_ON_THE_LEDGER.format(issuer_address)))

            # Load the wallet using the secret key
            sender_wallet = Wallet.from_seed(sender_seed)
            sender_wallet_balance = get_balance(sender_wallet.classic_address, client)
            issuer_wallet_balance = get_balance(issuer_address, client)
            logger.info(
                f"Sender wallet retrieved: {sender_wallet.classic_address} Sender Address Balance: {sender_wallet_balance} Issuer Address Balance: {issuer_wallet_balance}")

            offers = client.request(prepare_account_offers(sender_wallet.classic_address)).result["offers"]
            if any(("currency" in offer["taker_gets"] and offer["taker_gets"]["currency"] == currency_code) or
                   ("currency" in offer["taker_pays"] and offer["taker_pays"]["currency"] == currency_code)
                   for offer in offers):
                raise XRPLException(error_response("Outstanding offers prevent trustline removal"))

            # Check trustline eligibility
            response = client.request(prepare_account_lines_for_offer(sender_wallet.classic_address))
            lines = [line for line in response.result["lines"] if
                     line["currency"] == currency_code and line["account"] == issuer_address]
            if not lines:
                raise XRPLException(error_response("Trustline not found"))
            if float(lines[0]["balance"]) != 0:
                raise XRPLException(error_response("Trustline balance must be 0 to remove"))

            # Fetch current fee
            fee_response = client.request(Fee())
            if validate_xrpl_response_data(fee_response):
                process_transaction_error(fee_response)

            # Use open_ledger_fee for worst-case scenario
            fee_drops = fee_response.result["drops"]["open_ledger_fee"]
            fee_xrp = float(fee_drops) / 1000000  # Convert to XRP

            # Add a small buffer (e.g., 2x fee)
            buffer_xrp = fee_xrp * 2

            if float(sender_wallet_balance) < buffer_xrp:
                raise XRPLException(error_response("Insufficient XRP for transaction fee"))
            logger.info(f"Fee: {fee_drops} drops, Buffer: {buffer_xrp} XRP, Balance: {sender_wallet_balance} XRP")

            account_info_response = client.request(prepare_account_data(sender_wallet.classic_address, False))
            if validate_xrpl_response_data(account_info_response):
                process_transaction_error(account_info_response)

            sequence_number = account_info_response.result["account_data"]["Sequence"]
            logger.info(f"Fetched sequence number: {sequence_number}")

            # Get current ledger for LastLedgerSequence
            current_ledger = get_latest_validated_ledger_sequence(client)
            logger.info(f"Current ledger: {current_ledger}")

            trust_set_tx = create_trust_set_transaction(currency_code, str(0), issuer_address,
                                                        sender_wallet.classic_address,
                                                        sequence_number, fee_drops, current_ledger)

            logger.info(f"LastLedgerSequence: {trust_set_tx.last_ledger_sequence}")

            logger.info("signing and submitting the transaction, awaiting a response")
            submit_and_wait_start_time = int((time.time()) * 1000)
            logger.info(f"Time before submission: {submit_and_wait_start_time}")

            try:
                logger.info("signing and submitting the transaction, awaiting a response")
                validated_tx_response = submit_and_wait(trust_set_tx, client, sender_wallet)
            except XRPLException as e:
                process_unexpected_error(e)

            try:
                logger.info("signing and submitting the transaction, awaiting a response")
                submit_and_wait_end_time = int((time.time()) * 1000)
            except XRPLException as e:
                process_unexpected_error(e)

            logger.info(f"Time after submission: {submit_and_wait_end_time - submit_and_wait_start_time}")

            if validate_xrpl_response_data(validated_tx_response):
                process_transaction_error(validated_tx_response)

            count_xrp_received(validated_tx_response.result, issuer_address)

            tx_hash = validated_tx_response.result['hash']
            logger.info(
                f"Transaction validated with hash: {tx_hash} in ledger: {validated_tx_response.result['ledger_index']}")
            logger.info(f"Trust line set successfully for account {issuer_address}")
            return create_trust_set_response(validated_tx_response, issuer_address, currency_code, 'EMPTY_LIMIT')

        except (XRPLRequestFailureException, XRPLException, XRPRangeException) as e:
            # Handle error message
            return handle_error_new(e, status_code=500, function_name=function_name)
        except Exception as e:
            # Handle error message
            return handle_error_new(e, status_code=500, function_name=function_name)
        finally:
            logger.info(LEAVING_FUNCTION_LOG.format(function_name, total_execution_time_in_millis(start_time)))
