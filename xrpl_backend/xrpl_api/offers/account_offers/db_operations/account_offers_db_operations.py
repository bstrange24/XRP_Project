import logging

import django
from django.utils.dateparse import parse_datetime
from ...account_offers.models.account_offers_model import OfferCancelResponse, OfferCancelAffectedNode

logger = logging.getLogger('xrpl_app')

def save_offer_cancel_response(response_data: dict):
    """
    Saves an XRPL 'OfferCancel' response into the database.
    """
    try:
        result = response_data
        if not result:
            raise ValueError("Missing 'result' in response data")

        # Ensure the required field 'ctid' is present
        ctid = result.get("ctid")
        if not ctid:
            raise ValueError("Missing 'ctid' in the result data")

        # Parse close_time_iso safely
        close_time_str = result.get("close_time_iso")
        if not close_time_str or not isinstance(close_time_str, str):
            raise ValueError("Missing or invalid 'close_time_iso' in the result data")

        close_time = parse_datetime(close_time_str)
        if close_time is None:
            raise ValueError(f"Failed to parse close_time_iso: {close_time_str}")

        # Create and save the main response object
        offer_cancel = OfferCancelResponse(
            ctid=result.get("ctid"),
            hash=result.get("hash"),
            ledger_hash=result.get("ledger_hash"),
            ledger_index=result.get("ledger_index"),
            close_time_iso=close_time,
            validated=result.get("validated", False),
            meta=result.get("meta"),
            tx_json=result.get("tx_json"),
        )
        offer_cancel.save()

        # Process and save each affected node found in the meta field.
        meta = result.get("meta", {})
        affected_nodes = meta.get("AffectedNodes", [])
        for node in affected_nodes:
            # Each node is a dict with a single key (e.g., "DeletedNode" or "ModifiedNode")
            for node_type, node_data in node.items():
                OfferCancelAffectedNode.objects.create(
                    response=offer_cancel,
                    node_type=node_type,
                    ledger_entry_type=node_data.get("LedgerEntryType"),
                    ledger_index=node_data.get("LedgerIndex"),
                    final_fields=node_data.get("FinalFields"),
                    previous_fields=node_data.get("PreviousFields"),
                    previous_txn_id=node_data.get("PreviousTxnID"),
                    previous_txn_lgr_seq=node_data.get("PreviousTxnLgrSeq"),
                )
    except django.db.IntegrityError as e:
        logger.error(f"IntegrityError caught saving transaction history data: {e}")
    except django.db.DataError as e:
        logger.error(f"DataError caught saving transaction history data: {e}")
    except Exception as e:
        logger.error(f"Unexpected exception caught saving transaction history data: {e}")

