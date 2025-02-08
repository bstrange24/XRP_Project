from django.db import models

class XrplPaymentData(models.Model):
    sender = models.CharField(max_length=35)  # Sender's XRPL address
    receiver = models.CharField(max_length=35)  # Receiver's XRPL address
    amount = models.DecimalField(max_digits=20, decimal_places=6)  # Amount in XRP
    transaction_hash = models.CharField(max_length=64, unique=True)  # XRPL transaction hash
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.sender} -> {self.receiver}: {self.amount} XRP"

    class Meta:
        db_table = 'xrpl_payment_data'

class XrplAccountData(models.Model):
    # account_data fields
    objects = None
    account = models.CharField(max_length=100, unique=True)  # Account ID
    balance = models.DecimalField(max_digits=20, decimal_places=0)  # Account balance
    flags = models.IntegerField()  # Flags (stored as an integer)
    ledger_entry_type = models.CharField(max_length=100)  # Ledger entry type (e.g., "AccountRoot")
    owner_count = models.IntegerField()  # Owner count
    previous_txn_id = models.CharField(max_length=255)  # Previous transaction ID
    previous_txn_lgr_seq = models.IntegerField()  # Previous transaction ledger sequence
    sequence = models.IntegerField()  # Sequence number
    index = models.CharField(max_length=255)  # Account index

    # account_flags (stored as boolean fields)
    allow_trustline_clawback = models.BooleanField(default=False)
    default_ripple = models.BooleanField(default=False)
    deposit_auth = models.BooleanField(default=False)
    disable_master_key = models.BooleanField(default=False)
    disallow_incoming_check = models.BooleanField(default=False)
    global_freeze = models.BooleanField(default=False)
    no_freeze = models.BooleanField(default=False)
    password_spent = models.BooleanField(default=False)
    require_authorization = models.BooleanField(default=False)
    require_destination_tag = models.BooleanField(default=False)

    # Ledger-related fields
    ledger_hash = models.CharField(max_length=255)  # Ledger hash
    ledger_index = models.IntegerField()  # Ledger index
    validated = models.BooleanField(default=False)  # Whether the transaction is validated

    def __str__(self):
        return f"Account {self.account} with balance {self.balance}"

    class Meta:
        db_table = 'xrpl_account_data'

class XrplLedgerEntryData(models.Model):
    ledger_index = models.CharField(max_length=64, unique=True)
    close_time_iso = models.DateTimeField()
    ctid = models.CharField(max_length=16)
    hash = models.CharField(max_length=64)
    seq = models.IntegerField()
    ticket_count = models.IntegerField()
    ledger_entry_type = models.CharField(max_length=32)
    previous_fields_balance = models.BigIntegerField()
    previous_txn_id = models.CharField(max_length=64)
    previous_txn_lgr_seq = models.IntegerField()
    account = models.CharField(max_length=64)
    balance = models.BigIntegerField()
    flags = models.IntegerField()
    owner_count = models.IntegerField()
    transaction_index = models.IntegerField()
    transaction_result = models.CharField(max_length=16)
    delivered_amount = models.BigIntegerField()
    validated = models.BooleanField()

    def __str__(self):
        return f"Ledger Entry {self.ledger_index}"

    class Meta:
        db_table = 'xrpl_ledger_entry_data'

class XrplTransactionData(models.Model):
    ledger_entry = models.ForeignKey(XrplLedgerEntryData, on_delete=models.CASCADE, related_name='transactions')
    account = models.CharField(max_length=64)
    deliver_max = models.BigIntegerField()
    destination = models.CharField(max_length=64)
    fee = models.BigIntegerField()
    flags = models.IntegerField()
    last_ledger_sequence = models.IntegerField()
    sequence = models.IntegerField()
    signing_pub_key = models.CharField(max_length=128)
    transaction_type = models.CharField(max_length=16)
    txn_signature = models.TextField()
    date = models.DateTimeField()
    ledger_index = models.IntegerField()

    def __str__(self):
        return f"Transaction {self.ledger_index} for Ledger Entry {self.ledger_entry.ledger_index}"

    class Meta:
        db_table = 'xrpl_transaction_data'