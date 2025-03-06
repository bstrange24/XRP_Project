import json
import logging
import random
import time

from django.core.paginator import Paginator
from django.utils.decorators import method_decorator
from django.views import View
from django.views.decorators.csrf import csrf_exempt
from tenacity import retry, wait_exponential, stop_after_attempt
from xrpl import XRPLException
from xrpl.account import does_account_exist
from xrpl.asyncio.clients import XRPLRequestFailureException
from xrpl.ledger import get_latest_validated_ledger_sequence
from xrpl.transaction import submit_and_wait
from xrpl.utils import XRPRangeException
from xrpl.wallet import Wallet

from .db_operations.nft_db_operations import save_nft_mint_transaction, save_nft_sell_transactions, \
    save_nft_buy_transactions, save_nft_burn_transactions
from .nft_utils import prepare_nftoken_mint_request, prepare_account_nft_request, create_nftoken_response, \
    prepare_nftoken_burn_request, create_nftoken_with_pagination_response, process_sell_account_nft, \
    create_nftoken_mint_response, verify_nft_ownership, check_existing_nft_sell_offers, cancel_nft_sell_offers, \
    create_failed_nftoken_burn_response, prepare_nftoken_sell_offers_request, prepare_nftoken_accept_offer, \
    create_nftoken_buy_response, create_nftoken_cancel_response
from ..constants.constants import RETRY_BACKOFF, MAX_RETRIES, ENTERING_FUNCTION_LOG, \
    MISSING_REQUEST_PARAMETERS, ERROR_INITIALIZING_CLIENT, LEAVING_FUNCTION_LOG, \
    SENDER_SEED_IS_INVALID, INVALID_WALLET_IN_REQUEST, MINT_NFT_TX_FLAG_OPTIONS, ACCOUNT_DOES_NOT_EXIST_ON_THE_LEDGER
from ..errors.error_handling import error_response, process_transaction_error, handle_error_new, \
    process_unexpected_error
from ..utilities.utilities import get_xrpl_client, validate_xrpl_response_data, \
    total_execution_time_in_millis, is_valid_xrpl_seed, validate_xrp_wallet, count_xrp_received

logger = logging.getLogger('xrpl_app')


