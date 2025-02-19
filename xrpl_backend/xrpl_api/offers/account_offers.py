import json
import logging
import time
from decimal import Decimal

from django.utils.decorators import method_decorator
from django.views import View
from django.views.decorators.csrf import csrf_exempt
from django.apps import apps
from rest_framework.decorators import api_view
from tenacity import retry, wait_exponential, stop_after_attempt
from xrpl.asyncio.clients import AsyncWebsocketClient
from xrpl.asyncio.transaction import autofill_and_sign, XRPLReliableSubmissionException

from xrpl.models import XRP
from xrpl.utils import drops_to_xrp, get_balance_changes
from xrpl.wallet import Wallet

from ..accounts.account_utils import prepare_account_lines_for_offer, prepare_account_offers, \
    create_account_offers_response, create_get_account_offers_response
from ..constants import ACCOUNT_IS_REQUIRED, ENTERING_FUNCTION_LOG, LEAVING_FUNCTION_LOG, RETRY_BACKOFF, MAX_RETRIES, \
    ERROR_INITIALIZING_CLIENT, XRPL_RESPONSE
from ..currency.currency_util import create_issued_currency_the_user_wants, \
    create_amount_the_user_wants_to_spend
from ..errors.error_handling import handle_error
from ..offers.account_offers_util import process_offer, create_book_offer, create_offer
from ..utils import get_request_param, total_execution_time_in_millis, validate_xrpl_response, get_xrpl_client

logger = logging.getLogger('xrpl_app')


