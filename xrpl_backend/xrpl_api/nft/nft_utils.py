import json
import logging
import time

from django.http import JsonResponse
from xrpl import XRPLException
from xrpl.models import NFTokenMint, AccountNFTs, NFTokenBurn, NFTSellOffers, NFTokenAcceptOffer, NFTokenCreateOffer, \
    NFTokenCreateOfferFlag, NFTokenMintFlag, NFTokenCancelOffer
from xrpl.transaction import submit_and_wait
from xrpl.wallet import Wallet

from .db_operations.nft_db_operations import save_nft_sell_transactions
from ..constants.constants import MISSING_REQUEST_PARAMETERS, SENDER_SEED_IS_INVALID
from ..errors.error_handling import error_response, process_transaction_error, process_unexpected_error
from ..utilities.utilities import validate_xrpl_response_data, total_execution_time_in_millis, is_valid_xrpl_seed

logger = logging.getLogger('xrpl_app')


def process_sell_account_nft(client, request_data, minted):
    start_time = time.time()
    function_name = 'sell_account_nft'
    logger.info(f"Entering {function_name}")

    try:
        nft_token_id = request_data.get("nft_token_id")
        seller_seed = request_data.get("seller_seed")
        nftoken_sell_amount = str(request_data.get("nftoken_sell_amount"))  # Convert to string
        check_existing_offers = request_data.get("check_existing_offers", False)
        cancel_existing_offers = request_data.get("cancel_existing_offers", False)

        if not all([nft_token_id, seller_seed, nftoken_sell_amount]):
            raise ValueError(error_response(MISSING_REQUEST_PARAMETERS))

        if not is_valid_xrpl_seed(seller_seed):
            raise XRPLException(error_response(SENDER_SEED_IS_INVALID))

        if int(nftoken_sell_amount) <= 0:  # Still works as int for this check
            raise ValueError(error_response("Sell amount must be greater than zero"))

        issuer_wallet = Wallet.from_seed(seller_seed)
        logger.info(f"Received parameters: NFT token id: {nft_token_id} NFT sell amount: {nftoken_sell_amount}")

        logger.info(f"Received parameters: NFT token id: {nft_token_id}")
        logger.info(
            f"Issuer Account: {issuer_wallet} nft_token_id: {nft_token_id} nftoken_sell_amount: {nftoken_sell_amount}")

        # Verify NFT ownership
        account_nfts_response = verify_nft_ownership(client, issuer_wallet.classic_address, nft_token_id)

        existing_offers = []
        if check_existing_offers:
            existing_offers = check_existing_nft_sell_offers(client, nft_token_id, issuer_wallet.classic_address)
            if existing_offers and cancel_existing_offers:
                offer_ids = [offer['nft_offer_index'] for offer in existing_offers]
                cancel_nft_sell_offers(client, issuer_wallet, offer_ids)

        if account_nfts_response.result['account_nfts']:
            nft_int = 1
            logger.info(f"NFTs owned by {issuer_wallet}:")
            for nft in account_nfts_response.result['account_nfts']:
                logger.debug(
                    f"{nft_int}. NFToken metadata: NFT ID: {nft['NFTokenID']} Issuer: {nft['Issuer']} NFT Taxon: {nft['NFTokenTaxon']}")
                nft_int += 1

            logger.info(
                f"Selling NFT {nft_token_id} for {int(nftoken_sell_amount) / 1000000} XRP on the open market...")

            sell_transaction_request = prepare_nftoken_create_offer(issuer_wallet.classic_address, nft_token_id,
                                                                    nftoken_sell_amount)
            try:
                logger.info("signing and submitting the transaction, awaiting a response")
                sell_transaction_response = submit_and_wait(transaction=sell_transaction_request, client=client,
                                                        wallet=issuer_wallet)
            except XRPLException as e:
                process_unexpected_error(e)

            if validate_xrpl_response_data(sell_transaction_response):
                process_transaction_error(sell_transaction_response)

            save_nft_sell_transactions(sell_transaction_response.result)

            sell_tx_result = sell_transaction_response.result
            logger.info(f"Sell Offer tx result: {sell_tx_result['meta']['TransactionResult']}")
            logger.debug(f"burn_tx_result: {json.dumps(sell_tx_result, indent=2)}")

            # Index through the tx's metadata and check the changes that occurred on the ledger (AffectedNodes)
            for node in sell_tx_result['meta']['AffectedNodes']:
                if "CreatedNode" in list(node.keys())[0] and "NFTokenOffer" in node['CreatedNode']['LedgerEntryType']:
                    logger.info(f"Sell Offer metadata: NFT ID: {node['CreatedNode']['NewFields']['NFTokenID']}")
                    logger.info(f"Sell Offer ID: {node['CreatedNode']['LedgerIndex']}")
                    logger.info(f"Offer amount: {node['CreatedNode']['NewFields']['Amount']}")
                    logger.info(f"drops Offer owner: {node['CreatedNode']['NewFields']['Owner']} Raw metadata: {node}")

            # Query the sell offer
            sell_offers_response = client.request(prepare_nftoken_sell_offers_request(nft_token_id))
            if validate_xrpl_response_data(sell_offers_response):
                process_transaction_error(sell_offers_response)

            offer_int = 1
            logger.info(f"Existing Sell Offers for NFT {nft_token_id}:")
            for offer in sell_offers_response.result['offers']:
                logger.info(f"{offer_int}. Sell Offer metadata: NFT ID: {sell_offers_response.result['nft_id']}")
                logger.info(f"Sell Offer ID: {offer['nft_offer_index']} Offer amount: {offer['amount']} drops")
                logger.info(f"Offer owner: {offer['owner']} Raw metadata: {offer}")
                offer_int += 1

            if minted:
                return create_nftoken_response(sell_tx_result, 'sold')
            else:
                return process_sell_tx(sell_tx_result)
        else:
            raise ValueError(
                error_response(f"NFT token ID {nft_token_id} does not exist or is not owned by the account."))
    except Exception as e:
        raise Exception(f"Error in {function_name}: {str(e)}")  # Improved exception handling
    finally:
        logger.info(f"Leaving {function_name}, execution time: {total_execution_time_in_millis(start_time)} ms")


