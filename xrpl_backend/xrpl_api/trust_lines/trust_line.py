from django.core.paginator import Paginator
import json
import logging
import time

import xrpl
from django.views import View
from rest_framework.decorators import api_view
from tenacity import wait_exponential, stop_after_attempt, retry
from xrpl import XRPLException
from xrpl.asyncio.clients import XRPLRequestFailureException
from xrpl.models import AccountLines, Fee, IssuedCurrencyAmount, TrustSet
from xrpl.transaction import submit, sign
from xrpl.utils import XRPRangeException, xrp_to_drops
from xrpl.wallet import Wallet
from xrpl.account import does_account_exist

from .trust_line_util import trust_line_response, create_trust_set_transaction, create_trust_set_response, \
    wait_for_validation
from ..accounts.account_utils import create_account_lines_response, prepare_account_lines, \
    prepare_account_lines_for_offer, prepare_account_data
from ..constants import RETRY_BACKOFF, MAX_RETRIES, ENTERING_FUNCTION_LOG, \
    ERROR_INITIALIZING_CLIENT, LEAVING_FUNCTION_LOG, XRPL_RESPONSE, MISSING_REQUEST_PARAMETERS, \
    INVALID_WALLET_IN_REQUEST, ACCOUNT_DOES_NOT_EXIST_ON_THE_LEDGER
from ..errors.error_handling import handle_engine_result, handle_error, error_response, process_transaction_error, \
    handle_error_new
