from xrpl.wallet import generate_faucet_wallet
from xrpl.clients import JsonRpcClient
from xrpl.models.requests import AccountInfo
# from xrpl.utils import get_account_root

# Connect to the XRP Ledger mainnet
MAINNET_URL = "https://xrplcluster.com/"  # Public mainnet JSON-RPC endpoint
client = JsonRpcClient(MAINNET_URL)

# Generate a new wallet (this creates a test wallet funded via faucet for testnet,
# but we'll simulate mainnet-style generation)
# Note: For mainnet, you typically generate the wallet locally and fund it manually
from xrpl.wallet import Wallet

# Generate a new wallet seed and instantiate the wallet
new_wallet = Wallet.create()

# Print wallet details
print("New Wallet Details:")
print(f"Classic Address: {new_wallet.classic_address}")
print(f"Public Key: {new_wallet.public_key}")
print(f"Private Key: {new_wallet.private_key}")
print(f"Seed: {new_wallet.seed}")

# Optional: Check if the wallet is funded (requires funding on mainnet)
try:
    account_info = client.request(AccountInfo(
        account=new_wallet.classic_address,
        ledger_index="validated"
    ))
    print(f"Account Balance: {account_info.result['account_data']['Balance']} drops")
except Exception as e:
    print("Account not funded yet or error occurred:", e)