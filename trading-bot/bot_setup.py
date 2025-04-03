import base64
import logging
import os
import time
from io import BytesIO
import qrcode
import asyncio
import yaml
from logging.config import dictConfig
from quart import Quart, render_template, jsonify
from xrpl.asyncio.clients import AsyncJsonRpcClient
from xrpl.models import OfferCreate, AccountInfo, AccountLines, GenericRequest, Ledger, AccountOffers, OfferCancel
from xrpl.asyncio.transaction import autofill_and_sign, submit
from xrpl.wallet import Wallet

from utils.constants import ENTERING_FUNCTION_LOG, JSON_RPC_URL

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger('xrpl_trading_bot')

app = Quart(__name__, template_folder='templates2')

class TradingBot2:
    def __init__(self):
        self.incremental_reserve = None
        self.base_reserve = None
        self.sell_premium = None
        self.default_trade_amount = None
        self.config = None
        self.wallets = []  # List of Wallet objects, one per meme coin
        self.client = None
        self.running = False
        self.meme_coins = []  # List of {'currency': str, 'issuer': str, 'trade_amount': float, 'wallet': Wallet}
        self.task = None
        self.thread = None
        self.owner_count = {}  # Per-wallet owner count
        self.metrics = {'trades_executed': 0, 'trade_errors': 0, 'xrp_spent': 0}
        self.balances = {'XRP': {}}  # Nested dict: {'XRP': {address: balance}, currency: {address: balance}}
        self.trade_history = []
        self.active_requests = set()
        self.request_counter = 0

    async def initialize(self):
        try:
            self.client = AsyncJsonRpcClient(JSON_RPC_URL)
            await self.load_config()
            await self.load_wallets()  # Changed to load_wallets (plural)
            await self.cancel_unused_offers()
            await self.get_balance()
            logger.info("Bot initialized successfully.")
        except Exception as e:
            logger.error(f"Initialization failed: {str(e)}", exc_info=True)
            raise

    async def load_config(self):
        global logger
        try:
            with open("config/bot_setup_config.yaml", 'r') as f:
                self.config = yaml.safe_load(f)

            logging_config = self.config.get('logging', {})
            if logging_config:
                file_handler = logging_config['handlers'].get('file', {})
                if 'filename' in file_handler:
                    file_handler['filename'] = os.path.join(BASE_DIR, file_handler['filename'])
                dictConfig(logging_config)
                logger = logging.getLogger('xrpl_trading_bot')

            self.meme_coins = self.config['meme_coins']
            self.default_trade_amount = float(self.config['settings']['trade_amount'])
            self.sell_premium = float(self.config['settings']['sell_premium'])
            self.base_reserve = float(self.config['settings']['base_reserve'])
            self.incremental_reserve = float(self.config['settings']['incremental_reserve'])
            for i, meme in enumerate(self.meme_coins):
                meme['trade_amount'] = float(meme.get('trade_amount', self.default_trade_amount))
                meme['wallet_index'] = i + 1  # Link to wallet (1-based index)
                address_key = f"buy_bot_address{meme['wallet_index']}"
                if address_key not in self.config['wallet']:
                    raise ValueError(f"Missing wallet entry for {address_key}")
                self.balances[meme['currency']] = {}
            logger.info(f"Config loaded: Trading {len(self.meme_coins)} meme coins")
        except Exception as e:
            logger.error(f"Config load error: {e}")
            raise

    async def load_wallets(self):
        try:
            self.wallets = []
            for i, meme in enumerate(self.meme_coins):
                wallet_index = meme['wallet_index']
                address_key = f"buy_bot_address{wallet_index}"
                seed_key = f"buy_bot_seed{wallet_index}"
                wallet_secret = self.config['wallet'][seed_key]
                wallet = Wallet.from_seed(wallet_secret)
                expected_address = self.config['wallet'][address_key]
                if wallet.classic_address != expected_address:
                    raise ValueError(f"Seed {seed_key} does not match address {address_key}")
                self.wallets.append(wallet)
                self.balances['XRP'][wallet.classic_address] = 0
                self.balances[meme['currency']][wallet.classic_address] = 0
                self.owner_count[wallet.classic_address] = 0
                logger.info(f"Wallet {wallet_index} loaded: {wallet.classic_address}")
            if len(self.wallets) != len(self.meme_coins):
                raise ValueError(f"Number of wallets ({len(self.wallets)}) does not match number of meme coins ({len(self.meme_coins)})")
        except Exception as e:
            logger.error(f"Wallet load error: {e}")
            raise

    async def cancel_unused_offers(self):
        logger.info("\n")
        start_time = time.time()
        function_name = 'cancel_unused_offers'
        logger.info(f"Entering: {function_name}")
        try:
            for wallet in self.wallets:
                while True:
                    offers_response = await self.client.request(
                        AccountOffers(account=wallet.classic_address, ledger_index="validated")
                    )
                    offers = offers_response.result.get('offers', [])
                    if not offers:
                        logger.info(f"No offers to cancel for {wallet.classic_address}")
                        break
                    for offer in offers:
                        tx = OfferCancel(account=wallet.classic_address, offer_sequence=offer['seq'])
                        signed_tx = await autofill_and_sign(tx, self.client, wallet)
                        submit_result = await submit(signed_tx, self.client)
                        logger.info(f"Cancelled offer {offer['seq']} for {wallet.classic_address}: {submit_result.result}")
                    await asyncio.sleep(2)
        except Exception as e:
            raise Exception(f"Exception in cancel_unused_offers: {str(e)}")
        finally:
            end_time = time.time()
            logger.info(f"Done cancelling offers")
            logger.info(f"Leaving: {function_name}. Total execution time in ms: {int((end_time - start_time) * 1000)}")


    async def get_latest_validated_ledger_index(self):
        self.request_counter += 1
        request_id = f"get_latest_validated_ledger_index_{self.request_counter}"
        self.active_requests.add(request_id)
        try:
            response = await self.client.request(Ledger(ledger_index="validated"))
            return response.result["ledger_index"]
        except Exception as e:
            logger.error(f"get_latest_validated_ledger_index failed: {str(e)}", exc_info=True)
            raise
        finally:
            self.active_requests.remove(request_id)

    async def get_balance(self):
        start_time = time.time()
        function_name = 'get_balance'
        logger.info(ENTERING_FUNCTION_LOG.format(function_name))

        self.request_counter += 1
        request_id = f"get_balance_{self.request_counter}"
        self.active_requests.add(request_id)
        try:
            for i, wallet in enumerate(self.wallets):
                account_info_response = await self.client.request(AccountInfo(account=wallet.classic_address, ledger_index="validated"))
                account_info = account_info_response.result["account_data"]
                total_xrp = float(account_info['Balance']) / 1000000
                self.owner_count[wallet.classic_address] = int(account_info.get('OwnerCount', 0))
                total_reserve = self.base_reserve + (self.owner_count[wallet.classic_address] * self.incremental_reserve)
                self.balances['XRP'][wallet.classic_address] = total_xrp - total_reserve

                account_lines_response = await self.client.request(AccountLines(account=wallet.classic_address, ledger_index="validated"))
                lines_response = account_lines_response.result
                meme = self.meme_coins[i]
                currency = meme['currency']
                issuer = meme['issuer']
                self.balances[currency][wallet.classic_address] = next(
                    (float(line['balance']) for line in lines_response.get('lines', []) if line['currency'] == currency and line['account'] == issuer),
                    0
                )
                logger.info(f"Balances for {wallet.classic_address}: XRP={self.balances['XRP'][wallet.classic_address]:.6f}, {currency}={self.balances[currency][wallet.classic_address]:.2f}")
        except Exception as e:
            logger.error(f"get_balance failed: {str(e)}", exc_info=True)
            raise
        finally:
            self.active_requests.remove(request_id)
            end_time = time.time()
            logger.info(f"Leaving: {function_name}. Total execution time in ms: {int((end_time - start_time) * 1000)}")

    async def get_market_price(self, currency, issuer):
        start_time = time.time()
        function_name = 'get_market_price'
        logger.info(ENTERING_FUNCTION_LOG.format(function_name))

        self.request_counter += 1
        request_id = f"get_market_price_{self.request_counter}"
        self.active_requests.add(request_id)
        try:
            offers_response = await self.client.request(GenericRequest(
                command="book_offers",
                taker_gets={"currency": currency, "issuer": issuer},
                taker_pays={"currency": "XRP"},
                limit=50
            ))
            offers_response = offers_response.result.get("offers", [])
            if offers_response:
                market_buy = min(
                    float(o["TakerPays"]) / 1000000 / float(o["TakerGets"]["value"])
                    for o in offers_response
                )
                return market_buy
            return 0.000013
        except Exception as e:
            logger.error(f"get_market_price failed for {currency}: {str(e)}", exc_info=True)
            raise
        finally:
            self.active_requests.remove(request_id)
            end_time = time.time()
            logger.info(f"Leaving: {function_name}. Total execution time in ms: {int((end_time - start_time) * 1000)}")

    async def place_buy_offer(self, currency, issuer, trade_amount, wallet):
        start_time = time.time()
        function_name = 'place_buy_offer'
        logger.info(ENTERING_FUNCTION_LOG.format(function_name))

        self.request_counter += 1
        request_id = f"place_buy_offer_{self.request_counter}"
        self.active_requests.add(request_id)
        try:
            await self.get_balance()
            market_price = await self.get_market_price(currency, issuer)
            bid_price = market_price * 1.005
            buy_xrp = int(trade_amount * bid_price * 1000000)
            if self.balances['XRP'][wallet.classic_address] < (buy_xrp / 1000000) + 0.000020:
                logger.warning(f"Insufficient XRP for {currency} on {wallet.classic_address}: {self.balances['XRP'][wallet.classic_address]}")
                return
            tx_buy = OfferCreate(
                account=wallet.classic_address,
                taker_gets={"currency": currency, "issuer": issuer, "value": str(trade_amount)},
                taker_pays=str(buy_xrp),
                last_ledger_sequence=await self.get_latest_validated_ledger_index() + 20
            )
            signed_tx_buy = await autofill_and_sign(tx_buy, self.client, wallet)
            logger.info(f"Submitting buy offer for {currency} at {bid_price} XRP/{currency} from {wallet.classic_address}")
            prelim_result = await submit(signed_tx_buy, self.client)
            logger.info(f"Buy offer submitted for {currency}: {prelim_result.result}")
            trade_status = prelim_result.result.get('engine_result')
            trade = {
                'type': 'buy',
                'currency': currency,
                'price': bid_price,
                'amount': trade_amount,
                'xrp_spent': buy_xrp / 1000000,
                'wallet': wallet.classic_address,
                'timestamp': time.strftime('%Y-%m-%d %H:%M:%S'),
                'status': trade_status
            }
            self.trade_history.append(trade)
            if trade_status == "tesSUCCESS":
                self.metrics['trades_executed'] += 1
                self.metrics['xrp_spent'] += buy_xrp / 1000000
            else:
                self.metrics['trade_errors'] += 1
                logger.warning(f"Buy offer failed for {currency}: {prelim_result.result}")
        except Exception as e:
            logger.error(f"place_buy_offer failed for {currency}: {str(e)}", exc_info=True)
            raise
        finally:
            self.active_requests.remove(request_id)
            end_time = time.time()
            logger.info(f"Leaving: {function_name}. Total execution time in ms: {int((end_time - start_time) * 1000)}")

    async def place_sell_offer(self, currency, issuer, trade_amount, wallet):
        start_time = time.time()
        function_name = 'place_sell_offer'
        logger.info(ENTERING_FUNCTION_LOG.format(function_name))

        self.request_counter += 1
        request_id = f"place_sell_offer_{self.request_counter}"
        self.active_requests.add(request_id)
        try:
            await self.get_balance()
            if self.balances[currency][wallet.classic_address] < trade_amount:
                logger.info(f"Insufficient {currency} on {wallet.classic_address}")
                return
            market_price = await self.get_market_price(currency, issuer)
            ask_price = market_price * 1.005
            sell_xrp = int(trade_amount * ask_price * 1000000)
            tx_sell = OfferCreate(
                account=wallet.classic_address,
                taker_gets=str(sell_xrp),
                taker_pays={"currency": currency, "issuer": issuer, "value": str(trade_amount)},
                last_ledger_sequence=await self.get_latest_validated_ledger_index() + 50
            )
            signed_tx_sell = await autofill_and_sign(tx_sell, self.client, wallet)
            logger.info(f"Submitting sell offer for {currency} at {ask_price} XRP/{currency} from {wallet.classic_address}")
            prelim_result = await submit(signed_tx_sell, self.client)
            logger.info(f"Sell offer submitted for {currency}: {prelim_result.result}")
            trade_status = prelim_result.result.get('engine_result')
            trade = {
                'type': 'sell',
                'currency': currency,
                'price': ask_price,
                'amount': trade_amount,
                'xrp_received': sell_xrp / 1000000,
                'wallet': wallet.classic_address,
                'timestamp': time.strftime('%Y-%m-%d %H:%M:%S'),
                'status': trade_status
            }
            self.trade_history.append(trade)
            if trade_status == "tesSUCCESS":
                self.metrics['trades_executed'] += 1
            else:
                self.metrics['trade_errors'] += 1
        except Exception as e:
            logger.error(f"place_sell_offer failed for {currency}: {str(e)}", exc_info=True)
            raise
        finally:
            self.active_requests.remove(request_id)
            end_time = time.time()
            logger.info(f"Leaving: {function_name}. Total execution time in ms: {int((end_time - start_time) * 1000)}")

    async def run(self):
        iteration = 0
        while self.running:
            start_time = time.time()
            function_name = 'run'
            logger.info(ENTERING_FUNCTION_LOG.format(function_name))

            iteration += 1
            logger.info(f"Bot 2 iteration {iteration}")
            await self.get_balance()
            tasks = []

            # for i, meme in enumerate(self.meme_coins):
            #     currency = meme['currency']
            #     issuer = meme['issuer']
            #     trade_amount = meme['trade_amount']
            #     wallet = self.wallets[i]
            #     # Place multiple buy offers concurrently
            #     tasks.append(self.place_buy_offer(currency, issuer, trade_amount, wallet))
            #     offers_response = await self.client.request(
            #         AccountOffers(account=wallet.classic_address, ledger_index="validated"))
            #     sell_offers = [o for o in offers_response.result.get('offers', []) if
            #                    'TakerGets' in o and isinstance(o['TakerGets'], str) and
            #                    o.get('TakerPays', {}).get('currency') == currency]
            #     # Place up to 5 sell offers per currency
            #     for _ in range(max(0, 5 - len(sell_offers))):
            #         tasks.append(self.place_sell_offer(currency, issuer, trade_amount, wallet))
            # await asyncio.gather(*tasks, return_exceptions=True)  # Execute all offers concurrently
            # await asyncio.sleep(1)
            #
            # end_time = time.time()
            # logger.info(f"Leaving: {function_name}. Total execution time in ms: {int((end_time - start_time) * 1000)}")

            for i, meme in enumerate(self.meme_coins):
                currency = meme['currency']
                issuer = meme['issuer']
                trade_amount = meme['trade_amount']
                wallet = self.wallets[i]
                await self.place_buy_offer(currency, issuer, trade_amount, wallet)
                offers_response = await self.client.request(AccountOffers(account=wallet.classic_address, ledger_index="validated"))
                sell_offers = [o for o in offers_response.result.get('offers', []) if 'TakerGets' in o and isinstance(o['TakerGets'], str)]
                for _ in range(max(0, 3 - len(sell_offers))):
                    await self.place_sell_offer(currency, issuer, trade_amount, wallet)
            await asyncio.sleep(1)
            end_time = time.time()
            logger.info(f"Leaving: {function_name}. Total execution time in ms: {int((end_time - start_time) * 1000)}")

