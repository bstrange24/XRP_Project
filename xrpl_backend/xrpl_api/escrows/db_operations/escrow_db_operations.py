import logging
import django
from ..models.escrow_models import EscrowTransaction, EscrowTransactionAffectedNode
import pytz

logger = logging.getLogger('xrpl_app')

from datetime import datetime

def save_create_escrow_response(response, fulfillment):
    try:
        # Parse top-level fields
        tx_hash = response["hash"]
        close_time_iso = datetime.strptime(response["close_time_iso"], "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=pytz.UTC)

        # Prepare tx_json data
        tx_json = response["tx_json"]
        meta = response["meta"]

        with django.db.transaction.atomic():
            # Save or update the main EscrowTransaction
            escrow_tx, created = EscrowTransaction.objects.update_or_create(
                hash=tx_hash,
                defaults={
                    "close_time_iso": close_time_iso,
                    "ctid": response["ctid"],
                    "ledger_hash": response["ledger_hash"],
                    "ledger_index": response["ledger_index"],
                    "validated": response["validated"],
                    "transaction_result": meta["TransactionResult"],
                    "transaction_index": meta["TransactionIndex"],
                    "account": tx_json["Account"],
                    "amount": tx_json["Amount"],
                    "cancel_after": tx_json.get("CancelAfter"),
                    "condition": tx_json.get("Condition"),
                    "destination": tx_json["Destination"],
                    "fee": tx_json["Fee"],
                    "finish_after": tx_json.get("FinishAfter"),
                    "flags": tx_json["Flags"],
                    "last_ledger_sequence": tx_json["LastLedgerSequence"],
                    "sequence": tx_json["Sequence"],
                    "signing_pub_key": tx_json["SigningPubKey"],
                    "transaction_type": tx_json["TransactionType"],
                    "txn_signature": tx_json["TxnSignature"],
                    "date": tx_json["date"],
                    'fulfillment': fulfillment,
                }
            )

            # Handle AffectedNodes
            EscrowTransactionAffectedNode.objects.filter(escrow_transaction=escrow_tx).delete()  # Clear old nodes if updating
            for node in meta["AffectedNodes"]:
                node_data = node.get("ModifiedNode") or node.get("CreatedNode")
                if not node_data:
                    continue

                node_type = "ModifiedNode" if "ModifiedNode" in node else "CreatedNode"
                final_fields = node_data.get("FinalFields", {})
                previous_fields = node_data.get("PreviousFields", {})

                EscrowTransactionAffectedNode.objects.create(
                    escrow_transaction=escrow_tx,
                    ledger_entry_type=node_data["LedgerEntryType"],
                    ledger_index=node_data["LedgerIndex"],
                    account=final_fields.get("Account"),
                    amount=final_fields.get("Amount"),
                    balance=final_fields.get("Balance"),
                    flags=final_fields.get("Flags"),
                    owner=final_fields.get("Owner"),
                    owner_count=final_fields.get("OwnerCount"),
                    sequence=final_fields.get("Sequence"),
                    root_index=final_fields.get("RootIndex"),
                    condition=final_fields.get("Condition"),
                    destination=final_fields.get("Destination"),
                    cancel_after=final_fields.get("CancelAfter"),
                    finish_after=final_fields.get("FinishAfter"),
                    previous_balance=previous_fields.get("Balance"),
                    previous_owner_count=previous_fields.get("OwnerCount"),
                    previous_sequence=previous_fields.get("Sequence"),
                    previous_txn_id=node_data.get("PreviousTxnID"),
                    previous_txn_lgr_seq=node_data.get("PreviousTxnLgrSeq"),
                    node_type=node_type,
                )

        return escrow_tx
    except django.db.IntegrityError as e:
        logger.error(f"IntegrityError caught saving transaction history data: {e}")
    except django.db.DataError as e:
        logger.error(f"DataError caught saving transaction history data: {e}")
    except Exception as e:
        logger.error(f"Unexpected exception caught saving transaction history data: {e}")