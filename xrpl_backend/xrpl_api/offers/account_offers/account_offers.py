import json
import logging
import time
from decimal import Decimal

import xrpl
from django.apps import apps
from django.core.paginator import Paginator
from django.utils.decorators import method_decorator
from django.views import View
from django.views.decorators.csrf import csrf_exempt
from xrpl import XRPLException
from xrpl.account import get_balance
from xrpl.asyncio.account import does_account_exist
from xrpl.asyncio.clients import AsyncWebsocketClient, XRPLRequestFailureException
from xrpl.asyncio.transaction import autofill_and_sign, XRPLReliableSubmissionException
from xrpl.core.addresscodec import XRPLAddressCodecException
from xrpl.ledger import get_latest_validated_ledger_sequence
from xrpl.models import XRP, Fee
from xrpl.transaction import submit_and_wait
from xrpl.utils import drops_to_xrp, get_balance_changes
from xrpl.wallet import Wallet

from .db_operations.account_offers_db_operations import save_offer_cancel_response
from ...accounts.account_utils import prepare_account_data, create_cancel_offers_response
from ...constants.constants import ENTERING_FUNCTION_LOG, LEAVING_FUNCTION_LOG, \
    ERROR_INITIALIZING_CLIENT, INVALID_WALLET_IN_REQUEST, ACCOUNT_DOES_NOT_EXIST_ON_THE_LEDGER, \
    MISSING_REQUEST_PARAMETERS, UNABLE_TO_FETCH_ACCOUNT_OFFERS, NO_OFFER_TO_CANCEL_FOR_THIS_ACCOUNT
from ...currency.currency_util import buyer_create_issued_currency, \
    create_amount_the_buyer_wants_to_spend
from ...errors.error_handling import handle_error_new, error_response, process_transaction_error, \
    process_unexpected_error
from ...offers.account_offers.account_offers_util import process_offer, create_book_offer, create_offer, \
    prepare_account_lines_for_offer, prepare_account_offers, create_account_offers_response, \
    create_get_account_offers_response, prepare_account_offers_paginated, prepare_cancel_offer
from ...utilities.utilities import total_execution_time_in_millis, get_xrpl_client, \
    validate_xrp_wallet, validate_xrpl_response_data

logger = logging.getLogger('xrpl_app')


@method_decorator(csrf_exempt, name="dispatch")
class GetAccountOffers(View):
    def __init__(self):
        super().__init__()
        self.client = None  # Lazy-loaded client

    def _initialize_client(self):
        """Lazy initialization of the XRPL client."""
        if not self.client:
            self.client = get_xrpl_client()
            if not self.client:
                raise XRPLException(error_response(ERROR_INITIALIZING_CLIENT))

    def post(self, request, *args, **kwargs):
        return self.get_account_offers(request)

    def get(self, request, *args, **kwargs):
        return self.get_account_offers(request)

    def get_account_offers(self, request=None, account=None, page=1, page_size=10):
        """

        :rtype: object
        """
        # Capture the start time to track the execution duration.
        start_time = time.time()
        function_name = 'get_account_offers'
        logger.info(ENTERING_FUNCTION_LOG.format(function_name))

        try:
            # Initialize the client if not already initialized
            self._initialize_client()

            # Extract wallet address from request parameters
            data = json.loads(request.body)
            account = data.get("account")

            if not account or not validate_xrp_wallet(account):
                raise XRPLException(error_response(INVALID_WALLET_IN_REQUEST))

            if not xrpl.account.does_account_exist(account, self.client):
                raise XRPLException(error_response(ACCOUNT_DOES_NOT_EXIST_ON_THE_LEDGER.format(account)))

            account_offers = []  # Initialize an empty list to store account lines
            marker = None  # Initialize the marker to manage pagination

            # Loop to fetch all account lines for the account, using pagination via 'marker'
            while True:
                # Prepare the account offers request with the current marker (for pagination)
                account_offers_info = prepare_account_offers_paginated(account, marker)

                # Send the request to XRPL to fetch account offers
                account_offers_response = self.client.request(account_offers_info)
                if validate_xrpl_response_data(account_offers_response):
                    process_transaction_error(account_offers_response)

                offers = account_offers_response.result.get('offers', [])
                if offers:
                    logger.info(f"Found {len(offers)} offers for wallet {account}.")
                else:
                    logger.info(f"No offers found for wallet {account} in this batch.")

                # Add the fetched account lines to the account_lines list
                account_offers.extend(offers)

                # Check if there are more pages of account lines to fetch using the 'marker' field.
                # If 'marker' is not present, break the loop, as we have fetched all pages.
                marker = account_offers_response.result.get('marker')
                if not marker:
                    break

            # Extract pagination parameters from the request
            page = data.get("page", 1)
            page = int(page) if page else 1

            page_size = data.get("page_size", 1)
            page_size = int(page_size) if page_size else 1

            # Paginate the account lines using Django's Paginator
            paginator = Paginator(account_offers, page_size)
            paginated_offers = paginator.get_page(page)

            return create_get_account_offers_response(paginated_offers, paginator)

        except (XRPLRequestFailureException, XRPLException, XRPLAddressCodecException, ValueError) as e:
            # Handle error message
            return handle_error_new(e, status_code=500, function_name=function_name)
        except Exception as e:
            # Handle error message
            return handle_error_new(e, status_code=500, function_name=function_name)
        finally:
            logger.info(LEAVING_FUNCTION_LOG.format(function_name, total_execution_time_in_millis(start_time)))