bot2 = TradingBot2()

@app.route('/')
async def index():
    try:
        logger.info("Rendering index page...")
        qr_codes = []
        for wallet in bot2.wallets:
            qr = qrcode.QRCode()
            qr.add_data(wallet.classic_address)
            qr_buffer = BytesIO()
            qr.make_image().save(qr_buffer)
            qr_codes.append(base64.b64encode(qr_buffer.getvalue()).decode())
        return await render_template('index.html',
                                     metrics=bot2.metrics,
                                     balances=bot2.balances,
                                     wallets=bot2.wallets,
                                     qr_codes=qr_codes,  # Pass list of QR codes
                                     running=bot2.running,
                                     meme_coins=bot2.meme_coins)
    except Exception as e:
        logger.error(f"Error in index route: {e}", exc_info=True)
        return "Internal Server Error index", 500

@app.route('/start', methods=['POST'])
async def start_bot():
    try:
        if not bot2.running:
            bot2.running = True
            asyncio.create_task(bot2.run())
            logging.info("Bot 2 thread started")
            return jsonify({'status': 'success', 'message': 'Bot 2 started'})
        return jsonify({'status': 'error', 'message': 'Bot 2 already running'})
    except Exception as e:
        logging.error(f"Error in start_bot: {e}", exc_info=True)
        return "Internal Server Error start_bot", 500

