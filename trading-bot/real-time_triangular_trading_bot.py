import asyncio
from decimal import Decimal, ROUND_DOWN, getcontext, InvalidOperation
import aiohttp
from xrpl.asyncio.clients import AsyncWebsocketClient
from xrpl.models import OfferCancel, AccountInfo, AccountOffers, AccountLines, BookOffers, IssuedCurrencyAmount, IssuedCurrency, XRP
from xrpl.models.requests import Ledger
from xrpl.models.transactions import OfferCreate, TrustSet
from xrpl.asyncio.account import get_next_valid_seq_number
from xrpl.asyncio.transaction import submit_and_wait
from xrpl.wallet import Wallet
import os
import platform

from utils.constants import ON_THE_DEX_URL
from utils.utilities import decode_currency, check_price_change_over_time, check_volume_change_over_time, check_buys_and_sells_over_time, encode_currency

WEB_SOCKET_URL = "wss://s1.ripple.com"  # Mainnet URL
SLIPPAGE_TOLERANCE = 0.02  # 2% tolerance for price movement
OFFER_TIMEOUT = 300  # Cancel offers after 5 minutes
MAX_NUMBER_OF_TRADES_TO_EXECUTE = 1

class RealTimeArbitrageBot:
    def __init__(self, websocket_url=WEB_SOCKET_URL, spread_percent=0.001):
        self.websocket_url = websocket_url
        self.prices = {}
        self.buy_prices = {}
        self.sell_prices = {}
        self.trade_amount = 0.5  # Default trade amount
        self.ledger_fee = "12"
        self.total_fee_triangular = float(self.ledger_fee) * 4 / 1_000_000  # Fee for 4 trades
        self.min_profit = 0.001  # Lowered to capture smaller opportunities
        self.max_price_history = 10
        self.wallet = Wallet.from_seed("sEdTZP4rtDiXYEoYDLdDXoqKqtedQrC")  # Replace with your mainnet seed
        self.client = AsyncWebsocketClient(self.websocket_url)
        self.trade_count = 0
        self.base_reserve = 1.0
        self.owner_reserve = 0.2
        self.spread_percent = spread_percent
        self.blocked_issuers = {
            "rhvf9fe6PP3GC8Bku2Ug7iQPjPDxYZfrxN", "rHFE5b7dqkBSxSWiCKqAbUHTb1Yp59GirV",
            "r93hE5FNShDdUqazHzNvwsCxL9mSqwyiru", "rJAvx8FtrLR3RyZyM1LyVQFxxsLdT1PmdS",
            "rMxCKbEDwqr76QuheSUMdEGf4B9xJ8m5De", "rDvVS42ZgKvFNuacNvJZyQe83JQbTEDVRu",
            "r9mZNnos1GLtc55tkmr21G9BgXxV7w9hT1"
        }
        # getcontext().prec = 15
        getcontext().prec = 28  # Increased to 28 for higher precision
        self.tokens_to_check = []

    def get_amount_value(self, amount):
        if isinstance(amount, str):
            return float(amount)
        elif isinstance(amount, dict) and "value" in amount:
            return float(amount["value"])
        return None

    def get_token_key(self, currency, issuer=None):
        return f"{currency}:{issuer}" if issuer else currency

    async def ensure_open_client(self, client):
        if not client.is_open():
            await client.open()
        return client

    async def get_current_ledger(self, client):
        ledger_request = Ledger(ledger_index="validated")
        response = await client.request(ledger_request)
        return int(response.result["ledger_index"])

    async def cleanup_residuals(self, client, currency, issuer):
        lines_response = await client.request(AccountLines(account=self.wallet.classic_address, ledger_index="validated"))
        for line in lines_response.result.get("lines", []):
            if line["currency"] == currency and line["account"] == issuer:
                balance = float(line["balance"])
                if balance > 0.0001:  # Sell if above a small threshold
                    ask, bid = await self.get_xrpl_order_book(IssuedCurrency(currency=currency, issuer=issuer), XRP(), client)
                    if bid:
                        xrp_amount = Decimal(str(balance)) * Decimal(str(bid)) * Decimal('1.05')  # 2% buffer
                        xrp_amount_str = str(xrp_amount.quantize(Decimal('0.000001'), rounding=ROUND_DOWN))
                        xrp_drops = int(float(xrp_amount_str) * 1_000_000)
                        sell_sequence = await get_next_valid_seq_number(self.wallet.classic_address, client)
                        current_ledger = await self.get_current_ledger(client)
                        sell_tx = OfferCreate(
                            account=self.wallet.classic_address,
                            taker_gets=IssuedCurrencyAmount(currency=currency, issuer=issuer, value=str(balance)),
                            taker_pays=str(xrp_drops), sequence=sell_sequence, fee=self.ledger_fee, flags=0,
                            last_ledger_sequence=current_ledger + 100
                        )
                        result = await submit_and_wait(sell_tx, client, self.wallet)
                        print(f"Cleaned up {balance} {currency}: {result.result}")

    async def cancel_offer(self, sequence, client):
        cancel_tx = OfferCancel(
            account=self.wallet.classic_address,
            offer_sequence=sequence,
            sequence=await get_next_valid_seq_number(self.wallet.classic_address, client),
            fee=self.ledger_fee
        )
        result = await submit_and_wait(cancel_tx, client, self.wallet)
        print(f"Offer {sequence} cancellation result: {result.result}")
        return result.is_successful()

    async def cancel_stale_offers(self):
        async with AsyncWebsocketClient(self.websocket_url) as client:
            await self.ensure_open_client(client)
            self.wallet.sequence = await get_next_valid_seq_number(self.wallet.classic_address, client)
            offers_request = AccountOffers(account=self.wallet.classic_address)
            offers_response = await client.request(offers_request)
            offers = offers_response.result.get("offers", [])
            for offer in offers:
                sequence = offer["seq"]
                print(f"Found open offer: Sequence {sequence}")
                cancel_tx = OfferCancel(
                    account=self.wallet.classic_address,
                    offer_sequence=sequence,
                    sequence=self.wallet.sequence,
                    fee=self.ledger_fee
                )
                try:
                    result = await submit_and_wait(cancel_tx, client, self.wallet)
                    print(f"Cancel offer {sequence} result: {result.result}")
                    if result.is_successful():
                        self.wallet.sequence += 1
                        print(f"Successfully canceled stale offer {sequence}")
                except Exception as e:
                    print(f"Error canceling offer {sequence}: {str(e)}")

    async def setup_trustline(self, currency, issuer):
        async with AsyncWebsocketClient(self.websocket_url) as client:
            await self.ensure_open_client(client)
            trust_sequence = await get_next_valid_seq_number(self.wallet.classic_address, client)
            current_ledger = await self.get_current_ledger(client)
            trust_set = TrustSet(
                account=self.wallet.classic_address,
                # limit_amount={"currency": currency, "issuer": issuer, "value": "1000000"},
                limit_amount=IssuedCurrencyAmount(currency=currency, issuer=issuer, value="1000000"),
                sequence=trust_sequence,
                fee=self.ledger_fee,
                last_ledger_sequence=current_ledger + 100
            )
            result = await submit_and_wait(trust_set, client, self.wallet)
            print(f"Trust line setup result for {currency}:{issuer}: {result.result}")
            if result.is_successful():
                self.wallet.sequence = await get_next_valid_seq_number(self.wallet.classic_address, client)
            return result.is_successful()

    async def get_market_prices(self, currency, issuer, client):
        token_decoded = decode_currency(currency)
        token_key = f"{currency}.{issuer}"
        try:
            # Ensure client is open before XRPL request
            await self.ensure_open_client(client)

            # Try XRPL order book first
            book_offers = await client.request(BookOffers(
                taker_gets=XRP(),
                taker_pays=IssuedCurrency(currency=currency, issuer=issuer),
                limit=10,
                ledger_index="validated"
            ))
            offers = book_offers.result.get("offers", [])
            if offers:
                best_ask = None
                best_bid = None
                for offer in offers:
                    taker_gets_amount = float(offer["TakerGets"]) / 1_000_000  # XRP in drops to XRP
                    taker_pays_amount = float(offer["TakerPays"]["value"])
                    price = taker_gets_amount / taker_pays_amount  # XRP per token
                    if offer["Flags"] & 0x00020000:  # Sell offer (bid)
                        if best_bid is None or price > best_bid:
                            best_bid = price
                    else:  # Buy offer (ask)
                        if best_ask is None or price < best_ask:
                            best_ask = price
                if best_ask and best_bid:
                    print(f"XRPL Pricing for {token_decoded} - {token_key} Bid={best_bid:.8f}, Ask={best_ask:.8f}")
                    return best_ask, best_bid, (best_ask + best_bid) / 2
                elif best_ask:
                    # best_bid = best_ask * (1 - self.spread_percent)
                    best_bid = best_ask
                    print(f"XRPL Pricing (adjusted) for {token_key} Bid={best_bid:.8f}, Ask={best_ask:.8f}")
                    return best_ask, best_bid, best_ask
                elif best_bid:
                    best_ask = best_bid * (1 + self.spread_percent)
                    print(f"XRPL Pricing (adjusted) for {token_key} Bid={best_bid:.8f}, Ask={best_ask:.8f}")
                    return best_ask, best_bid, best_bid
                else:
                    print(f"No valid XRPL offers for {token_key}, falling back to DexScreener")

            # Fallback to DexScreener if no XRPL offers
            decoded_currency = decode_currency(currency)
            async with aiohttp.ClientSession() as session:
                async with session.get(f"https://api.dexscreener.com/latest/dex/search?q={decoded_currency}/XRP") as response:
                    if response.status != 200:
                        print(f"DexScreener API error: Status code {response.status}")
                        return None, None, None
                    data = await response.json()

            if "pairs" not in data or not data["pairs"]:
                print("No pairs found in DexScreener API response")
                return None, None, None

            target_address = f"{currency.upper()}.{issuer}"
            target_address_upper = f"{decoded_currency.upper()}.{issuer}"
            selected_pair = None
            for pair in data["pairs"]:
                if pair.get("baseToken", {}).get("address") == target_address or pair.get("baseToken", {}).get("address") == target_address_upper:
                    selected_pair = pair
                    break

            if not selected_pair:
                print(f"Desired pair with address {target_address} or {target_address_upper} not found")
                return None, None, None

            # if check_price_change_over_time(selected_pair):
            #     print("Insufficient price change over time")
            #     return None, None, None
            #
            # if check_volume_change_over_time(selected_pair):
            #     print("Insufficient volume change over time")
            #     return None, None, None
            #
            # if check_buys_and_sells_over_time(selected_pair):
            #     print("Insufficient buys/sells change over time")
            #     return None, None, None

            market_price_str = selected_pair.get("priceNative")
            if not market_price_str:
                print("No priceNative found in selected pair")
                return None, None, None

            try:
                market_price = float(market_price_str)
            except ValueError:
                print(f"Invalid priceNative format: {market_price_str}")
                return None, None, None

            if not (0.0000001 <= market_price <= 0.01):
                print(f"Warning: Market price {market_price:.8f} outside typical range [0.0000001, 0.01] for {token_key}")

            best_bid = market_price
            best_ask = market_price * (1 + self.spread_percent)

            print(f"DexScreener Pricing for {token_key} Market={market_price:.8f}, Bid={best_bid:.8f}, Ask={best_ask:.8f}")
            return best_ask, best_bid, market_price
        except Exception as e:
            print(f"Pricing Error for {token_key}: {str(e)}")
            return None, None, None

    async def check_pair_liquidity(self, taker_gets, taker_pays, client, min_depth=1):
        try:
            book_offers = await client.request(BookOffers(
                taker_gets=taker_gets,
                taker_pays=taker_pays,
                limit=20,
                ledger_index="validated"
            ))
            offers = book_offers.result.get("offers", [])
            liquidity_ok = len(offers) >= min_depth
            if not liquidity_ok:
                print(f"Liquidity check: {len(offers)} offers found, required {min_depth} for {taker_gets} -> {taker_pays}")
            else:
                print(f"Liquidity check passed: {len(offers)} offers found for {taker_gets} -> {taker_pays}")
            return liquidity_ok
        except Exception as e:
            print(f"Error checking liquidity: {str(e)}")
            return False

    async def check_liquidity(self, taker_gets, taker_pays, amount, client, expected_price, is_sell=False):
        try:
            book_offers = await client.request(BookOffers(
                taker_gets=taker_gets,
                taker_pays=taker_pays,
                limit=10,
                ledger_index="validated"
            ))
            offers = book_offers.result.get("offers", [])

            if not offers:
                print(f"No offers found for {taker_gets} -> {taker_pays}")
                return False

            print(f"Raw offers: {offers}")
            total_available = 0
            print(f"Checking liquidity for {taker_gets} -> {taker_pays}, Expected Price: {expected_price:.8f}, Is Sell: {is_sell}")
            for offer in offers:
                pays_amount = float(offer["TakerPays"]["value"] if isinstance(offer["TakerPays"], dict) else offer["TakerPays"])  # Token
                gets_amount = float(offer["TakerGets"]["value"] if isinstance(offer["TakerGets"], dict) else offer["TakerGets"]) / 1_000_000  # XRP
                price = gets_amount / pays_amount  # XRP/Token for buy orders (XRP -> Token)
                available = gets_amount if isinstance(taker_gets, XRP) else float(offer["TakerGets"]["value"])
                print(f"Offer: Price={price:.8f}, Available={available:.6f}")

                if is_sell:
                    if price >= expected_price / 1.01:  # Sell: want higher XRP/Token price
                        total_available += available
                else:
                    if price <= expected_price * 1.01:  # Buy: want lower XRP/Token price
                        total_available += pays_amount  # Use token amount for buy liquidity

                if total_available >= amount:
                    print(f"Sufficient liquidity for {taker_gets} -> {taker_pays}: {total_available:.6f} available at price {'≥' if is_sell else '≤'} {expected_price * (1 / 1.01 if is_sell else 1.01):.8f}")
                    return True

                # if is_sell:
                #     if price >= expected_price / 1.01:
                #         if isinstance(taker_gets, XRP):
                #             available = float(offer["TakerGets"]) / 1_000_000
                #         else:
                #             available = float(offer["TakerGets"]["value"])
                #         total_available += available
                # else:
                #     if price <= expected_price * 1.01:
                #         if isinstance(taker_gets, XRP):
                #             available = float(offer["TakerGets"]) / 1_000_000
                #         else:
                #             available = float(offer["TakerGets"]["value"])
                #         total_available += available
                #
                # if total_available >= amount:
                #     print(f"Sufficient liquidity for {taker_gets} -> {taker_pays}: {total_available:.6f} available")
                #     return True

            print(f"Insufficient liquidity for {taker_gets} -> {taker_pays}: {total_available:.6f} available, {amount:.6f} needed")
            return False
        except Exception as e:
            print(f"Error checking liquidity: {str(e)}")
            return False

    async def get_xrpl_order_book(self, taker_gets, taker_pays, client):
        try:
            book_offers = await client.request(BookOffers(
                taker_gets=taker_gets,
                taker_pays=taker_pays,
                limit=10,
                ledger_index="validated"
            ))
            offers = book_offers.result.get("offers", [])
            if not offers:
                print("No offers found in XRPL order book")
                return None, None

            best_bid = None
            best_ask = None
            for offer in offers:
                taker_gets_amount = float(offer["TakerGets"]["value"] if isinstance(offer["TakerGets"], dict) else offer["TakerGets"]) / 1_000_000
                taker_pays_amount = float(offer["TakerPays"]["value"] if isinstance(offer["TakerPays"], dict) else offer["TakerPays"]) / 1_000_000
                price = taker_pays_amount / taker_gets_amount
                if offer["Flags"] & 0x00020000:  # Sell offer (bid)
                    if best_bid is None or price > best_bid:
                        best_bid = price
                else:  # Buy offer (ask)
                    if best_ask is None or price < best_ask:
                        best_ask = price
            print(f"XRPL Order Book: Best Bid={best_bid}, Best Ask={best_ask}")
            return best_ask, best_bid
        except Exception as e:
            print(f"Error fetching XRPL order book: {str(e)}")
            return None, None

    async def fetch_top_tokens(self, client, max_tokens=10):
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(ON_THE_DEX_URL) as response:
                    if response.status != 200:
                        print(f"OnTheDEX API error: Status code {response.status}")
                        return []
                    data = await response.json()
        except Exception as e:
            print(f"Error calling OnTheDEX: {str(e)}")
            return []

        try:
            valid_pairs = []
            for pair in data.get('pairs', []):
                if not (pair.get("base") and pair["base"].get("currency") and pair["base"].get("issuer")):
                    continue
                if pair.get("quote") != "XRP":
                    continue
                if not isinstance(pair.get("num_trades"), (int, float)) or pair.get("num_trades", 0) <= 100:
                    continue
                if pair['base']['issuer'] in self.blocked_issuers:
                    print(f"Skipping: {pair['base']['issuer']}")
                    continue
                valid_pairs.append(pair)

            sorted_pairs = sorted(valid_pairs, key=lambda x: x["num_trades"], reverse=True)
            top_tokens = []
            for pair in sorted_pairs:
                token_encoded = f"{encode_currency(pair['base']['currency']).upper()}.{pair['base']['issuer']}"
                top_tokens.append(token_encoded)
                print(
                    f"Token: {pair['base']['currency']}, Issuer: {pair['base']['issuer']}, "
                    f"Token Issuer: {token_encoded}, Number of trades: {pair['num_trades']}, "
                    f"Trend: {pair.get('trend', 'N/A')}, Last Price: {pair.get('last', 'N/A')}"
                )
        except Exception as e:
            print(f"Error processing OnTheDEX response: {str(e)}")
            return []

        try:
            verified_tokens = []
            for token_key in top_tokens:
                currency, issuer = token_key.split(".")
                best_ask, best_bid, market_price = await self.get_market_prices(currency, issuer, client)
                if market_price is None or best_ask is None or best_bid is None:
                    print(f"Skipping {token_key} due to no pricing data")
                    continue

                # Check liquidity for XRP -> Token (buying token)
                min_amount_needed = float(self.trade_amount) / best_ask if best_ask > 0 else float('inf')
                has_buy_liquidity = await self.check_liquidity(
                    XRP(),
                    IssuedCurrency(currency=currency, issuer=issuer),
                    min_amount_needed,
                    client,
                    expected_price=best_ask,
                    is_sell=False
                )
                if not has_buy_liquidity:
                    print(f"Skipping {token_key} due to insufficient buy liquidity")
                    continue

                # Check liquidity for Token -> XRP (selling token)
                has_sell_liquidity = await self.check_liquidity(
                    IssuedCurrency(currency=currency, issuer=issuer),
                    XRP(),
                    min_amount_needed,  # Approximate, as sell amount depends on trade
                    client,
                    expected_price=best_bid,
                    is_sell=True
                )
                if not has_sell_liquidity:
                    print(f"Skipping {token_key} due to insufficient sell liquidity")
                    continue

                verified_tokens.append(token_key)
                print(f"Verified {token_key} has pricing data and sufficient buy/sell liquidity")
                if len(verified_tokens) >= max_tokens:
                    break

            print(f"Selected {len(verified_tokens)} top tokens with liquidity: {verified_tokens}")
            return verified_tokens
        except Exception as e:
            print(f"Error verifying tokens: {str(e)}")
            return []

    async def get_triangular_pairs(self, client, max_pairs=10):
        tokens = await self.fetch_top_tokens(client, max_tokens=20)
        triangular_pairs = []
        for i, token1 in enumerate(tokens):
            for token2 in tokens[i + 1:]:
                if token1 == token2:
                    continue
                triangular_pairs.append((token1, token2))
        print(f"Generated {len(triangular_pairs)} triangular pairs: {triangular_pairs}")
        return triangular_pairs[:max_pairs]

    async def check_triangular_arbitrage(self, token1_key, token2_key, client):
        print(f"Checking triangular arbitrage for {token1_key} -> {token2_key} -> XRP")
        try:
            currency1, issuer1 = token1_key.split(".")
            currency2, issuer2 = token2_key.split(".")

            best_ask1, best_bid1, market_price1 = await self.get_market_prices(currency1, issuer1, client)
            best_ask2, best_bid2, market_price2 = await self.get_market_prices(currency2, issuer2, client)
            if not all([market_price1, best_bid1, market_price2, best_bid2]) or any(p <= 0 for p in [market_price1, best_bid1, market_price2, best_bid2]):
                print(f"Invalid prices: {market_price1}, {best_bid1}, {market_price2}, {best_bid2}")
                return False

            prices = {
                "forward": {
                    "buy_token1": Decimal(str(best_ask1)),
                    "sell_token1": Decimal(str(best_bid1)),
                    "buy_token2": Decimal(str(best_ask2)),
                    "sell_token2": Decimal(str(best_bid2))
                },
                "reverse": {
                    "buy_token1": Decimal(str(best_ask2)),
                    "sell_token1": Decimal(str(best_bid2)),
                    "buy_token2": Decimal(str(best_ask1)),
                    "sell_token2": Decimal(str(best_bid1))
                }
            }

            best_profit = Decimal('-Infinity')
            best_direction = None

            slippage_factor = Decimal('1.01')  # 1% buffer
            for direction in ["forward", "reverse"]:
                p = prices[direction]
                initial_xrp = Decimal(str(self.trade_amount))
                # token1_amount = initial_xrp / (p["buy_token1"] * slippage_factor)  # Adjust buy price
                token1_amount = initial_xrp / p["buy_token1"]
                xrp_from_token1 = token1_amount * p["sell_token1"]
                token2_amount = xrp_from_token1 / p["buy_token2"]
                # token2_amount = xrp_from_token1 / (p["buy_token2"] * slippage_factor)  # Adjust buy price
                final_xrp = token2_amount * p["sell_token2"]
                total_fees = Decimal(str(self.total_fee_triangular))
                profit = final_xrp - initial_xrp - total_fees

                path = f"XRP -> {token1_key if direction == 'forward' else token2_key} -> XRP -> {token2_key if direction == 'forward' else token1_key} -> XRP"
                print(f"Triangular path ({direction}): {path}")
                print(f"Prices: Buy Token1={float(p['buy_token1']):.8f}, Sell Token1={float(p['sell_token1']):.8f}, Buy Token2={float(p['buy_token2']):.8f}, Sell Token2={float(p['sell_token2']):.8f}")
                print(f"Initial XRP: {float(initial_xrp):.6f}, Token1: {float(token1_amount):.6f}, XRP: {float(xrp_from_token1):.6f}, Token2: {float(token2_amount):.6f}, Final XRP: {float(final_xrp):.6f}")
                print(f"Total Fees: {float(total_fees):.6f}, Profit: {float(profit):.6f}, Min Profit: {self.min_profit}")

                if profit > best_profit:
                    best_profit = profit
                    best_direction = direction

            if Decimal(str(self.min_profit)) < best_profit < Decimal('1.0'):
                print(f"\n*** Triangular arbitrage opportunity ({best_direction})! Profit: {float(best_profit):.6f} ***")
                return True
            else:
                print(f"No triangular arbitrage. Best Profit: {float(best_profit):.6f} not in range [{self.min_profit}, 1.0]")
                return False
        except (InvalidOperation, ValueError) as e:
            print(f"Error in check_triangular_arbitrage: {str(e)}")
            return False

    # async def execute_triangular_trade(self, token1_key, token2_key):
    #     print(f"Executing triangular trade: {token1_key} -> {token2_key} -> XRP")
    #     try:
    #         currency1, issuer1 = token1_key.split(".")
    #         currency2, issuer2 = token2_key.split(".")
    #         initial_xrp_balance = None
    #
    #         async with AsyncWebsocketClient(self.websocket_url) as client:
    #             await self.ensure_open_client(client)
    #
    #             # Log initial XRP balance
    #             account_info = await client.request(AccountInfo(
    #                 account=self.wallet.classic_address, ledger_index="validated"
    #             ))
    #             initial_xrp_balance = float(account_info.result["account_data"]["Balance"]) / 1_000_000
    #             print(f"Starting XRP balance: {initial_xrp_balance:.6f}")
    #
    #             # Setup trustlines if needed (unchanged)
    #             trustline1_exists = False
    #             trustline2_exists = False
    #             lines_response = await client.request(AccountLines(
    #                 account=self.wallet.classic_address, ledger_index="validated"
    #             ))
    #             for line in lines_response.result.get("lines", []):
    #                 if line["currency"] == currency1 and line["account"] == issuer1:
    #                     trustline1_exists = True
    #                 if line["currency"] == currency2 and line["account"] == issuer2:
    #                     trustline2_exists = True
    #
    #             if not trustline1_exists:
    #                 if not await self.setup_trustline(currency1, issuer1):
    #                     return False
    #             if not trustline2_exists:
    #                 if not await self.setup_trustline(currency2, issuer2):
    #                     return False
    #
    #             # Get real-time prices
    #             ask1, bid1 = await self.get_xrpl_order_book(XRP(), IssuedCurrency(currency=currency1, issuer=issuer1), client)
    #             ask2, bid2 = await self.get_xrpl_order_book(XRP(), IssuedCurrency(currency=currency2, issuer=issuer2), client)
    #             if not all([ask1, bid1, ask2, bid2]):
    #                 print("Invalid market prices, aborting trade")
    #                 return False
    #
    #             prices = {
    #                 "forward": {"buy_token1": Decimal(str(ask1)), "sell_token1": Decimal(str(bid1)),
    #                             "buy_token2": Decimal(str(ask2)), "sell_token2": Decimal(str(bid2))},
    #                 "reverse": {"buy_token1": Decimal(str(ask2)), "sell_token1": Decimal(str(bid2)),
    #                             "buy_token2": Decimal(str(ask1)), "sell_token2": Decimal(str(bid1))}
    #             }
    #
    #             best_profit = Decimal('-Infinity')
    #             best_direction = None
    #             for direction in ["forward", "reverse"]:
    #                 p = prices[direction]
    #                 initial_xrp = Decimal(str(self.trade_amount))
    #                 token1_amount = initial_xrp / p["buy_token1"]
    #                 xrp_from_token1 = token1_amount * p["sell_token1"]
    #                 token2_amount = xrp_from_token1 / p["buy_token2"]
    #                 final_xrp = token2_amount * p["sell_token2"]
    #                 profit = final_xrp - initial_xrp - Decimal(str(self.total_fee_triangular))
    #                 if profit > best_profit:
    #                     best_profit = profit
    #                     best_direction = direction
    #
    #             if best_profit <= Decimal('0.05'):
    #                 print(f"No profitable direction found. Best Profit: {float(best_profit):.6f}")
    #                 return False
    #
    #             p = prices[best_direction]
    #             token1_currency = currency1 if best_direction == "forward" else currency2
    #             token1_issuer = issuer1 if best_direction == "forward" else issuer2
    #             token2_currency = currency2 if best_direction == "forward" else currency1
    #             token2_issuer = issuer2 if best_direction == "forward" else issuer1
    #
    #             # Trade 1: Buy Token1 with XRP (reduced buffer to 2%)
    #             token1_amount = Decimal(str(self.trade_amount)) / p["buy_token1"]
    #             token1_amount_buffered = token1_amount * Decimal('1.02')  # 2% buffer
    #             if not await self.check_liquidity(XRP(), IssuedCurrency(currency=token1_currency, issuer=token1_issuer),
    #                                               float(token1_amount_buffered), client):
    #                 print("Aborting trade due to insufficient liquidity for Trade 1")
    #                 return False
    #
    #             token1_amount_str = str(token1_amount_buffered.quantize(Decimal('0.000001'), rounding=ROUND_DOWN))
    #             buy_sequence1 = await get_next_valid_seq_number(self.wallet.classic_address, client)
    #             current_ledger = await self.get_current_ledger(client)
    #             buy_tx1 = OfferCreate(
    #                 account=self.wallet.classic_address,
    #                 taker_gets=str(int(self.trade_amount * 1_000_000)),
    #                 taker_pays=IssuedCurrencyAmount(currency=token1_currency, issuer=token1_issuer, value=token1_amount_str),
    #                 sequence=buy_sequence1, fee=self.ledger_fee, flags=0, last_ledger_sequence=current_ledger + 100
    #             )
    #             buy_result1 = await submit_and_wait(buy_tx1, client, self.wallet)
    #             if not buy_result1.is_successful():
    #                 print(f"Trade 1 failed: {buy_result1.result.get('engine_result')}")
    #                 return False
    #             print(f"Trade 1 submitted: {buy_result1.result}")
    #
    #             retries = 30
    #             token1_balance = 0.0
    #             for attempt in range(retries):
    #                 lines_response = await client.request(AccountLines(account=self.wallet.classic_address, ledger_index="validated"))
    #                 for line in lines_response.result.get("lines", []):
    #                     if line["currency"] == token1_currency and line["account"] == token1_issuer:
    #                         token1_balance = float(line["balance"])
    #                         break
    #                 if token1_balance >= float(token1_amount_str) * 0.99:
    #                     print(f"Trade 1 filled: {token1_balance} {token1_currency} received")
    #                     break
    #                 print(f"Waiting for Trade 1: Attempt {attempt + 1}/{retries}")
    #                 await asyncio.sleep(5)
    #             else:
    #                 print("Trade 1 did not fill in time, canceling")
    #                 await self.cancel_offer(buy_sequence1, client)
    #                 return False
    #
    #             # Trade 2: Sell Token1 for XRP
    #             xrp_from_token1 = Decimal(str(token1_balance)) * p["sell_token1"]
    #             xrp_from_token1_str = str(xrp_from_token1.quantize(Decimal('0.000001'), rounding=ROUND_DOWN))
    #             xrp_from_token1_drops = int(float(xrp_from_token1_str) * 1_000_000)
    #             if not await self.check_liquidity(IssuedCurrency(currency=token1_currency, issuer=token1_issuer), XRP(),
    #                                               float(token1_balance), client):
    #                 print("Aborting trade due to insufficient liquidity for Trade 2")
    #                 return False
    #
    #             buy_sequence2 = await get_next_valid_seq_number(self.wallet.classic_address, client)
    #             current_ledger = await self.get_current_ledger(client)
    #             buy_tx2 = OfferCreate(
    #                 account=self.wallet.classic_address,
    #                 taker_gets=IssuedCurrencyAmount(currency=token1_currency, issuer=token1_issuer, value=str(token1_balance)),
    #                 taker_pays=str(xrp_from_token1_drops), sequence=buy_sequence2, fee=self.ledger_fee, flags=0,
    #                 last_ledger_sequence=current_ledger + 100
    #             )
    #             buy_result2 = await submit_and_wait(buy_tx2, client, self.wallet)
    #             if not buy_result2.is_successful():
    #                 print(f"Trade 2 failed: {buy_result2.result.get('engine_result')}")
    #                 return False
    #             print(f"Trade 2 submitted: {buy_result2.result}")
    #
    #             xrp_balance = 0.0
    #             for attempt in range(retries):
    #                 account_info = await client.request(AccountInfo(account=self.wallet.classic_address, ledger_index="validated"))
    #                 xrp_balance = float(account_info.result["account_data"]["Balance"]) / 1_000_000
    #                 if xrp_balance >= float(xrp_from_token1_str) * 0.99:
    #                     print(f"Trade 2 filled: {xrp_balance} XRP received")
    #                     break
    #                 print(f"Waiting for Trade 2: Attempt {attempt + 1}/{retries}")
    #                 await asyncio.sleep(5)
    #             else:
    #                 print("Trade 2 did not fill in time, canceling")
    #                 await self.cancel_offer(buy_sequence2, client)
    #                 return False
    #
    #             # Trade 3: Buy Token2 with XRP (reduced buffer to 2%)
    #             token2_amount = Decimal(str(xrp_from_token1)) / p["buy_token2"]
    #             token2_amount_buffered = token2_amount * Decimal('1.03')  # 2% buffer
    #             if not await self.check_liquidity(XRP(), IssuedCurrency(currency=token2_currency, issuer=token2_issuer),
    #                                               float(token2_amount_buffered), client):
    #                 print("Aborting trade due to insufficient liquidity for Trade 3")
    #                 return False
    #
    #             token2_amount_str = str(token2_amount_buffered.quantize(Decimal('0.000001'), rounding=ROUND_DOWN))
    #             buy_sequence3 = await get_next_valid_seq_number(self.wallet.classic_address, client)
    #             current_ledger = await self.get_current_ledger(client)
    #             buy_tx3 = OfferCreate(
    #                 account=self.wallet.classic_address,
    #                 taker_gets=str(xrp_from_token1_drops),
    #                 taker_pays=IssuedCurrencyAmount(currency=token2_currency, issuer=token2_issuer, value=token2_amount_str),
    #                 sequence=buy_sequence3, fee=self.ledger_fee, flags=0, last_ledger_sequence=current_ledger + 100
    #             )
    #             buy_result3 = await submit_and_wait(buy_tx3, client, self.wallet)
    #             if not buy_result3.is_successful():
    #                 print(f"Trade 3 failed: {buy_result3.result.get('engine_result')}")
    #                 return False
    #             print(f"Trade 3 submitted: {buy_result3.result}")
    #
    #             token2_balance = 0.0
    #             for attempt in range(retries):
    #                 lines_response = await client.request(AccountLines(account=self.wallet.classic_address, ledger_index="validated"))
    #                 for line in lines_response.result.get("lines", []):
    #                     if line["currency"] == token2_currency and line["account"] == token2_issuer:
    #                         token2_balance = float(line["balance"])
    #                         break
    #                 if token2_balance >= float(token2_amount_str) * 0.99:
    #                     print(f"Trade 3 filled: {token2_balance} {token2_currency} received")
    #                     break
    #                 print(f"Waiting for Trade 3: Attempt {attempt + 1}/{retries}")
    #                 await asyncio.sleep(5)
    #             else:
    #                 print("Trade 3 did not fill in time, canceling")
    #                 await self.cancel_offer(buy_sequence3, client)
    #                 return False
    #
    #             # Trade 4: Sell Token2 for XRP
    #             final_xrp = Decimal(str(token2_balance)) * p["sell_token2"]
    #             final_xrp_str = str(final_xrp.quantize(Decimal('0.000001'), rounding=ROUND_DOWN))
    #             final_xrp_drops = int(float(final_xrp_str) * 1_000_000)
    #             if not await self.check_liquidity(IssuedCurrency(currency=token2_currency, issuer=token2_issuer), XRP(),
    #                                               float(token2_balance), client):
    #                 print("Aborting trade due to insufficient liquidity for Trade 4")
    #                 return False
    #
    #             sell_sequence = await get_next_valid_seq_number(self.wallet.classic_address, client)
    #             current_ledger = await self.get_current_ledger(client)
    #             sell_tx = OfferCreate(
    #                 account=self.wallet.classic_address,
    #                 taker_gets=IssuedCurrencyAmount(currency=token2_currency, issuer=token2_issuer, value=str(token2_balance)),
    #                 taker_pays=str(final_xrp_drops), sequence=sell_sequence, fee=self.ledger_fee, flags=0,
    #                 last_ledger_sequence=current_ledger + 100
    #             )
    #             sell_result = await submit_and_wait(sell_tx, client, self.wallet)
    #             if not sell_result.is_successful():
    #                 print(f"Trade 4 failed: {sell_result.result.get('engine_result')}")
    #                 return False
    #             print(f"Trade 4 submitted: {sell_result.result}")
    #
    #             final_balance = 0.0
    #             for attempt in range(retries):
    #                 account_info = await client.request(AccountInfo(account=self.wallet.classic_address, ledger_index="validated"))
    #                 final_balance = float(account_info.result["account_data"]["Balance"]) / 1_000_000
    #                 if final_balance >= float(final_xrp_str) * 0.99:
    #                     profit = final_balance - initial_xrp_balance - float(self.total_fee_triangular)
    #                     print(f"Trade 4 filled: Triangular trade completed. Final XRP balance: {final_balance:.6f}, Profit: {profit:.6f}")
    #                     self.trade_count += 1
    #                     break
    #                 print(f"Waiting for Trade 4: Attempt {attempt + 1}/{retries}")
    #                 await asyncio.sleep(5)
    #             else:
    #                 print("Trade 4 did not fill in time, canceling")
    #                 await self.cancel_offer(sell_sequence, client)
    #                 return False
    #
    #             # Cleanup residual tokens
    #             await self.cleanup_residuals(client, currency1, issuer1)
    #             await self.cleanup_residuals(client, currency2, issuer2)
    #             return True
    #
    #     except Exception as e:
    #         print(f"Error in execute_triangular_trade: {str(e)}")
    #         return False

    async def execute_triangular_trade(self, token1_key, token2_key):
        print(f"Executing triangular trade: {token1_key} -> {token2_key} -> XRP")
        try:
            currency1, issuer1 = token1_key.split(".")
            currency2, issuer2 = token2_key.split(".")

            async with AsyncWebsocketClient(self.websocket_url) as client:
                await self.ensure_open_client(client)

                # Track starting balance
                account_info = await client.request(AccountInfo(account=self.wallet.classic_address, ledger_index="validated"))
                start_xrp = float(account_info.result["account_data"]["Balance"]) / 1_000_000
                print(f"Starting XRP balance: {start_xrp:.6f}")

                # Trustline setup
                trustline1_exists = False
                trustline2_exists = False
                lines_response = await client.request(AccountLines(account=self.wallet.classic_address, ledger_index="validated"))
                for line in lines_response.result.get("lines", []):
                    if line["currency"] == currency1 and line["account"] == issuer1:
                        trustline1_exists = True
                    if line["currency"] == currency2 and line["account"] == issuer2:
                        trustline2_exists = True
                if not trustline1_exists:
                    print(f"Setting up trustline for {token1_key}")
                    if not await self.setup_trustline(currency1, issuer1):
                        print(f"Failed to set trustline for {token1_key}")
                        return False
                if not trustline2_exists:
                    print(f"Setting up trustline for {token2_key}")
                    if not await self.setup_trustline(currency2, issuer2):
                        print(f"Failed to set trustline for {token2_key}")
                        return False

                # Initial price fetch
                best_ask1, best_bid1, market_price1 = await self.get_market_prices(currency1, issuer1, client)
                best_ask2, best_bid2, market_price2 = await self.get_market_prices(currency2, issuer2, client)
                if not all([best_ask1, best_bid1, best_ask2, best_bid2]) or any(p <= 0 for p in [best_ask1, best_bid1, best_ask2, best_bid2]):
                    print("Invalid market prices, aborting triangular trade")
                    return False

                prices = {
                    "forward": {
                        "buy_token1": Decimal(str(best_ask1)),
                        "sell_token1": Decimal(str(best_bid1)),
                        "buy_token2": Decimal(str(best_ask2)),
                        "sell_token2": Decimal(str(best_bid2))
                    },
                    "reverse": {
                        "buy_token1": Decimal(str(best_ask2)),
                        "sell_token1": Decimal(str(best_bid2)),
                        "buy_token2": Decimal(str(best_ask1)),
                        "sell_token2": Decimal(str(best_bid1))
                    }
                }

                # Determine best direction
                best_profit = Decimal('-Infinity')
                best_direction = None
                for direction in ["forward", "reverse"]:
                    p = prices[direction]
                    initial_xrp = Decimal(str(self.trade_amount))
                    token1_amount = initial_xrp / p["buy_token1"]
                    xrp_from_token1 = token1_amount * p["sell_token1"]
                    token2_amount = xrp_from_token1 / p["buy_token2"]
                    final_xrp = token2_amount * p["sell_token2"]
                    profit = final_xrp - initial_xrp - Decimal(str(self.total_fee_triangular))
                    if profit > best_profit:
                        best_profit = profit
                        best_direction = direction

                if best_profit <= Decimal(str(self.min_profit)):
                    print(f"No profitable direction found. Best Profit: {float(best_profit):.6f}")
                    return False

                p = prices[best_direction]
                token1_currency = currency1 if best_direction == "forward" else currency2
                token1_issuer = issuer1 if best_direction == "forward" else issuer2
                token2_currency = currency2 if best_direction == "forward" else currency1
                token2_issuer = issuer2 if best_direction == "forward" else issuer1

                # Trade 1: Buy Token1 with XRP (with retry logic)
                retries = 12  # 60 seconds total
                min_fill_amount = 1000  # Minimum acceptable fill in token units
                for retry_attempt in range(3):  # Try up to 3 times
                    token1_amount = Decimal(str(self.trade_amount)) / p["buy_token1"]
                    token1_amount_buffered = token1_amount / Decimal('1.02')  # Pay 2% more XRP to outbid
                    if not await self.check_liquidity(
                            XRP(),
                            IssuedCurrency(currency=token1_currency, issuer=token1_issuer),
                            float(token1_amount_buffered),
                            client,
                            expected_price=float(p["buy_token1"]),
                            is_sell=False
                    ):
                        print(f"Aborting due to insufficient liquidity for Trade 1 (attempt {retry_attempt + 1})")
                        return False

                    # Verify sell offer availability
                    book_offers = await client.request(BookOffers(
                        taker_gets=XRP(),
                        taker_pays=IssuedCurrency(currency=token1_currency, issuer=token1_issuer),
                        limit=10,
                        ledger_index="validated"
                    ))
                    offers = book_offers.result.get("offers", [])
                    best_ask = None
                    sell_offer_available = False
                    for offer in offers:
                        if not (offer["Flags"] & 0x00020000):  # Buy offer (ask)
                            price = float(offer["TakerGets"]) / 1_000_000 / float(offer["TakerPays"]["value"])
                            if best_ask is None or price < best_ask:
                                best_ask = price
                        elif offer["Flags"] & 0x00020000:  # Sell offer
                            price = float(offer["TakerGets"]) / 1_000_000 / float(offer["TakerPays"]["value"])
                            available = float(offer["TakerPays"]["value"])
                            if price <= float(p["buy_token1"]) * 1.02 and available >= float(token1_amount_buffered):
                                sell_offer_available = True
                                print(f"Sell offer found: Price={price:.8f}, Available={available:.6f}")
                                break
                    if not sell_offer_available:
                        print(f"No matching sell offers for {token1_currency}.{token1_issuer} at ≤ {float(p['buy_token1']) * 1.02:.8f}, {'retrying' if retry_attempt < 2 else 'aborting'}")
                        if retry_attempt == 2:
                            return False
                        await asyncio.sleep(1)  # Brief delay before retry
                        continue
                    elif best_ask is None:
                        print(f"No buy offers found for {token1_currency}.{token1_issuer}, proceeding based on sell offer (attempt {retry_attempt + 1})")
                    elif best_ask > float(p["buy_token1"]) * 1.02:
                        print(f"Order book shifted, best ask {best_ask:.8f} exceeds expected {float(p['buy_token1']):.8f}, {'retrying' if retry_attempt < 2 else 'aborting'}")
                        if retry_attempt == 2:
                            return False
                        await asyncio.sleep(1)
                        continue

                    token1_amount_str = str(token1_amount_buffered.quantize(Decimal('0.000001'), rounding=ROUND_DOWN))
                    print(f"token1_amount_str (adjusted to beat ask): {token1_amount_str}")
                    buy_sequence1 = await get_next_valid_seq_number(self.wallet.classic_address, client)
                    current_ledger = await self.get_current_ledger(client)
                    buy_tx1 = OfferCreate(
                        account=self.wallet.classic_address,
                        taker_gets=str(int(self.trade_amount * 1_000_000)),
                        taker_pays=IssuedCurrencyAmount(currency=token1_currency, issuer=token1_issuer, value=token1_amount_str),
                        sequence=buy_sequence1,
                        fee=self.ledger_fee,
                        flags=0,
                        last_ledger_sequence=current_ledger + 100
                    )
                    buy_result1 = await submit_and_wait(buy_tx1, client, self.wallet)
                    if not buy_result1.is_successful():
                        print(f"Trade 1 failed (attempt {retry_attempt + 1}): {buy_result1.result.get('engine_result')}")
                        return False
                    print(f"Trade 1 submitted (attempt {retry_attempt + 1}): {buy_result1.result}")

                    # Wait for fill, enforce minimum fill
                    token1_balance = 0.0
                    for attempt in range(retries):
                        lines_response = await client.request(AccountLines(account=self.wallet.classic_address, ledger_index="validated"))
                        for line in lines_response.result.get("lines", []):
                            if line["currency"] == token1_currency and line["account"] == token1_issuer:
                                token1_balance = float(line["balance"])
                                break
                        if token1_balance >= min_fill_amount:  # Require minimum fill
                            print(f"Trade 1 filled: {token1_balance} {token1_currency} received")
                            break
                        elif token1_balance > 0:
                            print(f"Trade 1 partial fill too small: {token1_balance} {token1_currency} received, retrying")
                            await self.cancel_offer(buy_sequence1, client)
                            break
                        print(f"Waiting for Trade 1 (attempt {retry_attempt + 1}): Attempt {attempt + 1}/{retries}")
                        await asyncio.sleep(5)
                    else:
                        print(f"Trade 1 did not fill sufficiently (attempt {retry_attempt + 1}), canceling")
                        await self.cancel_offer(buy_sequence1, client)
                        if retry_attempt == 2:
                            print("Retry Trade 1 failed, aborting")
                            return False
                        await asyncio.sleep(1)
                        continue
                    if token1_balance < min_fill_amount:
                        if retry_attempt == 2:
                            print(f"Trade 1 fill too small after retries: {token1_balance}, aborting")
                            return False
                        await asyncio.sleep(1)
                        continue
                    break  # Exit retry loop if Trade 1 fills sufficiently

                # Trade 2: Sell Token1 for XRP
                xrp_from_token1 = Decimal(str(token1_balance)) * p["sell_token1"]
                xrp_from_token1_str = str(xrp_from_token1.quantize(Decimal('0.000001'), rounding=ROUND_DOWN))
                xrp_from_token1_drops = int(float(xrp_from_token1_str) * 1_000_000)
                if xrp_from_token1_drops < 10:  # XRPL minimum amount check
                    print(f"Trade 2 amount too small: {xrp_from_token1_drops} drops, skipping trade")
                    return False
                if not await self.check_liquidity(
                        IssuedCurrency(currency=token1_currency, issuer=token1_issuer),
                        XRP(),
                        float(token1_balance),
                        client,
                        expected_price=float(p["sell_token1"]),
                        is_sell=True
                ):
                    print("Aborting trade due to insufficient liquidity for Trade 2")
                    return False

                buy_sequence2 = await get_next_valid_seq_number(self.wallet.classic_address, client)
                current_ledger = await self.get_current_ledger(client)
                buy_tx2 = OfferCreate(
                    account=self.wallet.classic_address,
                    taker_gets=IssuedCurrencyAmount(currency=token1_currency, issuer=token1_issuer, value=str(token1_balance)),
                    taker_pays=str(xrp_from_token1_drops),
                    sequence=buy_sequence2,
                    fee=self.ledger_fee,
                    flags=0,
                    last_ledger_sequence=current_ledger + 100
                )
                buy_result2 = await submit_and_wait(buy_tx2, client, self.wallet)
                if not buy_result2.is_successful():
                    print(f"Trade 2 failed: {buy_result2.result.get('engine_result')}")
                    return False
                print(f"Trade 2 submitted: {buy_result2.result}")

                for attempt in range(retries):
                    account_info = await client.request(AccountInfo(account=self.wallet.classic_address, ledger_index="validated"))
                    xrp_balance = float(account_info.result["account_data"]["Balance"]) / 1_000_000
                    if xrp_balance >= float(xrp_from_token1_str) * 0.99:
                        print(f"Trade 2 filled: {xrp_balance} XRP received")
                        break
                    print(f"Waiting for Trade 2: Attempt {attempt + 1}/{retries}")
                    await asyncio.sleep(5)
                else:
                    print("Trade 2 did not fill in time, canceling")
                    await self.cancel_offer(buy_sequence2, client)
                    return False

                # Trade 3: Buy Token2 with XRP
                if not await self.check_liquidity(
                        XRP(),
                        IssuedCurrency(currency=token2_currency, issuer=token2_issuer),
                        float(xrp_from_token1 / p["buy_token2"]),
                        client,
                        expected_price=float(p["buy_token2"]),
                        is_sell=False
                ):
                    print("Aborting trade due to insufficient liquidity for Trade 3")
                    return False

                # Revalidate order book before submission
                book_offers = await client.request(BookOffers(
                    taker_gets=XRP(),
                    taker_pays=IssuedCurrency(currency=token2_currency, issuer=token2_issuer),
                    limit=10,
                    ledger_index="validated"
                ))
                offers = book_offers.result.get("offers", [])
                best_ask = None
                for offer in offers:
                    if not (offer["Flags"] & 0x00020000):  # Buy offer (ask)
                        price = float(offer["TakerGets"]) / 1_000_000 / float(offer["TakerPays"]["value"])
                        funded_gets = float(offer.get("taker_gets_funded", offer["TakerGets"])) / 1_000_000
                        if funded_gets >= float(offer["TakerGets"]) / 1_000_000 * 0.99:  # At least 99% funded
                            if best_ask is None or price < best_ask:
                                best_ask = price
                if best_ask and best_ask > float(p["buy_token2"]) * 1.02:
                    print(f"Order book shifted, new best ask {best_ask:.8f} exceeds expected {float(p['buy_token2']):.8f}, aborting")
                    return False

                if best_ask:
                    print(f"Best ask found: {best_ask:.8f}")
                    token2_amount_base = Decimal(str(xrp_from_token1_drops)) / Decimal('1000000') / Decimal(str(best_ask))
                    token2_amount_str = str(token2_amount_base.quantize(Decimal('0.000001'), rounding=ROUND_DOWN))
                    taker_gets_adjusted = int(Decimal(str(xrp_from_token1_drops)) * Decimal('1.15'))  # 15% overbid
                    effective_price = float(taker_gets_adjusted) / 1000000 / float(token2_amount_str)
                    print(f"Submitting Trade 3 with: TakerGets={taker_gets_adjusted}, TakerPays={token2_amount_str}, effective price={effective_price:.8f}")
                else:
                    print("No best ask found, aborting Trade 3")
                    return False

                if float(token2_amount_str) <= 0 or taker_gets_adjusted < 10:
                    print(f"Invalid Trade 3 amounts: TakerGets={taker_gets_adjusted} drops, TakerPays={token2_amount_str}, skipping trade")
                    return False

                buy_sequence3 = await get_next_valid_seq_number(self.wallet.classic_address, client)
                current_ledger = await self.get_current_ledger(client)
                buy_tx3 = OfferCreate(
                    account=self.wallet.classic_address,
                    taker_gets=str(taker_gets_adjusted),
                    taker_pays=IssuedCurrencyAmount(currency=token2_currency, issuer=token2_issuer, value=token2_amount_str),
                    sequence=buy_sequence3,
                    fee=self.ledger_fee,
                    flags=0,
                    last_ledger_sequence=current_ledger + 100
                )
                buy_result3 = await submit_and_wait(buy_tx3, client, self.wallet)
                if not buy_result3.is_successful():
                    print(f"Trade 3 failed: {buy_result3.result.get('engine_result')}")
                    return False
                print(f"Trade 3 submitted: {buy_result3.result}")

                retries = 24  # Allow up to 120 seconds
                for attempt in range(retries):
                    lines_response = await client.request(AccountLines(account=self.wallet.classic_address, ledger_index="validated"))
                    token2_balance = 0.0
                    for line in lines_response.result.get("lines", []):
                        if line["currency"] == token2_currency and line["account"] == token2_issuer:
                            token2_balance = float(line["balance"])
                            break
                    if token2_balance >= float(token2_amount_str) * 0.5:  # Accept 50% or more of expected fill
                        print(f"Trade 3 partially filled: {token2_balance} {token2_currency} received")
                        break
                    # Log order book for debugging
                    book_offers = await client.request(BookOffers(
                        taker_gets=XRP(),
                        taker_pays=IssuedCurrency(currency=token2_currency, issuer=token2_issuer),
                        limit=5,
                        ledger_index="validated"
                    ))
                    print(f"Trade 3 order book (attempt {attempt + 1}): {book_offers.result.get('offers', [])}")
                    print(f"Waiting for Trade 3: Attempt {attempt + 1}/{retries}")
                    await asyncio.sleep(5)
                else:
                    print("Trade 3 did not fill sufficiently, canceling")
                    await self.cancel_offer(buy_sequence3, client)
                    return False

                # Trade 4: Sell Token2 for XRP
                final_xrp = Decimal(str(token2_balance)) * p["sell_token2"]
                final_xrp_str = str(final_xrp.quantize(Decimal('0.000001'), rounding=ROUND_DOWN))

            final_xrp_drops = int(float(final_xrp_str) * 1_000_000)
            if final_xrp_drops < 10:
                print(f"Trade 4 amount too small: {final_xrp_drops} drops, skipping trade")
                return False
            if not await self.check_liquidity(
                    IssuedCurrency(currency=token2_currency, issuer=token2_issuer),
                    XRP(),
                    float(token2_balance),
                    client,
                    expected_price=float(p["sell_token2"]),
                    is_sell=True
            ):
                print("Aborting trade due to insufficient liquidity for Trade 4")
                return False

            sell_sequence = await get_next_valid_seq_number(self.wallet.classic_address, client)
            current_ledger = await self.get_current_ledger(client)
            sell_tx = OfferCreate(
                account=self.wallet.classic_address,
                taker_gets=IssuedCurrencyAmount(currency=token2_currency, issuer=token2_issuer, value=str(token2_balance)),
                taker_pays=str(final_xrp_drops),
                sequence=sell_sequence,
                fee=self.ledger_fee,
                flags=0,
                last_ledger_sequence=current_ledger + 100
            )
            sell_result = await submit_and_wait(sell_tx, client, self.wallet)
            if not sell_result.is_successful():
                print(f"Trade 4 failed: {sell_result.result.get('engine_result')}")
                return False
            print(f"Trade 4 submitted: {sell_result.result}")

            for attempt in range(retries):
                account_info = await client.request(AccountInfo(account=self.wallet.classic_address, ledger_index="validated"))
                final_balance = float(account_info.result["account_data"]["Balance"]) / 1_000_000
                if final_balance >= float(final_xrp_str) * 0.99:
                    print(f"Trade 4 filled: Triangular trade completed. Final XRP balance: {final_balance:.6f}")
                    self.trade_count += 1
                    break
                print(f"Waiting for Trade 4: Attempt {attempt + 1}/{retries}")
                await asyncio.sleep(5)
            else:
                print("Trade 4 did not fill in time, canceling")
                await self.cancel_offer(sell_sequence, client)
                return False

            # Clean up residuals
            # await self.cleanup_residuals(client, token1_currency, token1_issuer)
            # await self.cleanup_residuals(client, token2_currency, token2_issuer)

            # Log final profit
            account_info = await client.request(AccountInfo(account=self.wallet.classic_address, ledger_index="validated"))
            end_xrp = float(account_info.result["account_data"]["Balance"]) / 1_000_000
            profit = end_xrp - start_xrp
            print(f"Trade profit/loss: {profit:.6f} XRP (Start: {start_xrp:.6f}, End: {end_xrp:.6f})")

            return True

        except (InvalidOperation, ValueError) as e:
            print(f"Error in execute_triangular_trade: {str(e)}")
            return False
        except Exception as e:
            print(f"Unexpected error in execute_triangular_trade: {str(e)}")
            return False

    # async def execute_triangular_trade(self, token1_key, token2_key):
    #     print(f"Executing triangular trade: {token1_key} -> {token2_key} -> XRP")
    #     try:
    #         currency1, issuer1 = token1_key.split(".")
    #         currency2, issuer2 = token2_key.split(".")
    #
    #         async with AsyncWebsocketClient(self.websocket_url) as client:
    #             await self.ensure_open_client(client)
    #
    #             # Track starting balance
    #             account_info = await client.request(AccountInfo(account=self.wallet.classic_address, ledger_index="validated"))
    #             start_xrp = float(account_info.result["account_data"]["Balance"]) / 1_000_000
    #             print(f"Starting XRP balance: {start_xrp:.6f}")
    #
    #             # Trustline setup
    #             trustline1_exists = False
    #             trustline2_exists = False
    #             lines_response = await client.request(AccountLines(account=self.wallet.classic_address, ledger_index="validated"))
    #             for line in lines_response.result.get("lines", []):
    #                 if line["currency"] == currency1 and line["account"] == issuer1:
    #                     trustline1_exists = True
    #                 if line["currency"] == currency2 and line["account"] == issuer2:
    #                     trustline2_exists = True
    #             if not trustline1_exists:
    #                 print(f"Setting up trustline for {token1_key}")
    #                 if not await self.setup_trustline(currency1, issuer1):
    #                     print(f"Failed to set trustline for {token1_key}")
    #                     return False
    #             if not trustline2_exists:
    #                 print(f"Setting up trustline for {token2_key}")
    #                 if not await self.setup_trustline(currency2, issuer2):
    #                     print(f"Failed to set trustline for {token2_key}")
    #                     return False
    #
    #             # Initial price fetch
    #             best_ask1, best_bid1, market_price1 = await self.get_market_prices(currency1, issuer1, client)
    #             best_ask2, best_bid2, market_price2 = await self.get_market_prices(currency2, issuer2, client)
    #             if not all([best_ask1, best_bid1, best_ask2, best_bid2]) or any(p <= 0 for p in [best_ask1, best_bid1, best_ask2, best_bid2]):
    #                 print("Invalid market prices, aborting triangular trade")
    #                 return False
    #
    #             prices = {
    #                 "forward": {
    #                     "buy_token1": Decimal(str(best_ask1)),
    #                     "sell_token1": Decimal(str(best_bid1)),
    #                     "buy_token2": Decimal(str(best_ask2)),
    #                     "sell_token2": Decimal(str(best_bid2))
    #                 },
    #                 "reverse": {
    #                     "buy_token1": Decimal(str(best_ask2)),
    #                     "sell_token1": Decimal(str(best_bid2)),
    #                     "buy_token2": Decimal(str(best_ask1)),
    #                     "sell_token2": Decimal(str(best_bid1))
    #                 }
    #             }
    #
    #             # Determine best direction
    #             best_profit = Decimal('-Infinity')
    #             best_direction = None
    #             for direction in ["forward", "reverse"]:
    #                 p = prices[direction]
    #                 initial_xrp = Decimal(str(self.trade_amount))
    #                 token1_amount = initial_xrp / p["buy_token1"]
    #                 xrp_from_token1 = token1_amount * p["sell_token1"]
    #                 token2_amount = xrp_from_token1 / p["buy_token2"]
    #                 final_xrp = token2_amount * p["sell_token2"]
    #                 profit = final_xrp - initial_xrp - Decimal(str(self.total_fee_triangular))
    #                 if profit > best_profit:
    #                     best_profit = profit
    #                     best_direction = direction
    #
    #             if best_profit <= Decimal(str(self.min_profit)):
    #                 print(f"No profitable direction found. Best Profit: {float(best_profit):.6f}")
    #                 return False
    #
    #             p = prices[best_direction]
    #             token1_currency = currency1 if best_direction == "forward" else currency2
    #             token1_issuer = issuer1 if best_direction == "forward" else issuer2
    #             token2_currency = currency2 if best_direction == "forward" else currency1
    #             token2_issuer = issuer2 if best_direction == "forward" else issuer1
    #
    #             # Trade 1: Buy Token1 with XRP (with retry logic)
    #             retries = 12  # 60 seconds total
    #             for retry_attempt in range(2):  # Try twice: initial + one retry
    #                 # Calculate amount and adjust to beat best ask
    #                 token1_amount = Decimal(str(self.trade_amount)) / p["buy_token1"]
    #                 token1_amount_buffered = token1_amount * Decimal('0.99')  # Pay 0.1% more (get slightly less token)
    #                 if not await self.check_liquidity(XRP(), IssuedCurrency(currency=token1_currency, issuer=token1_issuer), float(token1_amount_buffered), client, expected_price=float(p["buy_token1"]), is_sell=False):
    #                     print(f"Aborting due to insufficient liquidity for Trade 1 (attempt {retry_attempt + 1})")
    #                     return False
    #
    #                 # Verify order book just before submission
    #                 book_offers = await client.request(BookOffers(
    #                     taker_gets=XRP(),
    #                     taker_pays=IssuedCurrency(currency=token1_currency, issuer=token1_issuer),
    #                     limit=10,
    #                     ledger_index="validated"
    #                 ))
    #                 offers = book_offers.result.get("offers", [])
    #                 best_ask = None
    #                 for offer in offers:
    #                     if not (offer["Flags"] & 0x00020000):  # Buy offer (ask)
    #                         price = float(offer["TakerGets"]) / 1_000_000 / float(offer["TakerPays"]["value"])
    #                         if best_ask is None or price < best_ask:
    #                             best_ask = price
    #                 if best_ask is None:
    #                     print(f"No buy offers found for {token1_currency}.{token1_issuer}, proceeding based on prior liquidity check (attempt {retry_attempt + 1})")
    #                 elif best_ask > float(p["buy_token1"]) * 1.01:
    #                     print(f"Order book shifted, best ask {best_ask:.8f} exceeds expected {float(p['buy_token1']):.8f}, {'retrying' if retry_attempt == 0 else 'aborting'}")
    #                     if retry_attempt == 1:
    #                         return False
    #                     # Refresh prices for retry
    #                     best_ask1, best_bid1, market_price1 = await self.get_market_prices(currency1, issuer1, client)
    #                     best_ask2, best_bid2, market_price2 = await self.get_market_prices(currency2, issuer2, client)
    #                     if not all([best_ask1, best_bid1, best_ask2, best_bid2]) or any(p <= 0 for p in [best_ask1, best_bid1, best_ask2, best_bid2]):
    #                         print("Invalid market prices after retry, aborting")
    #                         return False
    #                     prices["forward"] = {"buy_token1": Decimal(str(best_ask1)), "sell_token1": Decimal(str(best_bid1)), "buy_token2": Decimal(str(best_ask2)), "sell_token2": Decimal(str(best_bid2))}
    #                     prices["reverse"] = {"buy_token1": Decimal(str(best_ask2)), "sell_token1": Decimal(str(best_bid2)), "buy_token2": Decimal(str(best_ask1)), "sell_token2": Decimal(str(best_bid1))}
    #                     p = prices[best_direction]
    #                     continue
    #
    #                 token1_amount_str = str(token1_amount_buffered.quantize(Decimal('0.000001'), rounding=ROUND_DOWN))
    #                 print(f"token1_amount_str (adjusted to beat ask): {token1_amount_str}")
    #                 buy_sequence1 = await get_next_valid_seq_number(self.wallet.classic_address, client)
    #                 current_ledger = await self.get_current_ledger(client)
    #                 buy_tx1 = OfferCreate(
    #                     account=self.wallet.classic_address,
    #                     taker_gets=str(int(self.trade_amount * 1_000_000)),
    #                     taker_pays=IssuedCurrencyAmount(currency=token1_currency, issuer=token1_issuer, value=token1_amount_str),
    #                     sequence=buy_sequence1,
    #                     fee=self.ledger_fee,
    #                     flags=0,
    #                     last_ledger_sequence=current_ledger + 100
    #                 )
    #                 buy_result1 = await submit_and_wait(buy_tx1, client, self.wallet)
    #                 if not buy_result1.is_successful():
    #                     print(f"Trade 1 failed (attempt {retry_attempt + 1}): {buy_result1.result.get('engine_result')}")
    #                     return False
    #                 print(f"Trade 1 submitted (attempt {retry_attempt + 1}): {buy_result1.result}")
    #
    #                 # Wait for fill
    #                 token1_balance = 0.0
    #                 for attempt in range(retries):
    #                     lines_response = await client.request(AccountLines(account=self.wallet.classic_address, ledger_index="validated"))
    #                     for line in lines_response.result.get("lines", []):
    #                         if line["currency"] == token1_currency and line["account"] == token1_issuer:
    #                             token1_balance = float(line["balance"])
    #                             break
    #                     if token1_balance > 0:  # Accept any amount received
    #                         print(f"Trade 1 partially or fully filled: {token1_balance} {token1_currency} received")
    #                         break
    #                     # if token1_balance >= float(token1_amount_str) * 0.99:
    #                     #     print(f"Trade 1 filled: {token1_balance} {token1_currency} received")
    #                     #     break
    #                     print(f"Waiting for Trade 1 (attempt {retry_attempt + 1}): Attempt {attempt + 1}/{retries}")
    #                     await asyncio.sleep(5)
    #                 else:
    #                     print(f"Trade 1 did not fill in time (attempt {retry_attempt + 1}), canceling")
    #                     await self.cancel_offer(buy_sequence1, client)
    #                     if retry_attempt == 1:
    #                         print("Retry Trade 1 failed, aborting")
    #                         return False
    #                     # Refresh prices for retry
    #                     best_ask1, best_bid1, market_price1 = await self.get_market_prices(currency1, issuer1, client)
    #                     best_ask2, best_bid2, market_price2 = await self.get_market_prices(currency2, issuer2, client)
    #                     if not all([best_ask1, best_bid1, best_ask2, best_bid2]) or any(p <= 0 for p in [best_ask1, best_bid1, best_ask2, best_bid2]):
    #                         print("Invalid market prices after retry, aborting")
    #                         return False
    #                     prices["forward"] = {"buy_token1": Decimal(str(best_ask1)), "sell_token1": Decimal(str(best_bid1)), "buy_token2": Decimal(str(best_ask2)), "sell_token2": Decimal(str(best_bid2))}
    #                     prices["reverse"] = {"buy_token1": Decimal(str(best_ask2)), "sell_token1": Decimal(str(best_bid2)), "buy_token2": Decimal(str(best_ask1)), "sell_token2": Decimal(str(best_bid1))}
    #                     p = prices[best_direction]
    #                     continue
    #                 break  # Exit retry loop if Trade 1 fills
    #
    #             # Trade 2: Sell Token1 for XRP
    #             xrp_from_token1 = Decimal(str(token1_balance)) * p["sell_token1"]
    #             xrp_from_token1_str = str(xrp_from_token1.quantize(Decimal('0.000001'), rounding=ROUND_DOWN))
    #             xrp_from_token1_drops = int(float(xrp_from_token1_str) * 1_000_000)
    #             if not await self.check_liquidity(
    #                     IssuedCurrency(currency=token1_currency, issuer=token1_issuer),
    #                     XRP(),
    #                     float(token1_balance),
    #                     client,
    #                     expected_price=float(p["sell_token1"]),
    #                     is_sell=True
    #             ):
    #                 print("Aborting trade due to insufficient liquidity for Trade 2")
    #                 return False
    #
    #             buy_sequence2 = await get_next_valid_seq_number(self.wallet.classic_address, client)
    #             current_ledger = await self.get_current_ledger(client)
    #             buy_tx2 = OfferCreate(
    #                 account=self.wallet.classic_address,
    #                 taker_gets=IssuedCurrencyAmount(currency=token1_currency, issuer=token1_issuer, value=str(token1_balance)),
    #                 taker_pays=str(xrp_from_token1_drops),
    #                 sequence=buy_sequence2,
    #                 fee=self.ledger_fee,
    #                 flags=0,
    #                 last_ledger_sequence=current_ledger + 100
    #             )
    #             buy_result2 = await submit_and_wait(buy_tx2, client, self.wallet)
    #             if not buy_result2.is_successful():
    #                 print(f"Trade 2 failed: {buy_result2.result.get('engine_result')}")
    #                 return False
    #             print(f"Trade 2 submitted: {buy_result2.result}")
    #
    #             for attempt in range(retries):
    #                 account_info = await client.request(AccountInfo(account=self.wallet.classic_address, ledger_index="validated"))
    #                 xrp_balance = float(account_info.result["account_data"]["Balance"]) / 1_000_000
    #                 if xrp_balance >= float(xrp_from_token1_str) * 0.99:
    #                     print(f"Trade 2 filled: {xrp_balance} XRP received")
    #                     break
    #                 print(f"Waiting for Trade 2: Attempt {attempt + 1}/{retries}")
    #                 await asyncio.sleep(5)
    #             else:
    #                 print("Trade 2 did not fill in time, canceling")
    #                 await self.cancel_offer(buy_sequence2, client)
    #                 return False
    #
    #             # Trade 3: Buy Token2 with XRP
    #             token2_amount = xrp_from_token1 / p["buy_token2"]
    #             token2_amount_buffered = token2_amount * Decimal('0.999')  # Pay 0.1% more
    #             if not await self.check_liquidity(
    #                     XRP(),
    #                     IssuedCurrency(currency=token2_currency, issuer=token2_issuer),
    #                     float(token2_amount_buffered),
    #                     client,
    #                     expected_price=float(p["buy_token2"]),
    #                     is_sell=False
    #             ):
    #                 print("Aborting trade due to insufficient liquidity for Trade 3")
    #                 return False
    #
    #             token2_amount_str = str(token2_amount_buffered.quantize(Decimal('0.000001'), rounding=ROUND_DOWN))
    #             print(f"token2_amount_str (adjusted to beat ask): {token2_amount_str}")
    #             buy_sequence3 = await get_next_valid_seq_number(self.wallet.classic_address, client)
    #             current_ledger = await self.get_current_ledger(client)
    #             buy_tx3 = OfferCreate(
    #                 account=self.wallet.classic_address,
    #                 taker_gets=str(xrp_from_token1_drops),
    #                 taker_pays=IssuedCurrencyAmount(currency=token2_currency, issuer=token2_issuer, value=token2_amount_str),
    #                 sequence=buy_sequence3,
    #                 fee=self.ledger_fee,
    #                 flags=0,
    #                 last_ledger_sequence=current_ledger + 100
    #             )
    #             buy_result3 = await submit_and_wait(buy_tx3, client, self.wallet)
    #             if not buy_result3.is_successful():
    #                 print(f"Trade 3 failed: {buy_result3.result.get('engine_result')}")
    #                 return False
    #             print(f"Trade 3 submitted: {buy_result3.result}")
    #
    #             for attempt in range(retries):
    #                 lines_response = await client.request(AccountLines(account=self.wallet.classic_address, ledger_index="validated"))
    #                 token2_balance = 0.0
    #                 for line in lines_response.result.get("lines", []):
    #                     if line["currency"] == token2_currency and line["account"] == token2_issuer:
    #                         token2_balance = float(line["balance"])
    #                         break
    #                 if token2_balance >= float(token2_amount_str) * 0.99:
    #                     print(f"Trade 3 filled: {token2_balance} {token2_currency} received")
    #                     break
    #                 print(f"Waiting for Trade 3: Attempt {attempt + 1}/{retries}")
    #                 await asyncio.sleep(5)
    #             else:
    #                 print("Trade 3 did not fill in time, canceling")
    #                 await self.cancel_offer(buy_sequence3, client)
    #                 return False
    #
    #             # Trade 4: Sell Token2 for XRP
    #             final_xrp = Decimal(str(token2_balance)) * p["sell_token2"]
    #             final_xrp_str = str(final_xrp.quantize(Decimal('0.000001'), rounding=ROUND_DOWN))
    #             final_xrp_drops = int(float(final_xrp_str) * 1_000_000)
    #             if not await self.check_liquidity(
    #                     IssuedCurrency(currency=token2_currency, issuer=token2_issuer),
    #                     XRP(),
    #                     float(token2_balance),
    #                     client,
    #                     expected_price=float(p["sell_token2"]),
    #                     is_sell=True
    #             ):
    #                 print("Aborting trade due to insufficient liquidity for Trade 4")
    #                 return False
    #
    #             sell_sequence = await get_next_valid_seq_number(self.wallet.classic_address, client)
    #             current_ledger = await self.get_current_ledger(client)
    #             sell_tx = OfferCreate(
    #                 account=self.wallet.classic_address,
    #                 taker_gets=IssuedCurrencyAmount(currency=token2_currency, issuer=token2_issuer, value=str(token2_balance)),
    #                 taker_pays=str(final_xrp_drops),
    #                 sequence=sell_sequence,
    #                 fee=self.ledger_fee,
    #                 flags=0,
    #                 last_ledger_sequence=current_ledger + 100
    #             )
    #             sell_result = await submit_and_wait(sell_tx, client, self.wallet)
    #             if not sell_result.is_successful():
    #                 print(f"Trade 4 failed: {sell_result.result.get('engine_result')}")
    #                 return False
    #             print(f"Trade 4 submitted: {sell_result.result}")
    #
    #             for attempt in range(retries):
    #                 account_info = await client.request(AccountInfo(account=self.wallet.classic_address, ledger_index="validated"))
    #                 final_balance = float(account_info.result["account_data"]["Balance"]) / 1_000_000
    #                 if final_balance >= float(final_xrp_str) * 0.99:
    #                     print(f"Trade 4 filled: Triangular trade completed. Final XRP balance: {final_balance:.6f}")
    #                     self.trade_count += 1
    #                     break
    #                 print(f"Waiting for Trade 4: Attempt {attempt + 1}/{retries}")
    #                 await asyncio.sleep(5)
    #             else:
    #                 print("Trade 4 did not fill in time, canceling")
    #                 await self.cancel_offer(sell_sequence, client)
    #                 return False
    #
    #             # Clean up residuals
    #             # await self.cleanup_residuals(client, token1_currency, token1_issuer)
    #             # await self.cleanup_residuals(client, token2_currency, token2_issuer)
    #
    #             # Log final profit
    #             account_info = await client.request(AccountInfo(account=self.wallet.classic_address, ledger_index="validated"))
    #             end_xrp = float(account_info.result["account_data"]["Balance"]) / 1_000_000
    #             profit = end_xrp - start_xrp
    #             print(f"Trade profit/loss: {profit:.6f} XRP (Start: {start_xrp:.6f}, End: {end_xrp:.6f})")
    #
    #             return True
    #
    #     except (InvalidOperation, ValueError) as e:
    #         print(f"Error in execute_triangular_trade: {str(e)}")
    #         return False
    #     except Exception as e:
    #         print(f"Unexpected error in execute_triangular_trade: {str(e)}")
    #         return False

    # async def execute_triangular_trade(self, token1_key, token2_key):
    #     print(f"Executing triangular trade: {token1_key} -> {token2_key} -> XRP")
    #     try:
    #         currency1, issuer1 = token1_key.split(".")
    #         currency2, issuer2 = token2_key.split(".")
    #
    #         async with AsyncWebsocketClient(self.websocket_url) as client:
    #             await self.ensure_open_client(client)
    #
    #             account_info = await client.request(AccountInfo(account=self.wallet.classic_address, ledger_index="validated"))
    #             start_xrp = float(account_info.result["account_data"]["Balance"]) / 1_000_000
    #             print(f"Starting XRP balance: {start_xrp:.6f}")
    #
    #             trustline1_exists = False
    #             trustline2_exists = False
    #             lines_response = await client.request(AccountLines(
    #                 account=self.wallet.classic_address,
    #                 ledger_index="validated"
    #             ))
    #             for line in lines_response.result.get("lines", []):
    #                 if line["currency"] == currency1 and line["account"] == issuer1:
    #                     trustline1_exists = True
    #                 if line["currency"] == currency2 and line["account"] == issuer2:
    #                     trustline2_exists = True
    #
    #             if not trustline1_exists:
    #                 print(f"Setting up trustline for {token1_key}")
    #                 if not await self.setup_trustline(currency1, issuer1):
    #                     print(f"Failed to set trustline for {token1_key}")
    #                     return False
    #             if not trustline2_exists:
    #                 print(f"Setting up trustline for {token2_key}")
    #                 if not await self.setup_trustline(currency2, issuer2):
    #                     print(f"Failed to set trustline for {token2_key}")
    #                     return False
    #
    #             best_ask1, best_bid1, market_price1 = await self.get_market_prices(currency1, issuer1, client)
    #             best_ask2, best_bid2, market_price2 = await self.get_market_prices(currency2, issuer2, client)
    #             if not all([best_ask1, best_bid1, best_ask2, best_bid2]) or any(p <= 0 for p in [best_ask1, best_bid1, best_ask2, best_bid2]):
    #                 print("Invalid market prices, aborting triangular trade")
    #                 return False
    #
    #             prices = {
    #                 "forward": {
    #                     "buy_token1": Decimal(str(best_ask1)),
    #                     "sell_token1": Decimal(str(best_bid1)),
    #                     "buy_token2": Decimal(str(best_ask2)),
    #                     "sell_token2": Decimal(str(best_bid2))
    #                 },
    #                 "reverse": {
    #                     "buy_token1": Decimal(str(best_ask2)),
    #                     "sell_token1": Decimal(str(best_bid2)),
    #                     "buy_token2": Decimal(str(best_ask1)),
    #                     "sell_token2": Decimal(str(best_bid1))
    #                 }
    #             }
    #
    #             best_profit = Decimal('-Infinity')
    #             best_direction = None
    #             for direction in ["forward", "reverse"]:
    #                 p = prices[direction]
    #                 initial_xrp = Decimal(str(self.trade_amount))
    #                 token1_amount = initial_xrp / p["buy_token1"]
    #                 xrp_from_token1 = token1_amount * p["sell_token1"]
    #                 token2_amount = xrp_from_token1 / p["buy_token2"]
    #                 final_xrp = token2_amount * p["sell_token2"]
    #                 profit = final_xrp - initial_xrp - Decimal(str(self.total_fee_triangular))
    #                 if profit > best_profit:
    #                     best_profit = profit
    #                     best_direction = direction
    #
    #             if best_profit <= Decimal(str(self.min_profit)):
    #                 print(f"No profitable direction found. Best Profit: {float(best_profit):.6f}")
    #                 return False
    #
    #             p = prices[best_direction]
    #             token1_currency = currency1 if best_direction == "forward" else currency2
    #             token1_issuer = issuer1 if best_direction == "forward" else issuer2
    #             token2_currency = currency2 if best_direction == "forward" else currency1
    #             token2_issuer = issuer2 if best_direction == "forward" else issuer1
    #
    #             # Trade 1: Buy Token1 with XRP
    #             token1_amount = Decimal(str(self.trade_amount)) / p["buy_token1"]
    #             # token1_amount_buffered = token1_amount / Decimal('1.05')  # 10% buffer to increase price
    #             # token1_amount_buffered = token1_amount / Decimal('1.01')
    #             # token1_amount_buffered = token1_amount  # No buffer
    #             token1_amount_buffered = token1_amount * Decimal('0.999')  # Pay up to 0.1% more (get slightly less token)
    #             print(f"token1_amount: {float(token1_amount):.12f}")
    #             print(f"token1_amount_buffered: {float(token1_amount_buffered):.12f}")
    #             if not await self.check_liquidity(
    #                     XRP(),
    #                     IssuedCurrency(currency=token1_currency, issuer=token1_issuer),
    #                     float(token1_amount_buffered),
    #                     client,
    #                     expected_price=float(p["buy_token1"]),
    #                     is_sell=False
    #             ):
    #                 print("Aborting trade due to insufficient liquidity for Trade 1")
    #                 return False
    #
    #             token1_amount_str = str(token1_amount_buffered.quantize(Decimal('0.000001'), rounding=ROUND_DOWN))
    #             print(f"token1_amount_str (5% buffer for higher price): {token1_amount_str}")
    #             buy_sequence1 = await get_next_valid_seq_number(self.wallet.classic_address, client)
    #             current_ledger = await self.get_current_ledger(client)
    #             buy_tx1 = OfferCreate(
    #                 account=self.wallet.classic_address,
    #                 taker_gets=str(int(self.trade_amount * 1_000_000)),
    #                 taker_pays=IssuedCurrencyAmount(currency=token1_currency, issuer=token1_issuer, value=token1_amount_str),
    #                 sequence=buy_sequence1,
    #                 fee=self.ledger_fee,
    #                 flags=0,
    #                 last_ledger_sequence=current_ledger + 100
    #             )
    #             buy_result1 = await submit_and_wait(buy_tx1, client, self.wallet)
    #             if not buy_result1.is_successful():
    #                 print(f"Trade 1 failed: {buy_result1.result.get('engine_result')}")
    #                 return False
    #             print(f"Trade 1 submitted: {buy_result1.result}")
    #
    #             retries = 6
    #             for attempt in range(retries):
    #                 lines_response = await client.request(AccountLines(account=self.wallet.classic_address, ledger_index="validated"))
    #                 token1_balance = 0.0
    #                 for line in lines_response.result.get("lines", []):
    #                     if line["currency"] == token1_currency and line["account"] == token1_issuer:
    #                         token1_balance = float(line["balance"])
    #                         break
    #                 if token1_balance >= float(token1_amount_str) * 0.99:
    #                     print(f"Trade 1 filled: {token1_balance} {token1_currency} received")
    #                     break
    #                 print(f"Waiting for Trade 1: Attempt {attempt + 1}/{retries}")
    #                 await asyncio.sleep(5)
    #             else:
    #                 print("Trade 1 did not fill in time, canceling")
    #                 cancel_tx = OfferCancel(
    #                     account=self.wallet.classic_address,
    #                     offer_sequence=buy_sequence1,
    #                     sequence=await get_next_valid_seq_number(self.wallet.classic_address, client),
    #                     fee=self.ledger_fee
    #                 )
    #                 await submit_and_wait(cancel_tx, client, self.wallet)
    #                 return False
    #
    #             # Trade 2: Sell Token1 for XRP
    #             token1_amount_used = Decimal(str(token1_balance))
    #             xrp_from_token1 = token1_amount_used * p["sell_token1"]
    #             # xrp_from_token1 = Decimal(str(token1_balance)) * p["sell_token1"]
    #
    #             xrp_from_token1_str = str(xrp_from_token1.quantize(Decimal('0.000001'), rounding=ROUND_DOWN))
    #             xrp_from_token1_drops = int(float(xrp_from_token1_str) * 1_000_000)
    #             print(f"xrp_from_token1: {float(xrp_from_token1):.12f}")
    #             print(f"xrp_from_token1_str: {xrp_from_token1_str}")
    #             if not await self.check_liquidity(
    #                     IssuedCurrency(currency=token1_currency, issuer=token1_issuer),
    #                     XRP(),
    #                     float(token1_balance),
    #                     client,
    #                     expected_price=float(p["sell_token1"]),
    #                     is_sell=True
    #             ):
    #                 print("Aborting trade due to insufficient liquidity for Trade 2")
    #                 return False
    #
    #             buy_sequence2 = await get_next_valid_seq_number(self.wallet.classic_address, client)
    #             current_ledger = await self.get_current_ledger(client)
    #             buy_tx2 = OfferCreate(
    #                 account=self.wallet.classic_address,
    #                 taker_gets=IssuedCurrencyAmount(currency=token1_currency, issuer=token1_issuer, value=str(token1_balance)),
    #                 taker_pays=str(xrp_from_token1_drops),
    #                 sequence=buy_sequence2,
    #                 fee=self.ledger_fee,
    #                 flags=0,
    #                 last_ledger_sequence=current_ledger + 100
    #             )
    #             buy_result2 = await submit_and_wait(buy_tx2, client, self.wallet)
    #             if not buy_result2.is_successful():
    #                 print(f"Trade 2 failed: {buy_result2.result.get('engine_result')}")
    #                 return False
    #             print(f"Trade 2 submitted: {buy_result2.result}")
    #
    #             for attempt in range(retries):
    #                 account_info = await client.request(AccountInfo(
    #                     account=self.wallet.classic_address,
    #                     ledger_index="validated"
    #                 ))
    #                 xrp_balance = float(account_info.result["account_data"]["Balance"]) / 1_000_000
    #                 if xrp_balance >= float(xrp_from_token1_str) * 0.99:
    #                     print(f"Trade 2 filled: {xrp_balance} XRP received")
    #                     break
    #                 print(f"Waiting for Trade 2: Attempt {attempt + 1}/{retries}")
    #                 await asyncio.sleep(5)
    #             else:
    #                 print("Trade 2 did not fill in time, canceling")
    #                 cancel_tx = OfferCancel(
    #                     account=self.wallet.classic_address,
    #                     offer_sequence=buy_sequence2,
    #                     sequence=await get_next_valid_seq_number(self.wallet.classic_address, client),
    #                     fee=self.ledger_fee
    #                 )
    #                 await submit_and_wait(cancel_tx, client, self.wallet)
    #                 return False
    #
    #             # Trade 3: Buy Token2 with XRP
    #             token2_amount = xrp_from_token1 / p["buy_token2"]
    #             token2_amount_buffered = token2_amount / Decimal('1.01')
    #
    #             # token2_amount_buffered = token2_amount / Decimal('1.05')  # 10% buffer to increase price
    #             # token2_amount_buffered = token2_amount / Decimal('1.01')  # 1% buffer
    #             # token2_amount_buffered = token2_amount  # No buffer
    #             print(f"token2_amount: {float(token2_amount):.12f}")
    #             print(f"token2_amount_buffered: {float(token2_amount_buffered):.12f}")
    #             if not await self.check_liquidity(
    #                     XRP(),
    #                     IssuedCurrency(currency=token2_currency, issuer=token2_issuer),
    #                     float(token2_amount_buffered),
    #                     client,
    #                     expected_price=float(p["buy_token2"]),
    #                     is_sell=False
    #             ):
    #                 print("Aborting trade due to insufficient liquidity for Trade 3")
    #                 return False
    #
    #             token2_amount_str = str(token2_amount_buffered.quantize(Decimal('0.000001'), rounding=ROUND_DOWN))
    #             print(f"token2_amount_str (10% buffer for higher price): {token2_amount_str}")
    #
    #             buy_sequence3 = await get_next_valid_seq_number(self.wallet.classic_address, client)
    #             current_ledger = await self.get_current_ledger(client)
    #             buy_tx3 = OfferCreate(
    #                 account=self.wallet.classic_address,
    #                 taker_gets=str(xrp_from_token1_drops),
    #                 taker_pays=IssuedCurrencyAmount(currency=token2_currency, issuer=token2_issuer, value=token2_amount_str),
    #                 sequence=buy_sequence3,
    #                 fee=self.ledger_fee,
    #                 flags=0,
    #                 last_ledger_sequence=current_ledger + 100
    #             )
    #             buy_result3 = await submit_and_wait(buy_tx3, client, self.wallet)
    #             if not buy_result3.is_successful():
    #                 print(f"Trade 3 failed: {buy_result3.result.get('engine_result')}")
    #                 return False
    #             print(f"Trade 3 submitted: {buy_result3.result}")
    #
    #             for attempt in range(retries):
    #                 lines_response = await client.request(AccountLines(
    #                     account=self.wallet.classic_address,
    #                     ledger_index="validated"
    #                 ))
    #                 token2_balance = 0.0
    #                 for line in lines_response.result.get("lines", []):
    #                     if line["currency"] == token2_currency and line["account"] == token2_issuer:
    #                         token2_balance = float(line["balance"])
    #                         break
    #                 if token2_balance >= float(token2_amount_str) * 0.99:
    #                     print(f"Trade 3 filled: {token2_balance} {token2_currency} received")
    #                     break
    #                 print(f"Waiting for Trade 3: Attempt {attempt + 1}/{retries}")
    #                 await asyncio.sleep(5)
    #             else:
    #                 print("Trade 3 did not fill in time, canceling")
    #                 cancel_tx = OfferCancel(
    #                     account=self.wallet.classic_address,
    #                     offer_sequence=buy_sequence3,
    #                     sequence=await get_next_valid_seq_number(self.wallet.classic_address, client),
    #                     fee=self.ledger_fee
    #                 )
    #                 await submit_and_wait(cancel_tx, client, self.wallet)
    #                 return False
    #
    #             # Trade 4: Sell Token2 for XRP
    #             final_xrp = Decimal(str(token2_balance)) * p["sell_token2"]
    #             print(f"final_xrp: {final_xrp}")
    #             final_xrp_str = str(final_xrp.quantize(Decimal('0.000001'), rounding=ROUND_DOWN))
    #             print(f"final_xrp_str: {final_xrp_str}")
    #             final_xrp_drops = int(float(final_xrp_str) * 1_000_000)
    #             if not await self.check_liquidity(
    #                     IssuedCurrency(currency=token2_currency, issuer=token2_issuer),
    #                     XRP(),
    #                     float(token2_balance),
    #                     client,
    #                     expected_price=float(p["sell_token2"]),
    #                     is_sell=True
    #             ):
    #                 print("Aborting trade due to insufficient liquidity for Trade 4")
    #                 return False
    #
    #             sell_sequence = await get_next_valid_seq_number(self.wallet.classic_address, client)
    #             current_ledger = await self.get_current_ledger(client)
    #             sell_tx = OfferCreate(
    #                 account=self.wallet.classic_address,
    #                 taker_gets=IssuedCurrencyAmount(currency=token2_currency, issuer=token2_issuer, value=str(token2_balance)),
    #                 taker_pays=str(final_xrp_drops),
    #                 sequence=sell_sequence,
    #                 fee=self.ledger_fee,
    #                 flags=0,
    #                 last_ledger_sequence=current_ledger + 100
    #             )
    #             sell_result = await submit_and_wait(sell_tx, client, self.wallet)
    #             if not sell_result.is_successful():
    #                 print(f"Trade 4 failed: {sell_result.result.get('engine_result')}")
    #                 return False
    #             print(f"Trade 4 submitted: {sell_result.result}")
    #
    #             for attempt in range(retries):
    #                 account_info = await client.request(AccountInfo(
    #                     account=self.wallet.classic_address,
    #                     ledger_index="validated"
    #                 ))
    #                 final_balance = float(account_info.result["account_data"]["Balance"]) / 1_000_000
    #                 if final_balance >= float(final_xrp_str) * 0.99:
    #                     print(f"Trade 4 filled: Triangular trade completed. Final XRP balance: {final_balance:.6f}")
    #                     self.trade_count += 1
    #
    #                     # At the end of execute_triangular_trade, after Trade 4:
    #                     # await self.cleanup_residuals(client, token1_currency, token1_issuer)
    #                     # await self.cleanup_residuals(client, token2_currency, token2_issuer)
    #
    #                     account_info = await client.request(AccountInfo(account=self.wallet.classic_address, ledger_index="validated"))
    #                     end_xrp = float(account_info.result["account_data"]["Balance"]) / 1_000_000
    #                     profit = end_xrp - start_xrp
    #                     print(f"Trade profit/loss: {profit:.6f} XRP (Start: {start_xrp:.6f}, End: {end_xrp:.6f})")
    #                     return True
    #                 print(f"Waiting for Trade 4: Attempt {attempt + 1}/{retries}")
    #                 await asyncio.sleep(5)
    #             else:
    #                 cancel_tx = OfferCancel(
    #                     account=self.wallet.classic_address,
    #                     offer_sequence=sell_sequence,
    #                     sequence=await get_next_valid_seq_number(self.wallet.classic_address, client),
    #                     fee=self.ledger_fee
    #                 )
    #                 await submit_and_wait(cancel_tx, client, self.wallet)
    #                 return False
    #
    #     except (InvalidOperation, ValueError) as e:
    #         print(f"Error in execute_triangular_trade: {str(e)}")
    #         return False

    # async def run(self):
    #     await self.cancel_stale_offers()
    #     async with self.client as client:
    #         if not client.is_open():
    #             await client.open()
    #         self.wallet.sequence = await get_next_valid_seq_number(self.wallet.classic_address, client)
    #
    #     while True:
    #         try:
    #             print("\nStarting new triangular arbitrage scan...")
    #             triangular_pairs = await self.get_triangular_pairs(self.client, max_pairs=10)
    #
    #             if not triangular_pairs:
    #                 print("No pairs found, retrying in 15 seconds...")
    #                 await asyncio.sleep(15)
    #                 continue
    #
    #             print(f"Processing {len(triangular_pairs)} triangular pairs")
    #             for token1_key, token2_key in triangular_pairs:
    #                 async with AsyncWebsocketClient(self.websocket_url) as tri_client:
    #                     await self.ensure_open_client(tri_client)
    #                     if await self.check_triangular_arbitrage(token1_key, token2_key, tri_client):
    #                         success = await self.execute_triangular_trade(token1_key, token2_key)
    #                         if success and self.trade_count >= MAX_NUMBER_OF_TRADES_TO_EXECUTE:
    #                             print("Max trades reached, stopping bot...")
    #                             return
    #             print("Scan completed, waiting 15 seconds for next iteration...")
    #             await asyncio.sleep(15)
    #         except Exception as e:
    #             print(f"Error in run loop: {e}. Retrying in 5 seconds...")
    #             await asyncio.sleep(5)

    async def run(self):
        await self.cancel_stale_offers()
        async with self.client as client:
            if not client.is_open():
                await client.open()
            self.wallet.sequence = await get_next_valid_seq_number(self.wallet.classic_address, client)
        while True:
            try:
                print("\nStarting new triangular arbitrage scan...")
                triangular_pairs = await self.get_triangular_pairs(client, max_pairs=10)

                if not triangular_pairs:
                    print("No pairs found, retrying in 15 seconds...")
                    await asyncio.sleep(15)
                    continue

                print(f"Processing {len(triangular_pairs)} triangular pairs")
                for token1_key, token2_key in triangular_pairs:
                    async with AsyncWebsocketClient(self.websocket_url) as tri_client:
                        await self.ensure_open_client(tri_client)
                        if await self.check_triangular_arbitrage(token1_key, token2_key, tri_client):
                            await self.execute_triangular_trade(token1_key, token2_key)
                    if self.trade_count >= MAX_NUMBER_OF_TRADES_TO_EXECUTE:
                        print("Max trades reached, stopping bot...")
                        return

                print("Scan completed, waiting 10 seconds for next iteration...")
                await asyncio.sleep(15)
            except Exception as e:
                print(f"Error in run loop: {e}. Retrying in 5 seconds...")
                await asyncio.sleep(5)

async def main():
    bot = RealTimeArbitrageBot(spread_percent=0.001)
    await bot.run()

if __name__ == "__main__":
    asyncio.run(main())