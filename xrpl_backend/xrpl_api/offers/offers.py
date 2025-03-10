import json
import logging
import time

from django.core.paginator import Paginator
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import csrf_exempt
from xrpl import XRPLException
from xrpl.account import does_account_exist
from xrpl.asyncio.clients import XRPLRequestFailureException
from xrpl.core.addresscodec import XRPLAddressCodecException
from xrpl.transaction import submit_and_wait
from xrpl.wallet import Wallet

from .offers_util import check_balance, check_and_create_trust_line, get_offer_status, create_account_status_response, \
    create_cancel_account_status_response, create_taker_account_response, create_buyer_account_response, \
    create_seller_account_response, create_sell_offer, create_buy_offer, prepare_cancel_offer, prepare_account_lines, \
    prepare_account_offers_paginated, create_get_account_offers_response
from ..constants.constants import MISSING_REQUEST_PARAMETERS, LEAVING_FUNCTION_LOG, ENTERING_FUNCTION_LOG, \
    SENDER_SEED_IS_INVALID, ACCOUNT_DOES_NOT_EXIST_ON_THE_LEDGER, INVALID_WALLET_IN_REQUEST
from ..errors.error_handling import error_response, handle_error_new, process_transaction_error, \
    process_unexpected_error
from ..utilities.base_xrpl_view import BaseXRPLView
from ..utilities.utilities import total_execution_time_in_millis, is_valid_xrpl_seed, \
     validate_xrpl_response_data

logger = logging.getLogger('xrpl_app')

