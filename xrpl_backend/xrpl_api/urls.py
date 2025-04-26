from django.urls import path

from .accounts.accounts import CreateTestAccounts, CreateTestAccount, GetAccountInfo, GetAccountInfoFromHash, \
    GetAccountBalance, GetAccountConfiguration, UpdateAccountConfiguration
from .checks.checks import GetChecks, CreateTokenCheck, CreateXrpCheck, CashTokenCheck, CashXrpCheck, CancelCheck, \
    GetChecksPage
from .currency.currency import SendCrossCurrency
from .did.did import GetDid, SetDid, DeleteDid
from .escrows.escrows import GetEscrowSequenceNumber, CancelEscrow, GetEscrowAccountInfo, FinishEscrowTimeBased, CreateEscrowTimeBased, CreateEscrowConditionBased, FinishEscrowConditionBased
from .ledger.ledger import GetLedgerInfo, GetServerInfo, GetXrpReserves
from .nft.nft import MintNft, GetAccountNft, BuyNft, CancelNftOffers, BurnNft, SellNft
from .offers.offers import SellAccountOffers, BuyAccountOffers, TakerAccountOffers, AccountStatus, \
    CancelAccountOffers, GetAccountOffers, SellAccountOffersNonXrp, GetAccountBookOffers
from .oracles.oracle import GetPriceOracle, CreatePriceOracle, DeletePriceOracles
from .payments.payments import SendXrpPayments, SendXrpPaymentsAndDeleteAccount, SendXrpPaymentAndBlackHoleAccount, \
    SendMemePayments
from .transactions.transactions import GetTransactionHistory, GetTransactionStatus
from .trust_lines.trust_line import GetAccountTrustLines, SetTrustLines, RemoveTrustLine

