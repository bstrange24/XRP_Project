import asyncio
import base64
import logging
import os
import time
from io import BytesIO
from itertools import permutations

import httpx
import qrcode
import yaml
from xrpl.asyncio.clients import AsyncJsonRpcClient, AsyncWebsocketClient
from xrpl.asyncio.transaction import autofill_and_sign, submit_and_wait
from xrpl.models import Fee, BookOffers
from xrpl.wallet import Wallet
from quart import Quart, render_template, jsonify, request
from flask import render_template, jsonify
from db_operations.db_trades import initialize_database, store_trade, update_trade
from utils.constants import JSON_RPC_URL, ENTERING_FUNCTION_LOG, DEBUG, INFO, XRP
from utils.utilities import (
    log_leaving_function, prepare_account_lines, prepare_trust_set,
    prepare_account_info, prepare_account_offers, prepare_offer_cancel,
    prepare_offer_create_get_xrp, prepare_offer_create_get_meme,
    prepare_remove_trust_set, send_alert, confirm_transaction,
    log_entering_function, decode_currency, encode_currency
)

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger('xrpl_trading_bot')

app = Quart(__name__)

class TradingBot:
    def __init__(self):
        self.db_path = os.path.join(BASE_DIR, 'trades.db')
        initialize_database(self, logger)
        self.client = None
        self.wallet = None
        self.running = False
        self.task = None
        self.request_semaphore = asyncio.Semaphore(10)
        self.tx_semaphore = asyncio.Semaphore(2)
        self.active_requests = set()
        self.request_counter = 0
        self.balances = {'XRP': 0}
        self.last_balance_time = 0
        self.meme_coins = []
        self.trade_history = []
        self.metrics = {
            'buy_trades': 0, 'sell_trades': 0, 'triangular_trades': 0,
            'profit_xrp': 0, 'trade_errors': 0, 'runtime_errors': 0,
            'bot_iterations': 0
        }
        self.total_xrp_spent = 0
        self.total_xrp_received = 0
        self.owner_count = 0
        self.total_reserve = 0
        self.wallet_qr_codes = []
        # Configurable settings
        self.min_profit_xrp = None
        self.buy_discount = None
        self.sell_premium = None
        self.slippage_tolerance = None
        self.bot_sleep = None
        self.run_pause = None
        self.max_retries = None
        self.owner_count_limit = None
        self.max_meme_amount_to_hold = None
        self.base_reserve = None
        self.incremental_reserve = None
        self.stop_loss = None
        self.buy_sell_offers_limit = None
        self.buy_sell_offers_retry = None

    async def initialize(self):
        """Initialize the bot with wallet and configuration."""
        logger.info(ENTERING_FUNCTION_LOG.format('initialize'))
        start_time = time.time()
        try:
            self.client = AsyncJsonRpcClient(JSON_RPC_URL)
            self.client._client = httpx.AsyncClient(
                limits=httpx.Limits(max_connections=100, max_keepalive_connections=20),
                timeout=60.0
            )
            await self.load_config()
            self.wallet = await self.load_wallet()
            for meme in self.meme_coins:
                await self.ensure_trust_line(meme['currency'], meme['issuer'])
                self.balances[meme['currency']] = 0
            await self.update_balances(force=True)
            await self.cancel_unused_offers()
            logger.info(f"Bot initialized: {self.wallet.classic_address}")
        except Exception as e:
            logger.error(f"Initialization failed: {str(e)}")
            raise
        finally:
            log_leaving_function('initialize', start_time, logger, INFO)

    async def load_config(self):
        """Load configuration from YAML file."""
        logger.info(ENTERING_FUNCTION_LOG.format('load_config'))
        start_time = time.time()
        try:
            with open("config/trading_bot_config.yaml", 'r') as f:
                config = yaml.safe_load(f)
            self.meme_coins = config['meme_coins']
            settings = config['settings']
            self.min_profit_xrp = float(settings['min_profit_xrp'])
            self.buy_discount = float(settings['buy_discount'])
            self.sell_premium = float(settings['sell_premium'])
            self.slippage_tolerance = float(settings['slippage_tolerance'])
            self.bot_sleep = float(settings['bot_sleep'])
            self.run_pause = float(settings['run_pause'])
            self.max_retries = int(settings['max_retries'])
            self.owner_count_limit = int(settings['owner_count_limit'])
            self.max_meme_amount_to_hold = float(settings['max_meme_amount_to_hold'])
            self.base_reserve = float(settings['base_reserve'])
            self.incremental_reserve = float(settings['incremental_reserve'])
            self.stop_loss = float(settings['stop_loss'])
            self.buy_sell_offers_limit = int(settings['buy_sell_offers_limit'])
            self.buy_sell_offers_retry = int(settings['buy_sell_offers_retry'])
            logger.info(f"Config loaded: {len(self.meme_coins)} meme coins")
        except Exception as e:
            logger.error(f"Config load error: {str(e)}")
            raise
        finally:
            log_leaving_function('load_config', start_time, logger, INFO)

    async def load_wallet(self):
        """Load wallet from config."""
        logger.info(ENTERING_FUNCTION_LOG.format('load_wallet'))
        start_time = time.time()
        request_id = f"load_wallet_{self.request_counter}"
        self.active_requests.add(request_id)
        self.request_counter += 1
        try:
            with open("config/trading_bot_config.yaml", 'r') as f:
                config = yaml.safe_load(f)
            wallet_secret = config['wallet']['xaman_seed']
            wallet = Wallet.from_seed(wallet_secret)
            if wallet.classic_address != config['wallet']['xaman_address']:
                raise ValueError("Seed does not match wallet address")
            logger.info(f"Wallet loaded: {wallet.classic_address}")
            return wallet
        except Exception as e:
            logger.error(f"Wallet load failed: {str(e)}")
            raise
        finally:
            self.active_requests.remove(request_id)
            log_leaving_function('load_wallet', start_time, logger, INFO)

    async def ensure_trust_line(self, currency, issuer):
        """Ensure a trust line exists for a currency."""
        logger.info(ENTERING_FUNCTION_LOG.format('ensure_trust_line'))
        start_time = time.time()
        request_id = f"trust_line_{self.request_counter}"
        self.active_requests.add(request_id)
        self.request_counter += 1
        try:
            async with self.request_semaphore:
                response = await self.client.request(prepare_account_lines(self.wallet.classic_address, "validated"))
            for line in response.result.get("lines", []):
                if decode_currency(line["currency"]) == currency and line["account"] == issuer:
                    return True
            tx = prepare_trust_set(self.wallet.classic_address, encode_currency(currency), issuer, "1000000")
            result = await submit_and_wait(tx, self.client, self.wallet)
            if result.result['meta']['TransactionResult'] == "tesSUCCESS":
                logger.info(f"Trust line set for {currency}/{issuer}")
                return True
            logger.error(f"Failed to set trust line for {currency}: {result.result}")
            return False
        except Exception as e:
            logger.error(f"Trust line error: {str(e)}")
            return False
        finally:
            self.active_requests.remove(request_id)
            log_leaving_function('ensure_trust_line', start_time, logger, INFO)

    async def update_balances(self, force=False):
        """Update account balances."""
        logger.info(ENTERING_FUNCTION_LOG.format('update_balances'))
        start_time = time.time()
        if not force and time.time() - self.last_balance_time < 5:
            return
        request_id = f"balances_{self.request_counter}"
        self.active_requests.add(request_id)
        self.request_counter += 1
        try:
            async with self.request_semaphore:
                info = await self.client.request(prepare_account_info(self.wallet.classic_address, "validated"))
                lines = await self.client.request(prepare_account_lines(self.wallet.classic_address, "validated"))
            self.balances['XRP'] = int(info.result["account_data"]["Balance"]) / 1000000
            self.owner_count = info.result["account_data"]["OwnerCount"]
            self.total_reserve = self.base_reserve + self.owner_count * self.incremental_reserve
            self.balances['XRP'] -= self.total_reserve
            for meme in self.meme_coins:
                self.balances[meme['currency']] = 0
                for line in lines.result.get("lines", []):
                    if decode_currency(line["currency"]) == meme['currency'] and line["account"] == meme['issuer']:
                        self.balances[meme['currency']] = float(line["balance"])
            self.last_balance_time = time.time()
        except Exception as e:
            logger.error(f"Balance update error: {str(e)}")
            raise
        finally:
            self.active_requests.remove(request_id)
            log_leaving_function('update_balances', start_time, logger, INFO)

    async def get_fee(self):
        """Get current network fee."""
        try:
            async with self.request_semaphore:
                fee_response = await self.client.request(Fee())
            return max(float(fee_response.result["drops"]["median_fee"]) / 1000000, 0.000012)
        except Exception as e:
            logger.error(f"Fee fetch error: {str(e)}")
            return 0.000012  # Default minimum fee

    async def fetch_order_book(self, base, quote, base_issuer=None, quote_issuer=None):
        """Fetch order book for a currency pair."""
        logger.info(ENTERING_FUNCTION_LOG.format('fetch_order_book'))
        start_time = time.time()
        request_id = f"order_book_{self.request_counter}"
        self.active_requests.add(request_id)
        self.request_counter += 1
        try:
            taker_gets = {"currency": XRP} if base == 'XRP' else {"currency": encode_currency(base), "issuer": base_issuer}
            taker_pays = {"currency": XRP} if quote == 'XRP' else {"currency": encode_currency(quote), "issuer": quote_issuer}
            async with self.request_semaphore:
                async with AsyncWebsocketClient("wss://s1.ripple.com") as client:
                    self.client._client = client
                    response = await self.client.request(BookOffers(
                        taker_gets=taker_gets, taker_pays=taker_pays,
                        ledger_index="validated", limit=self.buy_sell_offers_limit
                    ))
            return response.result.get('offers', [])
        except Exception as e:
            logger.error(f"Order book fetch error for {base}/{quote}: {str(e)}")
            return []
        finally:
            self.active_requests.remove(request_id)
            log_leaving_function('fetch_order_book', start_time, logger, INFO)

    async def cancel_unused_offers(self):
        """Cancel all open offers."""
        logger.info(ENTERING_FUNCTION_LOG.format('cancel_unused_offers'))
        start_time = time.time()
        request_id = f"cancel_offers_{self.request_counter}"
        self.active_requests.add(request_id)
        self.request_counter += 1
        try:
            async with self.request_semaphore:
                response = await self.client.request(prepare_account_offers(self.wallet.classic_address, "validated"))
            offers = response.result.get('offers', [])
            for offer in offers[:10]:  # Limit to 10 per batch
                tx = prepare_offer_cancel(self.wallet.classic_address, offer['seq'])
                signed_tx = await autofill_and_sign(tx, self.client, self.wallet)
                result = await submit_and_wait(signed_tx, self.client, self.wallet)
                if result.result['meta']['TransactionResult'] == "tesSUCCESS":
                    logger.info(f"Cancelled offer {offer['seq']}")
                await asyncio.sleep(self.run_pause)
        except Exception as e:
            logger.error(f"Cancel offers error: {str(e)}")
        finally:
            self.active_requests.remove(request_id)
            log_leaving_function('cancel_unused_offers', start_time, logger, INFO)

    async def find_bilateral_arbitrage(self, currency, issuer):
        """Find bilateral arbitrage opportunity for a single currency."""
        logger.info(ENTERING_FUNCTION_LOG.format('find_bilateral_arbitrage'))
        start_time = time.time()
        request_id = f"bilateral_{self.request_counter}"
        self.active_requests.add(request_id)
        self.request_counter += 1
        try:
            await self.update_balances(force=True)
            trade_amount = next((m['trade_amount'] for m in self.meme_coins if m['currency'] == currency), 500)
            fee = await self.get_fee() * 2  # Buy + Sell

            if self.balances['XRP'] < self.total_reserve + fee + 0.01:
                return False, 0, 0, 0, None, None

            buy_offers = await self.fetch_order_book('XRP', currency, quote_issuer=issuer)
            sell_offers = await self.fetch_order_book(currency, 'XRP', base_issuer=issuer)

            if not buy_offers or not sell_offers:
                return False, 0, 0, 0, None, None

            best_buy = min(buy_offers, key=lambda o: float(o["TakerPays"]["value"]) / float(o["TakerGets"]))  # XRP → Token
            best_sell = max(sell_offers, key=lambda o: float(o["TakerGets"]) / float(o["TakerPays"]["value"]))  # Token → XRP

            buy_price = float(best_buy["TakerPays"]["value"]) / float(best_buy["TakerGets"]) / 1000000
            sell_price = float(best_sell["TakerGets"]) / float(best_sell["TakerPays"]["value"]) / 1000000
            trade_amount = min(trade_amount, float(best_buy["TakerPays"]["value"]), float(best_sell["TakerPays"]["value"]))

            adj_buy_price = buy_price * self.buy_discount
            adj_sell_price = sell_price * self.sell_premium
            profit = (adj_sell_price - adj_buy_price) * trade_amount - fee

            if profit > self.min_profit_xrp and (adj_sell_price - adj_buy_price) > (fee / trade_amount):
                logger.info(f"Bilateral opportunity for {currency}: Profit={profit:.6f} XRP")
                return True, adj_buy_price, adj_sell_price, profit, best_buy, best_sell
            return False, 0, 0, 0, None, None
        except Exception as e:
            logger.error(f"Bilateral arbitrage error for {currency}: {str(e)}")
            return False, 0, 0, 0, None, None
        finally:
            self.active_requests.remove(request_id)
            log_leaving_function('find_bilateral_arbitrage', start_time, logger, INFO)

    async def find_triangular_arbitrage(self, path):
        """Find triangular arbitrage opportunity for a path (e.g., XRP → PHNIX → SOLO → XRP)."""
        logger.info(ENTERING_FUNCTION_LOG.format('find_triangular_arbitrage'))
        start_time = time.time()
        request_id = f"triangular_{self.request_counter}"
        self.active_requests.add(request_id)
        self.request_counter += 1
        try:
            fee = await self.get_fee() * 3
            offers1 = await self.fetch_order_book(path[0], path[1], quote_issuer=self.get_issuer(path[1]))
            offers2 = await self.fetch_order_book(path[1], path[2], base_issuer=self.get_issuer(path[1]), quote_issuer=self.get_issuer(path[2]))
            offers3 = await self.fetch_order_book(path[2], path[0], base_issuer=self.get_issuer(path[2]))

            if not offers1 or not offers2 or not offers3:
                return False, 0, None, None, None

            best1 = min(offers1, key=lambda o: float(o["TakerPays"]["value"]) / float(o["TakerGets"]))  # XRP → Token1
            best2 = min(offers2, key=lambda o: float(o["TakerPays"]["value"]) / float(o["TakerGets"]))  # Token1 → Token2
            best3 = max(offers3, key=lambda o: float(o["TakerGets"]) / float(o["TakerPays"]["value"]))  # Token2 → XRP

            start_amount = min(10.0, float(best1["TakerGets"]) / 1000000)
            amount1 = start_amount * (float(best1["TakerPays"]["value"]) / float(best1["TakerGets"]))
            amount2 = amount1 * (float(best2["TakerPays"]["value"]) / float(best2["TakerGets"]))
            final_amount = amount2 * (float(best3["TakerGets"]) / float(best3["TakerPays"]["value"])) / 1000000

            profit = final_amount - start_amount - fee
            if profit > self.min_profit_xrp:
                logger.info(f"Triangular opportunity for {path}: Profit={profit:.6f} XRP")
                return True, profit, best1, best2, best3
            return False, 0, None, None, None
        except Exception as e:
            logger.error(f"Triangular arbitrage error for {path}: {str(e)}")
            return False, 0, None, None, None
        finally:
            self.active_requests.remove(request_id)
            log_leaving_function('find_triangular_arbitrage', start_time, logger, INFO)

    def get_issuer(self, currency):
        """Get issuer for a currency."""
        if currency == 'XRP':
            return None
        return next((m['issuer'] for m in self.meme_coins if m['currency'] == currency), None)

    async def execute_bilateral_trade(self, currency, issuer, buy_price, sell_price, profit, buy_offer, sell_offer):
        """Execute a bilateral arbitrage trade."""
        logger.info(ENTERING_FUNCTION_LOG.format('execute_bilateral_trade'))
        start_time = time.time()
        request_id = f"bilateral_trade_{self.request_counter}"
        self.active_requests.add(request_id)
        self.request_counter += 1
        try:
            trade_amount = min(
                float(buy_offer["TakerPays"]["value"]),
                float(sell_offer["TakerPays"]["value"]),
                next((m['trade_amount'] for m in self.meme_coins if m['currency'] == currency), 500)
            )
            buy_xrp = buy_price * trade_amount

            async with self.tx_semaphore:
                tx_buy = prepare_offer_create_get_xrp(self.wallet.classic_address, str(int(buy_xrp * 1000000)), currency, issuer, str(trade_amount))
                result_buy = await submit_and_wait(await autofill_and_sign(tx_buy, self.client, self.wallet), self.client, self.wallet)
                if result_buy.result['meta']['TransactionResult'] != "tesSUCCESS":
                    raise Exception(f"Buy failed: {result_buy.result}")

            self.metrics['buy_trades'] += 1
            self.total_xrp_spent += buy_xrp
            store_trade(self, logger, 'buy', currency, buy_price, trade_amount, buy_xrp, result_buy.result['tx_json']['hash'], "tesSUCCESS")

            await asyncio.sleep(self.run_pause)
            sell_xrp = sell_price * trade_amount
            async with self.tx_semaphore:
                tx_sell = prepare_offer_create_get_meme(self.wallet.classic_address, currency, issuer, str(trade_amount), str(int(sell_xrp * 1000000)))
                result_sell = await submit_and_wait(await autofill_and_sign(tx_sell, self.client, self.wallet), self.client, self.wallet)
                if result_sell.result['meta']['TransactionResult'] != "tesSUCCESS":
                    raise Exception(f"Sell failed: {result_sell.result}")

            self.metrics['sell_trades'] += 1
            self.total_xrp_received += sell_xrp
            realized_profit = sell_xrp - buy_xrp - (await self.get_fee() * 2)
            store_trade(self, logger, 'sell', currency, sell_price, trade_amount, sell_xrp, result_sell.result['tx_json']['hash'], "tesSUCCESS")
            update_trade(self, logger, realized_profit, currency)
            self.metrics['profit_xrp'] += realized_profit
            logger.info(f"Bilateral trade for {currency}: Profit={realized_profit:.6f} XRP")
        except Exception as e:
            logger.error(f"Bilateral trade error for {currency}: {str(e)}")
            self.metrics['trade_errors'] += 1
        finally:
            self.active_requests.remove(request_id)
            log_leaving_function('execute_bilateral_trade', start_time, logger, INFO)

    async def execute_triangular_trade(self, path, profit, offer1, offer2, offer3):
        """Execute a triangular arbitrage trade."""
        logger.info(ENTERING_FUNCTION_LOG.format('execute_triangular_trade'))
        start_time = time.time()
        request_id = f"triangular_trade_{self.request_counter}"
        self.active_requests.add(request_id)
        self.request_counter += 1
        try:
            start_xrp = min(10.0, float(offer1["TakerGets"]) / 1000000)
            amount1 = start_xrp * (float(offer1["TakerPays"]["value"]) / float(offer1["TakerGets"]))
            amount2 = amount1 * (float(offer2["TakerPays"]["value"]) / float(offer2["TakerGets"]))
            final_xrp = amount2 * (float(offer3["TakerGets"]) / float(offer3["TakerPays"]["value"])) / 1000000

            async with self.tx_semaphore:
                tx1 = prepare_offer_create_get_xrp(self.wallet.classic_address, str(int(start_xrp * 1000000)), path[1], self.get_issuer(path[1]), str(amount1))
                result1 = await submit_and_wait(await autofill_and_sign(tx1, self.client, self.wallet), self.client, self.wallet)
                if result1.result['meta']['TransactionResult'] != "tesSUCCESS":
                    raise Exception(f"Step 1 failed: {result1.result}")

            async with self.tx_semaphore:
                tx2 = prepare_offer_create_get_meme(self.wallet.classic_address, path[1], self.get_issuer(path[1]), str(amount1), str(amount2))
                result2 = await submit_and_wait(await autofill_and_sign(tx2, self.client, self.wallet), self.client, self.wallet)
                if result2.result['meta']['TransactionResult'] != "tesSUCCESS":
                    raise Exception(f"Step 2 failed: {result2.result}")

            async with self.tx_semaphore:
                tx3 = prepare_offer_create_get_meme(self.wallet.classic_address, path[2], self.get_issuer(path[2]), str(amount2), str(int(final_xrp * 1000000)))
                result3 = await submit_and_wait(await autofill_and_sign(tx3, self.client, self.wallet), self.client, self.wallet)
                if result3.result['meta']['TransactionResult'] != "tesSUCCESS":
                    raise Exception(f"Step 3 failed: {result3.result}")

            self.metrics['triangular_trades'] += 1
            self.total_xrp_spent += start_xrp
            self.total_xrp_received += final_xrp
            realized_profit = final_xrp - start_xrp - (await self.get_fee() * 3)
            self.metrics['profit_xrp'] += realized_profit
            self.trade_history.append({'type': 'triangular', 'path': path, 'profit': realized_profit, 'timestamp': time.time()})
            logger.info(f"Triangular trade for {path}: Profit={realized_profit:.6f} XRP")
        except Exception as e:
            logger.error(f"Triangular trade error for {path}: {str(e)}")
            self.metrics['trade_errors'] += 1
        finally:
            self.active_requests.remove(request_id)
            log_leaving_function('execute_triangular_trade', start_time, logger, INFO)

    def get_triangular_paths(self):
        """Generate triangular paths starting and ending with XRP."""
        currencies = ['XRP'] + [m['currency'] for m in self.meme_coins]
        return [p for p in permutations(currencies, 3) if p[0] == 'XRP' and p[2] == 'XRP']

    async def check_stop_loss(self):
        """Check if stop-loss threshold is reached."""
        logger.info(ENTERING_FUNCTION_LOG.format('check_stop_loss'))
        start_time = time.time()
        try:
            if self.total_xrp_spent == 0:
                return False
            await self.update_balances(force=True)
            unrealized = sum(self.balances[m['currency']] * await self.get_market_price(m['currency'], m['issuer']) for m in self.meme_coins)
            net_pnl = (self.total_xrp_received - self.total_xrp_spent) + unrealized
            loss_pct = net_pnl / self.total_xrp_spent if self.total_xrp_spent > 0 else 0
            if loss_pct <= self.stop_loss:
                logger.info(f"Stop-loss triggered: {loss_pct:.2%}")
                return True
            return False
        except Exception as e:
            logger.error(f"Stop-loss check error: {str(e)}")
            return False
        finally:
            log_leaving_function('check_stop_loss', start_time, logger, INFO)

    async def get_market_price(self, currency, issuer):
        """Get current market price for a currency."""
        offers = await self.fetch_order_book(currency, 'XRP', base_issuer=issuer)
        if offers:
            best = min(offers, key=lambda o: float(o["TakerPays"]["value"]) / float(o["TakerGets"]))
            return float(best["TakerPays"]["value"]) / float(best["TakerGets"]) / 1000000
        return 0

    async def run(self):
        """Main bot loop."""
        logger.info(ENTERING_FUNCTION_LOG.format('run'))
        start_time = time.time()
        iteration = 0
        paths = self.get_triangular_paths()
        try:
            while self.running:
                iteration += 1
                self.metrics['bot_iterations'] += 1
                logger.info(f"Iteration {iteration}")

                if await self.check_stop_loss():
                    self.running = False
                    break

                await self.update_balances(force=True)
                if self.owner_count >= self.owner_count_limit:
                    await self.cancel_unused_offers()

                # Bilateral arbitrage
                bilateral_tasks = [
                    self.find_bilateral_arbitrage(m['currency'], m['issuer'])
                    for m in self.meme_coins if self.balances[m['currency']] <= self.max_meme_amount_to_hold
                ]
                bilateral_results = await asyncio.gather(*bilateral_tasks, return_exceptions=True)
                for i, result in enumerate(bilateral_results):
                    if isinstance(result, Exception):
                        continue
                    has_opp, buy_price, sell_price, profit, buy_offer, sell_offer = result
                    if has_opp:
                        await self.execute_bilateral_trade(
                            self.meme_coins[i]['currency'], self.meme_coins[i]['issuer'],
                            buy_price, sell_price, profit, buy_offer, sell_offer
                        )

                # Triangular arbitrage
                triangular_tasks = [self.find_triangular_arbitrage(path) for path in paths]
                triangular_results = await asyncio.gather(*triangular_tasks, return_exceptions=True)
                for i, result in enumerate(triangular_results):
                    if isinstance(result, Exception):
                        continue
                    has_opp, profit, offer1, offer2, offer3 = result
                    if has_opp:
                        await self.execute_triangular_trade(paths[i], profit, offer1, offer2, offer3)

                await asyncio.sleep(self.bot_sleep)
        except Exception as e:
            logger.error(f"Run error: {str(e)}")
            self.metrics['runtime_errors'] += 1
        finally:
            log_leaving_function('run', start_time, logger, INFO)

    async def cleanup(self):
        """Clean up resources."""
        if self.client and hasattr(self.client, '_client'):
            await self.client._client.aclose()
            self.client = None

