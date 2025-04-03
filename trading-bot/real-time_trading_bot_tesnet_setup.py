import asyncio
from xrpl.asyncio.clients import AsyncWebsocketClient
from xrpl.asyncio.wallet import generate_faucet_wallet
from xrpl.models.transactions import Payment, TrustSet, OfferCreate
from xrpl.asyncio.transaction import sign, submit
from xrpl.asyncio.account import get_next_valid_seq_number

# WEB_SOCKET_URL = "wss://s1.ripple.com"
# WEB_SOCKET_URL = "wss://s.altnet.rippletest.net:51233/"
# WEB_SOCKET_URL = "wss://s.devnet.rippletest.net:51233"
# WEB_SOCKET_URL = "wss://s.devnet.rippletest.net:51233"
# WEB_SOCKET_URL = "wss://s1.ripple.com"
# WEB_SOCKET_URL = "wss://s.altnet.rippletest.net:51233/"
TESTNET_URL = "wss://s.altnet.rippletest.net:51233/"
# TESTNET_URL = "wss://s.devnet.rippletest.net:51233"
BASE_FEE = "10"  # 10 drops, typical testnet base fee

async def setup_test_orders():
    async with AsyncWebsocketClient(TESTNET_URL) as client:
        await client.open()

        # Step 1: Create issuer and trader wallets
        issuer_wallet = await generate_faucet_wallet(client, debug=True)
        trader_wallet = await generate_faucet_wallet(client, debug=True)

        print(f"Issuer Address: {issuer_wallet.classic_address}")
        print(f"Trader Address: {trader_wallet.classic_address}")

        # Step 2: Send initial FOO to trader (issuer pays)
        issuer_sequence = await get_next_valid_seq_number(issuer_wallet.classic_address, client)
        print(f"Issuer initial sequence: {issuer_sequence}")
        payment_tx = Payment(
            account=issuer_wallet.classic_address,
            destination=trader_wallet.classic_address,
            amount={"currency": "FOO", "value": "1000", "issuer": issuer_wallet.classic_address},
            sequence=issuer_sequence,
            fee=BASE_FEE  # Add fee
        )
        signed_payment = sign(payment_tx, issuer_wallet)
        payment_result = await submit(signed_payment, client)
        print(f"Payment result: {payment_result.result}")
        if payment_result.is_successful():
            issuer_wallet.sequence = issuer_sequence + 1
        else:
            print("Payment failed, check issuer funding or network.")
            return

        # Step 3: Trader sets trustline to issuer
        trader_sequence = await get_next_valid_seq_number(trader_wallet.classic_address, client)
        print(f"Trader initial sequence: {trader_sequence}")
        trust_set_tx = TrustSet(
            account=trader_wallet.classic_address,
            limit_amount={"currency": "FOO", "value": "10000", "issuer": issuer_wallet.classic_address},
            sequence=trader_sequence,
            fee=BASE_FEE  # Add fee
        )
        signed_trust = sign(trust_set_tx, trader_wallet)
        trust_result = await submit(signed_trust, client)
        print(f"Trustline result: {trust_result.result}")
        if trust_result.is_successful():
            trader_wallet.sequence = trader_sequence + 1

        # Wait for trustline to settle
        await asyncio.sleep(5)

        # Step 4: Trader places offers
        # Buy: 10 XRP for 100 FOO (0.1 XRP/FOO)
        trader_sequence = await get_next_valid_seq_number(trader_wallet.classic_address, client)
        print(f"Trader sequence for buy offer: {trader_sequence}")
        buy_offer = OfferCreate(
            account=trader_wallet.classic_address,
            taker_gets={"currency": "FOO", "value": "100", "issuer": issuer_wallet.classic_address},
            taker_pays=str(int(10 * 1_000_000)),
            sequence=trader_sequence,
            fee=BASE_FEE,  # Add fee
            flags=0
        )
        signed_buy = sign(buy_offer, trader_wallet)
        buy_result = await submit(signed_buy, client)
        print(f"Buy offer result: {buy_result.result}")
        if buy_result.is_successful():
            trader_wallet.sequence = trader_sequence + 1

        # Sell: 100 FOO for 12 XRP (0.12 XRP/FOO)
        trader_sequence = await get_next_valid_seq_number(trader_wallet.classic_address, client)
        print(f"Trader sequence for sell offer: {trader_sequence}")
        sell_offer = OfferCreate(
            account=trader_wallet.classic_address,
            taker_gets=str(int(12 * 1_000_000)),
            taker_pays={"currency": "FOO", "value": "100", "issuer": issuer_wallet.classic_address},
            sequence=trader_sequence,
            fee=BASE_FEE,  # Add fee
            flags=0
        )
        signed_sell = sign(sell_offer, trader_wallet)
        sell_result = await submit(signed_sell, client)
        print(f"Sell offer result: {sell_result.result}")
        print("Test orders placed. Run the bot to detect and trade.")

async def main():
    await setup_test_orders()

if __name__ == "__main__":
    asyncio.run(main())