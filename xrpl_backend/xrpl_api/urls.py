from django.urls import path
from .views import create_account, get_wallet_info, check_wallet_balance, account_set, delete_account, get_ledger_info, \
    get_xrp_reserves, get_account_trust_lines, get_account_offers, get_server_info, get_trust_line, set_trust_line
from .views import get_transaction_history, get_transaction_history_with_pagination, check_transaction_status
from .views import send_payment

urlpatterns = [
    # http://127.0.0.1:8000/xrpl/create-account/
    path('create-account/', create_account, name='create_account'),
    #  http://127.0.0.1:8000/xrpl/wallet-info/rMgaRbbZUBeoxwZevhv1mezuvA97eR4JHV/
    path('wallet-info/<str:wallet_address>/', get_wallet_info, name='get_wallet_info'),
    #  http://127.0.0.1:8000/xrpl/check-balance/rQGijrV8XYRseZAfjFvC9cDxxr58h9SvMY/
    path("check-wallet-balance/<str:wallet_address>/", check_wallet_balance, name="check_wallet_balance"),
    # http://127.0.0.1:8000/xrpl/account-set/?sender_seed=sEd742NyPHW2JUNbBeF7L9HNez6ne6B&require_destination_tag=false&disable_master_key=false&enable_regular_key=true
    path("account-set/", account_set, name="account_set"),
    # http://127.0.0.1:8000/xrpl/delete-account/rJJ7SKuoobMJZcRRqS2sYUhNeyUyGU8ML7/
    path('delete-account/<str:wallet_address>/', delete_account, name='delete_account'),

    # http://127.0.0.1:8000/xrpl/transaction-history/rQGijrV8XYRseZAfjFvC9cDxxr58h9SvMY/
    path("transaction-history/<str:wallet_address>/<str:transaction_hash>/", get_transaction_history, name="get_transaction_history"),
    # http://127.0.0.1:8000/xrpl/transaction-history-with-pag/rQGijrV8XYRseZAfjFvC9cDxxr58h9SvMY/
    path("transaction-history-with-pag/<str:wallet_address>/", get_transaction_history_with_pagination,
         name="get_transaction_history_with_pagination"),
    # http://127.0.0.1:8000/xrpl/check-transaction-status/80AD9114C666200C59F0405C445BF15F30E87E01CA2154ACFF746ABAB9C67803/
    path("check-transaction-status/<str:tx_hash>/", check_transaction_status, name="check_transaction_status"),

    # http://127.0.0.1:8000/xrpl/send-payment/?sender_seed=sEd75gQcwgacU52hPDULRCmpchbKz6M&receiver=rNkE8uqaptRMAiREQv2EasKXGrgJM2TvYW&amount=10
    path('send-payment/', send_payment, name='send_payment'),

    # This endpoint retrieves information about a specific ledger, such as its hash and the state of the ledger.
    # GET
    # http://127.0.0.1:8000/xrpl/get-ledger-info/?ledger_index=validated
    # http://127.0.0.1:8000/xrpl/get-ledger-info/?ledger_hash=<your_ledger_hash>
    path('get-ledger-info/', get_ledger_info, name='get_ledger_info'),

    # Fetches the current reserve requirements for an account, including the base reserve and reserve increment
    # GET
    # http://127.0.0.1:8000/xrpl/get-xrp-reserves/?account=r4ocA7HYdBXuvQPe1Dd7XUncZu8CT1QzkK
    path('get-xrp-reserves/', get_xrp_reserves, name='get_xrp_reserves'),

    # Retrieves the trust lines for an account, which shows the assets that are issued by other accounts and the trust limits.
    # GET
    # http://127.0.0.1:8000/xrpl/get-account-trust-lines/?account=r4ocA7HYdBXuvQPe1Dd7XUncZu8CT1QzkK
    path('get-account-trust-lines/', get_account_trust_lines, name='get_account_trust_lines'),

    # Fetches the offers (active orders) placed by an account on the XRP Ledger.
    # GET
    # http://127.0.0.1:8000/xrpl/get-account-offers/?account=r4ocA7HYdBXuvQPe1Dd7XUncZu8CT1QzkK
    path('get-account-offers/', get_account_offers, name='get_account_offers'),

    # Retrieves information about the XRPL server, such as its version, uptime, and other status-related information.
    # GET
    # http://127.0.0.1:8000/xrpl/get-server-info/
    path('get-server-info/', get_server_info, name='get_server_info'),

    # Retrieves the current trust line for an issuer on an account.
    # GET
    # http://127.0.0.1:8000/xrpl/get-trust-line/?wallet_address=r4ocA7HYdBXuvQPe1Dd7XUncZu8CT1QzkK
    path('get-trust-line/', get_trust_line, name='get_trust_line'),

    # Allows a user to set a trust line on their account for a specific issuer (could be used for assets like USD issued on XRPL).
    # POST http://localhost:8000/set-trust-line/
    # using a POST request with the required parameters (sender_seed, account, currency, and limit) in the request body
    # curl -X POST http://localhost:8000/set-trust-line/ \
    # -H "Content-Type: application/json" \
    # -d '{
    #   "sender_seed": "sEdh6DhK2g6vkj6Kr7p8j5KyQs3mRL8cgbtP2fwAf74p6Y7ob7C5",
    #   "account": "r4zjFbfZ3gFqFhAv9GZJ2Udy4zdP6M58PH",
    #   "currency": "USD",
    #   "limit": 1000
    # }'
    path('set-trust-line/', set_trust_line, name='set_trust_line'),






]