from django.utils.timezone import is_aware
from datetime import datetime, timezone
import logging

import django

from ...nft.models.nft_models import NFTTransaction, NFTAffectedNode, NFToken

logger = logging.getLogger('xrpl_app')

def save_nft_mint_transaction(data):
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

            return transaction
    except django.db.IntegrityError as e:
        logger.error(f"IntegrityError caught saving transaction history data: {e}")
    except django.db.DataError as e:
        logger.error(f"DataError caught saving transaction history data: {e}")
    except Exception as e:
        logger.error(f"Unexpected exception caught saving transaction history data: {e}")