@method_decorator(csrf_exempt, name="dispatch")
class AccountOffer(View):

    async def post(self, request, *args, **kwargs):
        return await self.create_offer(request)

    async def get(self, request, *args, **kwargs):
        return await self.create_offer(request)

    #### Need new error handling
    ####
    async def create_offer(self, request):
        start_time = time.time()  # Capture the start time
        function_name = 'AccountOffer'
        logger.info(ENTERING_FUNCTION_LOG.format(function_name))  # Log entering the function

        try:
            account = get_request_param(request, 'account')
            if not account:
                raise ValueError(ACCOUNT_IS_REQUIRED)  # Raise an error if the wallet address is missing.

            currency = get_request_param(request, 'currency')
            if not currency:
                raise ValueError('currency is required')  # Raise an error if the wallet address is missing.

            value = get_request_param(request, 'value')
            if not value:
                raise ValueError('value is required')  # Raise an error if the wallet address is missing.

            sender_seed = get_request_param(request, 'sender_seed')
            if not sender_seed:
                raise ValueError('sender seed is required')  # Raise an error if the wallet address is missing.

            sender_wallet = Wallet.from_seed(sender_seed)

            xrpl_config = apps.get_app_config('xrpl_api')

            async with AsyncWebsocketClient(xrpl_config.XRPL_WEB_SOCKET_NETWORK_URL) as client:
                we_want = create_issued_currency_the_user_wants(account, currency, value)
                logger.info(f"We want: {we_want}")
                we_spend = create_amount_the_user_wants_to_spend()
                logger.info(f"We spend: {we_spend}")

                proposed_quality = Decimal(we_spend["value"]) / Decimal(we_want["value"])
                logger.info(f"Proposed quality: {proposed_quality}")

                logger.info("Requesting orderbook information...")
                orderbook_info = await client.request(
                    create_book_offer(account, we_want, we_spend)
                )
                logger.info(f"Orderbook:{orderbook_info.result}")

                offers = orderbook_info.result.get("offers", [])
                logger.info(f"Offers: {offers}")

                want_amt = Decimal(we_want["value"])
                logger.info(f"Want amount: {want_amt}")

                running_total = Decimal(0)
                if len(offers) == 0:
                    logger.info("No Offers in the matching book. Offer probably won't execute immediately.")
                else:
                    for o in offers:
                        if Decimal(o["quality"]) <= proposed_quality:
                            logger.info(f"Matching Offer found, funded with {o.get('owner_funds')} "
                                        f"{we_want['currency']}")
                            running_total += Decimal(o.get("owner_funds", Decimal(0)))
                            if running_total >= want_amt:
                                logger.info("Full Offer will probably fill")
                                break
                        else:
                            # Offers are in ascending quality order, so no others after this
                            # will match either
                            logger.info("Remaining orders too expensive.")
                            break

                    logger.info(f"Total matched: {min(running_total, want_amt)} {we_want['currency']}")
                    if 0 < running_total < want_amt:
                        logger.info(f"Remaining {want_amt - running_total} {we_want['currency']} "
                                    "would probably be placed on top of the order book.")

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
                    orderbook2_info = await client.request(
                        create_book_offer(account, we_want, we_spend)
                    )
                    logger.info(f"Orderbook2: {orderbook2_info.result}")

                    # Since TakerGets/TakerPays are reversed, the quality is the inverse.
                    # You could also calculate this as 1 / proposed_quality.
                    offered_quality = Decimal(we_want["value"]) / Decimal(we_spend["value"])
                    logger.info(f"offered_quality: {offered_quality}")

                    tally_currency = we_spend["currency"]
                    logger.info(f"tally_currency: {tally_currency}")

                    if isinstance(tally_currency, XRP):
                        tally_currency = f"drops of {tally_currency}"
                    logger.info(f"tally_currency after isinstance: {tally_currency}")

                    offers2 = orderbook2_info.result.get("offers", [])
                    logger.info(f"offers2: {offers2}")

                    running_total2 = Decimal(0)
                    if len(offers2) == 0:
                        logger.info("No similar Offers in the book. Ours would be the first.")
                    else:
                        for o in offers2:
                            if Decimal(o["quality"]) <= offered_quality:
                                logger.info(f"Existing offer found, funded with {o.get('owner_funds')} "
                                            f"{tally_currency}")
                                running_total2 += Decimal(o.get("owner_funds", Decimal(0)))
                            else:
                                logger.info("Remaining orders are below where ours would be placed.")
                                break

                        logger.info(f"Our Offer would be placed below at least {running_total2} "
                                    f"{tally_currency}")
                        if 0 < running_total2 < want_amt:
                            logger.info(f"Remaining {want_amt - running_total2} {tally_currency} "
                                        "will probably be placed on top of the order book.")

                tx = create_offer(account, we_want, we_spend)
                logger.info(f"create_offer_create: {tx}")

                logger.info(f"before autofill_and_sign...")
                signed_tx = await autofill_and_sign(tx, client, sender_wallet)
                logger.info(f"after autofill_and_sign...")
                logger.info(f"before process_offer...")
                result = await process_offer(signed_tx, client)
                logger.info(f"after process_offer...")

                is_valid, response = validate_xrpl_response(result, required_keys=["meta"])
                if not is_valid:
                    raise Exception(response)
                else:
                    logger.info(f"Transaction succeeded:")
                    logger.info(f"{xrpl_config.XRPL_WEB_SOCKET_NETWORK_URL}{signed_tx.get_hash()}")

                # Check metadata ------------------------------------------------------------
                balance_changes = get_balance_changes(result.result["meta"])
                logger.info(f"Balance Changes:{balance_changes}")

                # Helper to convert an XRPL amount to a string for display
                def amt_str(amt) -> str:
                    if isinstance(amt, str):
                        return f"{drops_to_xrp(amt)} XRP"
                    else:
                        return f"{amt['value']} {amt['currency']}.{amt['issuer']}"

                offers_affected = 0
                for affnode in result.result["meta"]["AffectedNodes"]:
                    if "ModifiedNode" in affnode:
                        if affnode["ModifiedNode"]["LedgerEntryType"] == "Offer":
                            # Usually a ModifiedNode of type Offer indicates a previous Offer that
                            # was partially consumed by this one.
                            offers_affected += 1
                    elif "DeletedNode" in affnode:
                        if affnode["DeletedNode"]["LedgerEntryType"] == "Offer":
                            # The removed Offer may have been fully consumed, or it may have been
                            # found to be expired or unfunded.
                            offers_affected += 1
                    elif "CreatedNode" in affnode:
                        if affnode["CreatedNode"]["LedgerEntryType"] == "RippleState":
                            logger.info("Created a trust line.")
                        elif affnode["CreatedNode"]["LedgerEntryType"] == "Offer":
                            offer = affnode["CreatedNode"]["NewFields"]
                            logger.info(f"Created an Offer owned by {offer['Account']} with "
                                        f"TakerGets={amt_str(offer['TakerGets'])} and "
                                        f"TakerPays={amt_str(offer['TakerPays'])}.")

                logger.info(f"Modified or removed {offers_affected} matching Offer(s)")

                # Check balances
                logger.info("Getting address balances as of validated ledger...")
                balances = await client.request(prepare_account_lines_for_offer(account))
                logger.info(f"Balance result: {balances.result}")

                # Check Offers
                logger.info(f"Getting outstanding Offers from {account} as of validated ledger...")
                acct_offers = await client.request(prepare_account_offers(account))
                logger.info(f"Account Offers result: {acct_offers.result}")

                response_data = create_account_offers_response(orderbook_info, result, acct_offers)
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


    @api_view(['GET'])
    @retry(wait=wait_exponential(multiplier=RETRY_BACKOFF), stop=stop_after_attempt(MAX_RETRIES))
    def get_account_offers(self):
        """
        Retrieve account offers (open orders) for a given wallet address from the XRP Ledger.

        This function performs the following steps:
        1. Extracts the `wallet_address` query parameter from the request.
        2. Initializes the XRPL client to interact with the XRP Ledger.
        3. Prepares and sends a request to fetch account offers for the specified wallet address.
        4. Validates the response to ensure it contains the required data.
        5. Logs the raw response for debugging purposes.
        6. Extracts the offers from the response data.
        7. Logs the number of offers found or if no offers are present.
        8. Returns the formatted response containing the account offers.
        9. Handles any exceptions that occur during execution.
        10. Logs the total execution time of the function.

        Args:
            self (HttpRequest): The HTTP request object containing the `wallet_address` query parameter.

        Returns:
            JsonResponse: A JSON response containing the account offers or an error message.
        """
        start_time = time.time()  # Capture the start time to track the execution duration.
        function_name = 'get_account_offers'
        logger.info(ENTERING_FUNCTION_LOG.format(function_name))  # Log function entry.

        try:
            # Step 1: Retrieve the wallet address from the query parameters in the request.
            account = get_request_param(self, 'account')
            if not account:
                # If wallet address is missing, raise an error and return failure.
                raise ValueError(ACCOUNT_IS_REQUIRED)

            # Step 2: Initialize the XRPL client to interact with the XRPL network.
            client = get_xrpl_client()
            if not client:
                # If the client is not initialized, raise an error and return failure.
                raise ConnectionError(ERROR_INITIALIZING_CLIENT)

            # Step 3: Prepare the request for fetching account offers using the wallet address.
            account_offers_request = prepare_account_offers(account)
            # Send the request to the XRPL client to get the account offers.
            response = client.request(account_offers_request)

            # Step 4: Validate the response from XRPL to ensure it's successful and contains expected data.
            is_valid, response = validate_xrpl_response(response, required_keys=["validated"])
            if not is_valid:
                raise Exception(response)

            # Step 5: Log the raw response for debugging purposes (useful for detailed inspection).
            logger.debug(XRPL_RESPONSE)
            logger.debug(json.dumps(response, indent=4, sort_keys=True))

            # Step 6: Extract the offers from the response data.
            offers = response.get("offers", [])

            # Step 7: Log the number of offers found and return the response with the offer data.
            if offers:
                # If offers are found, log how many were found.
                logger.info(f"Found {len(offers)} offers for wallet {account}.")
            else:
                # If no offers are found, log this information.
                logger.info(f"No offers found for wallet {account}.")

            # Step 8: Log the successful fetching of offers for the account.
            logger.info(f"Successfully fetched offers for account {account}.")

            # Step 9: Prepare and return the response containing the offers.
            return create_get_account_offers_response(response)

        except Exception as e:
            # Step 10: Handle unexpected errors that might occur during the execution.
            return handle_error({'status': 'failure', 'message': f"{str(e)}"}, status_code=500,
                                function_name=function_name)
        finally:
            # Step 11: Log when the function exits, including the total execution time.
            logger.info(LEAVING_FUNCTION_LOG.format(function_name, total_execution_time_in_millis(start_time)))
