import json
import logging
import time
from decimal import Decimal

import xrpl
from django.core.paginator import Paginator
from django.utils.decorators import method_decorator
from django.views import View
from django.views.decorators.csrf import csrf_exempt
from django.apps import apps
from rest_framework.decorators import api_view
from tenacity import retry, wait_exponential, stop_after_attempt
from xrpl import XRPLException
from xrpl.asyncio.account import does_account_exist
from xrpl.asyncio.clients import AsyncWebsocketClient, XRPLRequestFailureException
from xrpl.asyncio.transaction import autofill_and_sign, XRPLReliableSubmissionException
from xrpl.core.addresscodec import XRPLAddressCodecException

from xrpl.models import XRP
from xrpl.utils import drops_to_xrp, get_balance_changes
from xrpl.wallet import Wallet

from ..constants.constants import ENTERING_FUNCTION_LOG, LEAVING_FUNCTION_LOG, RETRY_BACKOFF, MAX_RETRIES, \
    ERROR_INITIALIZING_CLIENT, INVALID_WALLET_IN_REQUEST, ACCOUNT_DOES_NOT_EXIST_ON_THE_LEDGER, \
    MISSING_REQUEST_PARAMETERS
from ..currency.currency_util import buyer_create_issued_currency, \
    create_amount_the_buyer_wants_to_spend
from ..errors.error_handling import handle_error, handle_error_new, error_response, process_transaction_error
from ..offers.account_offers_util import process_offer, create_book_offer, create_offer, \
    prepare_account_lines_for_offer, prepare_account_offers, create_account_offers_response, \
    create_get_account_offers_response, prepare_account_offers_paginated
from ..utils.utils1 import get_request_param, total_execution_time_in_millis, get_xrpl_client, \
    validate_xrp_wallet, validate_xrpl_response_data

logger = logging.getLogger('xrpl_app')


