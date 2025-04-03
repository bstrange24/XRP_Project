from xrpl.clients import JsonRpcClient
from xrpl.models import Payment, IssuedCurrencyAmount
from xrpl.wallet import Wallet
from xrpl.transaction import autofill_and_sign, submit

# Connect to XRPL Testnet
client = JsonRpcClient("https://s.altnet.rippletest.net:51234/")

kik_issuer = "rKacR1Mm32ve7wPsemwr52S9187StFTnWy"
kik_issuer_seed = 'sEdT2Bakk4p9e2W1BKVbvtzuQoZK256'
kik_account_a = 'rN34Ss5moqYKYB8v3c8B3LyNwSUTCUVSaV'
kik_account_a_seed = 'sEdVXYoiSjQgs1CuvbFD9Biqy1ZyMnP'
kik_account_b = 'rfQJe2GiUhQ5BZVAUtj4JV39t2aq7xKv3J'
kik_account_b_seed = 'sEdTwrJCwZyJ4UDm4G16eAyRgMeL2pa'

lam_issuer = 'r9N6k8vWCekj2F3a2iNuAGUEbmdr6d7ty4'
lam_issuer_seed = 'sEdS8WgkAKA1CnKYjMtwjx9oGycQfva'
lam_account_a = 'r985UBS7s7K9ytQyVkN7Hovkfb62KZVHfx'
lam_account_a_seed = 'sEdSMRumkDMgmRvsUXWGZ2XkvhMFEsT'
lam_account_b = 'rpA21iTZxerFzz7K9WgG5Ltr5CYCTfhdVT'
lam_account_b_seed = 'sEdT41wX5MhZRSBGW4jVDGzmxXt7F43'

tst_issuer = 'rEKBMamgBVqeqYNsHS2zstJT2id58GdYUM'
tst_issuer_seed = 'sEdSZWG5m4nQmb7JWdXC3ZRxfkw8PoG'
tst_account_a = 'rpAgpvztaPKYPwiTrtmeJhZnK5TebaQd9E'
tst_account_a_seed = 'sEd7jXsx3C6m2NSUPcFo1vTDv995jcx'
tst_account_b = 'rKR8Z8rYx7ESxJHytaf5s8rGDpJH8mygG4'
tst_account_b_seed = 'sEdV899ZkEGGNPmWVzg4rRG8mhCgJEZ'

bot_account = "rHDapemJvUwifB4vStymwXPPvsXjJSC7mq"
bot_seed = 'sEdT4FYXxxjfvy58595ozPFXqNKSNZL'

kik_currency = "KIK"
kik_amount = "100000"
lam_currency = "LAM"
lam_amount = "100000"
tst_currency = "TST"
tst_amount = "100000"

send_kik = True
send_lam = True
send_tst = True
################################################# Bot Payment Offers #################################################
#################### KIK ###########################
if send_kik:
    # Fund Account A
    kik_issuer_wallet = Wallet.from_seed(kik_issuer_seed)  # Issuer seed
    tx_fund_a = Payment(
        account=kik_issuer,
        destination=kik_account_a,  # Account A address
        amount=IssuedCurrencyAmount(currency=kik_currency, issuer=kik_issuer, value=str(kik_amount))
    )
    signed_tx_fund_a = autofill_and_sign(tx_fund_a, client, kik_issuer_wallet)
    response_fund_a = submit(signed_tx_fund_a, client)
    print(f"Funding Account A with KIK result: {response_fund_a.result['engine_result']}")

    # Fund Account B with KIK
    tx_fund_b = Payment(
        account=kik_issuer,
        destination=kik_account_b,  # Account B address
        amount=IssuedCurrencyAmount(currency=kik_currency, issuer=kik_issuer, value=str(kik_amount))
    )
    signed_tx_fund_b = autofill_and_sign(tx_fund_b, client, kik_issuer_wallet)
    response_fund_b = submit(signed_tx_fund_b, client)
    print(f"Funding Account B with KIK result: {response_fund_b.result['engine_result']}")

    # Fund Xaman Wallet
    tx_fund_bot = Payment(
        account=kik_issuer,
        destination=bot_account,  # Xaman Wallet
        amount=IssuedCurrencyAmount(currency=kik_currency, issuer=kik_issuer, value=str(kik_amount))
    )
    signed_tx_fund_bot = autofill_and_sign(tx_fund_bot, client, kik_issuer_wallet)
    response_fund_bot = submit(signed_tx_fund_bot, client)
    print(f"Funding Bot with KIK result: {response_fund_bot.result['engine_result']}")

