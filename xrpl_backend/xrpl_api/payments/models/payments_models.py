from django.db import models

class XrplPaymentData(models.Model):
    """
    A model representing XRPL payment data.

    Attributes:
        sender (str): The XRPL address of the sender.
        receiver (str): The XRPL address of the receiver.
        amount (Decimal): The amount of XRP sent.
        transaction_hash (str): The unique hash for the XRPL transaction.
        created_at (datetime): The timestamp when the record was created.
    """
    sender = models.CharField(max_length=35)  # Sender's XRPL address
    receiver = models.CharField(max_length=35)  # Receiver's XRPL address
    amount = models.DecimalField(max_digits=20, decimal_places=8)  # Amount in XRP
    transaction_hash = models.CharField(max_length=64, unique=True)  # XRPL transaction hash
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.sender} -> {self.receiver}: {self.amount} XRP"

    class Meta:
        db_table = 'xrpl_payment_data'