@method_decorator(csrf_exempt, name="dispatch")
class AccountOffer(View):

    async def post(self, request, *args, **kwargs):
        return await self.create_offer(request)

    async def get(self, request, *args, **kwargs):
        return await self.create_offer(request)

    async def create_offer(self, request):
        start_time = time.time()  # Capture the start time
        function_name = 'AccountOffer'
        logger.info(ENTERING_FUNCTION_LOG.format(function_name))  # Log entering the function

        try:
            # Extract the parameters from the request data.
            account = self.request.GET['account']
            currency = self.request.GET['currency']
            value = self.request.GET['value']
            sender_seed = self.request.GET['sender_seed']

            # If any of the required parameters are missing, raise an error.
            if not all([account, currency, value, sender_seed]):
                raise ValueError(MISSING_REQUEST_PARAMETERS)

            logger.info(f"Received parameters: account: {account}, currency: {currency}, value: {value}")

            sender_wallet = Wallet.from_seed(sender_seed)

            xrpl_config = apps.get_app_config('xrpl_api')

            async with AsyncWebsocketClient(xrpl_config.XRPL_WEB_SOCKET_NETWORK_URL) as client:
                if not does_account_exist(account, client):
                    raise XRPLException(error_response(ACCOUNT_DOES_NOT_EXIST_ON_THE_LEDGER.format(account)))

                buyer_wants = buyer_create_issued_currency(account, currency, value)
                logger.info(f"Buyer wants: {buyer_wants}")
                buyer_spend = create_amount_the_buyer_wants_to_spend()
                logger.info(f"Buyer spends: {buyer_spend}")

                proposed_quality = Decimal(buyer_spend["value"]) / Decimal(buyer_wants["value"])
                logger.info(f"Proposed quality: {proposed_quality}")

                logger.info("Requesting orderbook information...")
                orderbook_info_response = await client.request(create_book_offer(account, buyer_wants, buyer_spend))

                if validate_xrpl_response_data(orderbook_info_response):
                    process_transaction_error(orderbook_info_response)

                logger.info(f"Orderbook:{orderbook_info_response.result}")

                offers = orderbook_info_response.result.get("offers", [])
                logger.info(f"Offers: {offers}")

                buyer_amount = Decimal(buyer_wants["value"])
                logger.info(f"Buyer amount: {buyer_amount}")

                running_total = Decimal(0)
                if len(offers) == 0:
                    logger.info("No Offers in the matching book. Offer probably won't execute immediately.")
                else:
                    for o in offers:
                        if Decimal(o["quality"]) <= proposed_quality:
                            logger.info(f"Matching Offer found, funded with {o.get('owner_funds')} {buyer_wants['currency']}")
                            running_total += Decimal(o.get("owner_funds", Decimal(0)))
                            if running_total >= buyer_amount:
                                logger.info("Full Offer will probably fill")
                                break
                        else:
                            # Offers are in ascending quality order, so no others after this will match either
                            logger.info("Remaining orders too expensive.")
                            break

                    logger.info(f"Total matched: {min(running_total, buyer_amount)} {buyer_wants['currency']}")
                    if 0 < running_total < buyer_amount:
                        logger.info(f"Remaining {buyer_amount - running_total} {buyer_wants['currency']} would probably be placed on top of the order book.")

                if running_total == 0:
                    # If part of the Offer was expected to cross, then the rest would be placed
                    # at the top of the order book. If none did, then there might be other
                    # Offers going the same direction as ours already on the books with an
                    # equal or better rate. This code counts how much liquidity is likely to be
                    # above ours.
                    #
                    # Unlike above, this time we check for Offers going the same direction as
                    # ours, so TakerGets and TakerPays are reversed from the previous
                    # book_offers request.

                    logger.info("Requesting second orderbook information...")
                    orderbook2_info_response = await client.request(create_book_offer(account, buyer_wants, buyer_spend))

                    if validate_xrpl_response_data(orderbook2_info_response):
                        process_transaction_error(orderbook2_info_response)

                    logger.info(f"Orderbook2: {orderbook2_info_response.result}")

                    # Since TakerGets/TakerPays are reversed, the quality is the inverse.
                    # You could also calculate this as 1 / proposed_quality.
                    offered_quality = Decimal(buyer_wants["value"]) / Decimal(buyer_spend["value"])
                    logger.info(f"offered_quality: {offered_quality}")

                    tally_currency = buyer_spend["currency"]
                    logger.info(f"tally_currency: {tally_currency}")

                    if isinstance(tally_currency, XRP):
                        tally_currency = f"drops of {tally_currency}"
                    logger.info(f"tally_currency after isinstance: {tally_currency}")

                    offers2 = orderbook2_info_response.result.get("offers", [])
                    logger.info(f"offers2: {offers2}")

                    running_total2 = Decimal(0)
                    if len(offers2) == 0:
                        logger.info("No similar Offers in the book. Ours would be the first.")
                    else:
                        for o in offers2:
                            if Decimal(o["quality"]) <= offered_quality:
                                logger.info(f"Existing offer found, funded with {o.get('owner_funds')} {tally_currency}")
                                running_total2 += Decimal(o.get("owner_funds", Decimal(0)))
                            else:
                                logger.info("Remaining orders are below where ours would be placed.")
                                break

                        logger.info(f"Our Offer would be placed below at least {running_total2} {tally_currency}")
                        if 0 < running_total2 < buyer_amount:
                            logger.info(f"Remaining {buyer_amount - running_total2} {tally_currency} will probably be placed on top of the order book.")

                tx = create_offer(account, buyer_wants, buyer_spend)
                logger.info(f"Created offer: {tx}")

                logger.info(f"before autofill_and_sign...")
                signed_tx = await autofill_and_sign(tx, client, sender_wallet)

                # if validate_xrpl_response_data(signed_tx):
                #     process_transaction_error(signed_tx)
                logger.info(f"after autofill_and_sign...")


                logger.info(f"before process_offer...")
                process_offer_result = await process_offer(signed_tx, client)

                if validate_xrpl_response_data(process_offer_result):
                    process_transaction_error(process_offer_result)
                logger.info(f"after process_offer...")

                logger.info(f"Transaction succeeded:")
                logger.info(f"{xrpl_config.XRPL_WEB_SOCKET_NETWORK_URL}{signed_tx.get_hash()}")

                # Check metadata ------------------------------------------------------------
                balance_changes = get_balance_changes(process_offer_result.result["meta"])
                logger.info(f"Balance Changes:{balance_changes}")

                # Helper to convert an XRPL amount to a string for display
                def amt_str(amt) -> str:
                    if isinstance(amt, str):
                        return f"{drops_to_xrp(amt)} XRP"
                    else:
                        return f"{amt['value']} {amt['currency']}.{amt['issuer']}"

                offers_affected = 0
                for affected_node in process_offer_result.result["meta"]["AffectedNodes"]:
                    if "ModifiedNode" in affected_node:
                        if affected_node["ModifiedNode"]["LedgerEntryType"] == "Offer":
                            # Usually a ModifiedNode of type Offer indicates a previous Offer that
                            # was partially consumed by this one.
                            offers_affected += 1
                    elif "DeletedNode" in affected_node:
                        if affected_node["DeletedNode"]["LedgerEntryType"] == "Offer":
                            # The removed Offer may have been fully consumed, or it may have been
                            # found to be expired or unfunded.
                            offers_affected += 1
                    elif "CreatedNode" in affected_node:
                        if affected_node["CreatedNode"]["LedgerEntryType"] == "RippleState":
                            logger.info("Created a trust line.")
                        elif affected_node["CreatedNode"]["LedgerEntryType"] == "Offer":
                            offer = affected_node["CreatedNode"]["NewFields"]
                            logger.info(f"Created an Offer owned by {offer['Account']} with TakerGets={amt_str(offer['TakerGets'])} and TakerPays={amt_str(offer['TakerPays'])}.")

                logger.info(f"Modified or removed {offers_affected} matching Offer(s)")

                # Check balances
                logger.info("Getting address balances as of validated ledger...")
                balances = await client.request(prepare_account_lines_for_offer(account))

                if validate_xrpl_response_data(balances):
                    process_transaction_error(balances)

                logger.info(f"Balance result: {balances.result}")

                # Check Offers
                logger.info(f"Getting outstanding Offers from {account} as of validated ledger...")
                acct_offers = await client.request(prepare_account_offers(account))

                if validate_xrpl_response_data(acct_offers):
                    process_transaction_error(acct_offers)

                logger.info(f"Account Offers result: {acct_offers.result}")

                # response_data = create_account_offers_response(orderbook_info_response, result, acct_offers)
                response_data = create_account_offers_response(orderbook_info_response, process_offer_result)
                logger.info(f"response_data: {response_data}")

                return response_data

        except XRPLReliableSubmissionException as e:
            # Catch any exceptions that occur during the process. Handle error and return response
            return handle_error({'status': 'failure', 'message': f"{str(e)}"}, status_code=500,
                                function_name=function_name)
        except Exception as e:
            # Catch any exceptions that occur during the process. Handle error and return response
            return handle_error({'status': 'failure', 'message': f"{str(e)}"}, status_code=500,
                                function_name=function_name)
        finally:
            # Log leaving the function regardless of success or failure
            logger.info(LEAVING_FUNCTION_LOG.format(function_name, total_execution_time_in_millis(start_time)))