@method_decorator(csrf_exempt, name="dispatch")
class MintNft(View):
    def __init__(self):
        super().__init__()
        self.client = None  # Lazy-loaded client

    def post(self, request, *args, **kwargs):
        return self.mint_nft(request)

    def get(self, request, *args, **kwargs):
        return self.mint_nft(request)

    @retry(wait=wait_exponential(multiplier=RETRY_BACKOFF), stop=stop_after_attempt(MAX_RETRIES))
    def mint_nft(self, request):
        start_time = time.time()
        function_name = 'mint_nft'
        logger.info(ENTERING_FUNCTION_LOG.format(function_name))

        try:
            if not self.client:
                self.client = get_xrpl_client()
            if not self.client:
                raise XRPLException(error_response(ERROR_INITIALIZING_CLIENT))

            data = json.loads(request.body)
            minter_seed = data.get("minter_seed")
            mint_and_sell = str(data.get("mint_and_sell", "false")).lower() == "true"
            tx_flags = data.get("tx_flags", [])
            sell_amounts = data.get("sell_amounts", [])
            nft_count = data.get("nft_count", 1)
            transfer_fee = data.get("transfer_fee", 100)  # default to 1%

            if not minter_seed or not isinstance(nft_count, int) or nft_count <= 0:
                raise ValueError(error_response(MISSING_REQUEST_PARAMETERS))

            if not is_valid_xrpl_seed(minter_seed):
                raise XRPLException(error_response(SENDER_SEED_IS_INVALID))

            logger.info(f"Tx flag count: {len(tx_flags)} Sell amount count: {len(sell_amounts)} Nft Count: {nft_count}")
            if not (len(tx_flags) == len(sell_amounts) == nft_count):
                raise ValueError(
                    f"Size mismatch: Tx Flags = {len(tx_flags)}, Sell Amounts = {len(sell_amounts)}, Nft Count = {nft_count}")

            minter_wallet = Wallet.from_seed(minter_seed)
            minter_wallet_address = minter_wallet.classic_address

            logger.info(f"Minting {nft_count} NFTs on account {minter_wallet_address}")
            logger.info(f"Mint and Sell: {mint_and_sell} Tx Flags: {tx_flags} Sell Amounts: {sell_amounts}")

            minted_nfts = []
            failed_mints = []
            sell_response = []

            for i in range(nft_count):
                try:
                    tx_flag = tx_flags[i] if i < len(tx_flags) else None
                    if tx_flag not in MINT_NFT_TX_FLAG_OPTIONS:
                        tx_flag = None

                    taxon = random.randint(1, 999999)
                    mint_nft_transaction_request = prepare_nftoken_mint_request(minter_wallet_address, tx_flag, taxon,
                                                                                transfer_fee)
                    try:
                        logger.info("signing and submitting the transaction, awaiting a response")
                        mint_transaction_response = submit_and_wait(transaction=mint_nft_transaction_request,
                                                                client=self.client, wallet=minter_wallet)
                    except XRPLException as e:
                        process_unexpected_error(e)

                    if validate_xrpl_response_data(mint_transaction_response):
                        process_transaction_error(mint_transaction_response)

                    count_xrp_received(mint_transaction_response.result, minter_wallet_address)
                    print("Minted")
                    print(mint_transaction_response.result)
                    save_nft_mint_transaction(mint_transaction_response.result)

                    mint_tx_result = mint_transaction_response.result
                    logger.info(f"Mint {i + 1} result: {mint_tx_result['meta']['TransactionResult']}")

                    # Try to extract NFTokenID from the response
                    nft_token_id = mint_tx_result.get("nftoken_id")
                    if not nft_token_id:
                        # Fallback: Look in meta.AffectedNodes for ModifiedNode
                        meta = mint_tx_result.get('meta', {})
                        affected_nodes = meta.get('AffectedNodes', [])
                        for node in affected_nodes:
                            if 'ModifiedNode' in node and node['ModifiedNode']['LedgerEntryType'] == 'NFTokenPage':
                                final_nftokens = node['ModifiedNode']['FinalFields'].get('NFTokens', [])
                                prev_nftokens = node['ModifiedNode']['PreviousFields'].get('NFTokens', [])
                                # Find the new NFT by comparing FinalFields and PreviousFields
                                new_nfts = [nft for nft in final_nftokens if nft not in prev_nftokens]
                                if new_nfts:
                                    nft_token_id = new_nfts[0]['NFToken']['NFTokenID']
                                    break
                        if not nft_token_id:
                            raise ValueError(error_response(f"No NFTokenID found for mint {i + 1}"))

                    minted_nft = {"NFTokenID": nft_token_id, "NFTokenTaxon": taxon}
                    minted_nfts.append(minted_nft)
                    logger.info(f"Minted NFT {i + 1} ID: {nft_token_id}")

                    if mint_and_sell:
                        sell_amount = sell_amounts[i] if i < len(sell_amounts) else None
                        if not sell_amount:
                            raise ValueError(error_response(f"Missing sell amount for NFT {i + 1}"))
                        sell_data = {
                            "nft_token_id": nft_token_id,
                            "seller_seed": minter_seed,
                            "nftoken_sell_amount": sell_amount
                        }
                        sell_response = process_sell_account_nft(self.client, sell_data, False)
                        minted_nfts[-1]["sell_result"] = sell_response  # Directly assign the processed result
                except Exception as e:
                    logger.error(f"Failed to mint NFT {i + 1}: {str(e)}")
                    failed_mints.append({"index": i + 1, "error": str(e)})
                    continue

            # Confirm minted NFTs by querying the account
            get_account_nfts_response = self.client.request(prepare_account_nft_request(minter_wallet_address, None))
            if validate_xrpl_response_data(get_account_nfts_response):
                process_transaction_error(get_account_nfts_response)

            account_nfts = get_account_nfts_response.result['account_nfts']
            logger.info(f"Total NFTs owned by {minter_wallet_address}: {len(account_nfts)}")

            return create_nftoken_mint_response(minted_nfts, sell_response, failed_mints, nft_count)

        except (XRPLRequestFailureException, XRPLException, XRPRangeException) as e:
            return handle_error_new(e, status_code=500, function_name=function_name)
        except Exception as e:
            return handle_error_new(e, status_code=500, function_name=function_name)
        finally:
            logger.info(LEAVING_FUNCTION_LOG.format(function_name, total_execution_time_in_millis(start_time)))


