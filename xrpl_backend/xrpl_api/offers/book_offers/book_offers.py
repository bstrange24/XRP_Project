import json
import logging
import time
from decimal import Decimal
from http.cookiejar import debug

from django.apps import apps
from django.core.paginator import Paginator
from django.http import JsonResponse
from django.utils.decorators import method_decorator
from django.views import View
from django.views.decorators.csrf import csrf_exempt
from xrpl import XRPLException
from xrpl.asyncio.account import get_balance, does_account_exist
from xrpl.asyncio.clients import XRPLRequestFailureException, AsyncWebsocketClient
from xrpl.asyncio.transaction import autofill_and_sign, XRPLReliableSubmissionException, submit_and_wait
from xrpl.asyncio.wallet import generate_faucet_wallet
from xrpl.core.addresscodec import XRPLAddressCodecException
from xrpl.models import XRP, IssuedCurrencyAmount, BookOffers, AccountOffers, AccountInfo, TrustSet, Payment, \
    AccountLines, OfferCreate
from xrpl.utils import get_balance_changes, drops_to_xrp
from xrpl.wallet import Wallet

from ..account_offers.account_offers_util import create_book_offer, create_offer, process_offer, \
    prepare_account_lines_for_offer, prepare_account_offers, create_account_offers_response
from ...constants.constants import ENTERING_FUNCTION_LOG, LEAVING_FUNCTION_LOG, \
    ERROR_INITIALIZING_CLIENT, ACCOUNT_DOES_NOT_EXIST_ON_THE_LEDGER, INVALID_WALLET_IN_REQUEST, \
    MISSING_REQUEST_PARAMETERS
from ...currency.currency_util import buyer_create_issued_currency, create_amount_the_buyer_wants_to_spend
from ...errors.error_handling import handle_error_new, error_response, process_transaction_error, \
    process_unexpected_error
from ...offers.book_offers.book_offers_util import prepare_book_offers, \
    prepare_book_offers_paginated, create_book_offers_response
from ...utilities.utilities import total_execution_time_in_millis, get_xrpl_client, \
    validate_xrpl_response_data, validate_xrp_wallet

logger = logging.getLogger('xrpl_app')