@app.route('/stop', methods=['POST'])
async def stop_bot():
    try:
        if bot2.running:
            bot2.running = False
            if bot2.task:  # Cancel the bot.run() task if it exists
                bot2.task.cancel()
                try:
                    await bot2.task  # Wait for the task to be cancelled
                except asyncio.CancelledError:
                    logging.info("Bot task was cancelled successfully")

            # Wait for all active XRPL requests to complete
            timeout = 60  # seconds
            start_time = time.time()
            while bot2.active_requests and (time.time() - start_time) < timeout:
                logging.info(f"Waiting for {len(bot2.active_requests)} active requests to complete...")
                await asyncio.sleep(2)  # Brief sleep to avoid busy-waiting

            if bot2.active_requests:
                logging.warning(f"Timeout reached, {len(bot2.active_requests)} requests still active")

            logging.info("Bot stopped")
            return jsonify({'status': 'success', 'message': 'Bot 2 is sleeping'})
        return jsonify({'status': 'error', 'message': 'Bot 2 not running'})
    except Exception as e:
        logging.error(f"Error in stop_bot: {e}", exc_info=True)
        return "Internal Server Error stop_bot", 500

@app.route('/kill', methods=['POST'])
async def kill_bot():
    try:
        logging.info("Shutting down the application...")
        # Stop the bot if it's running
        if bot2.running:
            bot2.running = False
            if bot2.task:
                bot2.task.cancel()
                try:
                    await bot2.task
                except asyncio.CancelledError:
                    logging.info("Bot task was cancelled successfully")

            # Wait for all active XRPL requests to complete
            timeout = 20  # seconds
            start_time = time.time()
            while bot2.active_requests and (time.time() - start_time) < timeout:
                logging.info(f"Waiting for {len(bot2.active_requests)} active requests to complete...")
                await asyncio.sleep(2)  # Brief sleep to avoid busy-waiting

            if bot2.active_requests:
                logging.warning(f"Timeout reached, {len(bot2.active_requests)} requests still active")

        # Send a response to the client before shutting down
        response = jsonify({'status': 'success', 'message': 'The Application is toasted'})

        # Schedule a background task to shut down the server after the response is sent
        """Shut down the server gracefully."""
        logging.info("Shutting down the server...")
        asyncio.get_event_loop().create_task(app.shutdown())

        return response
    except Exception as e:
        logging.info(f"Error in kill_bot: {e}", exc_info=True)
        return "Internal Server Error kill_bot", 500