@method_decorator(csrf_exempt, name="dispatch")
class GetAccountNft(View):
    def __init__(self):
        super().__init__()
        self.client = None  # Lazy-loaded client

    def post(self, request, account, *args, **kwargs):
        return self.get_account_nft(request, account)

    def get(self, request, account, *args, **kwargs):
        return self.get_account_nft(request, account)

    @retry(wait=wait_exponential(multiplier=RETRY_BACKOFF), stop=stop_after_attempt(MAX_RETRIES))
    def get_account_nft(self, request, account):
        start_time = time.time()
        function_name = 'get_account_nft'
        logger.info(ENTERING_FUNCTION_LOG.format(function_name))

        try:
            if not self.client:
                self.client = get_xrpl_client()
            if not self.client:
                raise XRPLException(error_response(ERROR_INITIALIZING_CLIENT))

            logger.info(f"Parameters: wallet: {account}")

            if not all([account]):
                raise ValueError(error_response(MISSING_REQUEST_PARAMETERS))

            if not account or not validate_xrp_wallet(account):
                raise XRPLException(error_response(INVALID_WALLET_IN_REQUEST))

            if not does_account_exist(account, self.client):
                raise XRPLException(error_response(ACCOUNT_DOES_NOT_EXIST_ON_THE_LEDGER.format(account)))

            account_nfts_transactions = []
            marker = None

            # Loop to fetch all transactions for the account, using pagination through 'marker'
            while True:
                # Query the issuer account for its NFTs
                get_account_nfts_response = self.client.request(prepare_account_nft_request(account, marker))
                if validate_xrpl_response_data(get_account_nfts_response):
                    process_transaction_error(get_account_nfts_response)

                if get_account_nfts_response.result['account_nfts'] is not None and len(
                        get_account_nfts_response.result['account_nfts']) > 0:
                    response = get_account_nfts_response.result['account_nfts'][0]
                    logger.debug(
                        f"NFToken metadata: Issuer: {response['Issuer']} NFT ID: {response['NFTokenID']} NFT Taxon: {response['NFTokenTaxon']}")
                else:
                    logger.info(f"Account {account} has not minted any NFT's")

                account_nfts_transactions.extend(get_account_nfts_response.result["account_nfts"])

                # Check if there are more pages of transactions to fetch
                marker = get_account_nfts_response.result.get("marker")
                if not marker:
                    break

            # Extract pagination parameters from the request
            page = request.GET.get('page', 1)
            page = int(page) if page else 1

            page_size = request.GET.get('page_size', 10)
            page_size = int(page_size) if page_size else 1

            # Paginate the transactions
            paginator = Paginator(account_nfts_transactions, page_size)
            paginated_transactions = paginator.get_page(page)

            return create_nftoken_with_pagination_response(paginated_transactions, paginator)

        except (XRPLRequestFailureException, XRPLException, XRPRangeException) as e:
            return handle_error_new(e, status_code=500, function_name=function_name)
        except Exception as e:
            return handle_error_new(e, status_code=500, function_name=function_name)
        finally:
            logger.info(LEAVING_FUNCTION_LOG.format(function_name, total_execution_time_in_millis(start_time)))


