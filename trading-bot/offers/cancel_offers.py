from xrpl.clients import JsonRpcClient
from xrpl.models import AccountOffers, OfferCancel
from xrpl.transaction import autofill_and_sign, submit
from xrpl.wallet import Wallet

# Connect to the XRP Ledger (Testnet in this example)
client = JsonRpcClient("https://s.altnet.rippletest.net:51234")

# List of wallet addresses to check
xaman_wallet_seed = [
    "sEdT4FYXxxjfvy58595ozPFXqNKSNZL",  # Xaman
]

kik_wallet_seed = [
    "sEdT2Bakk4p9e2W1BKVbvtzuQoZK256",  # Issuer
    "sEdVXYoiSjQgs1CuvbFD9Biqy1ZyMnP",  # Account A
    "sEdTwrJCwZyJ4UDm4G16eAyRgMeL2pa",  # Account B
]

lam_wallet_seed = [
    "sEdS8WgkAKA1CnKYjMtwjx9oGycQfva",  # Issuer
    "sEdSMRumkDMgmRvsUXWGZ2XkvhMFEsT",  # Account A
    "sEdT41wX5MhZRSBGW4jVDGzmxXt7F43",  # Account B
]

tst_wallet_seed = [
    "sEdSZWG5m4nQmb7JWdXC3ZRxfkw8PoG",  # Issuer
    "sEd7jXsx3C6m2NSUPcFo1vTDv995jcx",  # Account A
    "sEdV899ZkEGGNPmWVzg4rRG8mhCgJEZ",  # Account B
]

misc = ["sEdS8WgkAKA1CnKYjMtwjx9oGycQfva"]
# Combine all wallet addresses into a single list
wallet_seeds = kik_wallet_seed + lam_wallet_seed + tst_wallet_seed + xaman_wallet_seed + misc


for wallet_seed in wallet_seeds:
    wallet = Wallet.from_seed(wallet_seed)
    try:
        while True:
            offers_response = client.request(
                AccountOffers(account=wallet.classic_address, ledger_index="validated")
            )
            offers = offers_response.result.get('offers', [])
            if not offers:
                print(f"No offers to cancel for {wallet.classic_address}")
                break
            for offer in offers:
                tx = OfferCancel(account=wallet.classic_address, offer_sequence=offer['seq'])
                signed_tx = autofill_and_sign(tx, client, wallet)
                submit_result = submit(signed_tx, client)
                print(f"Cancelled offer {offer['seq']} for {wallet.classic_address}: {submit_result.result['engine_result']}")
    except Exception as e:
        print(f"Error: {str(e)}")