bot = TradingBot()

@app.route('/')
async def index():
    qr = qrcode.QRCode()
    qr.add_data(bot.wallet.classic_address)
    qr_buffer = BytesIO()
    qr.make_image().save(qr_buffer)
    qr_data = base64.b64encode(qr_buffer.getvalue()).decode()
    return await render_template(
        'index.html', metrics=bot.metrics, balances=bot.balances,
        address=bot.wallet.classic_address, qr_code=qr_data, running=bot.running
    )

@app.route('/start', methods=['POST'])
async def start_bot():
    if not bot.running:
        bot.running = True
        bot.task = asyncio.create_task(bot.run())
        return jsonify({'status': 'success', 'message': 'Bot started'})
    return jsonify({'status': 'error', 'message': 'Bot already running'})

@app.route('/stop', methods=['POST'])
async def stop_bot():
    if bot.running:
        bot.running = False
        if bot.task:
            bot.task.cancel()
            await bot.task
        while bot.active_requests:
            await asyncio.sleep(0.5)
        return jsonify({'status': 'success', 'message': 'Bot stopped'})
    return jsonify({'status': 'error', 'message': 'Bot not running'})

@app.route('/status', methods=['GET'])
async def get_status():
    await bot.update_balances()
    return jsonify({
        'running': bot.running, 'metrics': bot.metrics, 'balances': bot.balances,
        'trade_history': bot.trade_history[-100:]
    })

async def initialize_bot():
    await bot.initialize()

if __name__ == "__main__":
    os.makedirs(os.path.join(BASE_DIR, 'logs'), exist_ok=True)
    asyncio.run(initialize_bot())
    app.run(host="127.0.0.1", port=5000)