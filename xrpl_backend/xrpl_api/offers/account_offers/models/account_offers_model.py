from django.db import models

from django.db import models
from django.utils.dateparse import parse_datetime

class OfferCancelResponse(models.Model):
    ctid = models.CharField(max_length=50, unique=True)
    hash = models.CharField(max_length=100)
    ledger_hash = models.CharField(max_length=100)
    ledger_index = models.IntegerField()
    close_time_iso = models.DateTimeField()
    validated = models.BooleanField()
    meta = models.JSONField()
    tx_json = models.JSONField()

    def __str__(self):
        return self.ctid

    class Meta:
        verbose_name = "Account Offer Transaction"
        verbose_name_plural = "Account Offer Transactions"
        db_table = 'xrpl_offer_cancel_data'
        indexes = [
            models.Index(fields=['hash'], name='tx_oc_hash_idx'),
            models.Index(fields=['ledger_index'], name='tx_oc_ledger_idx'),
        ]

class OfferCancelAffectedNode(models.Model):
    RESPONSE_TYPE_CHOICES = (
        ('DeletedNode', 'DeletedNode'),
        ('ModifiedNode', 'ModifiedNode'),
    )
    # Link each affected node to its parent response
    response = models.ForeignKey(OfferCancelResponse, on_delete=models.CASCADE, related_name="affected_nodes")
    node_type = models.CharField(max_length=20, choices=RESPONSE_TYPE_CHOICES)
    ledger_entry_type = models.CharField(max_length=50)
    ledger_index = models.CharField(max_length=100)
    final_fields = models.JSONField(null=True, blank=True)
    previous_fields = models.JSONField(null=True, blank=True)
    previous_txn_id = models.CharField(max_length=100, null=True, blank=True)
    previous_txn_lgr_seq = models.IntegerField(null=True, blank=True)

    def __str__(self):
        return f"{self.response.ctid} - {self.node_type} - {self.ledger_index}"

    class Meta:
        verbose_name = "Account Offer Affected Node Transaction"
        verbose_name_plural = "Account Offer Affected Node Transactions"
        db_table = 'xrpl_offer_cancel_affected_node_data'
        indexes = [
            models.Index(fields=['ledger_index'], name='tx_oca_ledger_idx'),
        ]