@method_decorator(csrf_exempt, name="dispatch")
class BurnNft(View):
    def __init__(self):
        super().__init__()
        self.client = None  # Lazy-loaded client

    def post(self, request, *args, **kwargs):
        return self.burn_nft(request)

    def get(self, request, *args, **kwargs):
        return self.burn_nft(request)

    @retry(wait=wait_exponential(multiplier=RETRY_BACKOFF), stop=stop_after_attempt(MAX_RETRIES))
    def burn_nft(self, request):
        start_time = time.time()
        function_name = 'burn_nft'
        logger.info(ENTERING_FUNCTION_LOG.format(function_name))

        try:
            if not self.client:
                self.client = get_xrpl_client()
            if not self.client:
                raise XRPLException(error_response(ERROR_INITIALIZING_CLIENT))

            # Extract parameters from the request
            data = json.loads(request.body)
            nft_token_id = data.get("nft_token_id")
            minter_seed = data.get("minter_seed")

            if not all([nft_token_id]):
                raise ValueError(error_response(MISSING_REQUEST_PARAMETERS))

            if not is_valid_xrpl_seed(minter_seed):
                raise XRPLException(error_response(SENDER_SEED_IS_INVALID))

            issuer_wallet = Wallet.from_seed(minter_seed)
            logger.info(f"Parameters: NFT token id: {nft_token_id}")

            burn_tx = prepare_nftoken_burn_request(issuer_wallet.classic_address, nft_token_id)

            try:
                logger.info("signing and submitting the transaction, awaiting a response")
                burn_tx_response = submit_and_wait(transaction=burn_tx, client=self.client, wallet=issuer_wallet)
            except XRPLException as e:
                process_unexpected_error(e)

            if validate_xrpl_response_data(burn_tx_response):
                process_transaction_error(burn_tx_response)

            count_xrp_received(burn_tx_response.result, issuer_wallet)
            save_nft_burn_transactions(burn_tx_response.result)

            burn_tx_result = burn_tx_response.result
            logger.info(f"Burn tx result: {burn_tx_result['meta']['TransactionResult']}")

            if burn_tx_result['meta']['TransactionResult'] == "tesSUCCESS":
                logger.info(f"Transaction was successfully validated, NFToken {nft_token_id} has been burned")
                return create_nftoken_response(burn_tx_result, 'burned')
            else:
                logger.error(
                    f"Transaction failed, NFToken was not burned, error code: {burn_tx_result['meta']['TransactionResult']}")
                return create_failed_nftoken_burn_response(burn_tx_result['meta']['TransactionResult'])

        except (XRPLRequestFailureException, XRPLException, XRPRangeException) as e:
            return handle_error_new(e, status_code=500, function_name=function_name)
        except Exception as e:
            return handle_error_new(e, status_code=500, function_name=function_name)
        finally:
            logger.info(LEAVING_FUNCTION_LOG.format(function_name, total_execution_time_in_millis(start_time)))


@method_decorator(csrf_exempt, name="dispatch")
class SellNft(View):
    def __init__(self):
        super().__init__()
        self.client = None  # Lazy-loaded client

    def post(self, request, *args, **kwargs):
        return self.sell_nft(request)

    def get(self, request, *args, **kwargs):
        return self.sell_nft(request)

    @retry(wait=wait_exponential(multiplier=RETRY_BACKOFF), stop=stop_after_attempt(MAX_RETRIES))
    def sell_nft(self, request):
        start_time = time.time()
        function_name = 'sell_nft'
        logger.info(f"Entering {function_name}")

        try:
            if not self.client:
                self.client = get_xrpl_client()
            if not self.client:
                raise XRPLException(error_response(ERROR_INITIALIZING_CLIENT))

            data = json.loads(request.body)
            return process_sell_account_nft(self.client, data, True)
        except (XRPLRequestFailureException, XRPLException, XRPRangeException) as e:
            return handle_error_new(e, status_code=500, function_name=function_name)
        except Exception as e:
            return handle_error_new(e, status_code=500, function_name=function_name)
        finally:
            logger.info(LEAVING_FUNCTION_LOG.format(function_name, total_execution_time_in_millis(start_time)))


