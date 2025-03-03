import time

from django.utils.timezone import is_aware
from datetime import datetime, timezone
import logging

import django

from ...constants.constants import ENTERING_FUNCTION_LOG, LEAVING_FUNCTION_LOG
from ...nft.models.nft_models import NFTTransaction, NFTAffectedNode, NFToken, NFTSellTransaction, NFTSellAffectedNode, \
    NFTSellTransactionJson, NFTBuyTransaction, NFTBurnTransaction, \
    NFTBurnTransactionJson, NFTBurnAffectedNode, NFTBuyTransactionData
from ...utilities.utilities import total_execution_time_in_millis

logger = logging.getLogger('xrpl_app')

def save_nft_mint_transaction(data):
    start_time = time.time()
    function_name = 'save_nft_mint_transaction'
    logger.info(ENTERING_FUNCTION_LOG.format(function_name))

    try:
        # Extract transaction data
        tx_data = data['tx_json']
        meta_data = data['meta']

        # Parse the datetime string into a timezone-aware datetime object
        close_time_iso = datetime.fromisoformat(data['close_time_iso'].replace('Z', '+00:00'))

        # Ensure the datetime is timezone-aware
        if not is_aware(close_time_iso):
            close_time_iso = close_time_iso.replace(tzinfo=timezone.utc)

        with django.db.transaction.atomic():
            # Create or update the NFTTransaction
            transaction, created = NFTTransaction.objects.update_or_create(
                hash=data['hash'],
                defaults={
                    'close_time_iso': close_time_iso,
                    'ctid': data['ctid'],
                    'ledger_hash': data['ledger_hash'],
                    'ledger_index': data['ledger_index'],
                    'transaction_index': meta_data.get('TransactionIndex'),
                    'transaction_result': meta_data.get('TransactionResult'),
                    'nftoken_id': meta_data.get('nftoken_id'),
                    'account': tx_data['Account'],
                    'fee': tx_data['Fee'],
                    'flags': tx_data['Flags'],
                    'last_ledger_sequence': tx_data['LastLedgerSequence'],
                    'nftoken_taxon': tx_data['NFTokenTaxon'],
                    'sequence': tx_data['Sequence'],
                    'signing_pub_key': tx_data['SigningPubKey'],
                    'transaction_type': tx_data['TransactionType'],
                    'txn_signature': tx_data['TxnSignature'],
                    'date': tx_data['date'],
                    'validated': data['validated'],
                }
            )

            # Save AffectedNodes
            for node in meta_data.get('AffectedNodes', []):
                node_type, node_data = next(iter(node.items()))
                affected_node, _ = NFTAffectedNode.objects.update_or_create(
                    transaction=transaction,
                    ledger_index=node_data.get('LedgerIndex'),
                    defaults={
                        'ledger_entry_type': node_data.get('LedgerEntryType'),
                        'final_fields': node_data.get('FinalFields'),
                        'previous_fields': node_data.get('PreviousFields'),
                        'previous_txn_id': node_data.get('PreviousTxnID'),
                        'previous_txn_lgr_seq': node_data.get('PreviousTxnLgrSeq'),
                    }
                )

                # Save NFTokens
                final_nftokens = node_data.get('FinalFields', {}).get('NFTokens', [])
                previous_nftokens = node_data.get('PreviousFields', {}).get('NFTokens', [])

                for nftoken in final_nftokens:
                    NFToken.objects.update_or_create(
                        affected_node=affected_node,
                        nftoken_id=nftoken['NFToken']['NFTokenID'],
                        defaults={
                            'final_nftoken': nftoken,
                        }
                    )

                for nftoken in previous_nftokens:
                    NFToken.objects.update_or_create(
                        affected_node=affected_node,
                        nftoken_id=nftoken['NFToken']['NFTokenID'],
                        defaults={
                            'previous_nftoken': nftoken,
                        }
                    )
            logger.info(f"Record saved in the database")
            logger.info(LEAVING_FUNCTION_LOG.format(function_name, total_execution_time_in_millis(start_time)))
            return transaction
    except django.db.IntegrityError as e:
        logger.error(f"IntegrityError caught saving transaction history data: {e}")
        print(f"IntegrityError caught saving transaction history data: {e}")
        logger.info(LEAVING_FUNCTION_LOG.format(function_name, total_execution_time_in_millis(start_time)))
    except django.db.DataError as e:
        logger.error(f"DataError caught saving transaction history data: {e}")
        print(f"DataError caught saving transaction history data: {e}")
        logger.info(LEAVING_FUNCTION_LOG.format(function_name, total_execution_time_in_millis(start_time)))
    except Exception as e:
        logger.error(f"Unexpected exception caught saving transaction history data: {e}")
        print(f"Unexpected exception caught saving transaction history data: {e}")
        logger.info(LEAVING_FUNCTION_LOG.format(function_name, total_execution_time_in_millis(start_time)))