@method_decorator(csrf_exempt, name='dispatch')  # Apply CSRF exemption to the entire class
class CreateBookOffers(View):
    """
    A class-based Django view to create book offers (buy/sell orders) on the XRPL TestNet with a new USD issuer.
    Manages trustlines and handles POST requests from Postman.
    Uses USD as the currency.
    """

    def __init__(self, *args, **kwargs):
        """
        Initialize the class with a JSON RPC client and create a new issuer wallet.
        Set up the two predefined accounts and check/create trustlines.
        """
        super().__init__(*args, **kwargs)
        if not self.client:
            self.client = get_xrpl_client()
        if not self.client:
            raise XRPLException(error_response(ERROR_INITIALIZING_CLIENT))

        # Create a new wallet to act as the USD issuer (funded via TestNet faucet)
        self.usd_issuer_wallet = generate_faucet_wallet(self.client)

        # Define the two TestNet accounts with their seeds
        self.account1 = Wallet(seed="sEdVg7gRSeQ7D6jMTwWCENsJK742qxT")
        self.account2 = Wallet(seed="sEdS5zxsgGbbtMKWkkBt3kdAvEBXdbY")

        # Check and create trustlines if they don't exist
        self._ensure_trustlines()

    def _ensure_trustlines(self):
        """
        Check for trustlines between the issuer and the two accounts.
        Create trustlines if they don't exist.
        """
        usd_currency = {"currency": "USD", "issuer": self.usd_issuer_wallet.classic_address}

        # Check trustlines for account1
        account1_lines = self.client.request(AccountLines(account=self.account1.classic_address)).result.get("lines",
                                                                                                             [])
        has_trustline1 = any(line["currency"] == "USD" and line["account"] == self.usd_issuer_wallet.classic_address
                             for line in account1_lines)

        if not has_trustline1:
            trust_tx1 = TrustSet(
                account=self.account1.classic_address,
                limit_amount={"currency": "USD", "issuer": self.usd_issuer_wallet.classic_address, "value": "1000000"}
            )
            logger.info("signing and submitting the transaction, awaiting a response")
            submit_and_wait(trust_tx1, self.client, self.account1)

        # Check trustlines for account2
        account2_lines = self.client.request(AccountLines(account=self.account2.classic_address)).result.get("lines",
                                                                                                             [])
        has_trustline2 = any(line["currency"] == "USD" and line["account"] == self.usd_issuer_wallet.classic_address
                             for line in account2_lines)

        if not has_trustline2:
            trust_tx2 = TrustSet(
                account=self.account2.classic_address,
                limit_amount={"currency": "USD", "issuer": self.usd_issuer_wallet.classic_address, "value": "1000000"}
            )
            logger.info("signing and submitting the transaction, awaiting a response")
            submit_and_wait(trust_tx2, self.client, self.account2)

    def create_offer(self, account_seed, taker_gets_amount, taker_pays_amount, is_buy=True):
        """
        Create a book offer (buy or sell) on the XRPL TestNet.

        Args:
            account_seed (str): Seed of the account creating the offer.
            taker_gets_amount (float): Amount the taker gets (USD for buy, XRP for sell).
            taker_pays_amount (float): Amount the taker pays (XRP for buy, USD for sell).
            is_buy (bool): True for buy offer (USD for XRP), False for sell (XRP for USD).

        Returns:
            dict: Response containing the transaction result.
        """
        if account_seed == self.account1.seed:
            wallet = self.account1
        elif account_seed == self.account2.seed:
            wallet = self.account2
        else:
            return {"error": "Invalid account seed provided"}

        usd_currency = {
            "currency": "USD",
            "issuer": self.usd_issuer_wallet.classic_address,
            "value": str(taker_gets_amount if is_buy else taker_pays_amount)
        }
        xrp_amount = str(int(float(taker_pays_amount if is_buy else taker_gets_amount) * 1000000))

        offer_tx = BookOffers(
            account=wallet.classic_address,
            taker_gets=usd_currency if is_buy else xrp_amount,
            taker_pays=xrp_amount if is_buy else usd_currency,
            flags=0
        )

        try:
            logger.info("signing and submitting the transaction, awaiting a response")
            response = submit_and_wait(offer_tx, self.client, wallet)
            tx_hash = response.result["hash"]
            tx_response = self.client.request(Tx(transaction=tx_hash))
            tx_details = tx_response.result

            return {
                "status": "success",
                "tx_hash": tx_hash,
                "details": tx_details
            }
        except Exception as e:
            return {"status": "error", "message": str(e)}

    def post(self, request, *args, **kwargs):
        """
        Handle POST requests for creating book offers on XRPL TestNet.
        Expects JSON body with account_seed, taker_gets_amount, taker_pays_amount, and is_buy.
        """
        try:
            data = json.loads(request.body)
            required_fields = ["account_seed", "taker_gets_amount", "taker_pays_amount", "is_buy"]
            if not all(field in data for field in required_fields):
                return JsonResponse({"error": "Missing required fields"}, status=400)

            account_seed = data["account_seed"]
            taker_gets_amount = float(data["taker_gets_amount"])
            taker_pays_amount = float(data["taker_pays_amount"])
            is_buy = data["is_buy"]

            result = self.create_offer(account_seed, taker_gets_amount, taker_pays_amount, is_buy)
            return JsonResponse(result)

        except json.JSONDecodeError:
            return JsonResponse({"error": "Invalid JSON format"}, status=400)
        except ValueError as e:
            return JsonResponse({"error": f"Invalid data: {str(e)}"}, status=400)
        except Exception as e:
            return JsonResponse({"error": f"Server error: {str(e)}"}, status=500)

    def get(self, request, *args, **kwargs):
        """
        Handle GET requests (optional, returns a simple message or error).
        """
        return JsonResponse({"error": "Method not allowed, use POST"}, status=405)


