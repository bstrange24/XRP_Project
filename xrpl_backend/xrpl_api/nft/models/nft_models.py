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
        db_table = 'xrpl_nft_mint_data'

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
        db_table = 'xrpl_nft_mint_affected_nodes_data'

class NFToken(models.Model):
    affected_node = models.ForeignKey(NFTAffectedNode, related_name='nftokens', on_delete=models.CASCADE)
    nftoken_id = models.CharField(max_length=64)
    final_nftoken = models.JSONField(null=True, blank=True)
    previous_nftoken = models.JSONField(null=True, blank=True)

    def __str__(self):
        return self.nftoken_id

    class Meta:
        db_table = 'xrpl_nft_mint_tokens_data'


class NFTSellTransaction(models.Model):
    close_time_iso = models.DateTimeField()
    ctid = models.CharField(max_length=16)
    hash = models.CharField(max_length=64, unique=True)
    ledger_hash = models.CharField(max_length=64)
    ledger_index = models.BigIntegerField()
    validated = models.BooleanField()

    class Meta:
        db_table = 'xrpl_nft_sell_data'
        indexes = [
            models.Index(fields=['hash']),
            models.Index(fields=['ledger_index']),
        ]

    def __str__(self):
        return f"Transaction {self.hash[:8]}... at ledger {self.ledger_index}"


class NFTSellTransactionJson(models.Model):
    transaction = models.OneToOneField(NFTSellTransaction, on_delete=models.CASCADE, related_name='tx_json')
    account = models.CharField(max_length=35)
    amount = models.CharField(max_length=20)
    fee = models.CharField(max_length=10)
    flags = models.IntegerField(null=True, blank=True, default=None)  # Changed to allow NULL
    last_ledger_sequence = models.BigIntegerField()
    nftoken_id = models.CharField(max_length=64)
    sequence = models.BigIntegerField()
    signing_pub_key = models.CharField(max_length=66)
    transaction_type = models.CharField(max_length=20)
    txn_signature = models.CharField(max_length=128)
    date = models.BigIntegerField()

    class Meta:
        db_table = 'xrpl_nft_sell_tx_json_data'
        indexes = [
            models.Index(fields=['account']),
            models.Index(fields=['transaction']),
        ]

    def __str__(self):
        return f"TxJson for {self.transaction.hash[:8]}..."


class NFTSellAffectedNode(models.Model):
    transaction = models.ForeignKey(NFTSellTransaction, on_delete=models.CASCADE, related_name='affected_nodes')
    node_type = models.CharField(max_length=20)
    ledger_entry_type = models.CharField(max_length=20)
    ledger_index = models.CharField(max_length=64)
    new_fields = models.JSONField(null=True, blank=True)
    final_fields = models.JSONField(null=True, blank=True)
    previous_fields = models.JSONField(null=True, blank=True)
    previous_txn_id = models.CharField(max_length=64, null=True, blank=True)
    previous_txn_lgr_seq = models.BigIntegerField(null=True, blank=True)

    class Meta:
        db_table = 'xrpl_nft_sell_affected_nodes_data'
        indexes = [
            models.Index(fields=['transaction']),
            models.Index(fields=['ledger_index']),
        ]

    def __str__(self):
        return f"{self.node_type} - {self.ledger_entry_type} for {self.transaction.hash[:8]}..."


class NFTBurnTransaction(models.Model):
    close_time_iso = models.DateTimeField()
    ctid = models.CharField(max_length=16)
    hash = models.CharField(max_length=64, unique=True)
    ledger_hash = models.CharField(max_length=64)
    ledger_index = models.BigIntegerField()
    validated = models.BooleanField()

    class Meta:
        db_table = 'xrpl_nft_burn_data'
        indexes = [
            models.Index(fields=['hash']),
            models.Index(fields=['ledger_index']),
        ]

    def __str__(self):
        return f"Transaction {self.hash[:8]}... at ledger {self.ledger_index}"


class NFTBurnTransactionJson(models.Model):
    transaction = models.OneToOneField(NFTBurnTransaction, on_delete=models.CASCADE, related_name='tx_json')
    account = models.CharField(max_length=35)
    fee = models.CharField(max_length=10)
    flags = models.IntegerField(null=True, blank=True, default=None)
    last_ledger_sequence = models.BigIntegerField()
    nftoken_sell_offer = models.CharField(max_length=64, null=True, blank=True)  # Specific to NFTokenAcceptOffer
    sequence = models.BigIntegerField()
    signing_pub_key = models.CharField(max_length=66)
    transaction_type = models.CharField(max_length=20)
    txn_signature = models.CharField(max_length=128)
    date = models.BigIntegerField()

    class Meta:
        db_table = 'xrpl_nft_burn_tx_json_data'
        indexes = [
            models.Index(fields=['account']),
            models.Index(fields=['transaction']),
        ]

    def __str__(self):
        return f"TxJson for {self.transaction.hash[:8]}..."