def save_nft_sell_transactions(response):
    start_time = time.time()
    function_name = 'save_nft_sell_transactions'
    logger.info(ENTERING_FUNCTION_LOG.format(function_name))

    try:
        with django.db.transaction.atomic():
            # Create transaction
            transaction = NFTSellTransaction(
                close_time_iso=response['close_time_iso'],
                ctid=response['ctid'],
                hash=response['hash'],
                ledger_hash=response['ledger_hash'],
                ledger_index=response['ledger_index'],
                validated=response['validated']
            )
            transaction.save()

            # Create transaction JSON with fallback for flags
            tx_json = NFTSellTransactionJson(
                transaction=transaction,
                account=response['tx_json']['Account'],
                amount=response['tx_json']['Amount'],
                fee=response['tx_json']['Fee'],
                flags=response['tx_json'].get('Flags'),  # Use .get() to handle missing Flags
                last_ledger_sequence=response['tx_json']['LastLedgerSequence'],
                nftoken_id=response['tx_json']['NFTokenID'],
                sequence=response['tx_json']['Sequence'],
                signing_pub_key=response['tx_json']['SigningPubKey'],
                transaction_type=response['tx_json']['TransactionType'],
                txn_signature=response['tx_json']['TxnSignature'],
                date=response['tx_json']['date']
            )
            tx_json.save()

            # Create affected nodes
            for node in response['meta']['AffectedNodes']:
                node_data = list(node.values())[0]
                affected_node = NFTSellAffectedNode(
                    transaction=transaction,
                    node_type=list(node.keys())[0],
                    ledger_entry_type=node_data['LedgerEntryType'],
                    ledger_index=node_data['LedgerIndex'],
                    new_fields=node_data.get('NewFields'),
                    final_fields=node_data.get('FinalFields'),
                    previous_fields=node_data.get('PreviousFields'),
                    previous_txn_id=node_data.get('PreviousTxnID'),
                    previous_txn_lgr_seq=node_data.get('PreviousTxnLgrSeq')
                )
                affected_node.save()

        logger.info(f"Record saved in the database")
        logger.info(LEAVING_FUNCTION_LOG.format(function_name, total_execution_time_in_millis(start_time)))
        return transaction
    except django.db.IntegrityError as e:
        logger.error(f"IntegrityError caught saving transaction history data: {e}")
        print(f"IntegrityError caught saving transaction history data: {e}")
        logger.info(LEAVING_FUNCTION_LOG.format(function_name, total_execution_time_in_millis(start_time)))
    except django.db.DataError as e:
        logger.error(f"DataError caught saving transaction history data: {e}")
        print(f"DataError caught saving transaction history data: {e}")
        logger.info(LEAVING_FUNCTION_LOG.format(function_name, total_execution_time_in_millis(start_time)))
    except Exception as e:
        logger.error(f"Unexpected exception caught saving transaction history data: {e}")
        print(f"Unexpected exception caught saving transaction history data: {e}")
        logger.info(LEAVING_FUNCTION_LOG.format(function_name, total_execution_time_in_millis(start_time)))


