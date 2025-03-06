import logging
import time

from django.http import JsonResponse
from django.utils.decorators import method_decorator
from django.views import View
from django.views.decorators.csrf import csrf_exempt
from xrpl import XRPLException
from xrpl.asyncio.clients import XRPLRequestFailureException
from xrpl.asyncio.wallet import XRPLFaucetException
from xrpl.wallet import generate_faucet_wallet, Wallet
from xrpl.models.requests import AccountLines, Tx
from xrpl.transaction import submit_and_wait
import json

from ..constants.constants import ERROR_INITIALIZING_CLIENT, MISSING_REQUEST_PARAMETERS, LEAVING_FUNCTION_LOG, \
    ENTERING_FUNCTION_LOG
from ..currency.currency_util import create_issued_currency_amount
from ..errors.error_handling import error_response, handle_error_new
from ..offers.book_offers.book_offers_util import prepare_offer_create, create_offers_response, prepare_offer_cancel
from ..payments.payments_util import create_offer_sell_payment_transaction
from ..trust_lines.trust_line_util import create_trust_set_sell_transaction
from ..utilities.utilities import get_xrpl_client, total_execution_time_in_millis

logger = logging.getLogger('xrpl_app')

@method_decorator(csrf_exempt, name="dispatch")
class CreateSellBookOffersGrok(View):
    def __init__(self):
        super().__init__()
        self.client = None  # Lazy-loaded client
        self.account1 = Wallet.from_seed("sEdVg7gRSeQ7D6jMTwWCENsJK742qxT")
        self.account2 = Wallet.from_seed("sEdS5zxsgGbbtMKWkkBt3kdAvEBXdbY")
        self.usd_issuer_wallet = None  # Lazy-loaded issuer wallet

    def post(self, request, *args, **kwargs):
        return self.create_offer_view(request)

    def get(self, request, *args, **kwargs):
        return self.create_offer_view(request)

    def create_offer_view(self, request):
        # Capture the start time
        start_time = time.time()
        function_name = 'create_offer_view'
        # Log entering the function
        logger.info(ENTERING_FUNCTION_LOG.format(function_name))

        try:
            if not self.client:
                self.client = get_xrpl_client()
            if not self.client:
                raise XRPLException(error_response(ERROR_INITIALIZING_CLIENT))
            if not self.usd_issuer_wallet:
                self.usd_issuer_wallet = generate_faucet_wallet(self.client)

            data = json.loads(request.body)
            required_fields = ["account_seed", "taker_gets_amount", "taker_pays_amount", "is_buy"]
            if not all(field in data for field in required_fields):
                return ValueError(error_response(MISSING_REQUEST_PARAMETERS))

            account_seed = data["account_seed"]
            taker_gets_amount = float(data["taker_gets_amount"])
            taker_pays_amount = float(data["taker_pays_amount"])
            is_buy = data["is_buy"]

            logger.info(f"Taker gets: {taker_gets_amount} Taker pays: {taker_pays_amount}")

            # Check trustlines and fund accounts
            usd_currency = create_issued_currency_amount(self.usd_issuer_wallet.classic_address, "USD", "100")
            #usd_currency = IssuedCurrencyAmount(currency="USD", issuer=self.usd_issuer_wallet.classic_address, value="100")

            # Check and set trustline for account1, then fund it
            account1_lines = self.client.request(AccountLines(account=self.account1.classic_address)).result.get("lines", [])
            has_trustline1 = any(line["currency"] == "USD" and line["account"] == self.usd_issuer_wallet.classic_address for line in account1_lines)

            if not has_trustline1:
                trust_tx1 = create_trust_set_sell_transaction(self.account1.classic_address, "USD", self.usd_issuer_wallet.classic_address, "1000000")
                logger.info("signing and submitting the transaction, awaiting a response")
                submit_and_wait(trust_tx1, self.client, self.account1)

                # Fund account1 with 100 USD from the issuer
                payment_tx1 = create_offer_sell_payment_transaction(self.usd_issuer_wallet.classic_address,self.account1.classic_address, usd_currency)
                logger.info("signing and submitting the transaction, awaiting a response")
                submit_and_wait(payment_tx1, self.client, self.usd_issuer_wallet)

            # Check and set trustline for account2, then fund it
            account2_lines = self.client.request(AccountLines(account=self.account2.classic_address)).result.get("lines", [])
            has_trustline2 = any(line["currency"] == "USD" and line["account"] == self.usd_issuer_wallet.classic_address for line in account2_lines)

            if not has_trustline2:
                trust_tx2 = create_trust_set_sell_transaction(self.account2.classic_address, "USD", self.usd_issuer_wallet.classic_address, "1000000")
                logger.info("signing and submitting the transaction, awaiting a response")
                submit_and_wait(trust_tx2, self.client, self.account2)

                # Fund account2 with 100 USD from the issuer
                payment_tx2 = create_offer_sell_payment_transaction(self.usd_issuer_wallet.classic_address,self.account2.classic_address, usd_currency)
                logger.info("signing and submitting the transaction, awaiting a response")
                submit_and_wait(payment_tx2, self.client, self.usd_issuer_wallet)

            if account_seed == self.account1.seed:
                wallet = self.account1
            elif account_seed == self.account2.seed:
                wallet = self.account2
            else:
                return JsonResponse({"error": "Invalid account seed provided"}, status=400)

            usd_currency = create_issued_currency_amount(self.usd_issuer_wallet.classic_address, "USD", taker_gets_amount if is_buy else taker_pays_amount)
            # usd_currency = IssuedCurrencyAmount(currency="USD", issuer=self.usd_issuer_wallet.classic_address, value=str(taker_gets_amount if is_buy else taker_pays_amount))
            xrp_amount = str(int(float(taker_pays_amount if is_buy else taker_gets_amount) * 1000000))

            offer_tx =prepare_offer_create(wallet.classic_address,usd_currency if is_buy else xrp_amount,xrp_amount if is_buy else usd_currency, 0)
            logger.info("signing and submitting the transaction, awaiting a response")
            response = submit_and_wait(offer_tx, self.client, wallet)

            tx_hash = response.result["hash"]
            tx_response = self.client.request(Tx(transaction=tx_hash))
            tx_details = tx_response.result

            return create_offers_response(tx_details)

        except (XRPLFaucetException, XRPLRequestFailureException, XRPLException) as e:
            # Handle error message
            return handle_error_new(e, status_code=500, function_name=function_name)
        except Exception as e:
            # Handle error message
            return handle_error_new(e, status_code=500, function_name=function_name)
        finally:
            logger.info(LEAVING_FUNCTION_LOG.format(function_name, total_execution_time_in_millis(start_time)))