from ..utils import get_request_param, get_xrpl_client, total_execution_time_in_millis, validate_xrpl_response, \
    validate_xrp_wallet, validate_xrpl_response_data

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


    #### Need new error handling
    ####
    @api_view(['POST'])
    @retry(wait=wait_exponential(multiplier=RETRY_BACKOFF), stop=stop_after_attempt(MAX_RETRIES))
    def set_trust_line(self):
        # Capture the start time to calculate the total execution time of the function
        start_time = time.time()
        function_name = 'set_trust_line'
        logger.info(ENTERING_FUNCTION_LOG.format(function_name))

        try:
            # Extract the parameters from the request data.
            # These parameters are necessary to create and submit a TrustSet transaction.
            sender_seed = get_request_param(self, 'sender_seed')
            account = get_request_param(self, 'account')
            currency = get_request_param(self, 'currency')
            limit = get_request_param(self, 'limit')

            # If any of the required parameters are missing, raise an error.
            if not sender_seed or not account or not currency or not limit:
                raise ValueError(MISSING_REQUEST_PARAMETERS)

            # Log the received parameters for debugging and verification.
            logger.debug(f"Received parameters - sender_seed: {sender_seed}, wallet_address: {account}, currency: {currency}, limit: {limit}")

            # Initialize XRPL client. Check if client is successfully initialized. Raise exception if client initialization fails
            client = get_xrpl_client()
            if not client:
                raise XRPLException(error_response(ERROR_INITIALIZING_CLIENT))

            if not does_account_exist(account, client):
                raise XRPLException(error_response(ACCOUNT_DOES_NOT_EXIST_ON_THE_LEDGER.format(account)))

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

            logger.info(f"Trust lines response: {fee_response}")

            # Extract the minimum fee from the response.
            fee = fee_response.result['drops']['minimum_fee']
            logger.info(f"Fetched network fee: {fee}")

            # Create a TrustSet transaction with the extracted parameters, including the fee and sequence number.
            trust_set_tx = create_trust_set_transaction(currency, limit_drops, account, sender_wallet.classic_address, sequence_number, fee)

            # Sign the transaction with the sender's wallet.
            signed_tx_response = sign(trust_set_tx, sender_wallet)
            logger.info(f"Trust lines response: {signed_tx_response}")

            if signed_tx_response.get_hash():
                tx_hash = signed_tx_response.get_hash()
            else:
                raise XRPLException(error_response('Not has in the signed TrustSet'))

            validated_tx_response = wait_for_validation(client, tx_hash)

            # Validate client response. Raise exception on error
            if validate_xrpl_response_data(validated_tx_response):
                process_transaction_error(validated_tx_response)

            # Log the success and return the response to indicate that the trust line was set successfully.
            logger.info(f"Transaction validated in ledger: {validated_tx_response.result['ledger_index']}")
            logger.info(f"Trust line set successfully for account {account}")
            return create_trust_set_response(signed_tx_response, account, currency, limit)

        except (XRPLRequestFailureException, XRPLException, XRPRangeException) as e:
            # Handle error message
            return handle_error_new(e, status_code=500, function_name=function_name)
        except Exception as e:
            # Handle error message
            return handle_error_new(e, status_code=500, function_name=function_name)
        finally:
            logger.info(LEAVING_FUNCTION_LOG.format(function_name, total_execution_time_in_millis(start_time)))

    #### Need new error handling
    ####
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
            account = get_request_param(self, 'account')
            currency_code = get_request_param(self, 'currency_code')
            issuer = get_request_param(self, 'issuer')

            # If any of the required parameters are missing, raise an error.
            if not sender_seed or not account or not currency_code or not issuer:
                raise ValueError(MISSING_REQUEST_PARAMETERS)

            # Log the received parameters for debugging and verification.
            logger.info(
                f"Received parameters - sender_seed: {sender_seed}, wallet_address: {account}, currency: {currency_code}, issuer: {issuer}")

            # Initialize the XRPL client to interact with the XRP ledger.
            # If the client cannot be initialized, raise an exception.
            client = get_xrpl_client()
            if not client:
                raise ConnectionError(ERROR_INITIALIZING_CLIENT)

            # Load the wallet using the secret key
            sender_wallet = Wallet.from_secret(sender_seed)
            # Fetch account info to get the current sequence number
            account_info = client.request(prepare_account_data(account, False))
            is_valid, response = validate_xrpl_response(account_info, required_keys=["account_data"])
            if not is_valid:
                raise Exception(response)

            sequence = account_info.result["account_data"]["Sequence"]

            # Fetch the current fee from the XRPL network
            fee_info = client.request(Fee())
            is_valid, response = validate_xrpl_response(fee_info, required_keys=["drops"])
            if not is_valid:
                raise Exception(response)

            fee = fee_info.result["drops"]["open_ledger_fee"]

            # Create a TrustSet transaction to remove the trust line by setting the limit to 0
            trust_set_tx = TrustSet(
                account=account,
                limit_amount=IssuedCurrencyAmount(
                    currency=currency_code,
                    issuer=issuer,
                    value=int(0)
                ),
                sequence=sequence,
                fee=fee,
            )

            # Sign the transaction with the sender's wallet.
            signed_tx = xrpl.transaction.sign(trust_set_tx, sender_wallet)
            logger.info(f"Signed transaction: {signed_tx}")

            # Submit the signed transaction to the XRPL network.
            response = submit(signed_tx, client)

            # Check the transaction response
            if response.is_successful():
                logger.info(f"Trust line for {currency_code} removed successfully.")
            else:
                logger.error(f"Error: {response.result['error']}, Message: {response.result.get('error_message', 'No additional details')}")

            # Handle the engine result
            engine_result = response.result.get("engine_result")
            engine_result_message = response.result.get("engine_result_message", "No additional details")
            handle_engine_result(engine_result, engine_result_message)

            is_valid, response = validate_xrpl_response(response, required_keys=["tx_json"])
            if not is_valid:
                raise Exception(response)

            return create_trust_set_response(response, account, currency_code, 'NOT THIS')


        except (XRPLRequestFailureException, XRPLException, XRPRangeException) as e:
            # Handle error message
            return handle_error_new(e, status_code=500, function_name=function_name)
        except Exception as e:
            # Handle error message
            return handle_error_new(e, status_code=500, function_name=function_name)
        finally:
            logger.info(LEAVING_FUNCTION_LOG.format(function_name, total_execution_time_in_millis(start_time)))