@method_decorator(csrf_exempt, name="dispatch")
class GetAccountOffers(BaseXRPLView):
    def __init__(self):
        super().__init__()

    def post(self, request):
        return self.get_account_offers(request)

    def get(self, request):
        return self.get_account_offers(request)

    def get_account_offers(self, request=None):
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

            if not account or not self._validate_xrp_wallet(account):
                raise XRPLException(error_response(INVALID_WALLET_IN_REQUEST))

            if not does_account_exist(account, self.client):
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

            if not all([wallet_seed]):
                raise ValueError(error_response(MISSING_REQUEST_PARAMETERS))

            if not self._is_valid_xrpl_seed(wallet_seed):
                raise XRPLException(error_response(SENDER_SEED_IS_INVALID))

            wallet = Wallet.from_seed(wallet_seed)

            # Get balances
            balances = check_balance(self, wallet, None)

            # Get active offers
            offers = get_offer_status(self, wallet.classic_address)
            logger.info(f"offers: {offers}")

            # Get trust lines
            trust_lines_response = self.client.request(prepare_account_lines(wallet.classic_address))
            trust_line_created = trust_lines_response.result.get("lines", [])
            logger.info(f"Trust lines created: {trust_line_created}")

            return create_account_status_response(balances, offers, trust_line_created)

        except (XRPLRequestFailureException, XRPLException, XRPLAddressCodecException, ValueError) as e:
            # Handle error message
            return handle_error_new(e, status_code=500, function_name=function_name)
        except Exception as e:
            # Handle error message
            return handle_error_new(e, status_code=500, function_name=function_name)
        finally:
            logger.info(LEAVING_FUNCTION_LOG.format(function_name, total_execution_time_in_millis(start_time)))


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
            amount = data.get("amount")
            currency_code = data.get("currency_code")
            trust_line_limit_amount = data.get("trust_line_limit_amount")

            if not all([seller_seed, issuer_address, xrp_amount, amount, currency_code, trust_line_limit_amount]):
                raise ValueError(error_response(MISSING_REQUEST_PARAMETERS))

            if not self._is_valid_xrpl_seed(seller_seed):
                raise XRPLException(error_response(SENDER_SEED_IS_INVALID))

            if not does_account_exist(issuer_address, self.client):
                raise XRPLException(error_response(ACCOUNT_DOES_NOT_EXIST_ON_THE_LEDGER.format(issuer_address)))

            if not self._is_valid_xrp_amount(xrp_amount):
                raise ValueError(error_response("Invalid XRP amount"))

            if not self._is_valid_currency_amount(str(amount), currency_code):
                raise ValueError(error_response("Invalid currency code or amount"))

            if not self._is_valid_amount(trust_line_limit_amount):
                raise ValueError(error_response("Invalid trust line limit amount"))

            seller_wallet = Wallet.from_seed(seller_seed)

            # Check and create trust line
            trust_line_created = check_and_create_trust_line(self, seller_wallet, issuer_address, currency_code, trust_line_limit_amount)

            # Check balances before offer
            balances_before = check_balance(self, seller_wallet, currency_code)

            # Create sell offer
            sell_offer_request = create_sell_offer(seller_wallet.classic_address, int(xrp_amount * 1000000),
                                                   currency_code, issuer_address, str(amount))

            try:
                logger.info("signing and submitting the transaction, awaiting a response")
                sell_offer_response = submit_and_wait(sell_offer_request, self.client, seller_wallet)
            except XRPLException as e:
                process_unexpected_error(e)

            if validate_xrpl_response_data(sell_offer_response):
                process_transaction_error(sell_offer_response)

            logger.debug(json.dumps(sell_offer_response.result, indent=4, sort_keys=True))

            result = sell_offer_response.result

            # Check balances after offer
            balances_after = check_balance(self, seller_wallet, currency_code)

            return create_seller_account_response(result, trust_line_created, balances_before, balances_after)

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
            amount = data.get("amount")
            currency_code = data.get("currency_code")
            trust_line_limit_amount = data.get("trust_line_limit_amount")

            if not all([buyer_seed, issuer_address, xrp_amount, amount, currency_code, trust_line_limit_amount]):
                raise ValueError(error_response(MISSING_REQUEST_PARAMETERS))

            if not is_valid_xrpl_seed(buyer_seed):
                raise XRPLException(error_response(SENDER_SEED_IS_INVALID))

            if not does_account_exist(issuer_address, self.client):
                raise XRPLException(error_response(ACCOUNT_DOES_NOT_EXIST_ON_THE_LEDGER.format(issuer_address)))

            if not self._is_valid_xrp_amount(xrp_amount):
                raise ValueError(error_response("Invalid XRP amount"))

            if not self._is_valid_currency_amount(str(amount), currency_code):
                raise ValueError(error_response("Invalid currency code or amount"))

            if not self._is_valid_amount(trust_line_limit_amount):
                raise ValueError(error_response("Invalid trust line limit amount"))

            buyer_wallet = Wallet.from_seed(buyer_seed)

            # Check and create trust line
            trust_line_created = check_and_create_trust_line(self, buyer_wallet, issuer_address, currency_code, trust_line_limit_amount)

            # Check balances before offer
            balances_before = check_balance(self, buyer_wallet, currency_code)

            # Create buy offer
            buy_offer_request = create_buy_offer(buyer_wallet.classic_address, currency_code, issuer_address,
                                                 str(amount), int(xrp_amount * 1000000))

            try:
                logger.info("signing and submitting the transaction, awaiting a response")
                buy_offer_response = submit_and_wait(buy_offer_request, self.client, buyer_wallet)
            except XRPLException as e:
                process_unexpected_error(e)

            if validate_xrpl_response_data(buy_offer_response):
                process_transaction_error(buy_offer_response)

            logger.debug(json.dumps(buy_offer_response.result, indent=4, sort_keys=True))

            result = buy_offer_response.result

            # Check balances after offer
            balances_after = check_balance(self, buyer_wallet, currency_code)

            return create_buyer_account_response(result, trust_line_created, balances_before, balances_after)

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
            amount = data.get("amount")
            currency_code = data.get("currency_code")
            direction = data.get("direction")  # "buy" or "sell"
            trust_line_limit_amount = data.get("trust_line_limit_amount")

            if not all([taker_seed, issuer_address, xrp_amount, amount, currency_code, direction, trust_line_limit_amount]):
                raise ValueError(error_response(MISSING_REQUEST_PARAMETERS))

            if not is_valid_xrpl_seed(taker_seed):
                raise XRPLException(error_response(SENDER_SEED_IS_INVALID))

            if not does_account_exist(issuer_address, self.client):
                raise XRPLException(error_response(ACCOUNT_DOES_NOT_EXIST_ON_THE_LEDGER.format(issuer_address)))

            if not self._is_valid_xrp_amount(xrp_amount):
                raise ValueError(error_response("Invalid XRP amount"))

            if not self._is_valid_currency_amount(str(amount), currency_code):
                raise ValueError(error_response("Invalid currency code or amount"))

            if not self._is_valid_amount(trust_line_limit_amount):
                raise ValueError(error_response("Invalid trust line limit amount"))

            taker_wallet = Wallet.from_seed(taker_seed)

            # Check and create trust line
            trust_line_created = check_and_create_trust_line(self, taker_wallet, issuer_address, currency_code, trust_line_limit_amount)

            # Check balances before offer
            balances_before = check_balance(self, taker_wallet, currency_code)

            # Create taker offer based on direction
            if direction == "buy":
                taker_offer_request = create_buy_offer(taker_wallet.classic_address, currency_code, issuer_address,
                                                       str(amount), int(xrp_amount * 1000000))
            elif direction == "sell":
                taker_offer_request = create_sell_offer(taker_wallet.classic_address, int(xrp_amount * 1000000),
                                                        currency_code, issuer_address, str(amount))
            else:
                raise ValueError(error_response("Invalid direction: must be 'buy' or 'sell'"))

            try:
                logger.info("signing and submitting the transaction, awaiting a response")
                taker_offer_response = submit_and_wait(taker_offer_request, self.client, taker_wallet)
            except XRPLException as e:
                process_unexpected_error(e)

            if validate_xrpl_response_data(taker_offer_response):
                process_transaction_error(taker_offer_response)

            logger.debug(json.dumps(taker_offer_response.result, indent=4, sort_keys=True))

            result = taker_offer_response.result

            # Check balances after offer
            balances_after = check_balance(self, taker_wallet, currency_code)

            return create_taker_account_response(result, trust_line_created, balances_before, balances_after)

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
                raise ValueError(error_response(MISSING_REQUEST_PARAMETERS))

            if not self._is_valid_xrpl_seed(wallet_seed):
                raise XRPLException(error_response(SENDER_SEED_IS_INVALID))

            wallet = Wallet.from_seed(wallet_seed)

            # Check balances before cancellation
            balances_before = check_balance(self, wallet, None)

            # Cancel offer
            cancel_offer_request = prepare_cancel_offer(wallet.classic_address, int(sequence))

            try:
                logger.info("signing and submitting the transaction, awaiting a response")
                cancel_offer_response = submit_and_wait(cancel_offer_request, self.client, wallet)
            except XRPLException as e:
                process_unexpected_error(e)

            if validate_xrpl_response_data(cancel_offer_response):
                process_transaction_error(cancel_offer_response)

            logger.debug(json.dumps(cancel_offer_response.result, indent=4, sort_keys=True))

            result = cancel_offer_response.result

            # Check balances after cancellation
            balances_after = check_balance(self, wallet, None)

            return create_cancel_account_status_response(result, balances_before, balances_after)

        except (XRPLRequestFailureException, XRPLException, XRPLAddressCodecException, ValueError) as e:
            # Handle error message
            return handle_error_new(e, status_code=500, function_name=function_name)
        except Exception as e:
            # Handle error message
            return handle_error_new(e, status_code=500, function_name=function_name)
        finally:
            logger.info(LEAVING_FUNCTION_LOG.format(function_name, total_execution_time_in_millis(start_time)))
