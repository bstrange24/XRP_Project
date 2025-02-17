# XRP_Project

Go here for xrpl documentation
https://xrpl-py.readthedocs.io/en/stable/source/snippets.html

https://xrpl.org/docs/references/protocol/transactions/types/accountdelete

Ripple¹	Testnet	https://s.altnet.rippletest.net:51234/	wss://s.altnet.rippletest.net:51233/	Testnet public server
XRPL Labs	Testnet	https://testnet.xrpl-labs.com/	wss://testnet.xrpl-labs.com/	Testnet public server with CORS support
Ripple¹	Testnet (Clio)	https://clio.altnet.rippletest.net:51234/	wss://clio.altnet.rippletest.net:51233/	Testnet public server with Clio


Ripple¹	Devnet	https://s.devnet.rippletest.net:51234/	wss://s.devnet.rippletest.net:51233/	Devnet public server
Ripple¹	Devnet (Clio)	https://clio.devnet.rippletest.net:51234/	wss://clio.devnet.rippletest.net:51233/	Devnet public server with Clio


Ripple¹	Sidechain-Devnet	https://sidechain-net2.devnet.rippletest.net:51234/	wss://sidechain-net2.devnet.rippletest.net:51233/	Sidechain Devnet to test cross-chain bridge features. Devnet serves as the locking chain while this sidechain serves as the issuing chain.
XRPL Labs	Xahau Testnet	https://xahau-test.net/	wss://xahau-test.net/	Hooks-enabled Xahau Testnet


Perform the following to setup this project:
1) Download Git for repo interaction (Git Bash, Tortoise Git)
2) Download repo from https://github.com/bstrange24/XRP_Project.git
3) Download an IDE. PyCharm was initially used.
4) Install Python. This uses version 3.13
4) Import GIt project into PyCharm.
5) Install the following packages:
   6) pip install Django
   7) pip install djangorestframework
   8) pip install django-cors-headers
   6) pip install xrpl-py
   7) pip install redis
   8) pip install tenacity
   9) pip install django-environ
   10) pip install environ
   8) node
   9) npm
   10) npm install -g @angular/cli


# Endpoint for creating a new XRPL account.
    # Example: http://127.0.0.1:8000/xrpl/create-account/
    path('create-account/', create_account, name='create_account'),

    # Endpoint for creating a new XRPL account.
    # Example: http://127.0.0.1:8000/xrpl/create_multiple_account/
    path('create-multiple-accounts/', create_multiple_account, name='create_multiple_account'),

    # Endpoint to fetch wallet information for a given wallet address.
    # Example: http://127.0.0.1:8000/xrpl/wallet-info/rMgaRbbZUBeoxwZevhv1mezuvA97eR4JHV/
    path('wallet-info/<str:wallet_address>/', get_wallet_info, name='get_wallet_info'),

    # Endpoint to check the balance of a given wallet address.
    # Example: http://127.0.0.1:8000/xrpl/check-wallet-balance/rQGijrV8XYRseZAfjFvC9cDxxr58h9SvMY/
    path("check-wallet-balance/<str:wallet_address>/", check_wallet_balance, name="check_wallet_balance"),

    # Endpoint to update account settings on the XRPL.
    # Example: http://127.0.0.1:8000/xrpl/account-set/?sender_seed=...&require_destination_tag=false
    path("account-set/", account_set, name="account_set"),

    # Endpoint to delete an account and transfer its remaining XRP balance to another wallet.
    # Example: http://127.0.0.1:8000/xrpl/black_hole_xrp/rJJ7SKuoobMJZcRRqS2sYUhNeyUyGU8ML7/
    path('black_hole_xrp/<str:wallet_address>/', black_hole_xrp, name='delete_account'),

    # Endpoint to get active offers on an account.
    # Example: http://127.0.0.1:8000/xrpl/get-account-offers/?account=r4ocA7HYdBXuvQPe1Dd7XUncZu8CT1QzkK
    path('get-account-offers/', get_account_offers, name='get_account_offers'),

    # Endpoint to retrieve the transaction history for a wallet address.
    # Example: http://127.0.0.1:8000/xrpl/transaction-history/rQGijrV8XYRseZAfjFvC9cDxxr58h9SvMY/...
    path("transaction-history/<str:wallet_address>/<str:previous_transaction_id>/", get_transaction_history,
         name="get_transaction_history"),

    # Endpoint to fetch transaction history with pagination.
    # Example: http://127.0.0.1:8000/xrpl/transaction-history-with-pag/rQGijrV8XYRseZAfjFvC9cDxxr58h9SvMY/
    path("transaction-history-with-pag/<str:wallet_address>/", get_transaction_history_with_pagination,
         name="get_transaction_history_with_pagination"),

    # Endpoint to check the status of a specific transaction.
    # Example: http://127.0.0.1:8000/xrpl/check-transaction-status/80AD9114C666200...
    path("check-transaction-status/<str:tx_hash>/", check_transaction_status, name="check_transaction_status"),

    # Endpoint to send a payment transaction from one wallet to another.
    # Example: http://127.0.0.1:8000/xrpl/send-payment/?sender_seed=...&receiver=...&amount=10
    path('send-payment/', send_payment, name='send_payment'),

    # Endpoint to send payment and delete the sender's wallet account.
    # Example: http://127.0.0.1:8000/xrpl/send-payment-delete-wallet/?sender_seed=...&receiver=...&amount=10
    path('send-payment-delete-wallet/<str:wallet_address>/', send_and_delete_wallet, name='send_and_delete_wallet'),

    # Endpoint to retrieve trust lines for a wallet address.
    # Example: http://127.0.0.1:8000/xrpl/get-trust-line/?wallet_address=r4ocA7HYdBXuvQPe1Dd7XUncZu8CT1QzkK
    path('get-trust-line/', get_trust_line, name='get_trust_line'),

    # Endpoint to retrieve detailed information about a specific ledger.
    # Example: http://127.0.0.1:8000/xrpl/get-ledger-info/?ledger_index=validated
    # Example: http://127.0.0.1:8000/xrpl/get-ledger-info/?ledger_hash=<ledger_hash>
    path('get-ledger-info/', get_ledger_info, name='get_ledger_info'),

    # Endpoint to get server information like version, uptime, and server status.
    # Example: http://127.0.0.1:8000/xrpl/get-server-info/
    path('get-server-info/', get_server_info, name='get_server_info'),

    # Endpoint to fetch the reserve requirements for accounts on the XRPL.
    # Example: http://127.0.0.1:8000/xrpl/get-xrp-reserves/?account=r4ocA7HYdBXuvQPe1Dd7XUncZu8CT1QzkK
    path('get-xrp-reserves/', get_xrp_reserves, name='get_xrp_reserves'),

    # Endpoint to retrieve all trust lines for a specific account.
    # Example: http://127.0.0.1:8000/xrpl/get-account-trust-lines/?account=r4ocA7HYdBXuvQPe1Dd7XUncZu8CT1QzkK
    path('get-account-trust-lines/', get_account_trust_lines, name='get_account_trust_lines'),

    # Endpoint to set a trust line for a specific issuer and currency.
    # Example:
    # POST http://localhost:8000/set-trust-line/
    # Body: {"sender_seed": "...", "account": "...", "currency": "USD", "limit": 1000}
    path('set-trust-line/', set_trust_line, name='set_trust_line'),
