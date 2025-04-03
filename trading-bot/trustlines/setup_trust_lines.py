from xrpl.clients import JsonRpcClient
from xrpl.models import TrustSet, IssuedCurrencyAmount
from xrpl.wallet import Wallet
from xrpl.transaction import autofill_and_sign, submit

# Connect to XRPL Testnet
client = JsonRpcClient("https://s.altnet.rippletest.net:51234/")

# Define accounts
kik_issuer = "rKacR1Mm32ve7wPsemwr52S9187StFTnWy"
kik_account_a = 'rN34Ss5moqYKYB8v3c8B3LyNwSUTCUVSaV'
kik_account_a_seed = 'sEdVXYoiSjQgs1CuvbFD9Biqy1ZyMnP'
kik_account_b = 'rfQJe2GiUhQ5BZVAUtj4JV39t2aq7xKv3J'
kik_account_b_seed = 'sEdTwrJCwZyJ4UDm4G16eAyRgMeL2pa'

lam_issuer = 'r9N6k8vWCekj2F3a2iNuAGUEbmdr6d7ty4'
lam_account_a = 'r985UBS7s7K9ytQyVkN7Hovkfb62KZVHfx'
lam_account_a_seed = 'sEdSMRumkDMgmRvsUXWGZ2XkvhMFEsT'
lam_account_b = 'rpA21iTZxerFzz7K9WgG5Ltr5CYCTfhdVT'
lam_account_b_seed = 'sEdT41wX5MhZRSBGW4jVDGzmxXt7F43'

tst_issuer = 'rEKBMamgBVqeqYNsHS2zstJT2id58GdYUM'
tst_account_a = 'rpAgpvztaPKYPwiTrtmeJhZnK5TebaQd9E'
tst_account_a_seed = 'sEd7jXsx3C6m2NSUPcFo1vTDv995jcx'
tst_account_b = 'rKR8Z8rYx7ESxJHytaf5s8rGDpJH8mygG4'
tst_account_b_seed = 'sEdV899ZkEGGNPmWVzg4rRG8mhCgJEZ'

bot_account = "rHDapemJvUwifB4vStymwXPPvsXjJSC7mq"
bot_seed = 'sEdT4FYXxxjfvy58595ozPFXqNKSNZL'

kik_currency = "KIK"
lam_currency = "LAM"
tst_currency = "TST"

################################################# Bot trust lines #################################################
bot_wallet = Wallet.from_seed(bot_seed)  # Xaman/Bot Wallet
tx_bot = TrustSet(
    account=bot_account,  # Xaman/Bot Wallet
    limit_amount=IssuedCurrencyAmount(currency=kik_currency, issuer=kik_issuer, value=str(1000000))
)
signed_tx_bot = autofill_and_sign(tx_bot, client, bot_wallet)
res = submit(signed_tx_bot, client)
print(f"Bot -> kik_issuer: {res.result['engine_result']}")

bot_wallet = Wallet.from_seed(bot_seed)  # Xaman/Bot Wallet
tx_bot = TrustSet(
    account=bot_account,  # Xaman/Bot Wallet
    limit_amount=IssuedCurrencyAmount(currency=lam_currency, issuer=lam_issuer, value=str(1000000))
)
signed_tx_bot = autofill_and_sign(tx_bot, client, bot_wallet)
res = submit(signed_tx_bot, client)
print(f"Bot -> lam_issuer: {res.result['engine_result']}")

bot_wallet = Wallet.from_seed(bot_seed)  # Xaman/Bot Wallet
tx_bot = TrustSet(
    account=bot_account,  # Xaman/Bot Wallet
    limit_amount=IssuedCurrencyAmount(currency=tst_currency, issuer=tst_issuer, value=str(1000000))
)
signed_tx_bot = autofill_and_sign(tx_bot, client, bot_wallet)
res = submit(signed_tx_bot, client)
print(f"Bot -> tst_issuer: {res.result['engine_result']}")


################################################# LAM trust line #################################################
wallet_a = Wallet.from_seed(lam_account_a_seed)  # Account A
tx_a = TrustSet(
    account=lam_account_a,  # Account A address
    limit_amount=IssuedCurrencyAmount(currency=lam_currency, issuer=lam_issuer, value=str(1000000))
)
signed_tx_a = autofill_and_sign(tx_a, client, wallet_a)
res = submit(signed_tx_a, client)
print(f"lam_account_a -> lam_issuer: {res.result['engine_result']}")

wallet_a = Wallet.from_seed(lam_account_b_seed)  # Account B
tx_a = TrustSet(
    account=lam_account_b,  # Account A address
    limit_amount=IssuedCurrencyAmount(currency=lam_currency, issuer=lam_issuer, value=str(1000000))
)
signed_tx_a = autofill_and_sign(tx_a, client, wallet_a)
res = submit(signed_tx_a, client)
print(f"lam_account_b -> lam_issuer: {res.result['engine_result']}")

################################################# KIK trust line #################################################
wallet_a = Wallet.from_seed(kik_account_a_seed)  # Account A
tx_a = TrustSet(
    account=kik_account_a,  # Account A address
    limit_amount=IssuedCurrencyAmount(currency=kik_currency, issuer=kik_issuer, value=str(1000000))
)
signed_tx_a = autofill_and_sign(tx_a, client, wallet_a)
res = submit(signed_tx_a, client)
print(f"kik_account_a -> kik_issuer: {res.result['engine_result']}")

wallet_a = Wallet.from_seed(kik_account_b_seed)  # Account B
tx_a = TrustSet(
    account=kik_account_b,  # Account A address
    limit_amount=IssuedCurrencyAmount(currency=kik_currency, issuer=kik_issuer, value=str(1000000))
)
signed_tx_a = autofill_and_sign(tx_a, client, wallet_a)
res = submit(signed_tx_a, client)
print(f"kik_account_b -> kik_issuer: {res.result['engine_result']}")

################################################# TST trust line #################################################
wallet_a = Wallet.from_seed(tst_account_a_seed)  # Account A
tx_a = TrustSet(
    account=tst_account_a,  # Account A address
    limit_amount=IssuedCurrencyAmount(currency=tst_currency, issuer=tst_issuer, value=str(1000000))
)
signed_tx_a = autofill_and_sign(tx_a, client, wallet_a)
res = submit(signed_tx_a, client)
print(f"tst_account_a -> tst_issuer: {res.result['engine_result']}")

wallet_a = Wallet.from_seed(tst_account_b_seed)  # Account B
tx_a = TrustSet(
    account=tst_account_b,  # Account A address
    limit_amount=IssuedCurrencyAmount(currency=tst_currency, issuer=tst_issuer, value=str(1000000))
)
signed_tx_a = autofill_and_sign(tx_a, client, wallet_a)
res = submit(signed_tx_a, client)
print(f"tst_account_b -> tst_issuer: {res.result['engine_result']}")