@app.route('/status', methods=['GET'])
async def get_status():
    try:
        safe_balances = {k: v for k, v in bot2.balances.items() if k is not None}
        return jsonify({
            'running': bot2.running,
            'metrics': bot2.metrics,
            'balances': safe_balances,
            'trade_history': bot2.trade_history[-1000:],
            'meme_coins': [{'currency': m['currency'], 'issuer': m['issuer'], 'trade_amount': m['trade_amount']} for m in bot2.meme_coins]
        })
    except Exception as e:
        logger.error(f"Error in get_status: {e}", exc_info=True)
        return "Internal Server Error get_status", 500

async def initialize_bot2():
    try:
        await bot2.initialize()
        logging.info("Bot initialized successfully.")
        for i, wallet in enumerate(bot2.wallets):
            logging.info(f"Wallet address: { wallet.classic_address} seed: {wallet.seed}")
        logging.info(f"Balances: {bot2.balances}")
    except Exception as e:
        logging.error(f"Failed to initialize bot: {e}", exc_info=True)
        raise

if __name__ == "__main__":
    logging.info("Initializing bot...")
    os.makedirs(os.path.join(BASE_DIR, 'logs'), exist_ok=True)
    asyncio.run(initialize_bot2()) # Call initialize_bot2() to initialize the bot

    logging.info("Starting Quart application with Hypercorn")
    from hypercorn.config import Config
    from hypercorn.asyncio import serve

    # Create a Hypercorn config
    config = Config()
    config.bind = ["127.0.0.1:5001"]
    config.use_reloader = False

    # Run the app with Hypercorn
    asyncio.run(serve(app, config))

