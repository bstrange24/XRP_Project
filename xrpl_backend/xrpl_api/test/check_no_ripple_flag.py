import xrpl
from xrpl.clients import JsonRpcClient
from xrpl.wallet import generate_faucet_wallet
from xrpl.models.transactions import AccountSet, TrustSet, Payment
from xrpl.transaction import submit_and_wait
from xrpl.models.requests import AccountLines
import logging
import time

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

client = JsonRpcClient("https://s.altnet.rippletest.net:51234/")


def disable_default_ripple(wallet, client):
    """Clear the DefaultRipple flag on an account"""
    account_set = AccountSet(
        account=wallet.classic_address,
        clear_flag=8
    )
    response = submit_and_wait(account_set, client, wallet)
    logging.info(f"Cleared DefaultRipple flag for {wallet.classic_address}: {response.result}")


def clear_noripple_trustline(wallet, currency, issuer, client):
    """Explicitly clear NoRipple on an existing trustline"""
    trust_set = TrustSet(
        account=wallet.classic_address,
        limit_amount={
            "currency": currency,
            "issuer": issuer,
            "value": "1000000"
        },
        flags=262144  # tfClearNoRipple flag
    )
    response = submit_and_wait(trust_set, client, wallet)
    logging.info(f"Cleared NoRipple on trustline for {wallet.classic_address}: {response.result}")


def check_trustlines(account):
    """Check trustlines for an account"""
    response = client.request(AccountLines(
        account=account,
        ledger_index="validated"
    )).result
    logging.info(f"Trustlines for {account}:")
    logging.info(f"response: {response}")


def main():
    # Create wallets
    issuer_wallet = generate_faucet_wallet(client)
    holder_wallet = generate_faucet_wallet(client)

    logging.info(f"Issuer wallet: {issuer_wallet.classic_address} (seed: {issuer_wallet.seed})")
    logging.info(f"Holder wallet: {holder_wallet.classic_address} (seed: {holder_wallet.seed})")

    # Clear DefaultRipple (just in case)
    disable_default_ripple(issuer_wallet, client)
    time.sleep(5)

    # Create initial trustline
    trust_set = TrustSet(
        account=holder_wallet.classic_address,
        limit_amount={
            "currency": "TST",
            "issuer": issuer_wallet.classic_address,
            "value": "1000000"
        },
        flags=0
    )
    submit_and_wait(trust_set, client, holder_wallet)
    time.sleep(5)

    # Send tokens
    payment = Payment(
        account=issuer_wallet.classic_address,
        destination=holder_wallet.classic_address,
        amount={
            "currency": "TST",
            "issuer": issuer_wallet.classic_address,
            "value": "1000"
        }
    )
    submit_and_wait(payment, client, issuer_wallet)
    time.sleep(5)

    # Explicitly clear NoRipple from both sides
    clear_noripple_trustline(holder_wallet, "TST", issuer_wallet.classic_address, client)
    time.sleep(5)
    clear_noripple_trustline(issuer_wallet, "TST", holder_wallet.classic_address, client)
    time.sleep(5)

    # Check final state
    check_trustlines(issuer_wallet.classic_address)
    check_trustlines(holder_wallet.classic_address)


if __name__ == "__main__":
    main()