@method_decorator(csrf_exempt, name="dispatch")
class CreateBookOffer(View):
    def __init__(self):
        super().__init__()
        self.client = None  # Lazy-loaded client

    # async def post(self, request, *args, **kwargs):
    #     return await self.create_book_offers(request)

    # async def get(self, request, *args, **kwargs):
    #     return await self.create_book_offers(request)

    async def post(self, request, *args, **kwargs):
        return await self.create_book_offers_easy(request)

    async def get(self, request, *args, **kwargs):
        return await self.create_book_offers_easy(request)

    # async def create_book_offers(self, request):
    #     start_time = time.time()  # Capture the start time
    #     function_name = 'create_book_offers'
    #     logger.info(ENTERING_FUNCTION_LOG.format(function_name))  # Log entering the function
    #
    #     if not self.client:
    #         self.client = get_xrpl_client()
    #     if not self.client:
    #         raise XRPLException(error_response(ERROR_INITIALIZING_CLIENT))
    #     try:
    #         # Extract the parameters from the request data.
    #         sender_seed = self.request.GET['sender_seed']
    #         account = self.request.GET['account']
    #         currency = self.request.GET['currency']
    #         value = self.request.GET['value']
    #
    #         # If any of the required parameters are missing, raise an error.
    #         if not all([account, currency, value, sender_seed]):
    #             raise ValueError(error_response(MISSING_REQUEST_PARAMETERS))
    #
    #         logger.info(f"Received parameters: account: {account}, currency: {currency}, value: {value}")
    #
    #         if not await does_account_exist(account, self.client):
    #             raise XRPLException(error_response(ACCOUNT_DOES_NOT_EXIST_ON_THE_LEDGER.format(account)))
    #
    #         sender_wallet = Wallet.from_seed(sender_seed)
    #         sender_wallet_balance = await get_balance(sender_wallet.classic_address, self.client)
    #         logger.info(f"Sender wallet retrieved: {sender_wallet.classic_address} Sender Address Balance: {sender_wallet_balance}")
    #
    #         xrpl_config = apps.get_app_config('xrpl_api')
    #
    #         async with AsyncWebsocketClient(xrpl_config.XRPL_WEB_SOCKET_NETWORK_URL) as client:
    #             buyer_wants = buyer_create_issued_currency(account, currency, value)
    #             logger.info(f"Buyer wants: {buyer_wants}")
    #             buyer_spend = create_amount_the_buyer_wants_to_spend()
    #             logger.info(f"Buyer spends: {buyer_spend}")
    #
    #             proposed_quality = Decimal(buyer_spend["value"]) / Decimal(buyer_wants["value"])
    #             logger.info(f"Proposed quality: {proposed_quality}")
    #
    #             logger.info("Requesting orderbook information...")
    #             orderbook_info_response = await client.request(create_book_offer(account, buyer_wants, buyer_spend))
    #
    #             if validate_xrpl_response_data(orderbook_info_response):
    #                 process_transaction_error(orderbook_info_response)
    #
    #             logger.info(f"Orderbook:{orderbook_info_response.result}")
    #
    #             offers = orderbook_info_response.result.get("offers", [])
    #             logger.info(f"Offers: {offers}")
    #
    #             buyer_amount = Decimal(buyer_wants["value"])
    #             logger.info(f"Buyer amount: {buyer_amount}")
    #
    #             running_total = Decimal(0)
    #             if len(offers) == 0:
    #                 logger.info("No Offers in the matching book. Offer probably won't execute immediately.")
    #             else:
    #                 for o in offers:
    #                     if Decimal(o["quality"]) <= proposed_quality:
    #                         logger.info(
    #                             f"Matching Offer found, funded with {o.get('owner_funds')} {buyer_wants['currency']}")
    #                         running_total += Decimal(o.get("owner_funds", Decimal(0)))
    #                         if running_total >= buyer_amount:
    #                             logger.info("Full Offer will probably fill")
    #                             break
    #                     else:
    #                         # Offers are in ascending quality order, so no others after this will match either
    #                         logger.info("Remaining orders too expensive.")
    #                         break
    #
    #                 logger.info(f"Total matched: {min(running_total, buyer_amount)} {buyer_wants['currency']}")
    #                 if 0 < running_total < buyer_amount:
    #                     logger.info(
    #                         f"Remaining {buyer_amount - running_total} {buyer_wants['currency']} would probably be placed on top of the order book.")
    #
    #             if running_total == 0:
    #                 # If part of the Offer was expected to cross, then the rest would be placed
    #                 # at the top of the order book. If none did, then there might be other
    #                 # Offers going the same direction as ours already on the books with an
    #                 # equal or better rate. This code counts how much liquidity is likely to be
    #                 # above ours.
    #                 #
    #                 # Unlike above, this time we check for Offers going the same direction as
    #                 # ours, so TakerGets and TakerPays are reversed from the previous
    #                 # book_offers request.
    #
    #                 logger.info("Requesting second orderbook information...")
    #                 orderbook2_info_response = await client.request(
    #                     create_book_offer(account, buyer_wants, buyer_spend))
    #
    #                 if validate_xrpl_response_data(orderbook2_info_response):
    #                     process_transaction_error(orderbook2_info_response)
    #
    #                 logger.info(f"Orderbook2: {orderbook2_info_response.result}")
    #
    #                 # Since TakerGets/TakerPays are reversed, the quality is the inverse.
    #                 # You could also calculate this as 1 / proposed_quality.
    #                 offered_quality = Decimal(buyer_wants["value"]) / Decimal(buyer_spend["value"])
    #                 logger.info(f"offered_quality: {offered_quality}")
    #
    #                 tally_currency = buyer_spend["currency"]
    #                 logger.info(f"tally_currency: {tally_currency}")
    #
    #                 if isinstance(tally_currency, XRP):
    #                     tally_currency = f"drops of {tally_currency}"
    #                 logger.info(f"tally_currency after isinstance: {tally_currency}")
    #
    #                 offers2 = orderbook2_info_response.result.get("offers", [])
    #                 logger.info(f"offers2: {offers2}")
    #
    #                 running_total2 = Decimal(0)
    #                 if len(offers2) == 0:
    #                     logger.info("No similar Offers in the book. Ours would be the first.")
    #                 else:
    #                     for o in offers2:
    #                         if Decimal(o["quality"]) <= offered_quality:
    #                             logger.info(
    #                                 f"Existing offer found, funded with {o.get('owner_funds')} {tally_currency}")
    #                             running_total2 += Decimal(o.get("owner_funds", Decimal(0)))
    #                         else:
    #                             logger.info("Remaining orders are below where ours would be placed.")
    #                             break
    #
    #                     logger.info(f"Our Offer would be placed below at least {running_total2} {tally_currency}")
    #                     if 0 < running_total2 < buyer_amount:
    #                         logger.info(
    #                             f"Remaining {buyer_amount - running_total2} {tally_currency} will probably be placed on top of the order book.")
    #
    #             tx = create_offer(account, buyer_wants, buyer_spend)
    #             logger.info(f"Created offer: {tx}")
    #
    #             logger.info(f"before autofill_and_sign...")
    #             signed_tx = await autofill_and_sign(tx, client, sender_wallet)
    #
    #             # if validate_xrpl_response_data(signed_tx):
    #             #     process_transaction_error(signed_tx)
    #             logger.info(f"after autofill_and_sign...")
    #
    #             logger.info(f"before process_offer...")
    #             process_offer_result = await process_offer(signed_tx, client)
    #
    #             if validate_xrpl_response_data(process_offer_result):
    #                 process_transaction_error(process_offer_result)
    #             logger.info(f"after process_offer...")
    #
    #             logger.info(f"Transaction succeeded:")
    #             logger.info(f"{xrpl_config.XRPL_WEB_SOCKET_NETWORK_URL}{signed_tx.get_hash()}")
    #
    #             # Check metadata ------------------------------------------------------------
    #             balance_changes = get_balance_changes(process_offer_result.result["meta"])
    #             logger.info(f"Balance Changes:{balance_changes}")
    #
    #             # Helper to convert an XRPL amount to a string for display
    #             def amt_str(amt) -> str:
    #                 if isinstance(amt, str):
    #                     return f"{drops_to_xrp(amt)} XRP"
    #                 else:
    #                     return f"{amt['value']} {amt['currency']}.{amt['issuer']}"
    #
    #             offers_affected = 0
    #             for affected_node in process_offer_result.result["meta"]["AffectedNodes"]:
    #                 if "ModifiedNode" in affected_node:
    #                     if affected_node["ModifiedNode"]["LedgerEntryType"] == "Offer":
    #                         # Usually a ModifiedNode of type Offer indicates a previous Offer that
    #                         # was partially consumed by this one.
    #                         offers_affected += 1
    #                 elif "DeletedNode" in affected_node:
    #                     if affected_node["DeletedNode"]["LedgerEntryType"] == "Offer":
    #                         # The removed Offer may have been fully consumed, or it may have been
    #                         # found to be expired or unfunded.
    #                         offers_affected += 1
    #                 elif "CreatedNode" in affected_node:
    #                     if affected_node["CreatedNode"]["LedgerEntryType"] == "RippleState":
    #                         logger.info("Created a trust line.")
    #                     elif affected_node["CreatedNode"]["LedgerEntryType"] == "Offer":
    #                         offer = affected_node["CreatedNode"]["NewFields"]
    #                         logger.info(
    #                             f"Created an Offer owned by {offer['Account']} with TakerGets={amt_str(offer['TakerGets'])} and TakerPays={amt_str(offer['TakerPays'])}.")
    #
    #             logger.info(f"Modified or removed {offers_affected} matching Offer(s)")
    #
    #             # Check balances
    #             logger.info("Getting address balances as of validated ledger...")
    #             balances = await client.request(prepare_account_lines_for_offer(account))
    #
    #             if validate_xrpl_response_data(balances):
    #                 process_transaction_error(balances)
    #
    #             logger.info(f"Balance result: {balances.result}")
    #
    #             # Check Offers
    #             logger.info(f"Getting outstanding Offers from {account} as of validated ledger...")
    #             acct_offers = await client.request(prepare_account_offers(account))
    #
    #             if validate_xrpl_response_data(acct_offers):
    #                 process_transaction_error(acct_offers)
    #
    #             logger.info(f"Account Offers result: {acct_offers.result}")
    #
    #             # response_data = create_account_offers_response(orderbook_info_response, result, acct_offers)
    #             response_data = create_account_offers_response(orderbook_info_response, process_offer_result)
    #             logger.info(f"response_data: {response_data}")
    #
    #             return response_data
    #
    #     except XRPLReliableSubmissionException as e:
    #         # Handle error message
    #         return handle_error_new(e, status_code=500, function_name=function_name)
    #     except Exception as e:
    #         # Handle error message
    #         return handle_error_new(e, status_code=500, function_name=function_name)
    #     finally:
    #         logger.info(LEAVING_FUNCTION_LOG.format(function_name, total_execution_time_in_millis(start_time)))


    async def create_book_offers_easy(self, request):
        start_time = time.time()  # Capture the start time
        function_name = 'create_book_offers_easy'
        logger.info(ENTERING_FUNCTION_LOG.format(function_name))  # Log entering the function

        if not self.client:
            self.client = get_xrpl_client()
        if not self.client:
            raise XRPLException(error_response(ERROR_INITIALIZING_CLIENT))
        try:
            # Extract the parameters from the request data.
            buyer_seed = self.request.GET['buyer_seed']
            issuer_seed = self.request.GET['issuer_seed']
            seller_seed = self.request.GET['seller_seed']
            value = self.request.GET['value']

            # If any of the required parameters are missing, raise an error.
            if not all([buyer_seed, issuer_seed, value, seller_seed]):
                raise ValueError(error_response(MISSING_REQUEST_PARAMETERS))

            # logger.info(f"Received parameters: buyer_wallet: {buyer_wallet} issuer_wallet: {issuer_wallet}, seller_wallet: {seller_wallet}, value: {value}")

            # if not await does_account_exist(buyer_wallet, self.client):
            #     raise XRPLException(error_response(ACCOUNT_DOES_NOT_EXIST_ON_THE_LEDGER.format(buyer_wallet)))

            # if not await does_account_exist(issuer_wallet, self.client):
            #     raise XRPLException(error_response(ACCOUNT_DOES_NOT_EXIST_ON_THE_LEDGER.format(issuer_wallet)))

            # if not await does_account_exist(seller_wallet, self.client):
            #     raise XRPLException(error_response(ACCOUNT_DOES_NOT_EXIST_ON_THE_LEDGER.format(seller_wallet)))

            buyer_wallet = Wallet.from_seed(buyer_seed)
            buyer_wallet_balance = await get_balance(buyer_wallet.classic_address, self.client)
            logger.info(f"Buyer wallet retrieved: {buyer_wallet.classic_address} Buyer Address Balance: {buyer_wallet_balance}")

            issuer_wallet = Wallet.from_seed(issuer_seed)
            issuer_wallet_balance = await get_balance(issuer_wallet.classic_address, self.client)
            logger.info(f"Issuer wallet retrieved: {issuer_wallet.classic_address} Issuer Address Balance: {issuer_wallet_balance}")

            seller_wallet = Wallet.from_seed(issuer_seed)
            seller_wallet_balance = await get_balance(seller_wallet.classic_address, self.client)
            logger.info(f"Sender wallet retrieved: {seller_wallet.classic_address} Sender Address Balance: {seller_wallet_balance}")

            xrpl_config = apps.get_app_config('xrpl_api')

            async with AsyncWebsocketClient(xrpl_config.XRPL_WEB_SOCKET_NETWORK_URL) as client:
                # Create trust line from buyer to issuer
                response = await client.request(AccountInfo(account=buyer_wallet.classic_address))
                sequence = response.result["account_data"]["Sequence"]
                ledger_index = response.result["ledger_current_index"]

                trust_tx = TrustSet(
                    account=buyer_wallet.classic_address,
                    limit_amount=IssuedCurrencyAmount(
                        currency="USD",
                        issuer=issuer_wallet.classic_address,
                        value="1000"),
                )

                try:
                    logger.info("signing and submitting the transaction, awaiting a response")
                    await submit_and_wait(trust_tx, client, buyer_wallet)
                except XRPLException as e:
                    process_unexpected_error(e)

                # Create trust line from seller to issuer
                response = await client.request(AccountInfo(account=seller_wallet.classic_address))
                sequence = response.result["account_data"]["Sequence"]
                ledger_index = response.result["ledger_current_index"]
                trust_tx = TrustSet(
                    account=seller_wallet.classic_address,
                    limit_amount=IssuedCurrencyAmount(
                        currency="USD",
                        issuer=issuer_wallet.classic_address,
                        value="1000"),
                )

                try:
                    logger.info("signing and submitting the transaction, awaiting a response")
                    await submit_and_wait(trust_tx, client, seller_wallet)
                except XRPLException as e:
                    process_unexpected_error(e)

                # Issuer sends 100 USD to buyer (to fund the offer)
                response = await client.request(AccountInfo(account=buyer_wallet.classic_address))
                sequence = response.result["account_data"]["Sequence"]
                ledger_index = response.result["ledger_current_index"]
                usd_payment_tx = Payment(
                    account=issuer_wallet.classic_address,
                    destination=buyer_wallet.classic_address,
                    amount=IssuedCurrencyAmount(
                        currency="USD",
                        issuer=issuer_wallet.classic_address,
                        value="100"
                    ))

                try:
                    logger.info("signing and submitting the transaction, awaiting a response")
                    await submit_and_wait(usd_payment_tx, client, issuer_wallet)
                except XRPLException as e:
                    process_unexpected_error(e)

                # Issuer sends 100 USD to seller (optional, for testing reverse trades)
                response = await client.request(AccountInfo(account=seller_wallet.classic_address))
                sequence = response.result["account_data"]["Sequence"]
                ledger_index = response.result["ledger_current_index"]
                usd_payment_tx = Payment(
                    account=issuer_wallet.classic_address,
                    destination=issuer_wallet.classic_address,
                    amount=IssuedCurrencyAmount(
                        currency="USD",
                        issuer=issuer_wallet.classic_address,
                        value="100"
                    ))

                try:
                    logger.info("signing and submitting the transaction, awaiting a response")
                    await submit_and_wait(usd_payment_tx, client, issuer_wallet)
                except XRPLException as e:
                    process_unexpected_error(e)

                # Check trust lines and balances for buyer
                account_lines_info = AccountLines(account=buyer_wallet.classic_address, ledger_index="validated")
                response = await client.request(account_lines_info)
                if "lines" not in response.result:
                    raise XRPLException('Account lines not found')
                trust_lines = response.result.get('lines', [])
                print(f"\nBuyer trust lines: {trust_lines}")
                # print(f"Buyer XRP: {check_balance(buyer_wallet)}")

                # Check trust lines and balances for seller
                account_lines_info = AccountLines(account=issuer_wallet.classic_address, ledger_index="validated")
                response = await client.request(account_lines_info)
                if "lines" not in response.result:
                    raise XRPLException('Account lines not found')
                trust_lines = response.result.get('lines', [])
                print(f"Seller trust lines: {trust_lines}")
                # print(f"Seller XRP: {check_balance(seller_seed_wallet.classic_address)}")

                # Seller places an offer: 10 XRP for 5 USD
                offer_tx = OfferCreate(
                    account=seller_wallet.classic_address,
                    taker_gets="10000000",  # 10 XRP in drops
                    taker_pays=IssuedCurrencyAmount(currency="USD", issuer=issuer_wallet.classic_address, value="5")
                )

                try:
                    logger.info("signing and submitting the transaction, awaiting a response")
                    response = submit_and_wait(offer_tx, client, seller_wallet.classic_address)
                except XRPLException as e:
                    process_unexpected_error(e)

                sequence = response.result['tx_json']['Sequence']
                print(f"\nSeller offer created: {response.result['tx_json']}")

                # Check seller's active offers
                request = AccountOffers(account=seller_wallet.classic_address)
                response = await client.request(request)
                print(f"Seller active offers: {response.result['offers']}")

                # Buyer places a matching offer: 5 USD for 10 XRP
                matching_offer_tx = OfferCreate(
                    account=buyer_wallet.classic_address,
                    taker_gets="10000000",  # 10 XRP in drops
                    taker_pays=IssuedCurrencyAmount(currency="USD", issuer=issuer_wallet.classic_address, value="5")
                )

                try:
                    logger.info("signing and submitting the transaction, awaiting a response")
                    response = submit_and_wait(matching_offer_tx, client, buyer_wallet.classic_address)
                except XRPLException as e:
                    process_unexpected_error(e)

                print(f"\nBuyer matching offer created: {response.result['tx_json']}")

                # Check buyer's active offers
                request = AccountOffers(account=buyer_wallet.classic_address)
                response = await client.request(request)
                print(f"Buyer active offers: {response.result['offers']}")

                # Check XRP/USD order book
                request = BookOffers(
                    taker_gets=XRP(),
                    taker_pays=IssuedCurrencyAmount(currency="USD", issuer=issuer_wallet.classic_address, value="0")
                )
                response = await client.request(request)
                print(f"\nOrder book issuer: {response.result['offers']}")

                # Check XRP/USD order book
                request = BookOffers(
                    taker_gets=XRP(),
                    taker_pays=IssuedCurrencyAmount(currency="USD", issuer=buyer_wallet.classic_address, value="0")
                )
                response = await client.request(request)
                print(f"Order book buyer_wallet: {response.result['offers']}")

                request = BookOffers(
                    taker_gets=XRP(),
                    taker_pays=IssuedCurrencyAmount(currency="USD", issuer=seller_wallet.classic_address, value="0")
                )
                response = await client.request(request)
                print(f"Order book seller_wallet: {response.result['offers']}")

                return JsonResponse({'r':'t'})

        except XRPLReliableSubmissionException as e:
            # Handle error message
            return handle_error_new(e, status_code=500, function_name=function_name)
        except Exception as e:
            # Handle error message
            return handle_error_new(e, status_code=500, function_name=function_name)
        finally:
            logger.info(LEAVING_FUNCTION_LOG.format(function_name, total_execution_time_in_millis(start_time)))