@method_decorator(csrf_exempt, name="dispatch")
class CancelAccountOffers(View):
    def __init__(self):
        super().__init__()
        self.client = None  # Lazy-loaded client

    def _initialize_client(self):
        """Lazy initialization of the XRPL client."""
        if not self.client:
            self.client = get_xrpl_client()
            if not self.client:
                raise XRPLException(error_response(ERROR_INITIALIZING_CLIENT))

    def post(self, request, *args, **kwargs):
        return self.cancel_account_offers(request)

    def get(self, request, *args, **kwargs):
        return self.cancel_account_offers(request)

    def cancel_account_offers(self, request):
        """
        Cancels all or specific offers for a given XRP Ledger account.

        This function performs the following steps:
        1. Initializes the XRPL client if not already initialized.
        2. Extracts the sender's wallet seed from the request.
        3. Loads the sender's wallet and retrieves its balance.
        4. Fetches the account's existing offers using the `GetAccountOffers` class.
        5. Validates the response and extracts the list of offers.
        6. Fetches the account's current sequence number and the latest validated ledger sequence.
        7. Fetches the current network fee.
        8. Iterates through the offers and cancels each one using an `OfferCancel` transaction.
        9. Returns a success response if all offers are canceled successfully.

        Parameters:
            request (HttpRequest): The Django HTTP request object containing the sender's wallet seed.

        Returns:
            JsonResponse: A JSON response indicating the success or failure of the operation.

        Raises:
            XRPLException: If any step fails, such as missing parameters, invalid wallet, or transaction errors.
        """
        # Capture the start time to track the execution duration.
        start_time = time.time()
        function_name = 'cancel_account_offers'
        logger.info(ENTERING_FUNCTION_LOG.format(function_name))

        try:
            # Initialize the client if not already initialized
            self._initialize_client()

            # Extract sender_seed from the request
            sender_seed = self.request.GET['sender_seed']
            if not sender_seed:
                raise XRPLException(error_response(MISSING_REQUEST_PARAMETERS))

            # Load the wallet using the secret key
            sender_wallet = Wallet.from_seed(sender_seed)
            sender_wallet_balance = get_balance(sender_wallet.classic_address, self.client)
            logger.info(
                f"Sender wallet retrieved: {sender_wallet.classic_address} Sender Address Balance: {sender_wallet_balance}")

            # Fetch the account's existing offers
            get_account_offers_instance = GetAccountOffers()
            get_account_offers_instance.request = request  # Manually set the request object
            account_offers_response = get_account_offers_instance.get_account_offers(
                account=sender_wallet.classic_address,
                page=1,  # Default page
                page_size=10  # Default page size
            )

            # Parse the account offers response
            if account_offers_response.status_code != 200:
                raise XRPLException(error_response(UNABLE_TO_FETCH_ACCOUNT_OFFERS))

            # Decode the JSON response
            response_data = json.loads(account_offers_response.content)
            account_offers = response_data.get('offers', [])

            if not account_offers:
                logger.info(f"No offers found for wallet {sender_wallet.classic_address}.")
                raise XRPLException(error_response(NO_OFFER_TO_CANCEL_FOR_THIS_ACCOUNT))

            # Fetch the account's sequence number
            account_info_request = prepare_account_data(sender_wallet.classic_address, False)
            account_info_response = self.client.request(account_info_request)
            if validate_xrpl_response_data(account_info_response):
                process_transaction_error(account_info_response)

            sequence = account_info_response.result["account_data"]["Sequence"]

            # Fetch the latest validated ledger sequence
            latest_ledger_sequence = get_latest_validated_ledger_sequence(self.client)
            last_ledger_sequence = latest_ledger_sequence + 20  # Add a buffer of 20 ledgers

            # Fetch the current network fee
            fee_response = self.client.request(Fee())
            if validate_xrpl_response_data(fee_response):
                process_transaction_error(fee_response)

            fee = fee_response.result["drops"]["open_ledger_fee"]
            logger.info(f"Fetched network fee: {fee}")

            # Cancel each offer
            for offer in account_offers:
                offer_id = offer.get('seq')  # Get the sequence number of the offer
                if not offer_id:
                    logger.warning(f"Skipping offer with missing sequence number: {offer}")
                    continue

                # Create an OfferCancel transaction
                cancel_offer_tx = prepare_cancel_offer(sender_wallet.classic_address, sequence, offer_id,
                                                       last_ledger_sequence, fee)

                # Sign and submit the transaction
                try:
                    logger.info("signing and submitting the transaction, awaiting a response")
                    cancel_offer_response = submit_and_wait(cancel_offer_tx, self.client, sender_wallet)
                except XRPLException as e:
                    process_unexpected_error(e)

                if validate_xrpl_response_data(cancel_offer_response):
                    process_transaction_error(cancel_offer_response)

                logger.info(f"Offer {offer_id} cancelled successfully.")

                # Save account data to databases
                save_offer_cancel_response(cancel_offer_response.result)

                # Return a success response
                return create_cancel_offers_response(cancel_offer_response)

        except (XRPLRequestFailureException, XRPLException, XRPLAddressCodecException, ValueError) as e:
            # Handle error message
            return handle_error_new(e, status_code=500, function_name=function_name)
        except Exception as e:
            # Handle error message
            return handle_error_new(e, status_code=500, function_name=function_name)
        finally:
            logger.info(LEAVING_FUNCTION_LOG.format(function_name, total_execution_time_in_millis(start_time)))