class NFTBurnAffectedNode(models.Model):
    transaction = models.ForeignKey(NFTBurnTransaction, on_delete=models.CASCADE, related_name='affected_nodes')
    node_type = models.CharField(max_length=20)  # ModifiedNode or DeletedNode
    ledger_entry_type = models.CharField(max_length=20)
    ledger_index = models.CharField(max_length=64)

    # Common fields for all node types
    flags = models.IntegerField(null=True, blank=True)
    nftoken_id = models.CharField(max_length=64, null=True, blank=True)
    previous_txn_id = models.CharField(max_length=64, null=True, blank=True)
    previous_txn_lgr_seq = models.BigIntegerField(null=True, blank=True)

    # NFTokenPage specific fields
    nftokens_final = models.JSONField(null=True, blank=True)  # Final NFTokens array
    nftokens_previous = models.JSONField(null=True, blank=True)  # Previous NFTokens array
    next_page_min = models.CharField(max_length=64, null=True, blank=True)
    previous_page_min = models.CharField(max_length=64, null=True, blank=True)

    # NFTokenOffer specific fields
    amount = models.CharField(max_length=20, null=True, blank=True)
    owner = models.CharField(max_length=35, null=True, blank=True)
    nftoken_offer_node = models.CharField(max_length=1, null=True, blank=True)
    owner_node = models.CharField(max_length=1, null=True, blank=True)

    # DirectoryNode specific fields
    root_index = models.CharField(max_length=64, null=True, blank=True)

    # AccountRoot specific fields
    account = models.CharField(max_length=35, null=True, blank=True)
    balance = models.CharField(max_length=20, null=True, blank=True)
    burned_nftokens = models.IntegerField(null=True, blank=True)
    first_nftoken_sequence = models.BigIntegerField(null=True, blank=True)
    minted_nftokens = models.IntegerField(null=True, blank=True)
    owner_count = models.IntegerField(null=True, blank=True)
    sequence = models.BigIntegerField(null=True, blank=True)

    # Previous fields for modified nodes
    previous_fields = models.JSONField(null=True, blank=True)

    class Meta:
        db_table = 'xrpl_nft_burn_affected_nodes_data'
        indexes = [
            models.Index(fields=['transaction']),
            models.Index(fields=['ledger_index']),
            models.Index(fields=['nftoken_id']),
        ]

    def __str__(self):
        return f"{self.node_type} - {self.ledger_entry_type} for {self.transaction.hash[:8]}..."


class NFTBuyTransaction(models.Model):
    account = models.CharField(max_length=35)
    ledger_current_index = models.BigIntegerField()
    validated = models.BooleanField()
    timestamp = models.DateTimeField(auto_now_add=True)  # To track when this snapshot was recorded

    class Meta:
        db_table = 'xrpl_nft_buy_transaction_data'
        indexes = [
            models.Index(fields=['account']),
            models.Index(fields=['ledger_current_index']),
        ]
        unique_together = ('account', 'ledger_current_index')  # Prevent duplicate snapshots

    def __str__(self):
        return f"NFT Snapshot for {self.account} at ledger {self.ledger_current_index}"


class NFTBuyTransactionData(models.Model):
    snapshot = models.ForeignKey(NFTBuyTransaction, on_delete=models.CASCADE, related_name='nfts')
    flags = models.IntegerField()
    issuer = models.CharField(max_length=35)
    nftoken_id = models.CharField(max_length=64, unique=True)
    nftoken_taxon = models.IntegerField()
    nft_serial = models.BigIntegerField()
    transfer_fee = models.IntegerField(null=True, blank=True)  # Optional field

    class Meta:
        db_table = 'xrpl_nft_buy_data'
        indexes = [
            models.Index(fields=['snapshot']),
            models.Index(fields=['nftoken_id']),
            models.Index(fields=['issuer']),
        ]

    def __str__(self):
        return f"NFT {self.nftoken_id} owned by {self.snapshot.account}"