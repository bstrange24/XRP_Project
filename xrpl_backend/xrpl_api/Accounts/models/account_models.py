from django.db import models
from django.db.models import JSONField


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


class AccountConfigurationTransaction(models.Model):
    """
    Represents an XRPL account transaction response with additional account settings.
    """
    close_time_iso = models.CharField(max_length=25)  # ISO 8601 timestamp, e.g., "2025-02-21T15:58:12Z"
    ctid = models.CharField(max_length=16)  # e.g., "C04CD87700000001"
    hash = models.CharField(max_length=64, unique=True)  # Transaction hash, unique identifier
    ledger_hash = models.CharField(max_length=64)  # Ledger hash
    ledger_index = models.BigIntegerField()  # Ledger sequence number
    validated = models.BooleanField(default=True)  # Validation status
    created_at = models.DateTimeField(auto_now_add=True, null=True)  # Record creation time

    # Additional ASF (Account Set Flags) fields
    asf_account_txn_id = models.BooleanField(null=True, blank=True)  # asfAccountTxnID
    asf_allow_trustline_clawback = models.BooleanField(null=True, blank=True)  # asfAllowTrustLineClawback
    asf_authorized_nftoken_minter = models.BooleanField(null=True, blank=True)  # asfAuthorizedNFTokenMinter
    asf_default_ripple = models.BooleanField(null=True, blank=True)  # asfDefaultRipple
    asf_deposit_auth = models.BooleanField(null=True, blank=True)  # asfDepositAuth
    asf_disable_master = models.BooleanField(null=True, blank=True)  # asfDisableMaster
    asf_disable_incoming_check = models.BooleanField(null=True, blank=True)  # asfDisallowIncomingCheck
    asf_disable_incoming_nftoken_offer = models.BooleanField(null=True, blank=True)  # asfDisallowIncomingNFTokenOffer
    asf_disable_incoming_paychan = models.BooleanField(null=True, blank=True)  # asfDisallowIncomingPayChan
    asf_disable_incoming_trustline = models.BooleanField(null=True, blank=True)  # asf_disable_incoming_trustline
    asf_disallow_xrp = models.BooleanField(null=True, blank=True)  # asfDisallowXRP
    asf_global_freeze = models.BooleanField(null=True, blank=True)  # asfGlobalFreeze
    asf_no_freeze = models.BooleanField(null=True, blank=True)  # asfNoFreeze
    asf_require_auth = models.BooleanField(null=True, blank=True)  # asfRequireAuth
    asf_require_dest = models.BooleanField(null=True, blank=True)  # asfRequireDest

    def __str__(self):
        return f"Transaction {self.hash} (Ledger {self.ledger_index})"

    class Meta:
        verbose_name = "Account Configuration Transaction"
        verbose_name_plural = "Account Configuration Transactions"
        db_table = 'xrpl_account_configuration_data'
        indexes = [
            models.Index(fields=['hash'], name='tx_hash_idx'),
            models.Index(fields=['ledger_index'], name='tx_ledger_idx'),
        ]


class AccountConfigurationTransactionMeta(models.Model):
    """
    Metadata for an XRPL account transaction.
    """
    transaction = models.OneToOneField(AccountConfigurationTransaction, on_delete=models.CASCADE, related_name="meta")
    transaction_index = models.IntegerField()
    transaction_result = models.CharField(max_length=20)

    def __str__(self):
        return f"Meta for {self.transaction.hash}"

    class Meta:
        db_table = 'xrpl_account_configuration_meta_data'


class AffectedNode(models.Model):
    """
    Affected node details within TransactionMeta.
    """
    meta = models.ForeignKey(AccountConfigurationTransactionMeta, on_delete=models.CASCADE, related_name="affected_nodes")
    ledger_entry_type = models.CharField(max_length=20)
    ledger_index = models.CharField(max_length=64)
    final_fields = JSONField()
    previous_fields = JSONField(null=True, blank=True)
    previous_txn_id = models.CharField(max_length=64, null=True, blank=True)
    previous_txn_lgr_seq = models.BigIntegerField(null=True, blank=True)

    def __str__(self):
        return f"Affected Node {self.ledger_index} for {self.meta.transaction.hash}"

    class Meta:
        db_table = 'xrpl_account_configuration_affected_nodes_data'


class TxJson(models.Model):
    """
    Transaction JSON details for an XRPL account transaction.
    """
    transaction = models.OneToOneField(AccountConfigurationTransaction, on_delete=models.CASCADE, related_name="tx_json")
    account = models.CharField(max_length=35)
    fee = models.CharField(max_length=10)
    flags = models.IntegerField()
    last_ledger_sequence = models.BigIntegerField()
    sequence = models.BigIntegerField()
    set_flag = models.IntegerField(null=True, blank=True)
    signing_pub_key = models.CharField(max_length=66)
    transaction_type = models.CharField(max_length=20)
    txn_signature = models.CharField(max_length=128)
    date = models.BigIntegerField()
    ledger_index = models.BigIntegerField()

    def __str__(self):
        return f"TxJson for {self.transaction.hash}"

    class Meta:
        db_table = 'xrpl_account_configuration_tx_json_data'