@method_decorator(csrf_exempt, name="dispatch")
class GetBookOffers(View):
    def __init__(self):
        super().__init__()
        self.client = None  # Lazy-loaded client

    def post(self, request, *args, **kwargs):
        return self.get_book_offers(request)

    def get(self, request, *args, **kwargs):
        return self.get_book_offers(request)

    def get_book_offers(self, request):
        start_time = time.time()
        function_name = 'get_book_offers'
        logger.info(ENTERING_FUNCTION_LOG.format(function_name))

        try:
            if not self.client:
                self.client = get_xrpl_client()
            if not self.client:
                raise XRPLException(error_response(ERROR_INITIALIZING_CLIENT))

            # Extract parameters from GET or POST
            taker_gets_currency = request.GET.get('taker_gets_currency', 'XRP')  # Default to XRP
            taker_gets_issuer = request.GET.get('taker_gets_issuer')  # Optional issuer for non-XRP
            taker_pays_currency = request.GET.get('taker_pays_currency')
            taker_pays_issuer = request.GET.get('taker_pays_issuer')
            taker = request.GET.get('taker')  # Optional account for fee perspective

            # Validate required parameters
            if not taker_pays_currency:
                raise XRPLException(error_response("Missing taker_pays_currency in request"))

            if not taker_pays_issuer and not validate_xrp_wallet(taker_pays_issuer):
                raise XRPLRequestFailureException(error_response(INVALID_WALLET_IN_REQUEST))

            if not does_account_exist(taker_pays_issuer, self.client):
                raise XRPLException(error_response(ACCOUNT_DOES_NOT_EXIST_ON_THE_LEDGER.format(taker_pays_issuer)))

            # Define taker_gets and taker_pays
            if taker_gets_currency == "XRP":
                taker_gets = {"currency": "XRP"}
            else:
                if not taker_gets_issuer:
                    raise XRPLException(error_response("taker_gets_issuer required for non-XRP currency"))
                taker_gets = prepare_book_offers(taker_gets_currency, taker_gets_issuer)

            if taker_pays_currency == "XRP":
                taker_pays = {"currency": "XRP"}
            else:
                if not taker_pays_issuer:
                    raise XRPLException(error_response("taker_pays_issuer required for non-XRP currency"))
                taker_pays = prepare_book_offers(taker_pays_currency, taker_pays_issuer)

            if len(taker_gets_currency) != 3 and taker_gets_currency != "XRP":
                raise XRPLException("Invalid taker_gets_currency")

            # Fetch BookOffers with pagination
            book_offers = []
            marker = None
            while True:
                book_offers_info = prepare_book_offers_paginated(taker_gets, taker_pays, taker, marker)
                book_offers_response = self.client.request(book_offers_info)
                if validate_xrpl_response_data(book_offers_response):
                    process_transaction_error(book_offers_response)

                offers = book_offers_response.result.get('offers', [])
                if offers:
                    logger.info(f"Found {len(offers)} offers for pair {taker_gets_currency}/{taker_pays_currency}.")
                else:
                    logger.info(f"No offers found for pair {taker_gets_currency}/{taker_pays_currency} in this batch.")

                book_offers.extend(offers)
                marker = book_offers_response.result.get('marker')
                if not marker:
                    break

            # Extract pagination parameters from the request
            page = self.request.GET.get('page', 1)
            page = int(page) if page else 1

            page_size = self.request.GET.get('page_size', 10)
            page_size = int(page_size) if page_size else 1

            paginator = Paginator(book_offers, page_size)
            paginated_offers = paginator.get_page(page)

            return create_book_offers_response(paginated_offers, paginator, taker_gets_currency, taker_pays_currency)

        except (XRPLRequestFailureException, XRPLException, XRPLAddressCodecException, ValueError) as e:
            logger.error(f"XRPL error: {str(e)}")
            return handle_error_new(e, status_code=500, function_name=function_name)
        except Exception as e:
            logger.error(f"Unexpected error: {str(e)}")
            return handle_error_new(e, status_code=500, function_name=function_name)
        finally:
            logger.info(LEAVING_FUNCTION_LOG.format(function_name, total_execution_time_in_millis(start_time)))