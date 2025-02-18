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


    the engine_result field in a transaction response:
    tesSUCCESS: The transaction was successfully applied.
    terRETRY: The transaction should be retried at a later time.
    terQUEUED: The transaction has been queued for processing.
    tecCLAIM: The fee was claimed but the transaction did not succeed.
    tecDIR_FULL: The directory node is full.
    tecFAILED_PROCESSING: The transaction failed to process.
    tecINSUF_RESERVE_LINE: Insufficient reserve to add the trust line.
    tecINSUF_RESERVE_OFFER: Insufficient reserve to create the offer.
    tecNO_DST: Destination account does not exist.
    tecNO_DST_INSUF_XRP: Destination account does not exist. Too little XRP sent to create it.
    tecNO_LINE_INSUF_RESERVE: No such line. Too little reserve to create it.
    tecNO_LINE_REDUNDANT: Redundant trust line.
    tecPATH_DRY: Path could not send partial amount.
    tecPATH_PARTIAL: Path could not send full amount.
    tecUNFUNDED: One of the participants in the transaction does not have enough funds.
    tecUNFUNDED_ADD: Insufficient balance to add to escrow.
    tecUNFUNDED_OFFER: Offer is unfunded.
    tecOVERSIZE: Object too large.
    tecCRYPTOCONDITION_ERROR: The crypto-condition is incorrect.
    tecINTERNAL: Internal error.
    temBAD_AMOUNT: The amount is invalid.
    temBAD_AUTH_MASTER: Authorization is not from the master key.
    temBAD_CURRENCY: The currency is invalid.
    temBAD_EXPIRATION: The expiration is invalid.
    temBAD_FEE: The fee is invalid.
    temBAD_ISSUER: The issuer is invalid.
    temBAD_LIMIT: The limit is invalid.
    temBAD_OFFER: The offer is invalid.
    temBAD_PATH: The path is invalid.
    temBAD_PATH_LOOP: The path loop is invalid.
    temBAD_REGKEY: The regular key is invalid.
    temBAD_SEND_XRP_LIMIT: The send XRP limit is invalid.
    temBAD_SEND_XRP_MAX: The send XRP max is invalid.
    temBAD_SEND_XRP_NO_DIRECT: The send XRP direct is invalid.
    temBAD_SEND_XRP_PARTIAL: The send XRP partial is invalid.
    temBAD_SEND_XRP_PATHS: The send XRP paths are invalid.
    temBAD_TICK_SIZE: The tick size is invalid.
    temBAD_TRANSACTION: The transaction is invalid.
    temBAD_TRANSFER_RATE: The transfer rate is invalid.
    temBAD_WALLET: The wallet is invalid.
    temDISABLED: The feature is disabled.
    temDST_NEEDED: The destination is needed.
    temINVALID: The transaction is invalid.
    temMALFORMED: The transaction is malformed.
    temREDUNDANT: The transaction is redundant.
    temSEQ_AND_TICK: The sequence and tick are invalid.
    temSEQ_ARITH: The sequence arithmetic is invalid.
    temSEQ_DISCRETE: The sequence is discrete.
    temSEQ_INCR: The sequence is incremental.
    temSEQ_PREV: The sequence is previous.
    temSEQ_SUB: The sequence is sub.
    temSEQ_UNCHANGED: The sequence is unchanged.
    temSIGNER: The signer is invalid.
    temUNCERTAIN: The transaction is uncertain.
    temUNKNOWN: The transaction is unknown.
    temUNSUPPORTED: The transaction is unsupported.
    temWRONG: The transaction is wrong.
    temXRP: The XRP amount is invalid.
    temXRP_PATHS: The XRP paths are invalid.
    temXRP_TO_NON_XRP: The XRP to non-XRP is invalid.
    temXRP_TO_XRP: The XRP to XRP is invalid.
    temXRP_TO_XRP_LIMIT: The XRP to XRP limit is invalid.
    temXRP_TO_XRP_MAX: The XRP to XRP max is invalid.
    temXRP_TO_XRP_NO_DIRECT: The XRP to XRP direct is invalid.
    temXRP_TO_XRP_PARTIAL: The XRP to XRP partial is invalid.
    temXRP_TO_XRP_PATHS: The XRP to XRP paths are invalid.
    temXRP_TO_XRP_TICK_SIZE: The XRP to XRP tick size is invalid.
    temXRP_TO_XRP_TRANSFER_RATE: The XRP to XRP transfer rate is invalid.
    temXRP_TO_XRP_WALLET: The XRP to XRP wallet is invalid.
    temXRP_WALLET: The XRP wallet is invalid.