#################### LAM ###########################
if send_lam:
    # # Fund Account A
    lam_issuer_wallet = Wallet.from_seed(lam_issuer_seed)  # Issuer seed
    tx_fund_a = Payment(
        account=lam_issuer,
        destination=lam_account_a,  # Account A address
        amount=IssuedCurrencyAmount(currency=lam_currency, issuer=lam_issuer, value=str(lam_amount))
    )
    signed_tx_fund_a = autofill_and_sign(tx_fund_a, client, lam_issuer_wallet)
    response_fund_a = submit(signed_tx_fund_a, client)
    print(f"Funding Account A with LAM result: {response_fund_a.result['engine_result']}")

    # Fund Account B
    tx_fund_b = Payment(
        account=lam_issuer,
        destination=lam_account_b,  # Account B address
        amount=IssuedCurrencyAmount(currency=lam_currency, issuer=lam_issuer, value=str(lam_amount))
    )
    signed_tx_fund_b = autofill_and_sign(tx_fund_b, client, lam_issuer_wallet)
    response_fund_b = submit(signed_tx_fund_b, client)
    print(f"Funding Account B with LAM result: {response_fund_b.result['engine_result']}")

    # Fund Xaman Wallet
    tx_fund_bot = Payment(
        account=lam_issuer,
        destination=bot_account,  # Xaman Wallet
        amount=IssuedCurrencyAmount(currency=lam_currency, issuer=lam_issuer, value=str(lam_amount))
    )
    signed_tx_fund_bot = autofill_and_sign(tx_fund_bot, client, lam_issuer_wallet)
    response_fund_bot = submit(signed_tx_fund_bot, client)
    print(f"Funding Bot with LAM result: {response_fund_bot.result['engine_result']}")

#################### TST ###########################
if send_tst:
    # Fund Account A
    tst_issuer_wallet = Wallet.from_seed(tst_issuer_seed)  # Issuer seed
    tx_fund_a = Payment(
        account=tst_issuer,
        destination=tst_account_a,  # Account A address
        amount=IssuedCurrencyAmount(currency=tst_currency, issuer=tst_issuer, value=str(tst_amount))
    )
    signed_tx_fund_a = autofill_and_sign(tx_fund_a, client, tst_issuer_wallet)
    response_fund_a = submit(signed_tx_fund_a, client)
    print(f"Funding Account A with TST result: {response_fund_a.result['engine_result']}")

    # Fund Account B
    tx_fund_b = Payment(
        account=tst_issuer,
        destination=tst_account_b,  # Account B address
        amount=IssuedCurrencyAmount(currency=tst_currency, issuer=tst_issuer, value=str(tst_amount))
    )
    signed_tx_fund_b = autofill_and_sign(tx_fund_b, client, tst_issuer_wallet)
    response_fund_b = submit(signed_tx_fund_b, client)
    print(f"Funding Account B with TST result: {response_fund_b.result['engine_result']}")

    # Fund Xaman Wallet
    tx_fund_bot = Payment(
        account=tst_issuer,
        destination=bot_account,  # Xaman Wallet
        amount=IssuedCurrencyAmount(currency=tst_currency, issuer=tst_issuer, value=str(tst_amount))
    )
    signed_tx_fund_bot = autofill_and_sign(tx_fund_bot, client, tst_issuer_wallet)
    response_fund_bot = submit(signed_tx_fund_bot, client)
    print(f"Funding Bot with TST result: {response_fund_bot.result['engine_result']}")