@method_decorator(csrf_exempt, name="dispatch")
class BuyNft(View):
    def __init__(self):
        super().__init__()
        self.client = None  # Lazy-loaded client

    def post(self, request, *args, **kwargs):
        return self.buy_nft(request)

    def get(self, request, *args, **kwargs):
        return self.buy_nft(request)

    @retry(wait=wait_exponential(multiplier=RETRY_BACKOFF), stop=stop_after_attempt(MAX_RETRIES))
    def buy_nft(self, request):
        start_time = time.time()
        function_name = 'buy_nft'
        logger.info(ENTERING_FUNCTION_LOG.format(function_name))

        try:
            if not self.client:
                self.client = get_xrpl_client()
            if not self.client:
                raise XRPLException(error_response(ERROR_INITIALIZING_CLIENT))

            # Extract parameters from the request
            data = json.loads(request.body)
            nft_token_id = data.get("nft_token_id")
            issuer_seed = data.get("issuer_seed")
            buyer_seed = data.get("buyer_seed")
            buy_offer_amount = data.get('buy_offer_amount')

            if not all([nft_token_id, issuer_seed, buyer_seed, buy_offer_amount]):
                raise ValueError(error_response(MISSING_REQUEST_PARAMETERS))

            if not is_valid_xrpl_seed(issuer_seed) or not is_valid_xrpl_seed(buyer_seed):
                raise XRPLException(error_response(SENDER_SEED_IS_INVALID))

            issuer_wallet = Wallet.from_seed(issuer_seed)
            issuer_address = issuer_wallet.classic_address

            buyer_wallet = Wallet.from_seed(buyer_seed)
            buyer_address = buyer_wallet.classic_address

            logger.info(f"Parameters: NFT token id: {nft_token_id} Buyer amount: {buy_offer_amount}")

            # Query the account's NFTs to verify ownership
            get_account_nfts_response = self.client.request(prepare_account_nft_request(issuer_address, None))
            if validate_xrpl_response_data(get_account_nfts_response):
                process_transaction_error(get_account_nfts_response)

            account_nfts = get_account_nfts_response.result.get('account_nfts', [])
            nft_exists = any(nft['NFTokenID'] == nft_token_id for nft in account_nfts)
            if not nft_exists:
                raise ValueError(
                    error_response(f"NFT token ID {nft_token_id} does not exist or is not owned by the seller."))
            else:
                for nft in account_nfts:
                    if nft['NFTokenID'] == nft_token_id:
                        logger.info(f"Found NFT: {nft}")
                        break

            sell_offers_response_request = self.client.request(prepare_nftoken_sell_offers_request(nft_token_id))
            if validate_xrpl_response_data(sell_offers_response_request):
                process_transaction_error(sell_offers_response_request)

            offer_objects = sell_offers_response_request.result
            if 'offers' not in offer_objects or not offer_objects['offers']:
                raise ValueError(error_response("No sell offers available for this NFT."))

            offer_int = 1
            for offer in offer_objects['offers']:
                logger.debug(
                    f"{offer_int}. Sell Offer metadata: NFT ID: {offer_objects['nft_id']} Sell Offer ID: {offer['nft_offer_index']}")
                logger.debug(
                    f" Offer amount: {offer['amount']} drops Offer owner: {offer['owner']} Raw metadata: {offer}")
                offer_int += 1

            selected_offer_index = offer_objects['offers'][0]['nft_offer_index']
            amount = offer_objects['offers'][0]['amount']
            logger.info(f"Selected sell offer: {selected_offer_index} with amount {amount} drops")

            last_ledger_sequence = get_latest_validated_ledger_sequence(self.client)
            accept_tx = prepare_nftoken_accept_offer(buyer_address, selected_offer_index, last_ledger_sequence)

            # Step 4: Sign and submit the transaction with the buyer’s wallet
            try:
                logger.info("signing and submitting the transaction, awaiting a response")
                accept_tx_signed = submit_and_wait(transaction=accept_tx, client=self.client, wallet=buyer_wallet)
            except XRPLException as e:
                process_unexpected_error(e)

            if validate_xrpl_response_data(accept_tx_signed):
                process_transaction_error(accept_tx_signed)

            count_xrp_received(accept_tx_signed.result, issuer_address)
            save_nft_buy_transactions(get_account_nfts_response.result)

            accept_tx_result = accept_tx_signed.result

            logger.info(f"NFTokenAcceptOffer tx result: {accept_tx_result['meta']['TransactionResult']}")

            for node in accept_tx_result['meta']['AffectedNodes']:
                if "ModifiedNode" in node and node['ModifiedNode']['LedgerEntryType'] == "NFTokenPage":
                    logger.info(f"NFT ownership transferred successfully. Metadata: {node}")

            return create_nftoken_buy_response(nft_token_id)

        except (XRPLRequestFailureException, XRPLException, XRPRangeException) as e:
            return handle_error_new(e, status_code=500, function_name=function_name)
        except Exception as e:
            return handle_error_new(e, status_code=500, function_name=function_name)
        finally:
            logger.info(LEAVING_FUNCTION_LOG.format(function_name, total_execution_time_in_millis(start_time)))


