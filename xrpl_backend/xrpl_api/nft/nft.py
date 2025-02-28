import logging
import time

from django.http import JsonResponse
from django.utils.decorators import method_decorator
from django.views import View
from django.views.decorators.csrf import csrf_exempt
from tenacity import retry, wait_exponential, stop_after_attempt
from xrpl import XRPLException
from xrpl.asyncio.clients import XRPLRequestFailureException
from xrpl.transaction import submit_and_wait
from xrpl.utils import XRPRangeException
from xrpl.wallet import Wallet

from .db_operations.nft_db_operations import save_nft_mint_transaction
from .nft_utils import prepare_nftoken_mint_request, prepare_account_nft_request, create_nftoken_response, \
    prepare_nftoken_burn_request, prepare_nftoken_sell_offers_request, prepare_nftoken_accept_offer, \
    prepare_nftoken_create_offer
from ..constants.constants import RETRY_BACKOFF, MAX_RETRIES, ENTERING_FUNCTION_LOG, \
    MISSING_REQUEST_PARAMETERS, ERROR_INITIALIZING_CLIENT, LEAVING_FUNCTION_LOG, \
    SENDER_SEED_IS_INVALID, INVALID_WALLET_IN_REQUEST
from ..errors.error_handling import error_response, process_transaction_error, handle_error_new
from ..utilities.utilities import get_xrpl_client, validate_xrpl_response_data, \
    total_execution_time_in_millis, is_valid_xrpl_seed, validate_xrp_wallet, count_xrp_received

logger = logging.getLogger('xrpl_app')