@method_decorator(csrf_exempt, name="dispatch")
class GetAccountOffers(View):

    def post(self, request, *args, **kwargs):
        return self.get_account_offers(request)

    def get(self, request, *args, **kwargs):
        return self.get_account_offers(request)

    def get_account_offers(self, request):
        # Capture the start time to track the execution duration.
        start_time = time.time()
        function_name = 'get_account_offers'
        logger.info(ENTERING_FUNCTION_LOG.format(function_name))

        try:
            account = self.request.GET['account']
            if not account or not validate_xrp_wallet(account):
                raise XRPLException(error_response(INVALID_WALLET_IN_REQUEST))

            # Initialize the XRPL client for further operations.
            client = get_xrpl_client()
            if not client:
                raise XRPLException(error_response(ERROR_INITIALIZING_CLIENT))

            if not xrpl.account.does_account_exist(account, client):
                raise XRPLException(error_response(ACCOUNT_DOES_NOT_EXIST_ON_THE_LEDGER.format(account)))

            account_offers = []  # Initialize an empty list to store account lines
            marker = None  # Initialize the marker to manage pagination

            # Loop to fetch all account lines for the account, using pagination via 'marker'
            while True:
                # Prepare the account offers request with the current marker (for pagination)
                account_offers_info = prepare_account_offers_paginated(account, marker)

                # Send the request to XRPL to fetch account offers
                account_offers_response = client.request(account_offers_info)
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
            page = self.request.GET.get('page', 1)
            page = int(page) if page else 1

            page_size = self.request.GET.get('page_size', 10)
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

    