import logging
from decimal import Decimal

from ..models.payments_models import XrplPaymentData
from django.db import transaction

logger = logging.getLogger('xrpl_app')

def save_payment_data(sender: str, receiver: str, amount: Decimal, transaction_hash: str):
    try:
        with transaction.atomic():
            XrplPaymentData.objects.create(
                sender=sender,
                receiver=receiver,
                amount=amount,
                transaction_hash=transaction_hash,
            )
    except Exception as e:
        # Handle error message
        logger.error(f"Error saving payment data: {e}")
    finally:
        pass