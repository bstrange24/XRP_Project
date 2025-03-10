import logging

import django

from ..models.payments_models import PaymentTransactionData, PaymentTransactionAffectedNode, \
    PaymentTransactionFinalFields, PaymentTransactionPreviousFields, PaymentTransactionTxJson, PaymentTransactionMeta
from django.db import transaction

logger = logging.getLogger('xrpl_app')


def save_payment_data(transaction_data, transaction_hash, sender_address, receiver_address, amount_xrp, fee_drops):
    try:
        with django.db.transaction.atomic():
            # Upsert Transaction using 'sender' as the key
            transaction, created = PaymentTransactionData.objects.update_or_create(
                transaction_hash=transaction_hash,  # Use transaction_hash as the lookup key
                defaults={
                    'close_time_iso': transaction_data['close_time_iso'],
                    'ctid': transaction_data['ctid'],
                    'ledger_hash': transaction_data['ledger_hash'],
                    'ledger_index': transaction_data['ledger_index'],
                    'transaction_index': transaction_data['meta']['TransactionIndex'],
                    'transaction_result': transaction_data['meta']['TransactionResult'],
                    'delivered_amount': transaction_data['meta']['delivered_amount'],
                    'validated': transaction_data.get('validated'),
                    'transaction_hash': transaction_hash,
                    'hash': transaction_hash,  # Ensure the hash is also updated
                    'receiver': receiver_address,
                    'amount': amount_xrp,
                    'fee_drops': fee_drops,
                }
            )

            if created:
                logger.info(f"Created new transaction for sender {sender_address} with hash {transaction_hash}")
            else:
                logger.info(f"Updated existing transaction for sender {sender_address} with hash {transaction_hash}")

            # Upsert Meta
            meta, _ = PaymentTransactionMeta.objects.update_or_create(
                transaction=transaction,
                defaults={
                    'transaction_index': transaction_data['meta']['TransactionIndex'],
                    'transaction_result': transaction_data['meta']['TransactionResult'],
                    'delivered_amount': transaction_data['meta']['delivered_amount']
                }
            )

            if meta:
                logger.debug(f"Created new meta for transaction with hash {transaction_hash}")
            else:
                logger.debug(f"Updated existing meta for transaction with hash {transaction_hash}")

            # Upsert AffectedNodes
            for node_data in transaction_data['meta']['AffectedNodes']:
                node_type = list(node_data.keys())[0]  # "ModifiedNode", "DeletedNode", or "CreatedNode"
                node = node_data[node_type]

                affected_node, _ = PaymentTransactionAffectedNode.objects.update_or_create(
                    meta=meta,
                    ledger_index=node['LedgerIndex'],
                    defaults={
                        'node_type': node_type,
                        'ledger_entry_type': node['LedgerEntryType'],
                        'previous_txn_id': node.get('PreviousTxnID'),
                        'previous_txn_lgr_seq': node.get('PreviousTxnLgrSeq')
                    }
                )

                if affected_node:
                    logger.debug(f"Created new affected node for transaction with hash {transaction_hash}")
                else:
                    logger.debug(f"Updated existing affected node for transaction with hash {transaction_hash}")

                # Upsert FinalFields if present
                if 'FinalFields' in node:
                    final_fields = PaymentTransactionFinalFields.objects.update_or_create(
                        affected_node=affected_node,
                        defaults={
                            'account': node['FinalFields'].get('Account'),
                            'account_txn_id': node['FinalFields'].get('AccountTxnID'),
                            'balance': node['FinalFields'].get('Balance'),
                            'flags': node['FinalFields'].get('Flags'),
                            'owner_count': node['FinalFields'].get('OwnerCount'),
                            'sequence': node['FinalFields'].get('Sequence')
                        }
                    )

                    if final_fields:
                        logger.debug(f"Created new final fields for transaction with hash {transaction_hash}")
                    else:
                        logger.debug(f"Updated existing final fields for transaction with hash {transaction_hash}")

                # Upsert PreviousFields if present
                if 'PreviousFields' in node:
                    previous_fields = PaymentTransactionPreviousFields.objects.update_or_create(
                        affected_node=affected_node,
                        defaults={
                            'account_txn_id': node['PreviousFields'].get('AccountTxnID'),
                            'balance': node['PreviousFields'].get('Balance'),
                            'sequence': node['PreviousFields'].get('Sequence')
                        }
                    )

                    if previous_fields:
                        logger.debug(f"Created new previous fields for transaction with hash {transaction_hash}")
                    else:
                        logger.debug(f"Updated existing previous fields for transaction with hash {transaction_hash}")

            # Upsert TxJson
            tx_json_data = transaction_data['tx_json']
            tx_json = PaymentTransactionTxJson.objects.update_or_create(
                transaction=transaction,
                defaults={
                    'account': tx_json_data['Account'],
                    'deliver_max': tx_json_data.get('DeliverMax'),
                    'destination': tx_json_data['Destination'],
                    'fee': tx_json_data['Fee'],
                    'flags': tx_json_data['Flags'],
                    'last_ledger_sequence': tx_json_data['LastLedgerSequence'],
                    'sequence': tx_json_data['Sequence'],
                    'signing_pub_key': tx_json_data['SigningPubKey'],
                    'transaction_type': tx_json_data['TransactionType'],
                    'txn_signature': tx_json_data['TxnSignature'],
                    'date': tx_json_data['date'],
                    'ledger_index': tx_json_data['ledger_index']
                }
            )

            if tx_json:
                logger.debug(f"Created new tx_json for transaction with hash {transaction_hash}")
            else:
                logger.debug(f"Updated existing tx_json for transaction with hash {transaction_hash}")

        return transaction
    except django.db.IntegrityError as e:
        logger.error(f"IntegrityError caught saving transaction history data: {e}")
    except django.db.DataError as e:
        logger.error(f"DataError caught saving transaction history data: {e}")
    except Exception as e:
        logger.error(f"Unexpected exception caught saving transaction history data: {e}")
