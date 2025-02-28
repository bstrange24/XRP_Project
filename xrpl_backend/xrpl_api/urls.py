from django.urls import path, reverse

from .accounts.accounts import Accounts
from .currency.currency import Currency
from .escrows.escrows import CreateEscrow, GetEscrowSequenceNumber, CancelEscrow, FinishEscrow, GetEscrowAccountInfo
from .ledger.ledger import LedgerInteraction
from .nft.nft import NftProcessing
from .offers.account_offers.account_offers import GetAccountOffers, CancelAccountOffers
from .offers.book_offers.book_offers import GetBookOffers, CreateBookOffer
from .payments.payments import SendXrpPayments, SendXrpPaymentsAndDeleteAccount, SendXrpPaymentAndBlackHoleAccount
from .transactions.transactions import Transactions
from .trust_lines.trust_line import TrustLine

urlpatterns = [
    # XRPL API Endpoints
    # Each path is mapped to a specific view function that handles the related XRPL operation.
    # These endpoints allow interaction with the XRPL blockchain to perform operations like creating accounts,
    # retrieving wallet information, managing transactions, setting trust lines, and more.

    # Endpoint for creating a new XRPL account.
    # Example: http://127.0.0.1:8000/xrpl/create-account/
    path('create-test-account/', Accounts.create_test_account, name='create_test_account'),

    # Endpoint for creating a new XRPL account.
    # Example: http://127.0.0.1:8000/xrpl/create_multiple_account/
    path('create-multiple-test-accounts/', Accounts.create_multiple_test_accounts, name='create_multiple_test_accounts'),

    # Endpoint to fetch wallet information for a given wallet address.
    # Example: http://127.0.0.1:8000/xrpl/account-info/rMgaRbbZUBeoxwZevhv1mezuvA97eR4JHV/
    path('account-info/<str:account>/', Accounts.get_account_info, name='get_account_info'),

    # Example: http://127.0.0.1:8000/xrpl/get-account-info-from-hash/?tx_hash=BED4E1E7CAB56600BA3C9597EAB606D9213B1E87B4FB7CE1F4885A3CC6755656
    path('get-account-info-from-hash/', Accounts.get_account_info_from_hash, name='get_account_info_from_hash'),

    # Endpoint to check the balance of a given wallet address.
    # Example: http://127.0.0.1:8000/xrpl/check-wallet-balance/rQGijrV8XYRseZAfjFvC9cDxxr58h9SvMY/
    path("check-account-balance/<str:account>/", Accounts.check_account_balance, name="check_account_balance"),

    # Endpoint to update account settings on the XRPL.
    # Example: http://127.0.0.1:8000/xrpl/config-account/?sender_seed=...&require_destination_tag=false
    path("update-account-config/", Accounts.update_account_config, name="update_account_config"),

    # Endpoint to retrieve account settings on the XRPL.
    # Example: http://127.0.0.1:8000/xrpl/get-account-config/rMgaRbbZUBeoxwZevhv1mezuvA97eR4JHV/
    path("get-account-config/<str:account>/", Accounts.get_account_config, name="get_account_config"),

    # Endpoint to blackhole all XRP in a wallet.
    # Example: http://127.0.0.1:8000/xrpl/black_hole_xrp/rJJ7SKuoobMJZcRRqS2sYUhNeyUyGU8ML7/
    path('send-xrp-payment-and-black-hole-account/', SendXrpPaymentAndBlackHoleAccount.as_view(), name='send_xrp_payment_and_black_hole_account'),

    # Endpoint to get all pairs in the order book
    # http://127.0.0.1:8000/xrpl/get-book-offers/?taker_gets_currency=XRP&taker_pays_currency=USD&taker_pays_issuer=rIssuerAddress&page=1&page_size=10
    path('get-book-offers/', GetBookOffers.as_view(), name='get_book_offers'),

    # Endpoint to get active offers on an account.
    # Example: http://127.0.0.1:8000/xrpl/get-account-offers/?wallet_address=r4ocA7HYdBXuvQPe1Dd7XUncZu8CT1QzkK
    path('get-account-offers/', GetAccountOffers.as_view(), name='get_account_offers'),

    # Endpoint to cancel an offer on an account.
    # Example: http://127.0.0.1:8000/xrpl/create-book-offer/?wallet_address=raGfE6LfRpUXNjmSYRqUyhWkU429XeYgEg&currency=TST&value=25&sendes_seed=sEdS82hNoMmkM7GottuGAFVecYTxRPH
    # path("create-book-offers/", CreateBookOffer.as_view(), name="create_book_offers"),
    path("create-book-offers-easy/", CreateBookOffer.as_view(), name="create_book_offers_easy"),

    # Endpoint to get created offers on an account.
    # Example: http://127.0.0.1:8000/xrpl/cancel-account-offers/?sender_seed=sEdVWMNWboHkJmE5sWC69Y4KghW1KXC
    path("cancel-account-offers/", CancelAccountOffers.as_view(), name="cancel_account_offers"),

    # Endpoint to retrieve the transaction history for a wallet address.
    # Example: http://127.0.0.1:8000/xrpl/transaction-history/rQGijrV8XYRseZAfjFvC9cDxxr58h9SvMY/...
    path("transaction-history/<str:account>/<str:previous_transaction_id>/", Transactions.get_transaction_history,
         name="get_transaction_history"),

    # Endpoint to fetch transaction history with pagination.
    # Example: http://127.0.0.1:8000/xrpl/transaction-history-with-pag/rQGijrV8XYRseZAfjFvC9cDxxr58h9SvMY/
    path("transaction-history-with-pag/<str:account>/", Transactions.get_transaction_history_with_pagination,
         name="get_transaction_history_with_pagination"),

    # Endpoint to check the status of a specific transaction.
    # Example: http://127.0.0.1:8000/xrpl/check-transaction-status/80AD9114C666200...
    path("check-transaction-status/<str:tx_hash>/", Transactions.check_transaction_status, name="check_transaction_status"),

    # Endpoint to send a payment transaction from one wallet to another.
    # Example: http://127.0.0.1:8000/xrpl/send-payment/?sender_seed=...&receiver=...&amount=10
    path('send-xrp-payment/', SendXrpPayments.as_view(), name='send_xrp_payment'),

    # Endpoint to send payment and delete the sender's wallet account.
    # Example: http://127.0.0.1:8000/xrpl/send-payment-delete-wallet/?sender_seed=...&receiver=...&amount=10
    path('send-xrp-payment-and-delete-account/', SendXrpPaymentsAndDeleteAccount.as_view(), name='send_xrp_payment_and_delete_account'),

    # Endpoint to retrieve detailed information about a specific ledger.
    # Example: http://127.0.0.1:8000/xrpl/get-ledger-info/?ledger_index=validated
    # Example: http://127.0.0.1:8000/xrpl/get-ledger-info/?ledger_hash=<ledger_hash>
    path('get-ledger-info/', LedgerInteraction.get_ledger_info, name='get_ledger_info'),

    # Endpoint to get ledger information like version, uptime, and ledger status.
    # Example: http://127.0.0.1:8000/xrpl/get-server-info/
    path('get-server-info/', LedgerInteraction.get_server_info, name='get_server_info'),

    # Endpoint to fetch the reserve requirements for accounts on the XRPL.
    # Example: http://127.0.0.1:8000/xrpl/get-xrp-reserves/?wallet_address=r4ocA7HYdBXuvQPe1Dd7XUncZu8CT1QzkK
    path('get-xrp-reserves/', LedgerInteraction.get_xrp_reserves, name='get_xrp_reserves'),

    # Endpoint to retrieve all trust lines for a specific account.
    # Example: http://127.0.0.1:8000/xrpl/get-account-trust-lines/?account=r4ocA7HYdBXuvQPe1Dd7XUncZu8CT1QzkK
    path('get-account-trust-lines/', TrustLine.get_account_trust_lines, name='get_account_trust_lines'),

    # Endpoint to set a trust line for a specific issuer and currency.
    # Example:
    # POST http://localhost:8000/set-trust-line/
    # Body: {"sender_seed": "...", "account": "...", "currency": "USD", "limit": 1000}
    path('set-trust-line/', TrustLine.set_trust_line, name='set_trust_line'),

    # Endpoint to retrieve trust lines for a wallet address.
    # Example: http://127.0.0.1:8000/xrpl/get-trust-line/?wallet_address=r4ocA7HYdBXuvQPe1Dd7XUncZu8CT1QzkK
    path('get-trust-line/', TrustLine.get_trust_line, name='get_trust_line'),

    # Endpoint to remove a trust lines for a wallet address.
    # Example: http://127.0.0.1:8000/xrpl/get-trust-line/?wallet_address=r4ocA7HYdBXuvQPe1Dd7XUncZu8CT1QzkK
    path('remove-trust-line/', TrustLine.remove_trust_line, name='remove_trust_line'),

    # Endpoint to escrow a wallet address.
    # Example: http://127.0.0.1:8000/xrpl/get-trust-line/?wallet_address=r4ocA7HYdBXuvQPe1Dd7XUncZu8CT1QzkK
    path('get-escrow-account-info/', GetEscrowAccountInfo.as_view(), name='get_escrow_account_info'),

    # Endpoint to create an escrow a wallet address.
    # Example: http://127.0.0.1:8000/xrpl/get-trust-line/?wallet_address=r4ocA7HYdBXuvQPe1Dd7XUncZu8CT1QzkK
    path('create-account-escrow/', CreateEscrow.as_view(), name='create_account_escrow'),

    # Example: http://127.0.0.1:8000/xrpl/get-escrow-sequence-number/?prev_txn_id=C48E7D7734ADDA1530E377627640AD436DBBD49D2D484B68D6EEBB13D933F998
    path('get-escrow-sequence-number/', GetEscrowSequenceNumber.as_view(), name='get_escrow_sequence_number'),

    # Example: http://127.0.0.1:8000/xrpl/create-account-escrow/?sender_seed=sEdTGT135RyS61mbc18hpcXSxwPDLQa&prev_txn_id=58C9D264585FEC50614D91C996C80831A6693DFA3D49BEE79754FF1E35A9B3EE
    path('cancel-escrow/', CancelEscrow.as_view(), name='cancel_escrow'),

    # http://127.0.0.1:8000/xrpl/finish-escrow/?escrow_account=rJq8pSDVVcXPEDP7QPMnNzbTWSDkk5MG82&sender_seed=sEd74ZUqk8ZcCCmDJoKriEMWUHGPWUb&prev_txn_id=9DAE3A5510FFFFFCE6A4B0C6DB5F882A1F5B37A9D107CA162F3C427F4A76C31E&tx_hash=9DAE3A5510FFFFFCE6A4B0C6DB5F882A1F5B37A9D107CA162F3C427F4A76C31E&ledger_index=5203679
    path('finish-escrow/', FinishEscrow.as_view(), name='finish_escrow'),

    # Endpoint to send currency payments.
    path('send-cross-currency-payment/', Currency.as_view(), name='send_cross_currency_payment'),

    # Example: http://127.0.0.1:8000/xrpl/mint-nft/?wallet_address=r4ocA7HYdBXuvQPe1Dd7XUncZu8CT1QzkK
    path('xrpl/mint-nft/', NftProcessing.as_view(), name='mint_nft'),

    # Example: http://127.0.0.1:8000/xrpl/mint-nft/?wallet_address=r4ocA7HYdBXuvQPe1Dd7XUncZu8CT1QzkK
    path('xrpl/get-account-nft/', NftProcessing.as_view(), name='get_account_nft'),

    # Example: http://127.0.0.1:8000/xrpl/burn-account-nft/rBKnvchY2NwDj1bufNUB61KXGnpPTMZ1Mm/
    path('xrpl/burn-account-nft/', NftProcessing.as_view(), name='burn_account_nft'),

    # Example: http://127.0.0.1:8000/xrpl/sell-account-nft/rBKnvchY2NwDj1bufNUB61KXGnpPTMZ1Mm/
    path('xrpl/sell-account-nft/', NftProcessing.as_view(), name='sell_account_nft'),

    # Example: http://127.0.0.1:8000/xrpl/buy-account-nft/rBKnvchY2NwDj1bufNUB61KXGnpPTMZ1Mm/
    path('xrpl/buy-account-nft/', NftProcessing.as_view(), name='buy_account_nft'),
]

