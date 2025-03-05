from django.urls import path, reverse

from .accounts.accounts import CreateTestAccounts, CreateTestAccount, GetAccountInfo, GetAccountInfoFromHash, \
    GetAccountBalance, GetAccountConfiguration, UpdateAccountConfiguration
from .currency.currency import SendCrossCurrency
from .escrows.escrows import CreateEscrow, GetEscrowSequenceNumber, CancelEscrow, FinishEscrow, GetEscrowAccountInfo
from .ledger.ledger import GetLedgerInfo, GetServerInfo, GetXrpReserves
from .nft.nft import MintNft, GetAccountNft, BuyNft, CancelNftOffers, BurnNft, SellNft
from .offers.account_offers.account_offers import GetAccountOffers, CancelAccountOffers
from .offers.book_offers.book_offers import GetBookOffers, CreateBookOffer
from .payments.payments import SendXrpPayments, SendXrpPaymentsAndDeleteAccount, SendXrpPaymentAndBlackHoleAccount
from .test.offers_grok import CreateSellBookOffersGrok, BuyBookOffersGrok
from .transactions.transactions import GetTransactionHistory, GetTransactionStatus
from .trust_lines.trust_line import GetAccountTrustLines, SetTrustLines, RemoveTrustLine

urlpatterns = [
    # XRPL API Endpoints
    # Each path is mapped to a specific view function that handles the related XRPL operation.
    # These endpoints allow interaction with the XRPL blockchain to perform operations like creating accounts,
    # retrieving wallet information, managing transactions, setting trust lines, and more.


    ################################# Accounts #################################
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



    ################################# Offers #################################
    # Endpoint to get all pairs in the order book
    # http://127.0.0.1:8000/xrpl/get-book-offers/?taker_gets_currency=XRP&taker_pays_currency=USD&taker_pays_issuer=rIssuerAddress&page=1&page_size=10
    path('get-book-offers/', GetBookOffers.as_view(), name='get_book_offers'),

    # Endpoint to get active offers on an account.
    # Example: http://127.0.0.1:8000/xrpl/get-account-offers/?wallet_address=r4ocA7HYdBXuvQPe1Dd7XUncZu8CT1QzkK
    path('account/offers/', GetAccountOffers.as_view(), name='get_account_offers'),

    path("create-book-offers-easy-grok/", CreateSellBookOffersGrok.as_view(), name="create_offer_view"),
    path("create-buy-book-offers-easy-grok/", BuyBookOffersGrok.as_view(), name="buy_offer_view"),


    # Endpoint to cancel an offer on an account.
    # Example: http://127.0.0.1:8000/xrpl/create-book-offer/?wallet_address=raGfE6LfRpUXNjmSYRqUyhWkU429XeYgEg&currency=TST&value=25&sendes_seed=sEdS82hNoMmkM7GottuGAFVecYTxRPH
    # path("create-book-offers/", CreateBookOffer.as_view(), name="create_book_offers"),
    path("create-book-offers-easy/", CreateBookOffer.as_view(), name="create_book_offers_easy"),

    # Endpoint to get created offers on an account.
    # Example: http://127.0.0.1:8000/xrpl/cancel-account-offers/?sender_seed=sEdVWMNWboHkJmE5sWC69Y4KghW1KXC
    path("cancel-account-offers/", CancelAccountOffers.as_view(), name="cancel_account_offers"),



    ################################# Transactions #################################
    # Endpoint to fetch transaction history with pagination.
    # Example: http://127.0.0.1:8000/xrpl/transaction-history-with-pag/rQGijrV8XYRseZAfjFvC9cDxxr58h9SvMY/
    path("transaction/history/", GetTransactionHistory.as_view(), name="get_transaction_history_with_pagination"),

    # Endpoint to check the status of a specific transaction.
    # Example: http://127.0.0.1:8000/xrpl/check-transaction-status/80AD9114C666200...
    path("transaction/status/", GetTransactionStatus.as_view(), name="check_transaction_status"),



    ################################# Payments #################################
    # Endpoint to send a payment transaction from one wallet to another.
    # Example: http://127.0.0.1:8000/xrpl/send-payment/?sender_seed=...&receiver=...&amount=10
    path('payment/send-xrp/', SendXrpPayments.as_view(), name='send_xrp_payment'),

    # Endpoint to send payment and delete the sender's wallet account.
    # Example: http://127.0.0.1:8000/xrpl/send-payment-delete-wallet/?sender_seed=...&receiver=...&amount=10
    path('payment/send-xrp/delete-account/', SendXrpPaymentsAndDeleteAccount.as_view(), name='send_xrp_payment_and_delete_account'),

    # Endpoint to send currency payments.
    path('payment/send-cross-currency/', SendCrossCurrency.as_view(), name='send_cross_currency_payment'),

    # Endpoint to blackhole all XRP in a wallet.
    # Example: http://127.0.0.1:8000/xrpl/black_hole_xrp/rJJ7SKuoobMJZcRRqS2sYUhNeyUyGU8ML7/
    path('payment/send-xrp/black-hole-account/', SendXrpPaymentAndBlackHoleAccount.as_view(), name='send_xrp_payment_and_black_hole_account'),



    ################################# Ledger #################################
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
    # Endpoint to escrow a wallet address.
    # Example: http://127.0.0.1:8000/xrpl/get-trust-line/?wallet_address=r4ocA7HYdBXuvQPe1Dd7XUncZu8CT1QzkK
    path('escrow/account/info/', GetEscrowAccountInfo.as_view(), name='get_escrow_account_info'),

    # Endpoint to create an escrow a wallet address.
    # Example: http://127.0.0.1:8000/xrpl/get-trust-line/?wallet_address=r4ocA7HYdBXuvQPe1Dd7XUncZu8CT1QzkK
    path('escrow/create/', CreateEscrow.as_view(), name='create_escrow'),

    # Example: http://127.0.0.1:8000/xrpl/get-escrow-sequence-number/?prev_txn_id=C48E7D7734ADDA1530E377627640AD436DBBD49D2D484B68D6EEBB13D933F998
    path('escrow/account/sequence-number/', GetEscrowSequenceNumber.as_view(), name='get_escrow_sequence_number'),

    # Example: http://127.0.0.1:8000/xrpl/create-account-escrow/?sender_seed=sEdTGT135RyS61mbc18hpcXSxwPDLQa&prev_txn_id=58C9D264585FEC50614D91C996C80831A6693DFA3D49BEE79754FF1E35A9B3EE
    path('escrow/cancel/', CancelEscrow.as_view(), name='cancel_escrow'),

    # http://127.0.0.1:8000/xrpl/finish-escrow/?escrow_account=rJq8pSDVVcXPEDP7QPMnNzbTWSDkk5MG82&sender_seed=sEd74ZUqk8ZcCCmDJoKriEMWUHGPWUb&prev_txn_id=9DAE3A5510FFFFFCE6A4B0C6DB5F882A1F5B37A9D107CA162F3C427F4A76C31E&tx_hash=9DAE3A5510FFFFFCE6A4B0C6DB5F882A1F5B37A9D107CA162F3C427F4A76C31E&ledger_index=5203679
    path('escrow/finish/', FinishEscrow.as_view(), name='finish_escrow'),




    ################################# NFTS #################################
    # Example: http://127.0.0.1:8000/xrpl/nfts/mint/
    path('nfts/mint/', MintNft.as_view(), name='mint_nft'),

    # Example: http://127.0.0.1:8000/xrpl/nfts/account-info/r93BywwD6bg7TUNmq5nDjTvmEYuyLqGbyU
    path('nfts/account/info/<str:account>/', GetAccountNft.as_view(), name='get_account_nft'),

    # Example: http://127.0.0.1:8000/xrpl/nfts/burn
    path('nfts/burn/', BurnNft.as_view(), name='burn_nft'),

    # Example: http://127.0.0.1:8000/xrpl/nfts/sell/
    path('nfts/sell/', SellNft.as_view(), name='sell_nft'),

    # Example: http://127.0.0.1:8000/xrpl/nfts/buy
    path('nfts/buy/', BuyNft.as_view(), name='buy_nft'),

    # Example: http://127.0.0.1:8000/xrpl/nfts/buy
    path('nfts/cancel/', CancelNftOffers.as_view(), name='cancel_nft_offers'),
]
