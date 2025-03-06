from django.db import models

class EscrowTransaction(models.Model):
    ESCROW_TYPES = (
        ('sent', 'Sent'),
        ('received', 'Received'),
    )

    escrow_id = models.CharField(max_length=64, unique=True)
    sender = models.CharField(max_length=35)
    receiver = models.CharField(max_length=35)
    amount = models.DecimalField(max_digits=15, decimal_places=6)
    prex_txn_id = models.CharField(max_length=64)
    redeem_date = models.DateTimeField()
    expiry_date = models.DateTimeField()
    type = models.CharField(max_length=8, choices=ESCROW_TYPES)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.type} Escrow {self.escrow_id} - {self.amount} XRP"

