from django.urls import path

from .accounts.accounts import Accounts
from .ledger.ledger import LedgerInteraction
from .offers.account_offers import AccountOffer
from .payments.payments import Payments
from .transactions.transactions import Transactions
from .trust_lines.trust_line import TrustLine

urlpatterns = [
    # XRPL API Endpoints
    # Each path is mapped to a specific view function that handles the related XRPL operation.
    # These endpoints allow interaction with the XRPL blockchain to perform operations like creating accounts,
    # retrieving wallet information, managing transactions, setting trust lines, and more.

    # Endpoint for creating a new XRPL account.
    # Example: http://127.0.0.1:8000/xrpl/create-account/
    path('create-account/', Accounts.create_account, name='create_account'),

    # Endpoint for creating a new XRPL account.
    # Example: http://127.0.0.1:8000/xrpl/create_multiple_account/
    path('create-multiple-accounts/', Accounts.create_multiple_accounts, name='create_multiple_account'),

    # Endpoint to fetch wallet information for a given wallet address.
    # Example: http://127.0.0.1:8000/xrpl/wallet-info/rMgaRbbZUBeoxwZevhv1mezuvA97eR4JHV/
    path('account-info/<str:wallet_address>/', Accounts.get_account_info, name='get_account_info'),

    # Endpoint to check the balance of a given wallet address.
    # Example: http://127.0.0.1:8000/xrpl/check-wallet-balance/rQGijrV8XYRseZAfjFvC9cDxxr58h9SvMY/
    path("check-account-balance/<str:wallet_address>/", Accounts.check_account_balance, name="check_account_balance"),

    # Endpoint to update account settings on the XRPL.
    # Example: http://127.0.0.1:8000/xrpl/config-account/?sender_seed=...&require_destination_tag=false
    path("config-account/", Accounts.config_account, name="config_account"),

    # Endpoint to blackhole all XRP in a wallet.
    # Example: http://127.0.0.1:8000/xrpl/black_hole_xrp/rJJ7SKuoobMJZcRRqS2sYUhNeyUyGU8ML7/
    path('black_hole_xrp/<str:wallet_address>/', Accounts.black_hole_xrp, name='delete_account'),

    # Endpoint to get active offers on an account.
    # Example: http://127.0.0.1:8000/xrpl/get-account-offers/?wallet_address=r4ocA7HYdBXuvQPe1Dd7XUncZu8CT1QzkK
    path('get-account-offers/', AccountOffer.get_account_offers, name='get_account_offers'),

    # Endpoint to get create an offer on an account.
    # Example: http://127.0.0.1:8000/xrpl/create-account-offer/?wallet_address=raGfE6LfRpUXNjmSYRqUyhWkU429XeYgEg&currency=TST&value=25&sender_seed=sEdS82hNoMmkM7GottuGAFVecYTxRPH
    path("create-account-offer/", AccountOffer.create_offer, name="create_account_offer"),

    # Endpoint to retrieve the transaction history for a wallet address.
    # Example: http://127.0.0.1:8000/xrpl/transaction-history/rQGijrV8XYRseZAfjFvC9cDxxr58h9SvMY/...
    path("transaction-history/<str:wallet_address>/<str:previous_transaction_id>/", Transactions.get_transaction_history,
         name="get_transaction_history"),

    # Endpoint to fetch transaction history with pagination.
    # Example: http://127.0.0.1:8000/xrpl/transaction-history-with-pag/rQGijrV8XYRseZAfjFvC9cDxxr58h9SvMY/
    path("transaction-history-with-pag/<str:wallet_address>/", Transactions.get_transaction_history_with_pagination,
         name="get_transaction_history_with_pagination"),

    # Endpoint to check the status of a specific transaction.
    # Example: http://127.0.0.1:8000/xrpl/check-transaction-status/80AD9114C666200...
    path("check-transaction-status/<str:tx_hash>/", Transactions.check_transaction_status, name="check_transaction_status"),

    # Endpoint to send a payment transaction from one wallet to another.
    # Example: http://127.0.0.1:8000/xrpl/send-payment/?sender_seed=...&receiver=...&amount=10
    path('send-payment/', Payments.send_payment, name='send_payment'),

    # Endpoint to send payment and delete the sender's wallet account.
    # Example: http://127.0.0.1:8000/xrpl/send-payment-delete-wallet/?sender_seed=...&receiver=...&amount=10
    path('send-payment-delete-wallet/<str:wallet_address>/', Payments.send_and_delete_wallet, name='send_and_delete_wallet'),

    # Endpoint to retrieve trust lines for a wallet address.
    # Example: http://127.0.0.1:8000/xrpl/get-trust-line/?wallet_address=r4ocA7HYdBXuvQPe1Dd7XUncZu8CT1QzkK
    path('get-trust-line/', TrustLine.get_trust_line, name='get_trust_line'),

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
]