@method_decorator(csrf_exempt, name="dispatch")
class BuyBookOffersGrok(View):
    def __init__(self):
        super().__init__()
        self.client = None  # Lazy-loaded client
        self.account1 = Wallet.from_seed("sEdVg7gRSeQ7D6jMTwWCENsJK742qxT")
        self.account2 = Wallet.from_seed("sEdS5zxsgGbbtMKWkkBt3kdAvEBXdbY")
        self.usd_issuer_wallet = None  # Lazy-loaded issuer wallet

    def post(self, request, *args, **kwargs):
        return self.buy_offer_view(request)

    def get(self, request, *args, **kwargs):
        return self.buy_offer_view(request)

    def buy_offer_view(self, request):
        # Capture the start time
        start_time = time.time()
        function_name = 'buy_offer_view'
        # Log entering the function
        logger.info(ENTERING_FUNCTION_LOG.format(function_name))

        try:
            if not self.client:
                self.client = get_xrpl_client()
            if not self.client:
                raise XRPLException(error_response(ERROR_INITIALIZING_CLIENT))
            if not self.usd_issuer_wallet:
                self.usd_issuer_wallet = generate_faucet_wallet(self.client)

            data = json.loads(request.body)
            required_fields = ["account_seed", "tx_hash"]
            if not all(field in data for field in required_fields):
                return ValueError(error_response(MISSING_REQUEST_PARAMETERS))

            account_seed = data["account_seed"]
            tx_hash = data["tx_hash"]

            # Check trustlines and fund accounts
            usd_currency_fund = create_issued_currency_amount(self.usd_issuer_wallet.classic_address, "USD", "100")
            # usd_currency_fund = IssuedCurrencyAmount(currency="USD", issuer=self.usd_issuer_wallet.classic_address, value="100")

            logger.info(f"Tx hash: {tx_hash}")

            # Check and set trustline for account1, then fund it
            account1_lines = self.client.request(AccountLines(account=self.account1.classic_address)).result.get("lines", [])
            has_trustline1 = any(line["currency"] == "USD" and line["account"] == self.usd_issuer_wallet.classic_address for line in account1_lines)

            if not has_trustline1:
                trust_tx1 = create_trust_set_sell_transaction(self.account1.classic_address, "USD", self.usd_issuer_wallet.classic_address, "1000000")
                logger.info("signing and submitting the transaction, awaiting a response")
                submit_and_wait(trust_tx1, self.client, self.account1)

                payment_tx1 = create_offer_sell_payment_transaction(self.usd_issuer_wallet.classic_address,self.account1.classic_address, usd_currency_fund)
                logger.info("signing and submitting the transaction, awaiting a response")
                submit_and_wait(payment_tx1, self.client, self.usd_issuer_wallet)

            # Check and set trustline for account2, then fund it
            account2_lines = self.client.request(AccountLines(account=self.account2.classic_address)).result.get(
                "lines", []
            )
            has_trustline2 = any(line["currency"] == "USD" and line["account"] == self.usd_issuer_wallet.classic_address
                                 for line in account2_lines)

            if not has_trustline2:
                trust_tx2 = create_trust_set_sell_transaction(self.account2.classic_address, "USD", self.usd_issuer_wallet.classic_address, "1000000")
                logger.info("signing and submitting the transaction, awaiting a response")
                submit_and_wait(trust_tx2, self.client, self.account2)

                payment_tx2 = create_offer_sell_payment_transaction(self.usd_issuer_wallet.classic_address,self.account2.classic_address, usd_currency_fund)
                logger.info("signing and submitting the transaction, awaiting a response")
                submit_and_wait(payment_tx2, self.client, self.usd_issuer_wallet)

            # Determine which account is buying and which created the offer
            if account_seed == self.account1.seed:
                buying_wallet = self.account1
                offering_account = self.account2  # Assume the other account created the offer
            elif account_seed == self.account2.seed:
                buying_wallet = self.account2
                offering_account = self.account1
            else:
                return ValueError(error_response("Invalid account seed provided"))

            # Get the original offer details from the tx_hash
            tx_response = self.client.request(Tx(transaction=tx_hash))
            if not tx_response.is_successful():
                return XRPLException(error_response(f"Failed to fetch transaction: {tx_response.result.get('error', 'Unknown error')}"))

            tx_details = tx_response.result
            if "TransactionType" not in tx_details['tx_json'] or tx_details['tx_json']["TransactionType"] != "OfferCreate":
                return XRPLException(error_response(f"Provided tx_hash is not a valid OfferCreate transaction or not found"))

            # Check if the transaction is validated
            if not tx_details.get("validated", False):
                return XRPLException(error_response(f"Transaction is not yet validated on the ledger"))

            original_taker_gets = tx_details['tx_json']["TakerGets"]
            original_taker_pays = tx_details['tx_json']["TakerPays"]

            # Reverse the original offer for buying
            if isinstance(original_taker_gets, dict) and original_taker_gets["currency"] == "USD":
                # Original offer sells USD for XRP, so we buy USD with XRP
                taker_gets = original_taker_gets  # USD
                taker_pays = original_taker_pays  # XRP
            else:
                # Original offer sells XRP for USD, so we buy XRP with USD
                taker_gets = original_taker_pays  # USD
                taker_pays = original_taker_gets  # XRP

            # Create the buying offer
            buy_offer_tx =prepare_offer_create(buying_wallet.classic_address,taker_gets,taker_pays, 0)

            logger.info("signing and submitting the transaction, awaiting a response")
            response = submit_and_wait(buy_offer_tx, self.client, buying_wallet)
            tx_hash = response.result["hash"]
            tx_response = self.client.request(Tx(transaction=tx_hash))
            tx_details = tx_response.result

            return create_offers_response(tx_details)

        except (XRPLFaucetException, XRPLRequestFailureException, XRPLException) as e:
            return handle_error_new(e, status_code=500, function_name=function_name)
        except Exception as e:
            # Handle error message
            return handle_error_new(e, status_code=500, function_name=function_name)
        finally:
            logger.info(LEAVING_FUNCTION_LOG.format(function_name, total_execution_time_in_millis(start_time)))


