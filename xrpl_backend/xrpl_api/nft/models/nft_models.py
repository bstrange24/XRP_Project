from django.db import models

class NFTTransaction(models.Model):
    close_time_iso = models.DateTimeField()
    ctid = models.CharField(max_length=32)
    hash = models.CharField(max_length=64, unique=True)
    ledger_hash = models.CharField(max_length=64)
    ledger_index = models.BigIntegerField()
    transaction_index = models.IntegerField(null=True, blank=True)
    transaction_result = models.CharField(max_length=20, null=True, blank=True)
    nftoken_id = models.CharField(max_length=64, null=True, blank=True)
    account = models.CharField(max_length=35)
    fee = models.CharField(max_length=20)
    flags = models.IntegerField()
    last_ledger_sequence = models.BigIntegerField()
    nftoken_taxon = models.IntegerField()
    sequence = models.BigIntegerField()
    signing_pub_key = models.CharField(max_length=66)
    transaction_type = models.CharField(max_length=20)
    txn_signature = models.CharField(max_length=128)
    date = models.BigIntegerField()
    validated = models.BooleanField()

    def __str__(self):
        return f"{self.transaction_type} - {self.hash}"

    class Meta:
        verbose_name = "Mint NFT"
        verbose_name_plural = "Mint NFT"
        indexes = [
            models.Index(fields=['transaction_type'], name='transaction_type_idx'),
        ]
        db_table = 'xrpl_mint_nft_data'

class NFTAffectedNode(models.Model):
    transaction = models.ForeignKey(NFTTransaction, related_name='affected_nodes', on_delete=models.CASCADE)
    ledger_entry_type = models.CharField(max_length=50)
    ledger_index = models.CharField(max_length=64)
    final_fields = models.JSONField(null=True, blank=True)
    previous_fields = models.JSONField(null=True, blank=True)
    previous_txn_id = models.CharField(max_length=64, null=True, blank=True)
    previous_txn_lgr_seq = models.BigIntegerField(null=True, blank=True)

    def __str__(self):
        return f"{self.ledger_entry_type} - {self.ledger_index}"

    class Meta:
        db_table = 'xrpl_mint_nft_affected_nodes_data'

class NFToken(models.Model):
    affected_node = models.ForeignKey(NFTAffectedNode, related_name='nftokens', on_delete=models.CASCADE)
    nftoken_id = models.CharField(max_length=64)
    final_nftoken = models.JSONField(null=True, blank=True)
    previous_nftoken = models.JSONField(null=True, blank=True)

    def __str__(self):
        return self.nftoken_id

    class Meta:
        db_table = 'xrpl_mint_nft_tokens_data'