def process_sell_tx(sell_tx_result):
    offer_id = None
    for node in sell_tx_result['meta'].get('AffectedNodes', []):
        if 'CreatedNode' in node and node['CreatedNode']['LedgerEntryType'] == 'NFTokenOffer':
            offer_id = node['CreatedNode']['LedgerIndex']
            break

    return {
        "hash": sell_tx_result['hash'],
        "offer_id": offer_id,
        "tx_json": sell_tx_result['tx_json']
    }


def verify_nft_ownership(client, account_address, nft_token_id):
    function_name = 'verify_nft_ownership'
    logger.info(f"Entering {function_name} for account {account_address} and NFT {nft_token_id}")

    try:
        # Query the account's NFTs
        account_nfts_response = client.request(prepare_account_nft_request(account_address, None))
        if validate_xrpl_response_data(account_nfts_response):
            process_transaction_error(account_nfts_response)

        # Check if the NFT is in the account's list
        owned_nfts = account_nfts_response.result['account_nfts']
        if not any(nft['NFTokenID'] == nft_token_id for nft in owned_nfts):
            raise ValueError(error_response(
                f"NFT token ID {nft_token_id} does not exist or is not owned by the account {account_address}."))

        logger.info(f"Verified ownership of NFT {nft_token_id} by account {account_address}")
        return account_nfts_response

    except Exception as e:
        logger.error(f"Error in {function_name}: {str(e)}")
        raise {str(e)}


def check_existing_nft_sell_offers(client, nft_token_id, owner_address):
    function_name = 'check_existing_nft_sell_offers'
    logger.info(f"Entering {function_name} for NFT {nft_token_id} and owner {owner_address}")

    try:
        sell_offers_response = client.request(prepare_nftoken_sell_offers_request(nft_token_id))
        if validate_xrpl_response_data(sell_offers_response):
            process_transaction_error(sell_offers_response)

        offers = sell_offers_response.result.get('offers', [])
        existing_sell_offers = [offer for offer in offers if offer['owner'] == owner_address]

        if existing_sell_offers:
            logger.info(f"Found {len(existing_sell_offers)} existing sell offers for NFT {nft_token_id}:")
            for offer in existing_sell_offers:
                logger.info(f"Existing offer: ID={offer['nft_offer_index']}, Amount={offer['amount']} drops")
        else:
            logger.info(f"No existing sell offers found for NFT {nft_token_id} by {owner_address}")

        return existing_sell_offers

    except Exception as e:
        logger.error(f"Error in {function_name}: {str(e)}")
        raise XRPLException(f"Failed to check existing sell offers: {str(e)}")


def cancel_nft_sell_offers(client, wallet, offer_ids):
    function_name = 'cancel_nft_sell_offers'
    logger.info(f"Entering {function_name} to cancel {len(offer_ids)} offers: {offer_ids}")

    try:
        if not offer_ids:
            logger.info("No offer IDs provided to cancel.")
            return

        cancel_tx_request = prepare_nftoken_cancel_offer(wallet.classic_address, offer_ids)
        try:
            logger.info("signing and submitting the transaction, awaiting a response")
            cancel_tx_response = submit_and_wait(transaction=cancel_tx_request, client=client, wallet=wallet)
        except XRPLException as e:
            process_unexpected_error(e)

        if validate_xrpl_response_data(cancel_tx_response):
            process_transaction_error(cancel_tx_response)

        cancel_tx_result = cancel_tx_response.result
        logger.info(f"Cancel transaction result: {cancel_tx_result['meta']['TransactionResult']}")

        for offer_id in offer_ids:
            logger.info(f"Canceled existing offer {offer_id}")

    except Exception as e:
        logger.error(f"Error in {function_name}: {str(e)}")
        raise XRPLException(f"Failed to cancel sell offers: {str(e)}")


