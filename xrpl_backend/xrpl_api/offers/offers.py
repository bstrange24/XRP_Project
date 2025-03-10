import json
import logging
import time

from django.utils.decorators import method_decorator
from django.views.decorators.csrf import csrf_exempt
from xrpl import XRPLException
from xrpl.asyncio.clients import XRPLRequestFailureException
from xrpl.core.addresscodec import XRPLAddressCodecException
from xrpl.models import AccountLines, OfferCreate, OfferCancel
from xrpl.models.amounts import IssuedCurrencyAmount
from xrpl.transaction import submit_and_wait
from xrpl.wallet import Wallet

from .offers_util import check_balance, check_and_create_trustline, get_offer_status, create_account_status_response, \
    create_cancel_account_status_response, create_taker_account_response, create_buyer_account_response, \
    create_seller_account_response
from ..constants.constants import MISSING_REQUEST_PARAMETERS, LEAVING_FUNCTION_LOG, ENTERING_FUNCTION_LOG
from ..errors.error_handling import error_response, handle_error_new
from ..utilities.base_xrpl_view import BaseXRPLView
from ..utilities.utilities import total_execution_time_in_millis

logger = logging.getLogger('xrpl_app')


@method_decorator(csrf_exempt, name="dispatch")
class SellAccountOffers(BaseXRPLView):
    def post(self, request):
        return self.sell_account_offers(request)

    def get(self, request):
        return self.sell_account_offers(request)

    def sell_account_offers(self, request):
        start_time = time.time()
        function_name = 'sell_account_offers'
        logger.info(ENTERING_FUNCTION_LOG.format(function_name))

        try:
            self._initialize_client()
            data = json.loads(request.body)
            seller_seed = data.get("seller_seed")
            issuer_address = data.get("issuer_address")
            xrp_amount = data.get("xrp_amount")
            usd_amount = data.get("usd_amount")

            if not all([seller_seed, issuer_address, xrp_amount, usd_amount]):
                raise ValueError(error_response(MISSING_REQUEST_PARAMETERS))

            seller_wallet = Wallet.from_seed(seller_seed)

            # Check and create trust line
            trustline_created = check_and_create_trustline(self, seller_wallet, issuer_address)

            # Check balances before offer
            balances_before = check_balance(self, seller_wallet)

            # Create sell offer
            sell_offer = OfferCreate(
                account=seller_wallet.classic_address,
                taker_gets=str(int(xrp_amount * 1000000)),  # Convert to drops
                taker_pays=IssuedCurrencyAmount(currency="USD", issuer=issuer_address, value=str(usd_amount))
            )
            response = submit_and_wait(sell_offer, self.client, seller_wallet)
            result = response.result

            # Check balances after offer
            balances_after = check_balance(self, seller_wallet)

            return create_seller_account_response(result, trustline_created, balances_before, balances_after)

        except (XRPLRequestFailureException, XRPLException, XRPLAddressCodecException, ValueError) as e:
            # Handle error message
            return handle_error_new(e, status_code=500, function_name=function_name)
        except Exception as e:
            # Handle error message
            return handle_error_new(e, status_code=500, function_name=function_name)
        finally:
            logger.info(LEAVING_FUNCTION_LOG.format(function_name, total_execution_time_in_millis(start_time)))


@method_decorator(csrf_exempt, name="dispatch")
class BuyAccountOffers(BaseXRPLView):
    def post(self, request):
        return self.buy_account_offers(request)

    def get(self, request):
        return self.buy_account_offers(request)

    def buy_account_offers(self, request):
        start_time = time.time()
        function_name = 'buy_account_offers'
        logger.info(ENTERING_FUNCTION_LOG.format(function_name))

        try:
            self._initialize_client()
            data = json.loads(request.body)
            buyer_seed = data.get("buyer_seed")
            issuer_address = data.get("issuer_address")
            xrp_amount = data.get("xrp_amount")
            usd_amount = data.get("usd_amount")

            if not all([buyer_seed, issuer_address, xrp_amount, usd_amount]):
                return self._send_response(False, error="Missing required fields")

            buyer_wallet = Wallet.from_seed(buyer_seed)

            # Check and create trust line
            trustline_created = check_and_create_trustline(self, buyer_wallet, issuer_address)

            # Check balances before offer
            balances_before = check_balance(self, buyer_wallet)

            # Create buy offer
            buy_offer = OfferCreate(
                account=buyer_wallet.classic_address,
                taker_gets=IssuedCurrencyAmount(currency="USD", issuer=issuer_address, value=str(usd_amount)),
                taker_pays=str(int(xrp_amount * 1000000))  # Convert to drops
            )
            response = submit_and_wait(buy_offer, self.client, buyer_wallet)
            result = response.result

            # Check balances after offer
            balances_after = check_balance(self, buyer_wallet)

            return create_buyer_account_response(result, trustline_created, balances_before, balances_after)

        except (XRPLRequestFailureException, XRPLException, XRPLAddressCodecException, ValueError) as e:
            # Handle error message
            return handle_error_new(e, status_code=500, function_name=function_name)
        except Exception as e:
            # Handle error message
            return handle_error_new(e, status_code=500, function_name=function_name)
        finally:
            logger.info(LEAVING_FUNCTION_LOG.format(function_name, total_execution_time_in_millis(start_time)))