@method_decorator(csrf_exempt, name="dispatch")
class CancelBookOffersGrok(View):
    def __init__(self):
        super().__init__()
        self.client = None  # Lazy-loaded client
        self.account1 = Wallet.from_seed("sEdVg7gRSeQ7D6jMTwWCENsJK742qxT")
        self.account2 = Wallet.from_seed("sEdS5zxsgGbbtMKWkkBt3kdAvEBXdbY")
        self.usd_issuer_wallet = None  # Lazy-loaded issuer wallet

    def post(self, request, *args, **kwargs):
        return self.cancel_offer_view(request)

    def get(self, request, *args, **kwargs):
        return self.cancel_offer_view(request)

    def cancel_offer_view(self, request):
        # Capture the start time
        start_time = time.time()
        function_name = 'cancel_offer_view'
        # Log entering the function
        logger.info(ENTERING_FUNCTION_LOG.format(function_name))

        try:
            if not self.client:
                self.client = get_xrpl_client()
            if not self.client:
                raise XRPLException(error_response(ERROR_INITIALIZING_CLIENT))
            if not self.usd_issuer_wallet:
                self.usd_issuer_wallet = generate_faucet_wallet(self.client)

            data = json.loads(request.body)
            required_fields = ["account_seed", "tx_hash"]
            if not all(field in data for field in required_fields):
                return ValueError(error_response(MISSING_REQUEST_PARAMETERS))

            account_seed = data["account_seed"]
            tx_hash = data["tx_hash"]

            logger.info(f"Tx hash: {tx_hash}")

            # Check trustlines and fund accounts (for consistency with previous classes)
            usd_currency_fund = create_issued_currency_amount(self.usd_issuer_wallet.classic_address, "USD", "100")
            #usd_currency_fund = IssuedCurrencyAmount(currency="USD", issuer=self.usd_issuer_wallet.classic_address, value="100")

            # Check and set trustline for account1, then fund it
            account1_lines = self.client.request(AccountLines(account=self.account1.classic_address)).result.get("lines", [])
            has_trustline1 = any(line["currency"] == "USD" and line["account"] == self.usd_issuer_wallet.classic_address for line in account1_lines)

            if not has_trustline1:
                trust_tx1 = create_trust_set_sell_transaction(self.account1.classic_address, "USD", self.usd_issuer_wallet.classic_address, "1000000")
                logger.info("signing and submitting the transaction, awaiting a response")
                submit_and_wait(trust_tx1, self.client, self.account1)

                payment_tx1 = create_offer_sell_payment_transaction(self.usd_issuer_wallet.classic_address,self.account1.classic_address, usd_currency_fund)
                logger.info("signing and submitting the transaction, awaiting a response")
                submit_and_wait(payment_tx1, self.client, self.usd_issuer_wallet)

            # Check and set trustline for account2, then fund it
            account2_lines = self.client.request(AccountLines(account=self.account2.classic_address)).result.get("lines", [])
            has_trustline2 = any(line["currency"] == "USD" and line["account"] == self.usd_issuer_wallet.classic_address for line in account2_lines)

            if not has_trustline2:
                trust_tx2 = create_trust_set_sell_transaction(self.account2.classic_address, "USD", self.usd_issuer_wallet.classic_address, "1000000")
                logger.info("signing and submitting the transaction, awaiting a response")
                submit_and_wait(trust_tx2, self.client, self.account2)

                payment_tx2 = create_offer_sell_payment_transaction(self.usd_issuer_wallet.classic_address,self.account2.classic_address, usd_currency_fund)
                logger.info("signing and submitting the transaction, awaiting a response")
                submit_and_wait(payment_tx2, self.client, self.usd_issuer_wallet)

            # Determine which account is canceling the offer
            if account_seed == self.account1.seed:
                wallet = self.account1
            elif account_seed == self.account2.seed:
                wallet = self.account2
            else:
                return ValueError(error_response("Invalid account seed provided"))

            # Get the original offer details from the tx_hash
            tx_response = self.client.request(Tx(transaction=tx_hash))
            if not tx_response.is_successful():
                return JsonResponse(
                    {"error": f"Failed to fetch transaction: {tx_response.result.get('error', 'Unknown error')}"},
                    status=400)

            tx_details = tx_response.result
            if "TransactionType" not in tx_details['tx_json'] or tx_details['tx_json'][
                "TransactionType"] != "OfferCreate":
                return XRPLException(error_response(f"Provided tx_hash is not a valid OfferCreate transaction or not found"))

            if not tx_details.get("validated", False):
                return XRPLException(error_response(f"Transaction is not yet validated on the ledger"))

            # Extract the offer sequence number
            offer_sequence = tx_details['tx_json']["Sequence"]

            # Create the OfferCancel transaction
            cancel_offer_tx =prepare_offer_cancel(wallet.classic_address, offer_sequence)

            # Submit the cancellation
            logger.info("signing and submitting the transaction, awaiting a response")
            response = submit_and_wait(cancel_offer_tx, self.client, wallet)
            tx_hash = response.result["hash"]
            tx_response = self.client.request(Tx(transaction=tx_hash))
            tx_details = tx_response.result

            return create_offers_response(tx_details)

        except (XRPLFaucetException, XRPLRequestFailureException, XRPLException) as e:
            return handle_error_new(e, status_code=500, function_name=function_name)
        except Exception as e:
            # Handle error message
            return handle_error_new(e, status_code=500, function_name=function_name)
        finally:
            logger.info(LEAVING_FUNCTION_LOG.format(function_name, total_execution_time_in_millis(start_time)))
