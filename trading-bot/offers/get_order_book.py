import asyncio
from xrpl.asyncio.clients import AsyncJsonRpcClient
from xrpl.models import BookOffers

# Connect to the XRP Ledger (Testnet)
client = AsyncJsonRpcClient("https://s.altnet.rippletest.net:51234")

xaman_wallet_addresses = ["rHDapemJvUwifB4vStymwXPPvsXjJSC7mq"]  # Xaman
rob = ["rPr9iQF4dXTrQwGQ8nJkGZWKymzTa1iCcr"]

kik_wallet_addresses = [
    "rKacR1Mm32ve7wPsemwr52S9187StFTnWy",  # Issuer
    "rN34Ss5moqYKYB8v3c8B3LyNwSUTCUVSaV",  # Account A
    "rfQJe2GiUhQ5BZVAUtj4JV39t2aq7xKv3J",  # Account B
]

lam_wallet_addresses = [
    "r9N6k8vWCekj2F3a2iNuAGUEbmdr6d7ty4",  # Issuer
    "r985UBS7s7K9ytQyVkN7Hovkfb62KZVHfx",  # Account A
    "rpA21iTZxerFzz7K9WgG5Ltr5CYCTfhdVT",  # Account B
]

tst_wallet_addresses = [
    "rEKBMamgBVqeqYNsHS2zstJT2id58GdYUM",  # Issuer
    "rpAgpvztaPKYPwiTrtmeJhZnK5TebaQd9E",  # Account A
    "rKR8Z8rYx7ESxJHytaf5s8rGDpJH8mygG4",  # Account B
]

# Combine all wallet addresses into a single list
wallet_addresses = kik_wallet_addresses + lam_wallet_addresses + tst_wallet_addresses + rob
currencies = ["KIK", "TST", "LAM", "ROB"]


async def fetch_offers(wallet, currency, is_buy_order=True):
    """Fetch buy/sell offers for a given wallet and currency."""
    try:
        offer_request = BookOffers(
            taker_gets={"currency": currency, "issuer": wallet} if is_buy_order else {"currency": "XRP"},
            taker_pays={"currency": "XRP"} if is_buy_order else {"currency": currency, "issuer": wallet},
            limit=10
        )
        response = await client.request(offer_request)

        if not response.is_successful():
            print(f"Error fetching offers for {wallet}: {response.result['error']}")
            return

        offers = response.result.get('offers', [])
        if not offers:
            print(f"No {'buy' if is_buy_order else 'sell'} offers found for {currency} - {wallet}")
            return

        print(f"\n--- {'BUY' if is_buy_order else 'SELL'} Offers for {currency} ({wallet}) ---")
        for offer in offers:
            print(f"Offer Sequence: {offer['Sequence']}")
            print(f"Taker Gets: {offer['TakerGets']}")
            print(f"Taker Pays: {offer['TakerPays']}")
            print(f"Flags: {offer['Flags']}")
            print(f"Expiration: {offer.get('Expiration', 'None')}")
            print("-" * 40)

    except Exception as e:
        print(f"Error processing {wallet}: {e}")


async def main():
    """Run async fetch tasks for all wallets and currencies."""
    tasks = []
    for wallet in wallet_addresses:
        for currency in currencies:
            tasks.append(fetch_offers(wallet, currency, is_buy_order=True))  # Buy offers
            tasks.append(fetch_offers(wallet, currency, is_buy_order=False))  # Sell offers
    await asyncio.gather(*tasks)


# Run the async event loop
asyncio.run(main())