def prepare_nftoken_mint_request(wallet_address, tx_flag, taxon, transfer_fee):
    if tx_flag is None:
        return NFTokenMint(
            account=wallet_address,
            nftoken_taxon=0
        )
    elif tx_flag == 'TF_TRANSFERABLE':
        return NFTokenMint(
            account=wallet_address,
            nftoken_taxon=taxon,
            flags=NFTokenMintFlag.TF_TRANSFERABLE,
            transfer_fee=transfer_fee
        )
    elif tx_flag == 'TF_BURNABLE':
        return NFTokenMint(
            account=wallet_address,
            nftoken_taxon=taxon,
            flags=NFTokenMintFlag.TF_BURNABLE
        )
    elif tx_flag == 'TF_ONLY_XRP':
        return NFTokenMint(
            account=wallet_address,
            nftoken_taxon=taxon,
            flags=NFTokenMintFlag.TF_ONLY_XRP
        )
    elif tx_flag == 'TRANSFER_AND_BURNABLE':
        return NFTokenMint(
            account=wallet_address,
            nftoken_taxon=taxon,
            transfer_fee=transfer_fee,
            flags=NFTokenMintFlag.TF_TRANSFERABLE | NFTokenMintFlag.TF_BURNABLE
        )
    elif tx_flag == 'TRANSFER_AND_XRP':
        return NFTokenMint(
            account=wallet_address,
            nftoken_taxon=taxon,
            transfer_fee=transfer_fee,
            flags=NFTokenMintFlag.TF_TRANSFERABLE | NFTokenMintFlag.TF_ONLY_XRP
        )
    elif tx_flag == 'BURNABLE_AND_XRP':
        return NFTokenMint(
            account=wallet_address,
            nftoken_taxon=taxon,
            flags=NFTokenMintFlag.TF_BURNABLE | NFTokenMintFlag.TF_ONLY_XRP
        )


def prepare_account_nft_request(wallet_address, marker):
    if marker is None:
        return AccountNFTs(
            account=wallet_address,
        )
    else:
        return AccountNFTs(
            account=wallet_address,
            limit=100,
            marker=marker,
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


def prepare_nftoken_accept_offer(wallet_address, selected_offer_index, last_ledger_sequence):
    return NFTokenAcceptOffer(
        account=wallet_address,
        nftoken_sell_offer=selected_offer_index,
        last_ledger_sequence=last_ledger_sequence + 300
    )


def prepare_nftoken_cancel_offer(wallet_address, token_offers):
    return NFTokenCancelOffer(
        account=wallet_address,
        nftoken_offers=token_offers,
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
        'status': 'success',
        'message': f'NFT successfully {message}',
        'result': response
    }, status=200)


def create_failed_nftoken_burn_response(response):
    return JsonResponse({
        'status': 'failure',
        'message': f'Transaction failed, NFToken was not burned.',
        'result': response
    }, status=200)


def create_nftoken_mint_response(minted_nfts, sell_response, failed_mints, nft_count):
    return JsonResponse({
        'status': 'success',
        "message": f"Minted {len(minted_nfts)} of {nft_count} requested NFTs",
        "minted_nfts": minted_nfts,
        "failed_mints": failed_mints,
        # "nfts_sold":sell_response,
    }, status=200)


def create_nftoken_buy_response(nft_token_id):
    return JsonResponse({
        'status': 'success',
        "message": f"NFT {nft_token_id} purchased successfully.",
    }, status=200)


def create_nftoken_cancel_response(message, offer_ids):
    if offer_ids is None:
        return JsonResponse({
            'status': 'success',
            "message": message,
            "offer ids:": offer_ids
        }, status=200)
    else:
        return JsonResponse({
            'status': 'success',
            "message": message,
        }, status=200)


def create_nftoken_with_pagination_response(paginated_transactions, paginator):
    return JsonResponse({
        "status": "success",
        "message": "Transaction history successfully retrieved.",
        # "transactions": paginated_transactions.object_list,
        "transactions": list(paginated_transactions),
        "page": paginated_transactions.number,
        "total_pages": paginator.num_pages,
        "total_count": paginator.count
    }, status=200)
