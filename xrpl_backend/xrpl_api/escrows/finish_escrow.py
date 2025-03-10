import secrets
import hashlib

# def generate_escrow_condition_and_fulfillment(secret_length=32):
#     """
#     Generate a PREIMAGE-SHA-256 condition and fulfillment pair for XRPL escrow.
#
#     Args:
#         secret_length (int): Length of the random secret (fulfillment) in bytes (default 32).
#
#     Returns:
#         tuple: (condition, fulfillment) as hex strings, condition includes Crypto-Conditions prefix/suffix.
#     """
#     # Generate random secret (fulfillment)
#     fulfillment_bytes = secrets.token_bytes(secret_length)
#     fulfillment = fulfillment_bytes.hex().upper()
#
#     # Compute SHA-256 hash (fingerprint)
#     fingerprint = hashlib.sha256(fulfillment_bytes).digest()  # 32 bytes
#
#     # Build full condition: prefix + fingerprint + length suffix
#     prefix = bytes.fromhex("A0258020")  # PREIMAGE-SHA-256, 32-byte hash
#     length_suffix = bytes.fromhex("8101" + f"{secret_length:02x}")  # DER length encoding
#     condition_bytes = prefix + fingerprint + length_suffix
#     condition = condition_bytes.hex().upper()
#
#     # Verify for debugging
#     computed_hash = hashlib.sha256(bytes.fromhex(fulfillment)).digest()
#     if computed_hash != fingerprint:
#         raise ValueError("Condition fingerprint mismatch")
#
#     print(f"Condition: {condition} (length: {len(condition)//2} bytes)")
#     print(f"Fulfillment: {fulfillment} (length: {len(fulfillment)//2} bytes)")
#     return condition, fulfillment

# Test it
# if __name__ == "__main__":
#     condition, fulfillment = generate_escrow_condition_and_fulfillment(secret_length=16)
#     print(f"Generated condition: {condition}")
#     print(f"Generated fulfillment: {fulfillment}")


# Condition: D1312A32687894C4A6A763950CBC99F56847962345AF70910EA4648F565B7BCD (length: 64 hex chars, 32 bytes)
# Fulfillment: 452ED2404174060B5E1D55ED892D7CCC (length: 32 hex chars, 16 bytes)
# Condition: D1312A32687894C4A6A763950CBC99F56847962345AF70910EA4648F565B7BCD
# Fulfillment: 452ED2404174060B5E1D55ED892D7CCC


from xrpl.clients import JsonRpcClient
from xrpl.models import EscrowFinish
from xrpl.transaction import submit_and_wait
from xrpl.wallet import generate_faucet_wallet

client = JsonRpcClient("https://s.altnet.rippletest.net:51234") # Connect to the testnetwork

# Complete an escrow
# Cannot be called until the finish time is reached

# Required fields (modify to match an escrow you create)
escrow_creator = generate_faucet_wallet(client=client).address

escrow_sequence = 27641268

# Optional fields

# Crypto condition that must be met before escrow can be completed, passed on escrow creation
condition = "A02580203882E2EB9B44130530541C4CC360D079F265792C4A7ED3840968897CB7DF2DA1810120"

# Crypto fulfillment of the condtion
fulfillment = "A0228020AED2C5FE4D147D310D3CFEBD9BFA81AD0F63CE1ADD92E00379DDDAF8E090E24C"

# Sender wallet object
sender_wallet = generate_faucet_wallet(client=client)

# Build escrow finish transaction
finish_txn = EscrowFinish(account=sender_wallet.address, owner=escrow_creator, offer_sequence=escrow_sequence, condition=condition, fulfillment=fulfillment)

# Autofill, sign, then submit transaction and wait for result
stxn_response = submit_and_wait(finish_txn, client, sender_wallet)

# Parse response and return result
stxn_result = stxn_response.result

# Parse result and print out the transaction result and transaction hash
print(stxn_result["meta"]["TransactionResult"])
print(stxn_result["hash"])