################## Works with one meme
# import base64
# import logging
# import os
# import time
# from io import BytesIO
# import qrcode
# import asyncio
# import yaml
# from logging.config import dictConfig
# from quart import Quart, render_template, jsonify
# from xrpl.asyncio.clients import AsyncJsonRpcClient
# from xrpl.models import OfferCreate, AccountInfo, AccountLines, GenericRequest, Ledger, AccountOffers, OfferCancel
# from xrpl.asyncio.transaction import autofill_and_sign, submit
# from xrpl.wallet import Wallet
#
# # Define BASE_DIR
# BASE_DIR = os.path.dirname(os.path.abspath(__file__))
# logging.basicConfig(level=logging.INFO)
# logger = logging.getLogger('xrpl_trading_bot')
#
# app = Quart(__name__, template_folder='templates2')
# JSON_RPC_URL = "https://s.altnet.rippletest.net:51234/"
#
# class TradingBot2:
#     def __init__(self):
#         self.incremental_reserve = None
#         self.base_reserve = None
#         self.sell_premium = None
#         self.trade_amount = None
#         self.issuer_address = None
#         self.config = None
#         self.wallet = None
#         self.client = None
#         self.running = False
#         self.currency = None
#         self.task = None  # Track the bot.run() task
#         self.thread = None
#         self.owner_count = None
#         self.metrics = {'trades_executed': 0, 'trade_errors': 0, 'xrp_spent': 0}
#         self.balances = {'XRP': 0}  # Initialize with only XRP
#         self.trade_history = []
#         self.active_requests = set()  # Track active network requests
#         self.request_counter = 0  # Unique ID for each request
#
#     async def initialize(self):
#         """Initialize the bot by loading config, wallet, and syncing balances."""
#         try:
#             self.client = AsyncJsonRpcClient(JSON_RPC_URL)
#             await self.load_config()
#             logging.info(f"Config loaded: Trading {self.currency} from issuer {self.issuer_address}")
#             self.wallet = await self.load_wallet()
#             await self.cancel_unused_offers()
#             await self.get_balance()
#             logging.info("Bot initialized successfully.")
#         except Exception as e:
#             logging.error(f"Initialization failed: {str(e)}", exc_info=True)
#             raise
#
#     async def load_config(self):
#         try:
#             with open('bot_setup_config.yaml', 'r') as f:
#                 self.config = yaml.safe_load(f)
#
#             # Extract logging config and apply it
#             logging_config = self.config.get('logging', {})
#             if logging_config:
#                 # Adjust the filename to be absolute based on BASE_DIR
#                 file_handler = logging_config['handlers'].get('file', {})
#                 if 'filename' in file_handler:
#                     file_handler['filename'] = os.path.join(BASE_DIR, file_handler['filename'])
#                 dictConfig(logging_config)
#                 global logging  # If logger is global; otherwise, define in class
#                 logging = logging.getLogger('xrpl_trading_bot')
#
#             self.currency = self.config['meme_coins'][0]['currency']
#             self.issuer_address = self.config['meme_coins'][0]['issuer']
#             self.trade_amount = float(self.config['settings']['trade_amount'])
#             self.sell_premium = 1.02
#             self.base_reserve = float(self.config['settings']['base_reserve'])
#             self.incremental_reserve = float(self.config['settings']['incremental_reserve'])
#         except Exception as e:
#             raise e
#
#     async def load_wallet(self):
#         wallet_secret = self.config['wallet']['buy_bot_seed']
#         wallet = Wallet.from_seed(wallet_secret)
#         if wallet.classic_address != self.config['wallet']['buy_bot_address']:
#             raise ValueError("Seed does not match wallet address")
#         logging.info(f"Wallet loaded: {wallet.classic_address}")
#         return wallet
#
#     async def cancel_unused_offers(self):
#         logging.info("\n")
#         start_time = time.time()
#         function_name = 'cancel_unused_offers'
#         logging.info(f"Entering: {function_name}")
#         try:
#             while True:
#                 offers_response = await self.client.request(
#                     AccountOffers(account=self.wallet.classic_address, ledger_index="validated")
#                 )
#                 offers = offers_response.result.get('offers', [])
#                 if not offers:
#                     # print(f"No offers to cancel")
#                     logging.info(f"No offers to cancel")
#                     break
#                 for offer in offers:
#                     tx = OfferCancel(account=self.wallet.classic_address, offer_sequence=offer['seq'])
#                     signed_tx = await autofill_and_sign(tx, self.client, self.wallet)
#                     submit_result = await submit(signed_tx, self.client)
#                     logging.info(f"Cancelled offer {offer['seq']}: {submit_result.result}")
#                     # logging.info(f"Cancelled offer {offer['seq']}: {submit_result.result}")
#                 await asyncio.sleep(2)
#         except Exception as e:
#             raise Exception(f"Exception in cancel_unused_offers: {str(e)}")
#         finally:
#             end_time = time.time()
#             logging.info(f"Done cancelling offers")
#             logging.info(f"Leaving: {function_name}. Total execution time in ms: {int((end_time - start_time) * 1000)}")
#         # print(f"Done cancelling offers")
#
#     async def get_latest_validated_ledger_index(self):
#         # Assign a unique request ID
#         self.request_counter += 1
#         request_id = f"get_balance_{self.request_counter}"
#         self.active_requests.add(request_id)
#
#         try:
#             response = await self.client.request(Ledger(ledger_index="validated"))
#             return response.result["ledger_index"]
#         except Exception as e:
#             logging.error(f"get_latest_validated_ledger_index failed: {str(e)}", exc_info=True)
#             raise
#         finally:
#             # Remove the request from tracking once it completes
#             self.active_requests.remove(request_id)
#
#     async def get_balance(self):
#         # Assign a unique request ID
#         self.request_counter += 1
#         request_id = f"get_balance_{self.request_counter}"
#         self.active_requests.add(request_id)
#
#         try:
#             account_info_response = await self.client.request(AccountInfo(account=self.wallet.classic_address, ledger_index="validated"))
#             account_info = account_info_response.result["account_data"]
#             total_xrp = float(account_info['Balance']) / 1000000
#             self.owner_count = int(account_info.get('OwnerCount', 0))
#             total_reserve = self.base_reserve + (self.owner_count * self.incremental_reserve)
#             self.balances['XRP'] = total_xrp - total_reserve
#             account_lines_response = await self.client.request(AccountLines(account=self.wallet.classic_address, ledger_index="validated"))
#             lines_response = account_lines_response.result
#             self.balances[self.currency] = next((float(line['balance']) for line in lines_response.get('lines', []) if line['currency'] == self.currency and line['account'] == self.issuer_address), 0)
#             # print(f"Balances: XRP={self.balances['XRP']:.6f}, {self.currency}={self.balances[self.currency]:.2f}")
#             logging.info(f"Balances: XRP={self.balances['XRP']:.6f}, {self.currency}={self.balances[self.currency]:.2f}")
#         except Exception as e:
#             logging.error(f"get_balance failed: {str(e)}", exc_info=True)
#             raise
#         finally:
#             # Remove the request from tracking once it completes
#             self.active_requests.remove(request_id)
#
#     async def get_market_price(self):
#         # Assign a unique request ID
#         self.request_counter += 1
#         request_id = f"get_market_price_{self.request_counter}"
#         self.active_requests.add(request_id)
#
#         try:
#             offers_response = await self.client.request(GenericRequest(
#                 command="book_offers",
#                 taker_gets={"currency": self.currency, "issuer": self.issuer_address},
#                 taker_pays={"currency": "XRP"},
#                 limit=50
#             ))
#             offers_response = offers_response.result.get("offers", [])
#             if offers_response:
#                 market_buy = min(
#                     float(o["TakerPays"]) / 1000000 / float(o["TakerGets"]["value"])
#                     for o in offers_response
#                 )
#                 return market_buy  # No cap
#             return 0.000013  # Fallback
#         except Exception as e:
#             logging.error(f"get_market_price failed: {str(e)}", exc_info=True)
#             raise
#         finally:
#             # Remove the request from tracking once it completes
#             self.active_requests.remove(request_id)
#
#     async def place_buy_offer(self):
#         # Assign a unique request ID
#         self.request_counter += 1
#         request_id = f"place_buy_offer_{self.request_counter}"
#         self.active_requests.add(request_id)
#
#         try:
#             await self.get_balance()
#             market_price = await self.get_market_price()
#             bid_price = market_price * 1.005
#             buy_xrp = int(self.trade_amount * bid_price * 1000000)
#             if self.balances['XRP'] < (buy_xrp / 1000000) + 0.000020:
#                 logging.warning(f"Insufficient XRP: {self.balances['XRP']}")
#                 return
#             tx_buy = OfferCreate(
#                 account=self.wallet.classic_address,
#                 taker_gets={"currency": self.currency, "issuer": self.issuer_address, "value": str(self.trade_amount)},
#                 taker_pays=str(buy_xrp),
#                 last_ledger_sequence=await self.get_latest_validated_ledger_index() + 20
#             )
#             signed_tx_buy = await autofill_and_sign(tx_buy, self.client, self.wallet)
#             logging.info(f"Submitting buy offer at {bid_price} XRP/{self.currency}")
#             prelim_result = await submit(signed_tx_buy, self.client)
#             logging.info(f"Buy offer submitted: {prelim_result.result}")
#             if prelim_result.result.get("engine_result") != "tesSUCCESS":
#                 logging.warning(f"Buy offer failed: {prelim_result.result}")
#             trade_status = prelim_result.result.get('engine_result')
#             trade = {
#                 'type': 'buy',
#                 'price': bid_price,
#                 'amount': self.trade_amount,
#                 'xrp_spent': buy_xrp / 1000000,
#                 'timestamp': time.strftime('%Y-%m-%d %H:%M:%S'),
#                 'status': trade_status
#             }
#             self.trade_history.append(trade)
#             if trade_status == "tesSUCCESS":
#                 self.metrics['trades_executed'] += 1
#                 self.metrics['xrp_spent'] += buy_xrp / 1000000
#             else:
#                 self.metrics['trade_errors'] += 1
#         except Exception as e:
#             logging.error(f"place_buy_offer failed: {str(e)}", exc_info=True)
#             raise
#         finally:
#             # Remove the request from tracking once it completes
#             self.active_requests.remove(request_id)
#
#     async def place_sell_offer(self):
#         # Assign a unique request ID
#         self.request_counter += 1
#         request_id = f"place_sell_offer_{self.request_counter}"
#         self.active_requests.add(request_id)
#
#         try:
#             await self.get_balance()
#             if self.balances[self.currency] < self.trade_amount:
#                 logging.info(f"Insufficient {self.currency}")
#                 return
#             market_price = await self.get_market_price()
#             ask_price = market_price * 1.005  # Dynamic sell price
#             sell_xrp = int(self.trade_amount * ask_price * 1000000)
#             tx_sell = OfferCreate(
#                 account=self.wallet.classic_address,
#                 taker_gets=str(sell_xrp),
#                 taker_pays={"currency": self.currency, "issuer": self.issuer_address, "value": str(self.trade_amount)},
#                 last_ledger_sequence=await self.get_latest_validated_ledger_index() + 50
#             )
#             signed_tx_sell = await autofill_and_sign(tx_sell, self.client, self.wallet)
#             logging.info(f"Submitting sell offer at {ask_price} XRP/{self.currency}")
#             # print(f"Submitting sell offer at {ask_price} XRP/{self.currency}")
#             logging.info(f"Submitting sell offer at {ask_price} XRP/{self.currency}")
#             prelim_result = await submit(signed_tx_sell, self.client)
#
#             # await self.get_balance()
#             # if self.balances[self.currency] < self.trade_amount:
#             #     logging.info(f"Insufficient {self.currency}")
#             #     return
#             # ask_price = 0.000017
#             # sell_xrp = int(self.trade_amount * ask_price * 1000000)
#             # tx_sell = OfferCreate(
#             #     account=self.wallet.classic_address,
#             #     taker_gets=str(sell_xrp),
#             #     taker_pays={"currency": self.currency, "issuer": self.issuer_address, "value": str(self.trade_amount)},
#             #     last_ledger_sequence=await self.get_latest_validated_ledger_index() + 50
#             # )
#             # signed_tx_sell = await autofill_and_sign(tx_sell, self.client, self.wallet)
#             # logging.info(f"Submitting sell offer at {ask_price} XRP/{self.currency}")
#             # print(f"Submitting sell offer at {ask_price} XRP/{self.currency}")
#             # prelim_result = await submit(signed_tx_sell, self.client)
#
#             # print(f"sell offer: {prelim_result}")
#             logging.info(f"sell offer: {prelim_result}")
#             trade_status = prelim_result.result.get('engine_result')
#             trade = {
#                 'type': 'sell',
#                 'price': ask_price,
#                 'amount': self.trade_amount,
#                 'xrp_received': sell_xrp / 1000000,
#                 'timestamp': time.strftime('%Y-%m-%d %H:%M:%S'),
#                 'status': trade_status
#             }
#             self.trade_history.append(trade)
#             if trade_status == "tesSUCCESS":
#                 self.metrics['trades_executed'] += 1
#             else:
#                 self.metrics['trade_errors'] += 1
#         except Exception as e:
#             logging.error(f"place_sell_offer failed: {str(e)}", exc_info=True)
#             raise
#         finally:
#             # Remove the request from tracking once it completes
#             self.active_requests.remove(request_id)
#
#     async def run(self):
#         iteration = 0
#         while self.running:
#             iteration += 1
#             # print(f"Bot 2 iteration {iteration}")
#             logging.info(f"Bot 2 iteration {iteration}")
#             # if iteration % 5 == 0:  # Every 5 iterations
#             #     await self.cancel_unused_offers()
#             await self.place_buy_offer()
#             # Place up to 3 sell offers if none exist
#             offers_response = await self.client.request(
#                 AccountOffers(account=self.wallet.classic_address, ledger_index="validated"))
#             sell_offers = [o for o in offers_response.result.get('offers', []) if
#                            'TakerGets' in o and isinstance(o['TakerGets'], str)]
#             for _ in range(max(0, 3 - len(sell_offers))):
#                 await self.place_sell_offer()
#             # if self.balances[self.currency] > 10000:
#             #     await self.place_sell_offer()
#             # await self.place_sell_offer()
#             await asyncio.sleep(1)
#
# bot2 = TradingBot2()
#
# @app.route('/')
# async def index():
#     try:
#         logging.info("Rendering index page...")
#         logging.info("Generating QR code...")
#         qr = qrcode.QRCode()
#         qr.add_data(bot2.wallet.classic_address)
#         qr_buffer = BytesIO()
#         qr.make_image().save(qr_buffer)
#         qr_data = base64.b64encode(qr_buffer.getvalue()).decode()
#         logging.info("QR code generated successfully.")
#         return await render_template('index.html',
#                                      metrics=bot2.metrics,
#                                      balances=bot2.balances,
#                                      address=bot2.wallet.classic_address,
#                                      qr_code=qr_data,
#                                      running=bot2.running,
#                                      currency=bot2.currency)
#     except Exception as e:
#         logging.error(f"Error in index route: {e}", exc_info=True)
#         return "Internal Server Error index", 500
#
# @app.route('/start', methods=['POST'])
# async def start_bot():
#     try:
#         if not bot2.running:
#             bot2.running = True
#             asyncio.create_task(bot2.run())
#             logging.info("Bot 2 thread started")
#             return jsonify({'status': 'success', 'message': 'Bot 2 started'})
#         return jsonify({'status': 'error', 'message': 'Bot 2 already running'})
#     except Exception as e:
#         logging.error(f"Error in start_bot: {e}", exc_info=True)
#         return "Internal Server Error start_bot", 500
#
# @app.route('/stop', methods=['POST'])
# async def stop_bot():
#     try:
#         if bot2.running:
#             bot2.running = False
#             if bot2.task:  # Cancel the bot.run() task if it exists
#                 bot2.task.cancel()
#                 try:
#                     await bot2.task  # Wait for the task to be cancelled
#                 except asyncio.CancelledError:
#                     logging.info("Bot task was cancelled successfully")
#
#             # Wait for all active XRPL requests to complete
#             timeout = 20  # seconds
#             start_time = time.time()
#             while bot2.active_requests and (time.time() - start_time) < timeout:
#                 logging.info(f"Waiting for {len(bot2.active_requests)} active requests to complete...")
#                 await asyncio.sleep(2)  # Brief sleep to avoid busy-waiting
#
#             if bot2.active_requests:
#                 logging.warning(f"Timeout reached, {len(bot2.active_requests)} requests still active")
#
#             logging.info("Bot stopped")
#             return jsonify({'status': 'success', 'message': 'Bot 2 is sleeping'})
#         return jsonify({'status': 'error', 'message': 'Bot 2 not running'})
#     except Exception as e:
#         logging.error(f"Error in stop_bot: {e}", exc_info=True)
#         return "Internal Server Error stop_bot", 500
#
# @app.route('/kill', methods=['POST'])
# async def kill_bot():
#     try:
#         logging.info("Shutting down the application...")
#         # Stop the bot if it's running
#         if bot2.running:
#             bot2.running = False
#             if bot2.task:
#                 bot2.task.cancel()
#                 try:
#                     await bot2.task
#                 except asyncio.CancelledError:
#                     logging.info("Bot task was cancelled successfully")
#
#             # Wait for all active XRPL requests to complete
#             timeout = 20  # seconds
#             start_time = time.time()
#             while bot2.active_requests and (time.time() - start_time) < timeout:
#                 logging.info(f"Waiting for {len(bot2.active_requests)} active requests to complete...")
#                 await asyncio.sleep(2)  # Brief sleep to avoid busy-waiting
#
#             if bot2.active_requests:
#                 logging.warning(f"Timeout reached, {len(bot2.active_requests)} requests still active")
#
#         # Send a response to the client before shutting down
#         response = jsonify({'status': 'success', 'message': 'The Application is toasted'})
#
#         # Schedule a background task to shut down the server after the response is sent
#         """Shut down the server gracefully."""
#         logging.info("Shutting down the server...")
#         asyncio.get_event_loop().create_task(app.shutdown())
#
#         return response
#     except Exception as e:
#         logging.info(f"Error in kill_bot: {e}", exc_info=True)
#         return "Internal Server Error kill_bot", 500
#
# @app.route('/status', methods=['GET'])
# async def get_status():
#     try:
#         # Filter out None keys from balances to prevent serialization issues
#         safe_balances = {k: v for k, v in bot2.balances.items() if k is not None}
#         return jsonify({
#             'running': bot2.running,
#             'metrics': bot2.metrics,
#             'balances': safe_balances,
#             'trade_history': bot2.trade_history[-1000:]
#         })
#     except Exception as e:
#         logging.error(f"Error in get_status: {e}", exc_info=True)
#         return "Internal Server Error get_status", 500
#
# async def initialize_bot2():
#     try:
#         await bot2.initialize()
#         logging.info("Bot initialized successfully.")
#         logging.info(f"Wallet address: {bot2.wallet.classic_address}")
#         logging.info(f"Balances: {bot2.balances}")
#     except Exception as e:
#         logging.error(f"Failed to initialize bot: {e}", exc_info=True)
#         raise
#
# if __name__ == "__main__":
#     logging.info("Initializing bot...")
#     os.makedirs(os.path.join(BASE_DIR, 'logs'), exist_ok=True)
#     asyncio.run(initialize_bot2()) # Call initialize_bot2() to initialize the bot
#
#     logging.info("Starting Quart application with Hypercorn")
#     from hypercorn.config import Config
#     from hypercorn.asyncio import serve
#
#     # Create a Hypercorn config
#     config = Config()
#     config.bind = ["127.0.0.1:5001"]
#     config.use_reloader = False
#
#     # Run the app with Hypercorn
#     asyncio.run(serve(app, config))