@method_decorator(csrf_exempt, name="dispatch")
class NftProcessing(View):
    def __init__(self):
        super().__init__()
        self.client = None  # Lazy-loaded client

    def post(self, request, *args, **kwargs):
        if request.path == '/xrpl/mint-nft/':
            return self.mint_nft(request)
        elif request.path == '/xrpl/get-account-nft/':
            return self.get_account_nft(request)
        elif request.path == '/xrpl/burn-account-nft/':
            return self.burn_account_nft(request)
        elif request.path == '/xrpl/sell-account-nft/':
            return self.sell_account_nft(request)
        elif request.path == '/xrpl/sell-account-nft/':
            return self.buy_account_nft(request)
        else:
            return JsonResponse({"error": "Invalid request path"}, status=400)

    def get(self, request, *args, **kwargs):
        if request.path == '/xrpl/mint-nft/':
            return self.mint_nft(request)
        elif request.path == '/xrpl/get-account-nft/':
            return self.get_account_nft(request)
        elif request.path == '/xrpl/burn-account-nft/':
            return self.burn_account_nft(request)
        elif request.path == '/xrpl/sell-account-nft/':
            return self.sell_account_nft(request)
        elif request.path == '/xrpl/sell-account-nft/':
            return self.buy_account_nft(request)
        else:
            return JsonResponse({"error": "Invalid request path"}, status=400)

    @retry(wait=wait_exponential(multiplier=RETRY_BACKOFF), stop=stop_after_attempt(MAX_RETRIES))
    def mint_nft(self, request):
        if not self.client:
            self.client = get_xrpl_client()
        if not self.client:
            raise XRPLException(error_response(ERROR_INITIALIZING_CLIENT))

        start_time = time.time()
        function_name = 'mint_nft'
        logger.info(ENTERING_FUNCTION_LOG.format(function_name))

        try:
            minter_seed = request.GET.get('minter_seed')

            if not all([minter_seed]):
                raise ValueError(error_response(MISSING_REQUEST_PARAMETERS))

            if not is_valid_xrpl_seed(minter_seed):
                raise XRPLException(error_response(SENDER_SEED_IS_INVALID))

            minter_wallet = Wallet.from_seed(minter_seed)
            minter_wallet_address = minter_wallet.classic_address

            logger.info(f"Parameters: Minter Account: {minter_wallet_address}")
            logger.info(f"Minting a NFT on account {minter_wallet_address}")

            mint_nft_transaction_request = prepare_nftoken_mint_request(minter_wallet_address)

            # Sign and submit mint_tx using issuer account
            mint_transaction_response = submit_and_wait(transaction=mint_nft_transaction_request, client=self.client,
                                                        wallet=minter_wallet)
            if validate_xrpl_response_data(mint_transaction_response):
                process_transaction_error(mint_transaction_response)

            count_xrp_received(mint_transaction_response.result, minter_wallet)

            save_nft_mint_transaction(mint_transaction_response.result)

            mint_tx_result = mint_transaction_response.result
            logger.info(f"Mint transaction result: {mint_tx_result['meta']['TransactionResult']}")
            logger.debug(f"mint_tx_result: {mint_tx_result}")

            # Query the issuer account for its NFTs
            get_account_nfts_response = self.client.request(prepare_account_nft_request(minter_wallet_address))
            if validate_xrpl_response_data(get_account_nfts_response):
                process_transaction_error(get_account_nfts_response)

            logger.debug(f"get_account_nfts_response: {get_account_nfts_response}")
            account_nfts = get_account_nfts_response.result['account_nfts'][0]
            logger.debug(f"get_account_nfts_response: {account_nfts}")
            logger.info(f"NFToken metadata: Issuer: {account_nfts['Issuer']} NFT ID: {account_nfts['NFTokenID']} NFT Taxon: {account_nfts['NFTokenTaxon']}")

            return create_nftoken_response(account_nfts, 'minted')

        except (XRPLRequestFailureException, XRPLException, XRPRangeException) as e:
            return handle_error_new(e, status_code=500, function_name=function_name)
        except Exception as e:
            return handle_error_new(e, status_code=500, function_name=function_name)
        finally:
            logger.info(LEAVING_FUNCTION_LOG.format(function_name, total_execution_time_in_millis(start_time)))

    @retry(wait=wait_exponential(multiplier=RETRY_BACKOFF), stop=stop_after_attempt(MAX_RETRIES))
    def get_account_nft(self, request):
        if not self.client:
            self.client = get_xrpl_client()
        if not self.client:
            raise XRPLException(error_response(ERROR_INITIALIZING_CLIENT))

        start_time = time.time()
        function_name = 'get_account_nft'
        logger.info(ENTERING_FUNCTION_LOG.format(function_name))

        try:
            # Extract parameters from the request
            account = request.GET.get('account')  # Receiver’s address

            if not all([account]):
                raise ValueError(error_response(MISSING_REQUEST_PARAMETERS))

            if not account or not validate_xrp_wallet(account):
                raise XRPLException(error_response(INVALID_WALLET_IN_REQUEST))

            logger.info(f"Parameters: wallet: {account}")

            # Query the issuer account for its NFTs
            get_account_nfts_response = self.client.request(prepare_account_nft_request(account))
            if validate_xrpl_response_data(get_account_nfts_response):
                process_transaction_error(get_account_nfts_response)

            logger.debug(f"get_account_nfts_response: {get_account_nfts_response}")

            response = get_account_nfts_response.result['account_nfts'][0]
            logger.info(f"NFToken metadata: Issuer: {response['Issuer']} NFT ID: {response['NFTokenID']} NFT Taxon: {response['NFTokenTaxon']}")

            return create_nftoken_response(get_account_nfts_response.result, 'retrieved')

        except (XRPLRequestFailureException, XRPLException, XRPRangeException) as e:
            return handle_error_new(e, status_code=500, function_name=function_name)
        except Exception as e:
            return handle_error_new(e, status_code=500, function_name=function_name)
        finally:
            logger.info(LEAVING_FUNCTION_LOG.format(function_name, total_execution_time_in_millis(start_time)))

    @retry(wait=wait_exponential(multiplier=RETRY_BACKOFF), stop=stop_after_attempt(MAX_RETRIES))
    def burn_account_nft(self, request):
        if not self.client:
            self.client = get_xrpl_client()
        if not self.client:
            raise XRPLException(error_response(ERROR_INITIALIZING_CLIENT))

        start_time = time.time()
        function_name = 'burn_account_nft'
        logger.info(ENTERING_FUNCTION_LOG.format(function_name))

        try:
            # Extract parameters from the request
            nft_token_id = request.GET.get('nft_token_id')
            minter_seed = request.GET.get('minter_seed')

            if not all([nft_token_id]):
                raise ValueError(error_response(MISSING_REQUEST_PARAMETERS))

            if not is_valid_xrpl_seed(minter_seed):
                raise XRPLException(error_response(SENDER_SEED_IS_INVALID))

            issuer_wallet = Wallet.from_seed(minter_seed)
            logger.info(f"Parameters: NFT token id: {nft_token_id}")
            print(f"Received parameters: NFT token id: {nft_token_id}")

            burn_tx = prepare_nftoken_burn_request(issuer_wallet.classic_address, nft_token_id)
            burn_tx_response = submit_and_wait(transaction=burn_tx, client=self.client, wallet=issuer_wallet)
            if validate_xrpl_response_data(burn_tx_response):
                process_transaction_error(burn_tx_response)

            count_xrp_received(burn_tx_response.result, issuer_wallet)
            # save_nft_mint_transaction(burn_tx_response.result)

            burn_tx_result = burn_tx_response.result
            logger.info(f"Burn tx result: {burn_tx_result['meta']['TransactionResult']} Tx response: {burn_tx_result}")
            print(f"Tx response: {burn_tx_result}")
            print(f"Burn tx result: {burn_tx_result['meta']['TransactionResult']}")

            if burn_tx_result['meta']['TransactionResult'] == "tesSUCCESS":
                logger.info(f"Transaction was successfully validated, NFToken {nft_token_id} has been burned")
                print(f"Transaction was successfully validated, NFToken {nft_token_id} has been burned")
            else:
                print(
                    f"Transaction failed, NFToken was not burned, error code: {burn_tx_result['meta']['TransactionResult']}")
                logger.error(
                    f"Transaction failed, NFToken was not burned, error code: {burn_tx_result['meta']['TransactionResult']}")

            return create_nftoken_response(burn_tx_result, 'burned')

        except (XRPLRequestFailureException, XRPLException, XRPRangeException) as e:
            return handle_error_new(e, status_code=500, function_name=function_name)
        except Exception as e:
            return handle_error_new(e, status_code=500, function_name=function_name)
        finally:
            logger.info(LEAVING_FUNCTION_LOG.format(function_name, total_execution_time_in_millis(start_time)))

    @retry(wait=wait_exponential(multiplier=RETRY_BACKOFF), stop=stop_after_attempt(MAX_RETRIES))
    def sell_account_nft(self, request):
        if not self.client:
            self.client = get_xrpl_client()
        if not self.client:
            raise XRPLException(error_response(ERROR_INITIALIZING_CLIENT))

        start_time = time.time()
        function_name = 'sell_account_nft'
        logger.info(ENTERING_FUNCTION_LOG.format(function_name))

        try:
            # Extract parameters from the request
            nft_token_id = request.GET.get('nft_token_id')
            seller_seed = request.GET.get('minter_seed')
            nftoken_sell_amount = request.GET.get('nftoken_sell_amount')

            if not is_valid_xrpl_seed(seller_seed):
                raise XRPLException(error_response(SENDER_SEED_IS_INVALID))

            if not all([nft_token_id, seller_seed, nftoken_sell_amount]):
                raise ValueError(error_response(MISSING_REQUEST_PARAMETERS))

            if int(nftoken_sell_amount) <= 0:
                raise ValueError(error_response("Sell amount must greater than zero"))

            issuer_wallet = Wallet.from_seed(seller_seed)
            logger.info(f"Received parameters: NFT token id: {nft_token_id} NFT sell amount: {nftoken_sell_amount}")
            print(f"Received parameters: NFT token id: {nft_token_id}")

            # Query the account's NFTs to verify ownership
            account_nfts_response = self.client.request(prepare_account_nft_request(issuer_wallet.classic_address))
            if validate_xrpl_response_data(account_nfts_response):
                process_transaction_error(account_nfts_response)

            nfts = account_nfts_response.result.get('account_nfts', [])
            nft_exists = any(nft['NFTokenID'] == nft_token_id for nft in nfts)

            if not nft_exists:
                raise ValueError(
                    error_response(f"NFT token ID {nft_token_id} does not exist or is not owned by the account."))

            # Construct a NFTokenCreateOffer transaction to sell the NFT
            logger.info(
                f"Selling NFT {nft_token_id} for {int(nftoken_sell_amount) / 1000000} XRP on the open market...")
            print(f"Selling NFT {nft_token_id} for {int(nftoken_sell_amount) / 1000000} XRP on the open market...")

            sell_transaction_request = prepare_nftoken_create_offer(issuer_wallet.classic_address, nft_token_id,
                                                                    nftoken_sell_amount)

            # Sign and submit sell_tx using minter account
            sell_transaction_response = submit_and_wait(transaction=sell_transaction_request, client=self.client,
                                                        wallet=issuer_wallet)
            if validate_xrpl_response_data(sell_transaction_response):
                process_transaction_error(sell_transaction_response)

            count_xrp_received(sell_transaction_response.result, issuer_wallet)

            sell_tx_result = sell_transaction_response.result
            logger.info(f"Sell Offer tx result: {sell_tx_result['meta']['TransactionResult']}")
            logger.debug(f"Tx response: {sell_tx_result}")

            # Query the sell offer
            sell_offers_response = self.client.request(prepare_nftoken_sell_offers_request(nft_token_id))
            if validate_xrpl_response_data(sell_offers_response):
                process_transaction_error(sell_offers_response)

            return create_nftoken_response(sell_offers_response.result, 'sold')

        except (XRPLRequestFailureException, XRPLException, XRPRangeException) as e:
            return handle_error_new(e, status_code=500, function_name=function_name)
        except Exception as e:
            return handle_error_new(e, status_code=500, function_name=function_name)
        finally:
            logger.info(LEAVING_FUNCTION_LOG.format(function_name, total_execution_time_in_millis(start_time)))

    @retry(wait=wait_exponential(multiplier=RETRY_BACKOFF), stop=stop_after_attempt(MAX_RETRIES))
    def buy_account_nft(self, request):
        if not self.client:
            self.client = get_xrpl_client()
        if not self.client:
            raise XRPLException(error_response(ERROR_INITIALIZING_CLIENT))

        start_time = time.time()
        function_name = 'buy_account_nft'
        logger.info(ENTERING_FUNCTION_LOG.format(function_name))

        try:
            # Extract parameters from the request
            nft_token_id = request.GET.get('nft_token_id')
            buyer_seed = request.GET.get('buyer_seed')

            if not all([nft_token_id, buyer_seed]):
                raise ValueError(error_response(MISSING_REQUEST_PARAMETERS))

            if not is_valid_xrpl_seed(buyer_seed):
                raise XRPLException(error_response(SENDER_SEED_IS_INVALID))

            buyer_wallet = Wallet.from_seed(buyer_seed)
            logger.info(f"Parameters: NFT token id: {nft_token_id}")
            print(f"Received parameters: NFT token id: {nft_token_id}")

            # Query the account's NFTs to verify ownership
            get_account_nfts_response = self.client.request(prepare_account_nft_request(buyer_wallet.classic_address))
            if validate_xrpl_response_data(get_account_nfts_response):
                process_transaction_error(get_account_nfts_response)

            account_nfts = get_account_nfts_response.result.get('account_nfts', [])

            nft_exists = any(nft['NFTokenID'] == nft_token_id for nft in account_nfts)
            if not nft_exists:
                raise ValueError(
                    error_response(f"NFT token ID {nft_token_id} does not exist or is not owned by the account."))

            # Query the sell offer
            sell_offers_response = self.client.request(prepare_nftoken_sell_offers_request(nft_token_id))
            if validate_xrpl_response_data(sell_offers_response):
                process_transaction_error(sell_offers_response)

            offer_objects = sell_offers_response.result

            logger.info(f"Accepting offer {offer_objects['offers'][0]['nft_offer_index']}...")
            print(f"Accepting offer {offer_objects['offers'][0]['nft_offer_index']}...")

            buy_transaction_request = prepare_nftoken_accept_offer(buyer_wallet.classic_address,
                                                                   offer_objects['offers'][0]['nft_offer_index'])
            buy_transaction_response = submit_and_wait(transaction=buy_transaction_request, client=self.client,
                                                       wallet=buyer_wallet)
            if validate_xrpl_response_data(buy_transaction_response):
                process_transaction_error(buy_transaction_response)

            count_xrp_received(buy_transaction_response.result, buyer_wallet.classic_address)

            buy_tx_result = buy_transaction_response.result
            logger.info(f"Buy Offer result: {buy_tx_result['meta']['TransactionResult']}")
            logger.info(f"Tx response: {buy_tx_result}")
            print(f"\n Buy Offer result: {buy_tx_result['meta']['TransactionResult']}"
                  f"\n      Tx response: {buy_tx_result}")

            return create_nftoken_response(offer_objects, 'bought')

        except (XRPLRequestFailureException, XRPLException, XRPRangeException) as e:
            return handle_error_new(e, status_code=500, function_name=function_name)
        except Exception as e:
            return handle_error_new(e, status_code=500, function_name=function_name)
        finally:
            logger.info(LEAVING_FUNCTION_LOG.format(function_name, total_execution_time_in_millis(start_time)))
