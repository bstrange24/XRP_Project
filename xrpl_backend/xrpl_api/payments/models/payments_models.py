from django.db import models

class PaymentTransactionData(models.Model):
    close_time_iso = models.DateTimeField()
    ctid = models.CharField(max_length=20)
    hash = models.CharField(max_length=64, unique=True)
    ledger_hash = models.CharField(max_length=64)
    ledger_index = models.BigIntegerField()
    transaction_index = models.IntegerField()
    transaction_result = models.CharField(max_length=20)
    delivered_amount = models.CharField(max_length=20)
    validated = models.BooleanField()
    transaction_hash = models.CharField(max_length=64, unique=True)
    sender = models.CharField(max_length=35)
    receiver = models.CharField(max_length=35)
    amount = models.DecimalField(max_digits=20, decimal_places=6)
    fee_drops = models.CharField(max_length=20)

    def __str__(self):
        return self.hash

    class Meta:
        db_table = 'xrpl_payment_transaction_data'

class PaymentTransactionMeta(models.Model):
    transaction = models.OneToOneField(PaymentTransactionData, on_delete=models.CASCADE, related_name='meta')
    transaction_index = models.IntegerField()
    transaction_result = models.CharField(max_length=20)
    delivered_amount = models.CharField(max_length=20)

    def __str__(self):
        return f"Meta for {self.transaction.hash}"

    class Meta:
        db_table = 'xrpl_payment_transaction_meta_data'

class PaymentTransactionAffectedNode(models.Model):
    meta = models.ForeignKey(PaymentTransactionMeta, on_delete=models.CASCADE, related_name='affected_nodes')
    ledger_entry_type = models.CharField(max_length=50)
    ledger_index = models.CharField(max_length=64)
    node_type = models.CharField(max_length=20, null=True, blank=True)  # Added field
    previous_txn_id = models.CharField(max_length=64, null=True, blank=True)  # Added field
    previous_txn_lgr_seq = models.CharField(max_length=64, null=True, blank=True)  # Added field

    def __str__(self):
        return f"AffectedNode {self.ledger_index} in {self.meta.transaction.hash}"

    class Meta:
        db_table = 'xrpl_payment_transaction_affected_node_data'

class PaymentTransactionFinalFields(models.Model):
    affected_node = models.OneToOneField(PaymentTransactionAffectedNode, on_delete=models.CASCADE, related_name='final_fields')
    account = models.CharField(max_length=35, null=True, blank=True)
    account_txn_id = models.CharField(max_length=64, null=True, blank=True)  # Allow NULL
    balance = models.CharField(max_length=20, null=True, blank=True)
    flags = models.IntegerField(null=True, blank=True)
    owner_count = models.IntegerField(null=True, blank=True)
    sequence = models.BigIntegerField(null=True, blank=True)

    def __str__(self):
        return f"FinalFields for {self.affected_node.ledger_index}"

    class Meta:
        db_table = 'xrpl_payment_transaction_final_fields_data'

class PaymentTransactionPreviousFields(models.Model):
    affected_node = models.OneToOneField(PaymentTransactionAffectedNode, on_delete=models.CASCADE, related_name='previous_fields')
    account_txn_id = models.CharField(max_length=64, null=True, blank=True)
    balance = models.CharField(max_length=20)
    sequence = models.BigIntegerField(null=True, blank=True)

    def __str__(self):
        return f"PreviousFields for {self.affected_node.ledger_index}"

    class Meta:
        db_table = 'xrpl_payment_transaction_previous_fields_data'

class PaymentTransactionTxJson(models.Model):
    transaction = models.OneToOneField(PaymentTransactionData, on_delete=models.CASCADE, related_name='tx_json')
    account = models.CharField(max_length=35)
    deliver_max = models.CharField(max_length=20, null=True, blank=True)
    destination = models.CharField(max_length=35)
    fee = models.CharField(max_length=20, null=True, blank=True)
    flags = models.IntegerField()
    last_ledger_sequence = models.BigIntegerField()
    sequence = models.BigIntegerField()
    signing_pub_key = models.CharField(max_length=66)
    transaction_type = models.CharField(max_length=20)
    txn_signature = models.CharField(max_length=128)
    date = models.BigIntegerField()
    ledger_index = models.BigIntegerField()

    def __str__(self):
        return f"TxJson for {self.transaction.hash}"

    class Meta:
        db_table = 'xrpl_payment_transaction_tx_json_data'