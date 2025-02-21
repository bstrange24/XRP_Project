from django.db import models

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


class Ledger(models.Model):
    """
    Represents ledger information fetched from the XRPL.
    """
    account_hash = models.CharField(max_length=64)  # 64-char hex string for account state hash
    close_flags = models.IntegerField(default=0)  # Flags for ledger close
    close_time = models.BigIntegerField()  # Unix timestamp (seconds since epoch)
    close_time_human = models.CharField(max_length=30)  # Human-readable UTC time
    close_time_iso = models.CharField(max_length=25)  # ISO 8601 format
    close_time_resolution = models.IntegerField()  # Resolution in seconds
    closed = models.BooleanField(default=True)  # Ledger closed status
    ledger_hash = models.CharField(max_length=64)  # 64-char hex string for ledger identifier
    ledger_index = models.BigIntegerField(unique=True)  # Ledger sequence number, unique
    parent_close_time = models.BigIntegerField()  # Previous ledger’s close time
    parent_hash = models.CharField(max_length=64)  # 64-char hex string for parent ledger
    total_coins = models.CharField(max_length=20)  # String for large total XRP supply
    transaction_hash = models.CharField(max_length=64)  # 64-char hex string for transactions
    validated = models.BooleanField(default=True)  # Ledger validation status
    created_at = models.DateTimeField(auto_now_add=True)  # When this record was added

    def __str__(self):
        return f"Ledger {self.ledger_index} - {self.ledger_hash}"

    class Meta:
        verbose_name = "Ledger"
        verbose_name_plural = "Ledgers"
        indexes = [
            models.Index(fields=['ledger_index'], name='ledger_index_idx'),
            models.Index(fields=['ledger_hash'], name='ledger_hash_idx'),
        ]
        db_table = 'xrpl_ledger_data'


class ServerInfo(models.Model):
    """
    Represents server information fetched from an XRPL node.
    Corresponds to the 'ledger_info.info' object in the response.
    """
    build_version = models.CharField(max_length=10)  # e.g., "2.3.1"
    complete_ledgers = models.CharField(max_length=20)  # e.g., "6-5036926"
    hostid = models.CharField(max_length=10)  # e.g., "TUN"
    initial_sync_duration_us = models.BigIntegerField()  # Microseconds
    io_latency_ms = models.IntegerField()  # Milliseconds
    jq_trans_overflow = models.CharField(max_length=10)  # Stringified integer, e.g., "0"
    load_factor = models.IntegerField()  # e.g., 1
    network_id = models.IntegerField()  # e.g., 1
    peer_disconnects = models.CharField(max_length=10)  # Stringified integer, e.g., "75031"
    peer_disconnects_resources = models.CharField(max_length=10)  # Stringified integer, e.g., "2533"
    peers = models.IntegerField()  # e.g., 87
    pubkey_node = models.CharField(max_length=35)  # XRPL public key, e.g., "n9KEk3..."
    server_state = models.CharField(max_length=20)  # e.g., "full"
    server_state_duration_us = models.BigIntegerField()  # Microseconds
    time = models.CharField(max_length=30)  # UTC timestamp, e.g., "2025-Feb-21 16:46:13.454362 UTC"
    uptime = models.BigIntegerField()  # Seconds
    validation_quorum = models.IntegerField()  # e.g., 5
    created_at = models.DateTimeField(auto_now_add=True, null=True)  # When this record was added

    def __str__(self):
        return f"Server {self.hostid} - {self.server_state} ({self.time})"

    class Meta:
        verbose_name = "Server Info"
        verbose_name_plural = "Server Info Records"
        db_table = 'xrpl_server_info'


class LastClose(models.Model):
    """
    Nested 'last_close' data for ServerInfo.
    """
    server_info = models.OneToOneField(ServerInfo, on_delete=models.CASCADE, related_name="last_close")
    converge_time_s = models.FloatField()  # Seconds, e.g., 3.001
    proposers = models.IntegerField()  # e.g., 6

    def __str__(self):
        return f"Last Close for {self.server_info.hostid}"


class Port(models.Model):
    """
    Nested 'ports' data for ServerInfo (multiple ports per server).
    """
    server_info = models.ForeignKey(ServerInfo, on_delete=models.CASCADE, related_name="ports")
    port = models.CharField(max_length=5)  # e.g., "2459"
    protocol = models.JSONField()  # List of protocols, e.g., ["peer"]

    def __str__(self):
        return f"Port {self.port} for {self.server_info.hostid}"


class StateAccountingEntry(models.Model):
    """
    Nested 'state_accounting' data for ServerInfo (one entry per state).
    """
    STATE_CHOICES = [
        ('connected', 'Connected'),
        ('disconnected', 'Disconnected'),
        ('full', 'Full'),
        ('syncing', 'Syncing'),
        ('tracking', 'Tracking'),
    ]

    server_info = models.ForeignKey(ServerInfo, on_delete=models.CASCADE, related_name="state_accounting")
    state = models.CharField(max_length=20, choices=STATE_CHOICES)  # e.g., "full"
    duration_us = models.BigIntegerField()  # Microseconds
    transitions = models.IntegerField()  # e.g., 1

    def __str__(self):
        return f"{self.state} for {self.server_info.hostid}"


class ValidatedLedger(models.Model):
    """
    Nested 'validated_ledger' data for ServerInfo.
    """
    server_info = models.OneToOneField(ServerInfo, on_delete=models.CASCADE, related_name="validated_ledger")
    age = models.IntegerField()  # Seconds since last validation, e.g., 2
    base_fee_xrp = models.FloatField()  # XRP fee, e.g., 0.00001
    hash = models.CharField(max_length=64)  # 64-char hex string
    reserve_base_xrp = models.IntegerField()  # XRP reserve, e.g., 1
    reserve_inc_xrp = models.FloatField()  # Incremental reserve, e.g., 0.2
    seq = models.BigIntegerField()  # Ledger sequence, e.g., 5036926

    def __str__(self):
        return f"Validated Ledger {self.seq} for {self.server_info.hostid}"