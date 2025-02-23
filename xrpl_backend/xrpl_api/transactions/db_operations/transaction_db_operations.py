import logging

import django

from ..models.transaction_models import TransactionHistoryData, TransactionAffectedNode, TransactionFinalFields, \
    TransactionPreviousFields, TransactionJson, TransactionMetaData, TransactionNewFields

logger = logging.getLogger('xrpl_app')

def save_transaction_history(transaction_data):
    try:
        transaction_hash = transaction_data.get('hash')

        with django.db.transaction.atomic():
            # Check if a transaction with the same hash already exists
            if TransactionHistoryData.objects.filter(hash=transaction_hash).exists():
                logger.info(f"Transaction with hash {transaction_hash} already exists. Skipping insert")
                return None  # Skip saving the duplicate transaction

            # Save TransactionHistoryData
            transaction = TransactionHistoryData.objects.create(
                close_time_iso=transaction_data['close_time_iso'],
                hash=transaction_data['hash'],
                ledger_hash=transaction_data['ledger_hash'],
                ledger_index=transaction_data['ledger_index'],
                validated=transaction_data['validated']
            )

            # Save TransactionMetaData
            meta_data = transaction_data['meta']
            meta = TransactionMetaData.objects.create(
                ledger_transaction=transaction,
                transaction_index=meta_data['TransactionIndex'],
                transaction_result=meta_data['TransactionResult'],
                delivered_amount=meta_data['delivered_amount']
            )

            # Save AffectedNodes
            for node_data in meta_data['AffectedNodes']:
                node_type = list(node_data.keys())[0]  # "ModifiedNode", "DeletedNode", or "CreatedNode"
                node = node_data[node_type]

                affected_node = TransactionAffectedNode.objects.create(
                    meta_data=meta,
                    node_type=node_type,
                    ledger_entry_type=node['LedgerEntryType'],
                    ledger_index=node['LedgerIndex'],
                    previous_txn_id=node.get('PreviousTxnID'),
                    previous_txn_lgr_seq=node.get('PreviousTxnLgrSeq')
                )

                # Save FinalFields if present
                if 'FinalFields' in node:
                    TransactionFinalFields.objects.create(
                        affected_node=affected_node,
                        account=node['FinalFields'].get('Account'),
                        balance=node['FinalFields'].get('Balance'),
                        flags=node['FinalFields'].get('Flags'),
                        owner_count=node['FinalFields'].get('OwnerCount'),
                        sequence=node['FinalFields'].get('Sequence'),
                        ticket_count=node['FinalFields'].get('TicketCount'),
                        index_next=node['FinalFields'].get('IndexNext'),
                        index_previous=node['FinalFields'].get('IndexPrevious'),
                        owner=node['FinalFields'].get('Owner'),
                        root_index=node['FinalFields'].get('RootIndex'),
                        owner_node=node['FinalFields'].get('OwnerNode'),
                        previous_txn_id=node['FinalFields'].get('PreviousTxnID'),
                        previous_txn_lgr_seq=node['FinalFields'].get('PreviousTxnLgrSeq'),
                        ticket_sequence=node['FinalFields'].get('TicketSequence')
                    )

                # Save PreviousFields if present
                if 'PreviousFields' in node:
                    TransactionPreviousFields.objects.create(
                        affected_node=affected_node,
                        balance=node['PreviousFields'].get('Balance'),
                        owner_count=node['PreviousFields'].get('OwnerCount'),
                        sequence=node['PreviousFields'].get('Sequence'),
                        ticket_count=node['PreviousFields'].get('TicketCount')
                    )

                # Save NewFields if present
                if 'NewFields' in node:
                    TransactionNewFields.objects.create(
                        affected_node=affected_node,
                        account=node['NewFields'].get('Account'),
                        balance=node['NewFields'].get('Balance'),
                        sequence=node['NewFields'].get('Sequence')
                    )

            # Save TransactionJson
            tx_json_data = transaction_data['tx_json']
            TransactionJson.objects.create(
                ledger_transaction=transaction,
                account=tx_json_data['Account'],
                deliver_max=tx_json_data.get('DeliverMax'),
                destination=tx_json_data['Destination'],
                fee=tx_json_data['Fee'],
                flags=tx_json_data['Flags'],
                last_ledger_sequence=tx_json_data['LastLedgerSequence'],
                sequence=tx_json_data['Sequence'],
                signing_pub_key=tx_json_data['SigningPubKey'],
                transaction_type=tx_json_data['TransactionType'],
                txn_signature=tx_json_data['TxnSignature'],
                date=tx_json_data['date'],
                ledger_index=tx_json_data['ledger_index'],
                ticket_sequence=tx_json_data.get('TicketSequence')
            )

        return transaction
    except django.db.IntegrityError as e:
        logger.error(f"IntegrityError caught saving transaction history data: {e}")
    except django.db.DataError as e:
        logger.error(f"DataError caught saving transaction history data: {e}")
    except Exception as e:
        logger.error(f"Unexpected exception caught saving transaction history data: {e}")

