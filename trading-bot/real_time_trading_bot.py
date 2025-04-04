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

from utils.constants import ON_THE_DEX_URL
from utils.utilities import decode_currency, check_price_change_over_time, check_volume_change_over_time, check_buys_and_sells_over_time, encode_currency

WEB_SOCKET_URL = "wss://s1.ripple.com"  # Mainnet URL
SLIPPAGE_TOLERANCE = 0.02  # 2% tolerance for price movement
OFFER_TIMEOUT = 300  # Cancel offers after 5 minutes

class RealTimeArbitrageBot:
    def __init__(self, websocket_url=WEB_SOCKET_URL, spread_percent=0.001):
        self.max_number_of_trades_to_execute = 3
        self.websocket_url = websocket_url
        self.prices = {}
        self.buy_prices = {}
        self.sell_prices = {}
        self.trade_amount = 0.5  # Amount in XRP, configurable
        self.ledger_fee = "12"  # Mainnet base fee in drops
        self.total_fee = float(self.ledger_fee) * 2 / 1_000_000  # Total fee for buy + sell
        self.min_profit = 0.00004
        self.max_price_history = 10
        self.wallet = Wallet.from_seed("sEdTZP4rtDiXYEoYDLdDXoqKqtedQrC")  # Replace with your mainnet seed
        self.client = AsyncWebsocketClient(self.websocket_url)
        self.trade_count = 0
        self.base_reserve = 1.0
        self.owner_reserve = 0.2
        self.spread_percent = spread_percent  # 1% spread by default, adjustable
        self.blocked_issuers = {"rhvf9fe6PP3GC8Bku2Ug7iQPjPDxYZfrxN", "rHFE5b7dqkBSxSWiCKqAbUHTb1Yp59GirV",
                                "r93hE5FNShDdUqazHzNvwsCxL9mSqwyiru", "rJAvx8FtrLR3RyZyM1LyVQFxxsLdT1PmdS",
                                "rMxCKbEDwqr76QuheSUMdEGf4B9xJ8m5De", "rDvVS42ZgKvFNuacNvJZyQe83JQbTEDVRu"}
        self.trusted_tokens = {
            "41524D5900000000000000000000000000000000.r319FqohpKLwjtcV2mosyC5sy125fDk4uH",  # ARMY
            # "524C555344000000000000000000000000000000.rMxCKbEDwqr76QuheSUMdEGf4B9xJ8m5De", # RLUSD
            # "524146464C450000000000000000000000000000.r99Lp4gCc1TRs9gncbBNPseyqEiuyW2SUa", # RAFFLE
            # "43414E4459000000000000000000000000000000.rBw5VxVudrbLpguMkz5MYx74suk7T8erCb", # Candy
            # "7843686F6D700000000000000000000000000000.rBbJonvm7kQBySWpv4Pc7QNQnb6fokSEjc", # XChomp
        }
        getcontext().prec = 15
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
            print("WebSocket closed, reopening...")
            await client.open()

    async def get_current_ledger(self, client):
        ledger_request = Ledger(ledger_index="validated")
        response = await client.request(ledger_request)
        return int(response.result["ledger_index"])

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
        # Construct the token key to match the trusted token format
        token_key = f"{currency}.{issuer}"
        try:
            # if token_key not in self.trusted_tokens:
            #     print(f"Token {token_key} not in trusted whitelist, skipping price fetch")
            #     return None, None, None

            decoded_currency = decode_currency(currency)
            print(f"decoded_currency: {decoded_currency}")
            print(f"dexscreener url: https://api.dexscreener.com/latest/dex/search?q={decoded_currency}/XRP")
            async with aiohttp.ClientSession() as session:
                async with session.get(f"https://api.dexscreener.com/latest/dex/search?q={decoded_currency}/XRP") as response:
                    if response.status != 200:
                        print(f"DexScreener API error: Status code {response.status}")
                        return None, None, None
                    data = await response.json()

            if "pairs" not in data or not data["pairs"]:
                print("No pairs found in DexScreener API response")
                return None, None, None

            # Find the specific pair with the desired baseToken address
            target_address = f"{currency.upper()}.{issuer}"
            target_address_upper = f"{decoded_currency.upper()}.{issuer}"
            selected_pair = None
            for pair in data["pairs"]:
                if pair.get("baseToken", {}).get("address") == target_address or pair.get("baseToken", {}).get("address") == target_address_upper:
                    selected_pair = pair
                    break

            if not selected_pair:
                print(f"Desired pair with address {target_address} or {target_address_upper} not found in API response")
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

            # Extract the market price (priceNative is in XRP)
            market_price_str = selected_pair.get("priceNative")
            if not market_price_str:
                print("No priceNative found in selected pair")
                return None, None, None

            try:
                market_price = float(market_price_str)
            except ValueError:
                print(f"Invalid priceNative format: {market_price_str}")
                return None, None, None

            # Validate market price
            if not (0.000006 <= market_price <= 0.0011):
                print(f"Market price {market_price:.8f} outside valid range [0.000006, 0.0011]")
                return None, None, None

            # Calculate best_bid and best_ask based on spread_percent
            # - best_bid: price at which others are willing to buy (lower than market)
            # - best_ask: price at which others are willing to sell (higher than market)
            # best_bid = market_price * (1 - self.spread_percent)
            best_bid = market_price
            best_ask = market_price * (1 + self.spread_percent)

            print(f"DexScreener Pricing for {token_key} Market={market_price:.8f}, Bid={best_bid:.8f}, Ask={best_ask:.8f}")
            return best_ask, best_bid, market_price

        except Exception as e:
            print(f"DexScreener Pricing Error for {token_key}: {str(e)}")
            return None, None, None

    async def fetch_top_tokens(self, client, max_tokens=10):
        # Step 1: Fetch API data
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(ON_THE_DEX_URL) as response:
                    if response.status != 200:
                        print(f"OnTheDEX API error: Status code {response.status}")
                        return []
                    data = await response.json()
        except Exception as e:
            print(f"Error calling OnTheDEX in fetch_top_tokens: {str(e)}")
            return []

        try:
            valid_pairs = []
            # Iterate over pairs and filter for valid XRPL tokens
            for pair in data.get('pairs', []):
                if not (pair.get("base") and pair["base"].get("currency") and pair["base"].get("issuer")):
                    continue

                # Filter for pairs where quote is XRP
                if pair.get("quote") != "XRP":
                    continue

                # Ensure num_trades exists and is a number
                if not isinstance(pair.get("num_trades"), (int, float)):
                    continue

                # Filter for num_trades > 1000
                if pair.get("num_trades", 0) <= 1000:
                    continue

                # Filter for trend == "up"
                if pair.get("trend") != "up":
                    continue

                if pair['base']['issuer'] in self.blocked_issuers:
                    print(f"Skipping: {pair['base']['issuer']}")
                    continue

                # Store the pair in valid_pairs
                valid_pairs.append(pair)

            # Sort pairs by num_trades in descending order
            sorted_pairs = sorted(valid_pairs, key=lambda x: x["num_trades"], reverse=True)
            top_tokens = []
            print(f"Found {len(sorted_pairs)} valid XRPL token pairs after filtering")
            if sorted_pairs:
                for pair in sorted_pairs:
                    trend = pair.get("trend", "N/A")
                    token_encoded = f"{encode_currency(pair['base']['currency']).upper()}.{pair['base']['issuer']}"
                    top_tokens.append(token_encoded)
                    print(
                        f"Token: {pair['base']['currency']}, "
                        f"Issuer: {pair['base']['issuer']}, "
                        f"Token Issuer: {token_encoded}, "
                        f"Number of trades: {pair['num_trades']}, "
                        f"Trend: {trend}, "
                        f"Last Price: {pair.get('last', 'N/A')}"
                    )
            else:
                print("No tokens meet the criteria (num_trades > 1000 and trend == 'up').")
        except Exception as e:
            print(f"Error checking OnTheDEX response in fetch_top_tokens: {str(e)}")
            return []

        try:
            # Verify DexScreener compatibility
            verified_tokens = []
            for token_key in top_tokens:
                currency, issuer = token_key.split(".")
                best_ask, best_bid, market_price = await self.get_market_prices(currency, issuer, client)
                if market_price is not None:
                    verified_tokens.append(token_key)
                    print(f"Verified {token_key} has DexScreener data")
                else:
                    print(f"Skipping {token_key}")
                if len(verified_tokens) >= max_tokens:
                    break

            print(f"Selected {len(verified_tokens)} top tokens: {verified_tokens}")
            return verified_tokens

        except Exception as e:
            print(f"Error verifying OnTheDEX tokens in fetch_top_tokens: {str(e)}")
            return []

    async def execute_trade(self, token_key, buy_price=None, sell_price=None):
        try:
            currency, issuer = token_key.split(".") if "." in token_key else (token_key, None)

            # if token_key not in self.trusted_tokens:
            #     print(f"Token {token_key} not in trusted whitelist, skipping trade")
            #     return False

            if issuer in self.blocked_issuers:
                print(f"Skipping trade with blocked issuer: {issuer}")
                return False
        except Exception as e:
            print(f"Error splitting token in execute trade: {str(e)}")
            return False

        async with AsyncWebsocketClient(self.websocket_url) as client:
            await self.ensure_open_client(client)
            account_info = await client.request(AccountInfo(
                account=self.wallet.classic_address,
                ledger_index="validated"
            ))

            try:
                balance = float(account_info.result["account_data"]["Balance"]) / 1_000_000
                owner_count = int(account_info.result["account_data"]["OwnerCount"])
                required_reserve = self.base_reserve + (owner_count + 3) * self.owner_reserve
                available_xrp = balance - required_reserve - (3 * float(self.ledger_fee) / 1_000_000)
                print(f"Total XRP: {balance}, Available XRP: {available_xrp}, Required Reserve: {required_reserve}, Owner Count: {owner_count}")
                if available_xrp < self.trade_amount:
                    print(f"Insufficient funds: Available {available_xrp} XRP, Required {self.trade_amount} XRP")
                    return False
            except Exception as e:
                print(f"Error getting available XRP in execute trade: {str(e)}")
                return False

            try:
                # Check if trustline exists
                lines_response = await client.request(AccountLines(
                    account=self.wallet.classic_address,
                    ledger_index="validated"
                ))
                trustline_exists = any(
                    line["currency"] == currency and line["account"] == issuer
                    for line in lines_response.result.get("lines", [])
                )
                if not trustline_exists:
                    trust_success = await self.setup_trustline(currency, issuer)
                    if not trust_success:
                        print(f"Trustline failed for {token_key}, skipping trade")
                        return False
                else:
                    print(f"Trustline for {token_key} already exists, skipping setup")
            except Exception as e:
                print(f"Error setting trust line in execute trade: {str(e)}")
                return False

            # Fetch real-time market price
            best_ask, best_bid, market_price = await self.get_market_prices(currency, issuer, client)
            if market_price is None:
                print(f"Failed to fetch valid market price for {token_key}, skipping trade")
                return False

            # Buy: Just below market price
            # buy_price = market_price * (1 - self.spread_percent)
            buy_price = market_price
            buy_amount = self.trade_amount / buy_price
            print(f"buy amount: {buy_amount}")

            try:
                buy_amount_str = str(Decimal(str(buy_amount)).quantize(Decimal('1E-15'), rounding=ROUND_DOWN))
                print(f"Market Price: {market_price:.10f}, Buy Price: {buy_price:.10f}")
            except InvalidOperation as e:
                print(f"Decimal quantize failed: {e}")
                return False
            except Exception as e:
                print(f"Error setting market price and buy price in execute trade: {str(e)}")
                return False

            try:
                buy_sequence = await get_next_valid_seq_number(self.wallet.classic_address, client)
            except Exception as e:
                print(f"Error getting next valid sequence number in execute trade: {str(e)}")
                return False
            try:
                current_ledger = await self.get_current_ledger(client)
            except Exception as e:
                print(f"Error getting current ledger in execute trade: {str(e)}")
                return False

            try:
                buy_tx = OfferCreate(
                    account=self.wallet.classic_address,
                    taker_gets=str(int(self.trade_amount * 1_000_000)),
                    taker_pays=IssuedCurrencyAmount(currency=currency, issuer=issuer, value=buy_amount_str),
                    sequence=buy_sequence,
                    fee=self.ledger_fee,
                    flags=0,
                    last_ledger_sequence=current_ledger + 100
                )
                print(f"Submitting buy at ledger {current_ledger}, LastLedgerSequence: {current_ledger + 100}")
            except Exception as e:
                print(f"Error setting buy offer create in execute trade: {str(e)}")
                return False

            try:
                buy_result = await submit_and_wait(buy_tx, client, self.wallet)
                print(f"Buy result: {buy_result.result}")
                if not buy_result.is_successful():
                    print(f"Buy failed for {token_key}: {buy_result.result.get('engine_result', 'Unknown error')}")
                    return False
            except Exception as e:
                print(f"Error in submit and wait in execute trade: {str(e)}")
                return False

            try:
                self.wallet.sequence = await get_next_valid_seq_number(self.wallet.classic_address, client)
            except Exception as e:
                print(f"Error getting next valid sequence number in execute trade: {str(e)}")
                return False

            retries = 20
            for attempt in range(retries):
                lines_response = await client.request(AccountLines(
                    account=self.wallet.classic_address,
                    ledger_index="validated"
                ))
                lines = lines_response.result.get("lines", [])
                token_balance = 0.0
                for line in lines:
                    if line["currency"] == currency and line["account"] == issuer:
                        token_balance = float(line["balance"])
                        break
                if token_balance >= float(buy_amount_str) * 0.99:
                    print(f"Buy offer filled: {token_balance} {currency} received")
                    break
                print(f"Attempt {attempt + 1}/{retries}: Waiting for buy to fill, current balance = {token_balance}")
                await asyncio.sleep(5)
            else:
                print(f"Buy offer did not fill within {retries * 5} seconds")
                cancel_tx = OfferCancel(
                    account=self.wallet.classic_address,
                    offer_sequence=buy_sequence,
                    sequence=self.wallet.sequence,
                    fee=self.ledger_fee
                )
                cancel_result = await submit_and_wait(cancel_tx, client, self.wallet)
                print(f"Cancel result for buy offer {buy_sequence}: {cancel_result.result}")
                self.wallet.sequence += 1
                return False

            # Sell: Just above market price
            sell_price = market_price * (1 + self.spread_percent)
            sell_xrp = float(buy_amount_str) * sell_price
            sell_xrp_str = str(Decimal(str(sell_xrp)).quantize(Decimal('1E-15'), rounding=ROUND_DOWN))
            sell_xrp_drops = int(float(sell_xrp_str) * 1_000_000)
            print(f"Sell Price: {sell_price:.10f}, Quantized sell_xrp_str: {sell_xrp_str}, Sell XRP drops: {sell_xrp_drops}")

            for retry in range(3):  # Retry up to 3 times
                sell_sequence = await get_next_valid_seq_number(self.wallet.classic_address, client)
                current_ledger = await self.get_current_ledger(client)
                sell_tx = OfferCreate(
                    account=self.wallet.classic_address,
                    # taker_gets={"currency": currency, "issuer": issuer, "value": buy_amount_str},
                    taker_gets=IssuedCurrencyAmount(currency=currency, issuer=issuer, value=buy_amount_str),
                    taker_pays=str(sell_xrp_drops),
                    sequence=sell_sequence,
                    fee=self.ledger_fee,
                    flags=0,
                    last_ledger_sequence=current_ledger + 100
                )

                print(f"Submitting sell (attempt {retry + 1}): {sell_tx.to_dict()}")
                sell_result = await submit_and_wait(sell_tx, client, self.wallet)
                print(f"Sell result: {sell_result.result}")
                print(f"Sell transaction metadata: {sell_result.result.get('meta', 'No metadata')}")

                if not sell_result.is_successful():
                    print(f"Sell failed for {token_key}: {sell_result.result.get('engine_result', 'Unknown error')}")
                    return False
                self.wallet.sequence = await get_next_valid_seq_number(self.wallet.classic_address, client)

                retries = 20
                for attempt in range(retries):
                    await asyncio.sleep(3)
                    offers_request = AccountOffers(account=self.wallet.classic_address, ledger_index="validated")
                    offers_response = await client.request(offers_request)
                    offers = offers_response.result.get("offers", [])
                    print(f"Attempt {attempt + 1}: AccountOffers after sell submission: {offers}")
                    if any(o["seq"] == sell_sequence for o in offers):
                        print(f"Sell offer {sell_sequence} confirmed in order book via AccountOffers")
                        self.trade_count += 1
                        return True

                    book_offers = await client.request(BookOffers(
                        taker_gets=IssuedCurrency(currency=currency, issuer=issuer),
                        taker_pays=XRP(),
                        limit=10,
                        ledger_index="validated"
                    ))
                    book_offers_list = book_offers.result.get("offers", [])
                    print(f"Attempt {attempt + 1}: BookOffers after sell submission: {book_offers_list}")
                    if any(o.get("Account") == self.wallet.classic_address and o.get("Sequence") == sell_sequence for o in book_offers_list):
                        print(f"Sell offer {sell_sequence} confirmed in order book via BookOffers")
                        self.trade_count += 1
                        return True

                    lines_response = await client.request(AccountLines(
                        account=self.wallet.classic_address,
                        ledger_index="validated"
                    ))
                    lines = lines_response.result.get("lines", [])
                    token_balance = 0.0
                    for line in lines:
                        if line["currency"] == currency and line["account"] == issuer:
                            token_balance = float(line["balance"])
                            break
                    print(f"Attempt {attempt + 1}: Token balance after sell: {token_balance}")
                    if token_balance < float(buy_amount_str) * 0.99:
                        print(f"Sell offer {sell_sequence} was filled (balance dropped)")
                        self.trade_count += 1
                        return True

                print(f"Sell offer {sell_sequence} not found after {retries} attempts, retrying...")
            else:
                print(f"Sell offer failed to persist after 3 retries, canceling last attempt")
                cancel_tx = OfferCancel(
                    account=self.wallet.classic_address,
                    offer_sequence=sell_sequence,
                    sequence=self.wallet.sequence,
                    fee=self.ledger_fee
                )
                cancel_result = await submit_and_wait(cancel_tx, client, self.wallet)
                print(f"Cancel result for sell offer {sell_sequence}: {cancel_result.result}")
                self.wallet.sequence += 1
                return False

    async def process_transaction(self, message):
        # Optionally keep for debugging or other transaction monitoring
        if message.get("type") != "transaction" or "tx_json" not in message:
            return
        txn = message["tx_json"]
        print(f"Received transaction: {txn['TransactionType']}")
        # Skip price updates since we use DexScreener

    async def check_arbitrage(self, token_key):
        try:
            async with AsyncWebsocketClient(self.websocket_url) as client:
                await self.ensure_open_client(client)
                best_ask, best_bid, market_price = await self.get_market_prices(token_key.split(".")[0], token_key.split(".")[1], client)
                if market_price is None or best_ask is None or best_bid is None:
                    print(f"Failed to fetch valid market price for {token_key}, skipping arbitrage check")
                    return
        except Exception as e:
            print(f"Error in arbitrage AsyncWebsocketClient: {str(e)}")

        try:
            # Calculate buy and sell prices based on market price
            # buy_price = market_price * (1 - self.spread_percent)  # Same as best_bid
            buy_price = market_price
            sell_price = market_price * (1 + self.spread_percent)  # Same as best_ask

            # Calculate profit
            buy_amount = self.trade_amount / buy_price  # Tokens bought with trade_amount XRP
            sell_xrp = buy_amount * sell_price  # XRP received from selling tokens
            profit = sell_xrp - self.trade_amount - self.total_fee  # Profit after fees

            # Check if profit meets minimum threshold
            if self.min_profit < profit < 1.0:  # Upper bound to avoid unrealistic profits
                print(f"{token_key} - Buy Price: {buy_price:.10f}, Sell Price: {sell_price:.10f}")
                print(f"Market Price: {market_price:.10f}, Profit: {profit:.10f}")
                print(f"*** {token_key} Arbitrage opportunity! Profit: {profit:.10f} ***")
                # await self.execute_trade(token_key, buy_price=buy_price, sell_price=sell_price)
            else:
                print(f"No arbitrage opportunity for {token_key}: Profit {profit:.10f} below threshold {self.min_profit}")

        except Exception as e:
            print(f"Error in arbitrage check: {str(e)}")

    async def run(self):
        # await self.cancel_stale_offers()
        async with self.client as client:
            if not client.is_open():
                await client.open()
            self.wallet.sequence = await get_next_valid_seq_number(self.wallet.classic_address, client)
        while True:
            try:
                self.tokens_to_check = await self.fetch_top_tokens(client, max_tokens=10)
                if not self.tokens_to_check:
                    print("No tokens found, retrying in 60 seconds...\n")
                    await asyncio.sleep(15)
                    continue

                # for token_key in self.trusted_tokens:
                for token_key in self.tokens_to_check:
                    await self.check_arbitrage(token_key)
                    if self.trade_count >= self.max_number_of_trades_to_execute:
                        print("One trade completed, stopping bot...")
                        return
                await asyncio.sleep(10)  # Check every 10 seconds
            except Exception as e:
                print(f"Error in run loop: {e}. Retrying in 5 seconds...")
                await asyncio.sleep(5)

async def main():
    bot = RealTimeArbitrageBot(spread_percent=0.001)  # 1% spread
    await bot.run()

if __name__ == "__main__":
    asyncio.run(main())
