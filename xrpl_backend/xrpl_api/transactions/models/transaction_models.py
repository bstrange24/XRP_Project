from django.db import models

class TransactionHistoryData(models.Model):
    close_time_iso = models.DateTimeField()
    hash = models.CharField(max_length=64, unique=True)
    ledger_hash = models.CharField(max_length=64)
    ledger_index = models.BigIntegerField()
    validated = models.BooleanField()

    def __str__(self):
        return f"Transaction {self.hash} (Ledger {self.ledger_index})"

    class Meta:
        db_table = 'xrpl_transaction_history_data'


class TransactionMetaData(models.Model):
    ledger_transaction = models.OneToOneField(TransactionHistoryData, on_delete=models.CASCADE, related_name='meta')
    transaction_index = models.IntegerField()
    transaction_result = models.CharField(max_length=20)
    delivered_amount = models.CharField(max_length=20)

    def __str__(self):
        return f"Meta for {self.ledger_transaction.hash}"

    class Meta:
        db_table = 'xrpl_transaction_history_meta_data'


class TransactionAffectedNode(models.Model):
    meta_data = models.ForeignKey(TransactionMetaData, on_delete=models.CASCADE, related_name='affected_nodes')
    node_type = models.CharField(max_length=20)  # "ModifiedNode", "DeletedNode", or "CreatedNode"
    ledger_entry_type = models.CharField(max_length=20)
    ledger_index = models.CharField(max_length=64)
    previous_txn_id = models.CharField(max_length=64, null=True, blank=True)
    previous_txn_lgr_seq = models.BigIntegerField(null=True, blank=True)

    def __str__(self):
        return f"{self.node_type} {self.ledger_index}"

    class Meta:
        db_table = 'xrpl_transaction_history_affected_node_data'


class TransactionFinalFields(models.Model):
    affected_node = models.OneToOneField(TransactionAffectedNode, on_delete=models.CASCADE, related_name='final_fields')
    account = models.CharField(max_length=35, null=True, blank=True)
    balance = models.CharField(max_length=20, null=True, blank=True)
    flags = models.IntegerField(null=True, blank=True)
    owner_count = models.IntegerField(null=True, blank=True)
    sequence = models.BigIntegerField(null=True, blank=True)
    ticket_count = models.IntegerField(null=True, blank=True)
    index_next = models.CharField(max_length=20, null=True, blank=True)
    index_previous = models.CharField(max_length=20, null=True, blank=True)
    owner = models.CharField(max_length=35, null=True, blank=True)
    root_index = models.CharField(max_length=64, null=True, blank=True)
    owner_node = models.CharField(max_length=20, null=True, blank=True)
    previous_txn_id = models.CharField(max_length=64, null=True, blank=True)
    previous_txn_lgr_seq = models.BigIntegerField(null=True, blank=True)
    ticket_sequence = models.BigIntegerField(null=True, blank=True)

    def __str__(self):
        return f"FinalFields for {self.affected_node.ledger_index}"

    class Meta:
        db_table = 'xrpl_transaction_history_final_fields_data'


class TransactionPreviousFields(models.Model):
    affected_node = models.OneToOneField(TransactionAffectedNode, on_delete=models.CASCADE, related_name='previous_fields')
    balance = models.CharField(max_length=20, null=True, blank=True)
    owner_count = models.IntegerField(null=True, blank=True)
    sequence = models.BigIntegerField(null=True, blank=True)
    ticket_count = models.IntegerField(null=True, blank=True)

    def __str__(self):
        return f"PreviousFields for {self.affected_node.ledger_index}"

    class Meta:
        db_table = 'xrpl_transaction_history_previous_fields_data'


class TransactionNewFields(models.Model):
    affected_node = models.OneToOneField(TransactionAffectedNode, on_delete=models.CASCADE, related_name='new_fields')
    account = models.CharField(max_length=35, null=True, blank=True)
    balance = models.CharField(max_length=20, null=True, blank=True)
    sequence = models.BigIntegerField(null=True, blank=True)

    def __str__(self):
        return f"NewFields for {self.affected_node.ledger_index}"

    class Meta:
        db_table = 'xrpl_transaction_history_new_fields_data'


class TransactionJson(models.Model):
    ledger_transaction = models.OneToOneField(TransactionHistoryData, on_delete=models.CASCADE, related_name='tx_json')
    account = models.CharField(max_length=35)
    deliver_max = models.CharField(max_length=20, null=True, blank=True)
    destination = models.CharField(max_length=35)
    fee = models.CharField(max_length=10)
    flags = models.IntegerField()
    last_ledger_sequence = models.BigIntegerField()
    sequence = models.BigIntegerField()
    signing_pub_key = models.CharField(max_length=66)
    transaction_type = models.CharField(max_length=20)
    txn_signature = models.CharField(max_length=144)
    date = models.BigIntegerField()
    ledger_index = models.BigIntegerField()
    ticket_sequence = models.BigIntegerField(null=True, blank=True)

    def __str__(self):
        return f"TxJson for {self.ledger_transaction.hash}"

    class Meta:
        db_table = 'xrpl_transaction_history_json_data'