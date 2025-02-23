import logging
import time

from django.core.paginator import Paginator
from django.utils.decorators import method_decorator
from django.views import View
from django.views.decorators.csrf import csrf_exempt
from xrpl import XRPLException
from xrpl.account import does_account_exist
from xrpl.asyncio.clients import XRPLRequestFailureException
from xrpl.core.addresscodec import XRPLAddressCodecException

from ...constants.constants import ENTERING_FUNCTION_LOG, LEAVING_FUNCTION_LOG, \
    ERROR_INITIALIZING_CLIENT, ACCOUNT_DOES_NOT_EXIST_ON_THE_LEDGER, INVALID_WALLET_IN_REQUEST
from ...errors.error_handling import handle_error_new, error_response, process_transaction_error
from ...offers.book_offers.book_offers_util import prepare_book_offers, \
    prepare_book_offers_paginated, create_book_offers_response
from ...utilities.utilities import total_execution_time_in_millis, get_xrpl_client, \
    validate_xrpl_response_data, validate_xrp_wallet

logger = logging.getLogger('xrpl_app')

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
        if not self.client:
            self.client = get_xrpl_client()
        if not self.client:
            raise XRPLException(error_response(ERROR_INITIALIZING_CLIENT))

        start_time = time.time()
        function_name = 'get_book_offers'
        logger.info(ENTERING_FUNCTION_LOG.format(function_name))

        try:
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

            # Paginate results
            page = int(request.GET.get('page', 1))
            page_size = int(request.GET.get('page_size', 10))
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