@method_decorator(csrf_exempt, name="dispatch")
class TakerAccountOffers(BaseXRPLView):
    def post(self, request):
        return self.taker_account_offers(request)

    def get(self, request):
        return self.taker_account_offers(request)

    def taker_account_offers(self, request):
        start_time = time.time()
        function_name = 'taker_account_offers'
        logger.info(ENTERING_FUNCTION_LOG.format(function_name))

        try:
            self._initialize_client()
            data = json.loads(request.body)
            taker_seed = data.get("taker_seed")
            issuer_address = data.get("issuer_address")
            xrp_amount = data.get("xrp_amount")
            usd_amount = data.get("usd_amount")
            direction = data.get("direction")  # "buy" or "sell"

            if not all([taker_seed, issuer_address, xrp_amount, usd_amount, direction]):
                return self._send_response(False, error="Missing required fields")

            taker_wallet = Wallet.from_seed(taker_seed)

            # Check and create trust line
            trustline_created = check_and_create_trustline(self, taker_wallet, issuer_address)

            # Check balances before offer
            balances_before = check_balance(self, taker_wallet)

            # Create taker offer based on direction
            if direction == "buy":
                taker_offer = OfferCreate(
                    account=taker_wallet.classic_address,
                    taker_gets=IssuedCurrencyAmount(currency="USD", issuer=issuer_address, value=str(usd_amount)),
                    taker_pays=str(int(xrp_amount * 1000000))  # Convert to drops
                )
            elif direction == "sell":
                taker_offer = OfferCreate(
                    account=taker_wallet.classic_address,
                    taker_gets=str(int(xrp_amount * 1000000)),  # Convert to drops
                    taker_pays=IssuedCurrencyAmount(currency="USD", issuer=issuer_address, value=str(usd_amount))
                )
            else:
                return self._send_response(False, error="Invalid direction: must be 'buy' or 'sell'")

            response = submit_and_wait(taker_offer, self.client, taker_wallet)
            result = response.result

            # Check balances after offer
            balances_after = check_balance(self, taker_wallet)

            return create_taker_account_response(result, trustline_created, balances_before, balances_after)

        except (XRPLRequestFailureException, XRPLException, XRPLAddressCodecException, ValueError) as e:
            # Handle error message
            return handle_error_new(e, status_code=500, function_name=function_name)
        except Exception as e:
            # Handle error message
            return handle_error_new(e, status_code=500, function_name=function_name)
        finally:
            logger.info(LEAVING_FUNCTION_LOG.format(function_name, total_execution_time_in_millis(start_time)))


@method_decorator(csrf_exempt, name="dispatch")
class CancelAccountOffers(BaseXRPLView):
    def post(self, request):
        return self.cancel_account_offers(request)

    def get(self, request):
        return self.cancel_account_offers(request)

    def cancel_account_offers(self, request):
        start_time = time.time()
        function_name = 'cancel_account_offers'
        logger.info(ENTERING_FUNCTION_LOG.format(function_name))

        try:
            self._initialize_client()
            data = json.loads(request.body)
            wallet_seed = data.get("wallet_seed")
            sequence = data.get("sequence")

            if not all([wallet_seed, sequence]):
                return self._send_response(False, error="Missing required fields")

            wallet = Wallet.from_seed(wallet_seed)

            # Check balances before cancellation
            balances_before = check_balance(self, wallet)

            # Cancel offer
            cancel_offer = OfferCancel(
                account=wallet.classic_address,
                offer_sequence=int(sequence)
            )
            response = submit_and_wait(cancel_offer, self.client, wallet)
            result = response.result

            # Check balances after cancellation
            balances_after = check_balance(self, wallet)

            return create_cancel_account_status_response(result, balances_before, balances_after)

        except (XRPLRequestFailureException, XRPLException, XRPLAddressCodecException, ValueError) as e:
            # Handle error message
            return handle_error_new(e, status_code=500, function_name=function_name)
        except Exception as e:
            # Handle error message
            return handle_error_new(e, status_code=500, function_name=function_name)
        finally:
            logger.info(LEAVING_FUNCTION_LOG.format(function_name, total_execution_time_in_millis(start_time)))


@method_decorator(csrf_exempt, name="dispatch")
class AccountStatus(BaseXRPLView):
    def post(self, request):
        return self.get_account_status(request)

    def get(self, request):
        return self.get_account_status(request)

    def get_account_status(self, request):
        start_time = time.time()
        function_name = 'get_account_status'
        logger.info(ENTERING_FUNCTION_LOG.format(function_name))

        try:
            self._initialize_client()
            data = json.loads(request.body)
            wallet_seed = data.get("wallet_seed")

            if not wallet_seed:
                return self._send_response(False, error="Missing wallet_seed")

            wallet = Wallet.from_seed(wallet_seed)

            # Get balances
            balances = check_balance(self, wallet)

            # Get active offers
            offers = get_offer_status(self, wallet.classic_address)

            # Get trust lines
            trustlines_response = self.client.request(
                AccountLines(account=wallet.classic_address, ledger_index="validated"))
            trustlines = trustlines_response.result.get("lines", [])

            return create_account_status_response(balances, offers, trustlines)

        except (XRPLRequestFailureException, XRPLException, XRPLAddressCodecException, ValueError) as e:
            # Handle error message
            return handle_error_new(e, status_code=500, function_name=function_name)
        except Exception as e:
            # Handle error message
            return handle_error_new(e, status_code=500, function_name=function_name)
        finally:
            logger.info(LEAVING_FUNCTION_LOG.format(function_name, total_execution_time_in_millis(start_time)))
