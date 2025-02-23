import json
import logging

import django

from ..models.escrow_models import EscrowTransaction

logger = logging.getLogger('xrpl_app')

# Function to save escrow response (not a model method, but included for convenience)
def save_escrow_response(response):
    from datetime import datetime
    try:
        for sent_txn in response.get("sent", []):
            EscrowTransaction.objects.create(
                escrow_id=sent_txn["escrow_id"],
                sender=sent_txn["sender"],
                receiver=sent_txn["receiver"],
                amount=float(sent_txn["amount"]),
                prex_txn_id=sent_txn["prex_txn_id"],
                redeem_date=datetime.strptime(sent_txn["redeem_date"], "%Y-%m-%d %H:%M:%S%z"),
                expiry_date=datetime.strptime(sent_txn["expiry_date"], "%Y-%m-%d %H:%M:%S%z"),
                type="sent"
            )
        for received_txn in response.get("received", []):
            EscrowTransaction.objects.create(
                escrow_id=received_txn["escrow_id"],
                sender=received_txn["sender"],
                receiver=received_txn["receiver"],
                amount=float(received_txn["amount"]),
                prex_txn_id=received_txn["prex_txn_id"],
                redeem_date=datetime.strptime(received_txn["redeem_date"], "%Y-%m-%d %H:%M:%S%z"),
                expiry_date=datetime.strptime(received_txn["expiry_date"], "%Y-%m-%d %H:%M:%S%z"),
                type="received"
            )
        print(Ledger.objects.first().created_at)
        return sent_txn

    except django.db.IntegrityError as e:
        logger.error(f"IntegrityError caught saving transaction history data: {e}")
    except django.db.DataError as e:
        logger.error(f"DataError caught saving transaction history data: {e}")
    except Exception as e:
        logger.error(f"Unexpected exception caught saving transaction history data: {e}")