def save_nft_burn_transactions(response):
    start_time = time.time()
    function_name = 'save_nft_burn_transactions'
    logger.info(ENTERING_FUNCTION_LOG.format(function_name))

    try:
        with django.db.transaction.atomic():
            # Create transaction
            transaction = NFTBurnTransaction(
                close_time_iso=response['close_time_iso'],
                ctid=response['ctid'],
                hash=response['hash'],
                ledger_hash=response['ledger_hash'],
                ledger_index=response['ledger_index'],
                validated=response['validated']
            )
            transaction.save()

            # Create transaction JSON
            tx_json = NFTBurnTransactionJson(
                transaction=transaction,
                account=response['tx_json']['Account'],
                fee=response['tx_json']['Fee'],
                flags=response['tx_json'].get('Flags'),
                last_ledger_sequence=response['tx_json']['LastLedgerSequence'],
                nftoken_sell_offer=response['tx_json'].get('NFTokenSellOffer'),
                sequence=response['tx_json']['Sequence'],
                signing_pub_key=response['tx_json']['SigningPubKey'],
                transaction_type=response['tx_json']['TransactionType'],
                txn_signature=response['tx_json']['TxnSignature'],
                date=response['tx_json']['date']
            )
            tx_json.save()

            # Create affected nodes
            for node in response['meta']['AffectedNodes']:
                node_type = list(node.keys())[0]  # ModifiedNode or DeletedNode
                node_data = node[node_type]

                affected_node = NFTBurnAffectedNode(
                    transaction=transaction,
                    node_type=node_type,
                    ledger_entry_type=node_data['LedgerEntryType'],
                    ledger_index=node_data['LedgerIndex'],
                    flags=node_data.get('FinalFields', {}).get('Flags'),
                    nftoken_id=node_data.get('FinalFields', {}).get('NFTokenID'),
                    previous_txn_id=node_data.get('PreviousTxnID'),
                    previous_txn_lgr_seq=node_data.get('PreviousTxnLgrSeq'),

                    # NFTokenPage fields
                    nftokens_final=node_data.get('FinalFields', {}).get('NFTokens'),
                    nftokens_previous=node_data.get('PreviousFields', {}).get('NFTokens'),
                    next_page_min=node_data.get('FinalFields', {}).get('NextPageMin'),
                    previous_page_min=node_data.get('FinalFields', {}).get('PreviousPageMin'),

                    # NFTokenOffer fields
                    amount=node_data.get('FinalFields', {}).get('Amount'),
                    owner=node_data.get('FinalFields', {}).get('Owner'),
                    nftoken_offer_node=node_data.get('FinalFields', {}).get('NFTokenOfferNode'),
                    owner_node=node_data.get('FinalFields', {}).get('OwnerNode'),

                    # DirectoryNode fields
                    root_index=node_data.get('FinalFields', {}).get('RootIndex'),

                    # AccountRoot fields
                    account=node_data.get('FinalFields', {}).get('Account'),
                    balance=node_data.get('FinalFields', {}).get('Balance'),
                    burned_nftokens=node_data.get('FinalFields', {}).get('BurnedNFTokens'),
                    first_nftoken_sequence=node_data.get('FinalFields', {}).get('FirstNFTokenSequence'),
                    minted_nftokens=node_data.get('FinalFields', {}).get('MintedNFTokens'),
                    owner_count=node_data.get('FinalFields', {}).get('OwnerCount'),
                    sequence=node_data.get('FinalFields', {}).get('Sequence'),

                    # Previous fields for ModifiedNode
                    previous_fields=node_data.get('PreviousFields')
                )
                affected_node.save()

        logger.info(f"Record saved in the database")
        logger.info(LEAVING_FUNCTION_LOG.format(function_name, total_execution_time_in_millis(start_time)))
        return transaction
    except django.db.IntegrityError as e:
        logger.error(f"IntegrityError caught saving transaction history data: {e}")
        print(f"IntegrityError caught saving transaction history data: {e}")
        logger.info(LEAVING_FUNCTION_LOG.format(function_name, total_execution_time_in_millis(start_time)))
    except django.db.DataError as e:
        logger.error(f"DataError caught saving transaction history data: {e}")
        print(f"DataError caught saving transaction history data: {e}")
        logger.info(LEAVING_FUNCTION_LOG.format(function_name, total_execution_time_in_millis(start_time)))
    except Exception as e:
        logger.error(f"Unexpected exception caught saving transaction history data: {e}")
        print(f"Unexpected exception caught saving transaction history data: {e}")
        logger.info(LEAVING_FUNCTION_LOG.format(function_name, total_execution_time_in_millis(start_time)))


# Function to create instances from the response
def save_nft_buy_transactions(response):
    start_time = time.time()
    function_name = 'save_nft_burn_transactions'
    logger.info(ENTERING_FUNCTION_LOG.format(function_name))

    try:
        with django.db.transaction.atomic():
            # Create snapshot
            snapshot = NFTBuyTransaction(
                account=response['account'],
                ledger_current_index=response['ledger_current_index'],
                validated=response['validated']
            )
            snapshot.save()

            # Create NFT records
            for nft_data in response['account_nfts']:
                nft = NFTBuyTransactionData(
                    snapshot=snapshot,
                    flags=nft_data['Flags'],
                    issuer=nft_data['Issuer'],
                    nftoken_id=nft_data['NFTokenID'],
                    nftoken_taxon=nft_data['NFTokenTaxon'],
                    nft_serial=nft_data['nft_serial'],
                    transfer_fee=nft_data.get('TransferFee')  # Optional, use .get() to handle absence
                )
                nft.save()

        return snapshot
    except django.db.IntegrityError as e:
        logger.error(f"IntegrityError caught saving transaction history data: {e}")
        print(f"IntegrityError caught saving transaction history data: {e}")
        logger.info(LEAVING_FUNCTION_LOG.format(function_name, total_execution_time_in_millis(start_time)))
    except django.db.DataError as e:
        logger.error(f"DataError caught saving transaction history data: {e}")
        print(f"DataError caught saving transaction history data: {e}")
        logger.info(LEAVING_FUNCTION_LOG.format(function_name, total_execution_time_in_millis(start_time)))
    except Exception as e:
        logger.error(f"Unexpected exception caught saving transaction history data: {e}")
        print(f"Unexpected exception caught saving transaction history data: {e}")
        logger.info(LEAVING_FUNCTION_LOG.format(function_name, total_execution_time_in_millis(start_time)))