@method_decorator(csrf_exempt, name="dispatch")
class CancelNftOffers(View):
    def __init__(self):
        super().__init__()
        self.client = None  # Lazy-loaded client

    def post(self, request, *args, **kwargs):
        return self.cancel_nft_offers(request)

    def get(self, request, *args, **kwargs):
        return self.cancel_nft_offers(request)

    @retry(wait=wait_exponential(multiplier=RETRY_BACKOFF), stop=stop_after_attempt(MAX_RETRIES))
    def cancel_nft_offers(self, request):
        start_time = time.time()
        function_name = 'buy_nft'
        logger.info(ENTERING_FUNCTION_LOG.format(function_name))

        try:
            if not self.client:
                self.client = get_xrpl_client()
            if not self.client:
                raise XRPLException(error_response(ERROR_INITIALIZING_CLIENT))

            # Extract parameters from the request
            data = json.loads(request.body)
            nft_token_id = data.get("nft_token_id")
            issuer_seed = data.get("issuer_seed")

            if not all([nft_token_id, issuer_seed]):
                raise ValueError(error_response(MISSING_REQUEST_PARAMETERS))

            if not is_valid_xrpl_seed(issuer_seed):
                raise XRPLException(error_response(SENDER_SEED_IS_INVALID))

            issuer_wallet = Wallet.from_seed(issuer_seed)
            issuer_address = issuer_wallet.classic_address

            logger.info(f"Parameters: NFT token id: {nft_token_id}")

            # Query the account's NFTs to verify ownership
            verify_nft_ownership(self.client, issuer_address, nft_token_id)
            existing_offers = check_existing_nft_sell_offers(self.client, nft_token_id, issuer_address)
            if existing_offers:
                offer_ids = [offer['nft_offer_index'] for offer in existing_offers]
                cancel_nft_sell_offers(self.client, issuer_wallet, offer_ids)
                return create_nftoken_cancel_response(f"NFT {nft_token_id} offer has bee cancelled successfully.",
                                                      offer_ids)
            else:
                return create_nftoken_cancel_response(f"NFT {nft_token_id} has not offers.", None)

        except (XRPLRequestFailureException, XRPLException, XRPRangeException) as e:
            return handle_error_new(e, status_code=500, function_name=function_name)
        except Exception as e:
            return handle_error_new(e, status_code=500, function_name=function_name)
        finally:
            logger.info(LEAVING_FUNCTION_LOG.format(function_name, total_execution_time_in_millis(start_time)))