urlpatterns = [
    # XRPL API Endpoints
    # Each path is mapped to a specific view function that handles the related XRPL operation.
    # These endpoints allow interaction with the XRPL blockchain to perform operations like creating accounts,
    # retrieving wallet information, managing transactions, setting trust lines, and more.

    ################################# Accounts #################################
    ############################################################################
    # Endpoint for creating a new XRPL account.
    # Example: http://127.0.0.1:8000/xrpl/create-account/
    path('account/create/test-account/', CreateTestAccount.as_view(), name='create_test_account'),

    # Endpoint for creating a new XRPL account.
    # Example: http://127.0.0.1:8000/xrpl/create_multiple_account/
    path('account/create/multiple/test-account/', CreateTestAccounts.as_view(), name='create_multiple_test_accounts'),

    # Endpoint to fetch wallet information for a given wallet address.
    # Example: http://127.0.0.1:8000/xrpl/account-info/rMgaRbbZUBeoxwZevhv1mezuvA97eR4JHV/
    path('account/info/', GetAccountInfo.as_view(), name='get_account_info'),

    # Example: http://127.0.0.1:8000/xrpl/get-account-info-from-hash/?tx_hash=BED4E1E7CAB56600BA3C9597EAB606D9213B1E87B4FB7CE1F4885A3CC6755656
    path('account/info/from-hash/', GetAccountInfoFromHash.as_view() , name='get_account_info_from_hash'),

    # Endpoint to check the balance of a given wallet address.
    # Example: http://127.0.0.1:8000/xrpl/check-wallet-balance/rQGijrV8XYRseZAfjFvC9cDxxr58h9SvMY/
    path("account/balance/", GetAccountBalance.as_view(), name="check_account_balance"),

    # Endpoint to update account settings on the XRPL.
    # Example: http://127.0.0.1:8000/xrpl/config-account/?sender_seed=...&require_destination_tag=false
    path("account/config/update/", UpdateAccountConfiguration.as_view(), name="update_account_config"),

    # Endpoint to retrieve account settings on the XRPL.
    # Example: http://127.0.0.1:8000/xrpl/get-account-config/rMgaRbbZUBeoxwZevhv1mezuvA97eR4JHV/
    path("account/config/", GetAccountConfiguration.as_view(), name="get_account_config"),


    ################################# Transactions #################################
    ################################################################################
    # Endpoint to fetch transaction history with pagination.
    # Example: http://127.0.0.1:8000/xrpl/transaction-history-with-pag/rQGijrV8XYRseZAfjFvC9cDxxr58h9SvMY/
    path("transaction/history/", GetTransactionHistory.as_view(), name="get_transaction_history_with_pagination"),

    # Endpoint to check the status of a specific transaction.
    # Example: http://127.0.0.1:8000/xrpl/check-transaction-status/80AD9114C666200...
    path("transaction/status/", GetTransactionStatus.as_view(), name="check_transaction_status"),


    ################################# DID #################################
    #######################################################################
    # Endpoint to get DID for account
    path("did/get", GetDid.as_view(), name="get_did"),

    # Endpoint to set DID for account
    path("did/set", SetDid.as_view(), name="set_did"),

    # Endpoint to delete DID for account
    path("did/delete", DeleteDid.as_view(), name="delete_did"),


    ################################# Ledger #################################
    ##########################################################################
    # Endpoint to retrieve detailed information about a specific ledger.
    # Example: http://127.0.0.1:8000/xrpl/get-ledger-info/?ledger_index=validated
    # Example: http://127.0.0.1:8000/xrpl/get-ledger-info/?ledger_hash=<ledger_hash>
    path('ledger/ledger-info/', GetLedgerInfo.as_view(), name='get_ledger_info'),

    # Endpoint to get ledger information like version, uptime, and ledger status.
    # Example: http://127.0.0.1:8000/xrpl/get-server-info/
    path('ledger/server-info/', GetServerInfo.as_view(), name='get_server_info'),

    # Endpoint to fetch the reserve requirements for accounts on the XRPL.
    # Example: http://127.0.0.1:8000/xrpl/get-xrp-reserves/?wallet_address=r4ocA7HYdBXuvQPe1Dd7XUncZu8CT1QzkK
    path('ledger/xrp-reserves/', GetXrpReserves.as_view(), name='get_xrp_reserves'),


    ################################# TrustLines #################################
    ##############################################################################
    # Endpoint to retrieve all trust lines for a specific account.
    # Example: http://127.0.0.1:8000/xrpl/get-account-trust-lines/?account=r4ocA7HYdBXuvQPe1Dd7XUncZu8CT1QzkK
    path('trustline/account/info/', GetAccountTrustLines.as_view(), name='get_account_trust_lines'),

    # Endpoint to set a trust line for a specific issuer and currency.
    # Example: http://localhost:8000/set-trust-line/
    path('trustline/set/', SetTrustLines.as_view(), name='set_trust_line'),

    # Endpoint to remove a trust lines for a wallet address.
    # Example: http://127.0.0.1:8000/xrpl/get-trust-line/?wallet_address=r4ocA7HYdBXuvQPe1Dd7XUncZu8CT1QzkK
    path('trustline/remove/', RemoveTrustLine.as_view(), name='remove_trust_line'),


    ################################# Escrows #################################
    ###########################################################################
    # http://127.0.0.1:8000/xrpl/escrow/account/info/
    path('escrow/account/info/', GetEscrowAccountInfo.as_view(), name='get_escrow_account_info'),

    # http://127.0.0.1:8000/xrpl/escrow/account/sequence-number/
    path('escrow/account/sequence-number/', GetEscrowSequenceNumber.as_view(), name='get_escrow_sequence_number'),

    # http://127.0.0.1:8000/xrpl/escrow/create/time-based
    path('escrow/create/time-based', CreateEscrowTimeBased.as_view(), name='create_escrow_time_based'),

    # http://127.0.0.1:8000/xrpl/escrow/finish/time-based
    path('escrow/finish/time-based', FinishEscrowTimeBased.as_view(), name='finish_escrow_time_based'),

    # http://127.0.0.1:8000/xrpl/escrow/create/condition-based
    path('escrow/create/condition-based', CreateEscrowConditionBased.as_view(), name='create_escrow_condition_based'),

    # http://127.0.0.1:8000/xrpl/escrow/finish/condition-based
    path('escrow/finish/condition-based', FinishEscrowConditionBased.as_view(), name='finish_escrow_condition_based'),

    # http://127.0.0.1:8000/xrpl/escrow/cancel/
    path('escrow/cancel/', CancelEscrow.as_view(), name='cancel_escrow'),


    ################################# NFTS #################################
    ########################################################################
    # Example: http://127.0.0.1:8000/xrpl/nfts/mint/
    path('nfts/mint/', MintNft.as_view(), name='mint_nft'),

    # Example: http://127.0.0.1:8000/xrpl/nfts/account-info/r93BywwD6bg7TUNmq5nDjTvmEYuyLqGbyU
    path('nfts/account/info/', GetAccountNft.as_view(), name='get_account_nft'),

    # Example: http://127.0.0.1:8000/xrpl/nfts/burn
    path('nfts/burn/', BurnNft.as_view(), name='burn_nft'),

    # Example: http://127.0.0.1:8000/xrpl/nfts/sell/
    path('nfts/sell/', SellNft.as_view(), name='sell_nft'),

    # Example: http://127.0.0.1:8000/xrpl/nfts/buy
    path('nfts/buy/', BuyNft.as_view(), name='buy_nft'),

    # Example: http://127.0.0.1:8000/xrpl/nfts/buy
    path('nfts/cancel/', CancelNftOffers.as_view(), name='cancel_nft_offers'),


    ################################# Checks #################################
    ##########################################################################
    # Endpoint to fetch check details history with pagination.
    # http://127.0.0.1:8000/xrpl/checks/get
    path("checks/get", GetChecks.as_view(), name="get_checks"),

    # http://127.0.0.1:8000/xrpl/checks/get/page
    path("checks/get/page", GetChecksPage.as_view(), name="get_checks_with_pagination"),

    # http://127.0.0.1:8000/xrpl/checks/create/token
    path("checks/create/token", CreateTokenCheck.as_view(), name="create_token_check"),

    # http://127.0.0.1:8000/xrpl/checks/create/xrp
    path("checks/create/xrp", CreateXrpCheck.as_view(), name="create_xrp_check"),

    # http://127.0.0.1:8000/xrpl/checks/cash/token
    path("checks/cash/token", CashTokenCheck.as_view(), name="cash_token_check"),

    # http://127.0.0.1:8000/xrpl/checks/cash/xrp
    path("checks/cash/xrp", CashXrpCheck.as_view(), name="cash_xrp_check"),

    # http://127.0.0.1:8000/xrpl/checks/cancel
    path("checks/cancel", CancelCheck.as_view(), name="cancel_check"),


    ################################# Oracles #################################
    ###########################################################################
    # http://127.0.0.1:8000/xrpl/oracle/price/get
    path("oracle/price/get", GetPriceOracle.as_view(), name="get_price_oracle"),

    # http://127.0.0.1:8000/xrpl/oracle/price/create
    path("oracle/price/create", CreatePriceOracle.as_view(), name="create_price_get_oracle"),

    # http://127.0.0.1:8000/xrpl/oracle/price/delete
    path("oracle/price/delete", DeletePriceOracles.as_view(), name="delete_price_oracle"),


    ################################# Payments #################################
    ############################################################################
    # http://127.0.0.1:8000/xrpl/payment/send-xrp/
    path('payment/send-xrp/', SendXrpPayments.as_view(), name='send_xrp_payment'),

    # http://127.0.0.1:8000/xrpl/payment/send-meme-payment/
    path('payment/send-meme-payment/', SendMemePayments.as_view(), name='send_meme_payment'),

    # Endpoint to send payment and delete the sender's wallet account.
    # http://127.0.0.1:8000/xrpl/payment/send-xrp/delete-account/
    path('payment/send-xrp/delete-account/', SendXrpPaymentsAndDeleteAccount.as_view(), name='send_xrp_payment_and_delete_account'),

    # Endpoint to blackhole all XRP in a wallet.
    # http://127.0.0.1:8000/xrpl/payment/send-xrp/black-hole-account/
    path('payment/send-xrp/black-hole-account/', SendXrpPaymentAndBlackHoleAccount.as_view(), name='send_xrp_payment_and_black_hole_account'),





    ################################# Offers #################################
    # Endpoint to get active offers on an account.
    path('account/offers/sell', SellAccountOffers.as_view(), name='sell_account_offers'),
    path('account/offers/sell/non_xrp', SellAccountOffersNonXrp.as_view(), name='sell_account_offers_non_xrp'),
    path('account/offers/buy', BuyAccountOffers.as_view(), name='buy_account_offers'),
    path('account/offers/taker', TakerAccountOffers.as_view(), name='taker_account_offers'),
    path('account/offers/cancel', CancelAccountOffers.as_view(), name='cancel_account_offers'),
    path('account/offers/get', AccountStatus.as_view(), name='get_account_status'),
    path('account/offers/get/page', GetAccountOffers.as_view(), name='get_account_offers'),
    path('account/offers/get/book/offer', GetAccountBookOffers.as_view(), name='get_account_book_offers'),


    ################################# Currency Payments #################################
    # Endpoint to send currency payments.
    path('payment/send-cross-currency/', SendCrossCurrency.as_view(), name='send_cross_currency_payment'),




]
