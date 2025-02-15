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


class XrplAccountData(models.Model):
    """
    A model representing XRPL account data.

    Attributes:
        account (str): The unique XRPL account ID.
        balance (Decimal): The account balance in drops.
        flags (int): Flags indicating account settings (as an integer).
        ledger_entry_type (str): The type of ledger entry (e.g., "AccountRoot").
        owner_count (int): The number of owned objects (e.g., trust lines, offers).
        previous_txn_id (str): The hash of the previous transaction affecting this account.
        previous_txn_lgr_seq (int): The ledger sequence of the previous transaction.
        sequence (int): The account's current sequence number.
        index (str): The unique account index.

        Flags (as booleans):
            allow_trustline_clawback (bool): Whether trustline clawbacks are allowed.
            default_ripple (bool): Whether rippling is enabled by default.
            deposit_auth (bool): Whether deposit authorization is required.
            disable_master_key (bool): Whether the master key is disabled.
            disallow_incoming_check (bool): Whether incoming checks are disallowed.
            global_freeze (bool): Whether the account is globally frozen.
            no_freeze (bool): Whether the account cannot freeze trustlines.
            password_spent (bool): Whether the password has been spent.
            require_authorization (bool): Whether authorization is required for trustlines.
            require_destination_tag (bool): Whether a destination tag is required.

        Ledger-related:
            ledger_hash (str): The hash of the ledger containing this account.
            ledger_index (int): The ledger index containing this account.
            validated (bool): Whether the account data has been validated.
    """
    account = models.CharField(max_length=100, unique=True)  # Account ID
    balance = models.DecimalField(max_digits=20, decimal_places=8)  # Account balance
    flags = models.IntegerField()  # Flags (stored as an integer)
    ledger_entry_type = models.CharField(max_length=100)  # Ledger entry type (e.g., "AccountRoot")
    owner_count = models.IntegerField()  # Owner count
    previous_txn_id = models.CharField(max_length=255)  # Previous transaction ID
    previous_txn_lgr_seq = models.IntegerField()  # Previous transaction ledger sequence
    sequence = models.IntegerField()  # Sequence number
    index = models.CharField(max_length=255)  # Account index

    # Account flags (stored as boolean fields)
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
    """
    A model representing XRPL ledger entry data.

    Attributes:
        ledger_index (str): The unique index of the ledger entry.
        close_time_iso (datetime): The ISO timestamp of the ledger's close time.
        ctid (str): The CTID (Checksum Transaction ID) associated with the ledger.
        hash (str): The unique hash of the ledger.
        seq (int): The sequence number of the ledger.
        ticket_count (int): The number of tickets in the ledger.
        ledger_entry_type (str): The type of the ledger entry.
        previous_fields_balance (int): The balance of the account before the last transaction.
        previous_txn_id (str): The hash of the previous transaction affecting this ledger entry.
        previous_txn_lgr_seq (int): The ledger sequence of the previous transaction.
        account (str): The XRPL account associated with this ledger entry.
        balance (int): The balance associated with the ledger entry.
        flags (int): Flags indicating the state of the ledger entry.
        owner_count (int): The count of owned objects.
        transaction_index (int): The transaction index in the ledger.
        transaction_result (str): The result of the transaction (e.g., "tesSUCCESS").
        delivered_amount (int): The amount delivered in the transaction.
        validated (bool): Whether the ledger entry is validated.
    """
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
    """
    A model representing XRPL transaction data.

    Attributes:
        ledger_entry (ForeignKey): The ledger entry associated with this transaction.
        account (str): The XRPL account initiating the transaction.
        deliver_max (int): The maximum amount to deliver in the transaction.
        destination (str): The destination account for the transaction.
        fee (int): The fee for the transaction.
        flags (int): Flags indicating transaction properties.
        last_ledger_sequence (int): The last ledger sequence number for the transaction.
        sequence (int): The sequence number of the transaction.
        signing_pub_key (str): The signing public key for the transaction.
        transaction_type (str): The type of the transaction (e.g., "Payment").
        txn_signature (str): The transaction's signature.
        date (datetime): The date and time of the transaction.
        ledger_index (int): The ledger index associated with the transaction.
    """
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
