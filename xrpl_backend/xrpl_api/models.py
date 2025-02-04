from django.db import models

class XRPLAccount(models.Model):
    objects = None
    account_id = models.CharField(max_length=35, unique=True)
    balance = models.DecimalField(max_digits=20, decimal_places=6)
    created_at = models.DateTimeField(auto_now_add=True)
    transaction_hash = models.CharField(max_length=64, unique=True, null=True)
    secret = models.CharField(max_length=35)

    def __str__(self):
        return self.account_id

class Payment(models.Model):
    sender = models.CharField(max_length=35)  # Sender's XRPL address
    receiver = models.CharField(max_length=35)  # Receiver's XRPL address
    amount = models.DecimalField(max_digits=20, decimal_places=6)  # Amount in XRP
    transaction_hash = models.CharField(max_length=64, unique=True)  # XRPL transaction hash
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.sender} -> {self.receiver}: {self.amount} XRP"