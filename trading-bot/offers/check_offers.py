from xrpl.clients import JsonRpcClient
from xrpl.models import AccountObjectType
from xrpl.models.requests import AccountObjects
from xrpl.core import addresscodec

# Connect to the XRP Ledger (Testnet in this example)
client = JsonRpcClient("https://s.altnet.rippletest.net:51234")

# List of wallet addresses to check
xaman_wallet_addresses = [
    "rHDapemJvUwifB4vStymwXPPvsXjJSC7mq",  # Xaman
]

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
# wallet_addresses = kik_wallet_addresses + lam_wallet_addresses + tst_wallet_addresses + xaman_wallet_addresses
wallet_addresses = xaman_wallet_addresses

# Loop through each wallet address
for wallet_address in wallet_addresses:
    try:
        # Check if the address is valid
        if not addresscodec.is_valid_classic_address(wallet_address):
            print(f"Invalid XRP Ledger address: {wallet_address}")
            continue  # Skip to the next wallet address

        # Create a request to get account objects (offers)
        account_objects_request = AccountObjects(
            account=wallet_address,
            type=AccountObjectType.OFFER,
            ledger_index="validated"
        )

        # Send the request to the XRP Ledger
        account_objects_response = client.request(account_objects_request)

        # Check if the request was successful
        if account_objects_response.is_successful():
            offers = account_objects_response.result.get("account_objects", [])
            counter = 0

            if offers:
                print(f"Offers for account {wallet_address}:")
                for offer in offers:
                    print(f"Offer Sequence: {offer['Sequence']}")
                    print(f"Taker Gets: {offer['TakerGets']}")
                    print(f"Taker Pays: {offer['TakerPays']}")
                    print(f"Flags: {offer['Flags']}")
                    print(f"Expiration: {offer.get('Expiration', 'None')}")
                    print("-" * 40)
                    counter = counter + 1
                print(f"Total offers: {counter}")
            else:
                print(f"No offers found for account {wallet_address}.")
        else:
            print(f"Failed to retrieve offers for account {wallet_address}.")
            print(f"Error: {account_objects_response.result['error']}")
    except Exception as e:
        print(f"Error: {str(e)}")