# from xrpl.clients import JsonRpcClient
# from xrpl.models import AccountObjectType, BookOffers
# from xrpl.models.requests import AccountObjects
# from xrpl.core import addresscodec
#
# # Connect to the XRP Ledger (Testnet in this example)
# client = JsonRpcClient("https://s.altnet.rippletest.net:51234")
#
# # List of wallet addresses to check
# xaman_wallet_addresses = [
#     "rHDapemJvUwifB4vStymwXPPvsXjJSC7mq",  # Xaman
# ]
#
# rob = ["rPr9iQF4dXTrQwGQ8nJkGZWKymzTa1iCcr"]
#
# kik_wallet_addresses = [
#     "rKacR1Mm32ve7wPsemwr52S9187StFTnWy",  # Issuer
#     "rN34Ss5moqYKYB8v3c8B3LyNwSUTCUVSaV",  # Account A
#     "rfQJe2GiUhQ5BZVAUtj4JV39t2aq7xKv3J",  # Account B
# ]
#
# lam_wallet_addresses = [
#     "r9N6k8vWCekj2F3a2iNuAGUEbmdr6d7ty4",  # Issuer
#     "r985UBS7s7K9ytQyVkN7Hovkfb62KZVHfx",  # Account A
#     "rpA21iTZxerFzz7K9WgG5Ltr5CYCTfhdVT",  # Account B
# ]
#
# tst_wallet_addresses = [
#     "rEKBMamgBVqeqYNsHS2zstJT2id58GdYUM",  # Issuer
#     "rpAgpvztaPKYPwiTrtmeJhZnK5TebaQd9E",  # Account A
#     "rKR8Z8rYx7ESxJHytaf5s8rGDpJH8mygG4",  # Account B
# ]
#
# # Combine all wallet addresses into a single list
# wallet_addresses = kik_wallet_addresses + lam_wallet_addresses + tst_wallet_addresses + rob
# currency = [
#     "KIK",
#     "TST",
#     "LAM",
#     "ROB"
# ]
#
# # Loop through each wallet address
# for wallet_address in wallet_addresses:
#     for cur in currency:
#         account_offers_info = BookOffers(
#             taker_gets={"currency": cur, "issuer": wallet_address},
#             taker_pays={"currency": "XRP"},
#             limit=10
#         )
#
#         # Send the request to XRPL to fetch account offers
#         account_offers_response = client.request(account_offers_info)
#         offers = account_offers_response.result.get('offers', [])
#         if offers:
#             counter = 0
#             for offer in offers:
#                 print(f"Sell {cur} to get XRP found for currency {cur}")
#                 print(f"Offer Sequence: {offer['Sequence']}")
#                 print(f"Taker Gets: {offer['TakerGets']}")
#                 print(f"Taker Pays: {offer['TakerPays']}")
#                 print(f"Flags: {offer['Flags']}")
#                 print(f"Expiration: {offer.get('Expiration', 'None')}")
#                 print("-" * 40)
#                 counter = counter + 1
#             print(f"Sell XRP for currency {cur} result: {account_offers_response.result}")
#         #else:
#             #print(f"No sell offers found for currency: {cur}/XRP and wallet: {wallet_address}")
#
# # Loop through each wallet address
# for wallet_address in wallet_addresses:
#     for cur in currency:
#         account_offers_info = BookOffers(
#             taker_gets={"currency": "XRP"},
#             taker_pays={"currency": cur, "issuer": wallet_address},
#             limit=10
#         )
#
#         # Send the request to XRPL to fetch account offers
#         account_offers_response = client.request(account_offers_info)
#
#         if account_offers_response.is_successful():
#             offers = account_offers_response.result.get('offers', [])
#             if offers:
#                 counter = 0
#                 for offer in offers:
#                     print(f"Sell {cur} to get XRP found for currency {cur}")
#                     print(f"Offer Sequence: {offer['Sequence']}")
#                     print(f"Taker Gets: {offer['TakerGets']}")
#                     print(f"Taker Pays: {offer['TakerPays']}")
#                     print(f"Flags: {offer['Flags']}")
#                     print(f"Expiration: {offer.get('Expiration', 'None')}")
#                     print("-" * 40)
#                     counter = counter + 1
#                 print(f"Total offer: {counter}")
#             # else:
#             #     print(f"No sell offers found for currency: XRP/{cur} and wallet: {wallet_address}")
#         else:
#             print(f"Failed to retrieve offers for account {wallet_address}.")
#             print(f"Error: {account_offers_response.result['error']}")