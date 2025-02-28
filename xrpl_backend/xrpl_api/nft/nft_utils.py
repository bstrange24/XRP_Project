import logging

from django.http import JsonResponse
from django.utils.decorators import method_decorator
from django.views import View
from django.views.decorators.csrf import csrf_exempt
from rest_framework.decorators import api_view
from tenacity import retry, wait_exponential, stop_after_attempt
from xrpl import XRPLException
from xrpl.account import does_account_exist
from xrpl.asyncio.clients import XRPLRequestFailureException
from xrpl.models import NFTokenMint, AccountNFTs, NFTokenBurn, NFTSellOffers, NFTokenAcceptOffer, NFTokenCreateOffer, \
    NFTokenCreateOfferFlag
from xrpl.utils import XRPRangeException
from xrpl.wallet import Wallet
from xrpl.models.transactions import Payment
from xrpl.models.requests import Fee
from xrpl.models.amounts import IssuedCurrencyAmount
from xrpl.transaction import sign, submit_and_wait
from xrpl.ledger import get_latest_validated_ledger_sequence
import time

from ..accounts.account_utils import prepare_account_data
from ..constants.constants import RETRY_BACKOFF, MAX_RETRIES, ENTERING_FUNCTION_LOG, \
    MISSING_REQUEST_PARAMETERS, ERROR_INITIALIZING_CLIENT, ACCOUNT_DOES_NOT_EXIST_ON_THE_LEDGER, LEAVING_FUNCTION_LOG
from ..errors.error_handling import error_response, process_transaction_error, handle_error_new
from ..trust_lines.trust_line_util import create_trust_set_response
from ..utilities.utilities import get_request_param, get_xrpl_client, validate_xrpl_response_data, \
    total_execution_time_in_millis

logger = logging.getLogger('xrpl_app')


def prepare_nftoken_mint_request(wallet_address):
    return NFTokenMint(
        account=wallet_address,
        nftoken_taxon=0
    )

def prepare_account_nft_request(wallet_address):
    return AccountNFTs(
        account=wallet_address
    )

def prepare_nftoken_burn_request(wallet_address, nft_token_id):
    return NFTokenBurn(
        account=wallet_address,
        nftoken_id=nft_token_id
    )

def prepare_nftoken_sell_offers_request(nft_token_id):
    return NFTSellOffers(
        nft_id=nft_token_id
    )

def prepare_nftoken_accept_offer(wallet_address, offer_objects):
    return NFTokenAcceptOffer(
                account=wallet_address,
                nftoken_sell_offer=offer_objects['offers'][0]['nft_offer_index']
            )

def prepare_nftoken_create_offer(wallet_address, nft_token_id, nftoken_sell_amount):
    return NFTokenCreateOffer(
        account=wallet_address,
        nftoken_id=nft_token_id,
        amount=nftoken_sell_amount,  # 10 XRP in drops, 1 XRP = 1,000,000 drops
        flags=NFTokenCreateOfferFlag.TF_SELL_NFTOKEN,
    )

def create_nftoken_response(response, message):
    return JsonResponse({
        'status':'success',
        'message': f'NFT successfully {message}',
        'result':response
    })