# app/models.py
from django.db import models

class EscrowTransaction(models.Model):
    """Main model for the escrow transaction response."""
    close_time_iso = models.DateTimeField()
    ctid = models.CharField(max_length=16)
    hash = models.CharField(max_length=64, unique=True)  # Transaction hash as unique identifier
    ledger_hash = models.CharField(max_length=64)
    ledger_index = models.PositiveIntegerField()
    validated = models.BooleanField(default=True)
    transaction_result = models.CharField(max_length=20)  # e.g., "tesSUCCESS"
    transaction_index = models.PositiveIntegerField()

    # tx_json fields (flattened into main model for simplicity)
    account = models.CharField(max_length=35)  # XRPL address
    amount = models.CharField(max_length=20)  # XRP in drops
    cancel_after = models.PositiveIntegerField(null=True, blank=True)
    condition = models.CharField(max_length=72, null=True, blank=True)
    fulfillment = models.CharField(max_length=72, null=True, blank=True)
    destination = models.CharField(max_length=35)
    fee = models.CharField(max_length=10)
    finish_after = models.PositiveIntegerField(null=True, blank=True)
    flags = models.PositiveIntegerField(default=0)
    last_ledger_sequence = models.PositiveIntegerField()
    sequence = models.PositiveIntegerField()
    signing_pub_key = models.CharField(max_length=66)
    transaction_type = models.CharField(max_length=20)  # e.g., "EscrowCreate"
    txn_signature = models.CharField(max_length=140)
    date = models.PositiveIntegerField()  # Ripple time

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'xrpl_escrow_transaction_data'
        verbose_name = 'Escrow Transaction'
        verbose_name_plural = 'Escrow Transactions'
        indexes = [
            models.Index(fields=['account'], name='idx_escrow_account'),
            models.Index(fields=['destination'], name='idx_escrow_destination'),
            models.Index(fields=['close_time_iso'], name='idx_escrow_close_time'),
            models.Index(fields=['condition'], name='idx_escrow_condition'),
            models.Index(fields=['ledger_index'], name='idx_escrow_ledger_index'),
            models.Index(fields=['account', 'close_time_iso'], name='idx_escrow_account_time'),
        ]

    def __str__(self):
        return f"Escrow {self.hash} - {self.account}"


class EscrowTransactionAffectedNode(models.Model):
    """Model for each affected node in the meta.AffectedNodes list."""
    escrow_transaction = models.ForeignKey(EscrowTransaction, on_delete=models.CASCADE, related_name='affected_nodes')
    ledger_entry_type = models.CharField(max_length=20)  # e.g., "AccountRoot", "Escrow"
    ledger_index = models.CharField(max_length=64)

    # Common fields for ModifiedNode and CreatedNode
    account = models.CharField(max_length=35, null=True, blank=True)
    amount = models.CharField(max_length=20, null=True, blank=True)  # For CreatedNode (Escrow)
    balance = models.CharField(max_length=20, null=True, blank=True)  # For AccountRoot
    flags = models.PositiveIntegerField(null=True, blank=True)
    owner = models.CharField(max_length=35, null=True, blank=True)
    owner_count = models.PositiveIntegerField(null=True, blank=True)
    sequence = models.PositiveIntegerField(null=True, blank=True)
    root_index = models.CharField(max_length=64, null=True, blank=True)
    condition = models.CharField(max_length=72, null=True, blank=True)  # For Escrow
    destination = models.CharField(max_length=35, null=True, blank=True)  # For Escrow
    cancel_after = models.PositiveIntegerField(null=True, blank=True)
    finish_after = models.PositiveIntegerField(null=True, blank=True)

    # Previous fields (for ModifiedNode)
    previous_balance = models.CharField(max_length=20, null=True, blank=True)
    previous_owner_count = models.PositiveIntegerField(null=True, blank=True)
    previous_sequence = models.PositiveIntegerField(null=True, blank=True)
    previous_txn_id = models.CharField(max_length=64, null=True, blank=True)
    previous_txn_lgr_seq = models.PositiveIntegerField(null=True, blank=True)

    node_type = models.CharField(max_length=20)  # "ModifiedNode" or "CreatedNode"

    class Meta:
        db_table = 'xrpl_escrow_transaction_affected_nodes'
        verbose_name = 'Affected Node'
        verbose_name_plural = 'Affected Nodes'
        indexes = [
            models.Index(fields=['escrow_transaction'], name='idx_affected_tx'),
            models.Index(fields=['account'], name='idx_affected_account'),
            models.Index(fields=['node_type'], name='idx_affected_node_type'),
            models.Index(fields=['ledger_index'], name='idx_affected_ledger_index'),
        ]

    def __str__(self):
        return f"{self.node_type} - {self.ledger_index}"