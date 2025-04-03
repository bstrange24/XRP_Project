import base64
import os
import time
from io import BytesIO

import httpx
import qrcode
import yaml
from logging.config import dictConfig
from flask import render_template, jsonify
import asyncio
from xrpl.asyncio.clients import AsyncJsonRpcClient, AsyncWebsocketClient
from xrpl.asyncio.transaction import autofill_and_sign, submit, submit_and_wait
from xrpl.models import Fee, BookOffers
from xrpl.wallet import Wallet
from quart import Quart, render_template, jsonify, request
import logging

from db_operations.db_trades import initialize_database, store_trade, update_trade
from utils.constants import JSON_RPC_URL, ENTERING_FUNCTION_LOG, DEBUG, INFO, XRP
from utils.utilities import log_leaving_function, prepare_account_lines, prepare_trust_set, prepare_account_info, \
    prepare_account_offers, prepare_offer_cancel, prepare_offer_create_get_xrp, prepare_offer_create_get_meme, \
    prepare_remove_trust_set, send_alert, confirm_transaction, log_entering_function, decode_currency, encode_currency

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger('xrpl_trading_bot')

app = Quart(__name__)

class TradingBot:
    def __init__(self):
        self.slippage_tolerance = None
        self.background_tasks = None
        self.buy_sell_offers_limit = None
        self.buy_sell_offers_retry = None
        self.max_retries = None
        self.alert_phone_email = None
        self.email_password = None
        self.email_address = None
        self.db_path = os.path.join(BASE_DIR, 'trades.db')
        initialize_database(self, logger)
        self.run_pause = None
        self.trust_line_max = None
        self.bot_timeout = None
        self.bot_sleep = None
        self.max_meme_amount_to_hold = None
        self.last_balance_time = 0
        self.owner_count_limit = None
        self.client = None
        self.wallet = None
        self.pre_trade_balances = 0
        self.min_profit_xrp = None
        self.buy_discount = None
        self.sell_premium = None
        self.config = None
        self.incremental_reserve = None
        self.base_reserve = None
        self.default_trade_amount = None
        self.issuer_address = None
        self.currency = None
        self.running = False # Track if the bot is running
        self.task = None  # Track the bot.run() task
        self.request_semaphore = asyncio.Semaphore(10)  # Limit concurrent requests
        self.tx_semaphore = asyncio.Semaphore(2)  # Limit to 2 concurrent transactions
        self.meme_coins = []  # List of {'currency': str, 'issuer': str}
        self.last_known_price = {}  # Cache last known prices
        self.trade_history = []
        self.wallet_qr_codes = []
        self.metrics = {'buy_trades_executed': 0, 'sell_trades_executed':0, 'trade_errors': 0, 'profit_xrp': 0, 'runtime_errors': 0, 'bot_iterations':0}
        self.balances = {'XRP': 0}
        self.owner_count = None
        self.active_requests = set()  # Track active network requests
        self.request_counter = 0  # Unique ID for each request
        self.total_xrp_spent = 0  # Total XRP spent on buys
        self.total_xrp_received = 0  # Total XRP received from sells
        self.total_reserve = 0
        self.stop_loss = None  # Loaded from config
        self.ledger_fee = 0

    async def initialize(self):
        global logger  # If logger is global; otherwise, define in class
        start_time = time.time()
        logger.info(ENTERING_FUNCTION_LOG.format('initialize'))
        try:
            self.client = AsyncJsonRpcClient(JSON_RPC_URL)
            self.client._client = httpx.AsyncClient(
                limits=httpx.Limits(max_connections=100, max_keepalive_connections=20),
                timeout=60.0
            )
            await self.load_config()
            self.wallet = await self.load_wallet()
            for meme in self.meme_coins:
                await self.check_trust_line(meme['currency'], meme['issuer'])
                self.balances[meme['currency']] = 0
            await self.get_balance(force_update=True)
            await self.cancel_unused_offers()
            self.background_tasks = [
                asyncio.create_task(self.background_balance_updater())
            ]
            logger.info(f"Bot initialized: {self.wallet.classic_address}")
        except Exception as e:
            logger.error(f"Initialization failed: {str(e)}", exc_info=True)
            raise
        finally:
            log_leaving_function('initialize', start_time, logger, INFO)

    async def background_balance_updater(self):
        """Periodically update balances in the background"""
        while self.running:
            try:
                await self.get_balance(force_update=True)
                await asyncio.sleep(10)  # Update every 10 seconds
            except Exception as e:
                logger.error(f"Balance updater error: {e}")
                await asyncio.sleep(self.bot_sleep)

    async def load_config(self):
        global logger
        start_time = time.time()
        logger.info(ENTERING_FUNCTION_LOG.format('load_config'))
        try:
            with open("config/trading_bot_config.yaml", 'r') as f:
                self.config = yaml.safe_load(f)
            logging_config = self.config.get('logging', {})
            if logging_config:
                # Adjust the filename to be absolute based on BASE_DIR
                file_handler = logging_config['handlers'].get('file', {})
                if 'filename' in file_handler:
                    file_handler['filename'] = os.path.join(BASE_DIR, file_handler['filename'])
                dictConfig(logging_config)
                logger = logging.getLogger('xrpl_trading_bot')

            self.meme_coins = self.config['meme_coins']
            self.currency = self.config['meme_coins'][0]['currency']
            self.issuer_address = self.config['meme_coins'][0]['issuer']
            self.default_trade_amount = float(self.config['settings']['trade_amount'])  # Default trade amount
            self.base_reserve = float(self.config['settings']['base_reserve'])
            self.incremental_reserve = float(self.config['settings']['incremental_reserve'])
            self.stop_loss = float(self.config['settings']['stop_loss'])
            self.buy_discount = float(self.config['settings']['buy_discount'])
            self.sell_premium = float(self.config['settings']['sell_premium'])
            self.min_profit_xrp = float(self.config['settings']['min_profit_xrp'])
            self.owner_count_limit = self.config['settings']['owner_count_limit']
            self.max_meme_amount_to_hold = self.config['settings']['max_meme_amount_to_hold']
            self.bot_sleep = self.config['settings']['bot_sleep']
            self.run_pause = self.config['settings']['run_pause']
            self.bot_timeout = self.config['settings']['bot_timeout']
            self.trust_line_max = self.config['settings']['trust_line_max']
            self.email_address = self.config['settings']['email_address']
            self.email_password = self.config['settings']['email_password']
            self.alert_phone_email = self.config['settings']['alert_phone_email']
            self.buy_sell_offers_retry = self.config['settings']['buy_sell_offers_retry']
            self.buy_sell_offers_limit = self.config['settings']['buy_sell_offers_limit']
            self.slippage_tolerance = self.config['settings']['slippage_tolerance']
            self.max_retries = self.config['settings']['max_retries']
            # Set trade_amount per meme coin, falling back to default
            for meme in self.meme_coins:
                meme['trade_amount'] = float(meme.get('trade_amount', self.default_trade_amount))
            logger.info(f"Config loaded: Trading {len(self.meme_coins)} meme coins - {self.meme_coins}")
        except Exception as e:
            logger.error(f"Config load error: {str(e)}")
            raise
        finally:
            log_leaving_function('load_config', start_time, logger, INFO)

    async def update_config(self, new_config):
        start_time = time.time()
        logger.info(ENTERING_FUNCTION_LOG.format('update_config'))
        try:
            # Read the existing config file to preserve other settings
            with open("config/trading_bot_config.yaml", 'r') as f:
                current_config = yaml.safe_load(f)

            # Identify removed meme coins
            current_currencies = {meme['currency'] for meme in current_config['meme_coins']}
            new_currencies = {meme['currency'] for meme in new_config['meme_coins']}
            removed_currencies = current_currencies - new_currencies
            removed_meme_coins = [
                meme for meme in current_config['meme_coins']
                if meme['currency'] in removed_currencies
            ]

            # Update the bot's internal state
            self.meme_coins = new_config['meme_coins']
            for meme in self.meme_coins:
                if meme['currency'] not in self.balances:
                    await self.check_trust_line(meme['currency'], meme['issuer'])
                    self.balances[meme['currency']] = 0
            current_currencies = {meme['currency'] for meme in self.meme_coins}
            for currency in list(self.balances.keys()):
                if currency != 'XRP' and currency not in current_currencies:
                    del self.balances[currency]

            self.min_profit_xrp = new_config['min_profit_xrp']
            self.buy_discount = new_config['buy_discount']
            self.sell_premium = new_config['sell_premium']

            # Update the parsed config object
            current_config['meme_coins'] = new_config['meme_coins']
            current_config['settings']['min_profit_xrp'] = new_config['min_profit_xrp']
            current_config['settings']['buy_discount'] = new_config['buy_discount']
            current_config['settings']['sell_premium'] = new_config['sell_premium']

            # Build the config file content
            config_content = [
                "meme_coins:\n"
            ]
            for meme in new_config['meme_coins']:
                config_content.append(f"  - currency: {meme['currency']}\n")
                config_content.append(f"    issuer: {meme['issuer']}\n")
                config_content.append(f"    trade_amount: {meme['trade_amount']}\n")
            for meme in removed_meme_coins:
                config_content.append(f"  # - currency: {meme['currency']}\n")
                config_content.append(f"  #   issuer: {meme['issuer']}\n")
                config_content.append(f"  #   trade_amount: {meme['trade_amount']}\n")

            config_content.append("settings:\n")
            for key, value in current_config['settings'].items():
                if key in ['min_profit_xrp', 'buy_discount', 'sell_premium']:
                    if key == 'min_profit_xrp':
                        config_content.append(f"  {key}: {value:.6f}\n")
                    else:
                        config_content.append(f"  {key}: {value}\n")
                else:
                    if key == 'check_interval':
                        config_content.append(f"  {key}: {value} # seconds to sleep the main bot\n")
                    elif key == 'trade_amount':
                        config_content.append(f"  {key}: {value}  # Amount of meme coin to trade\n")
                    elif key == 'stop_loss':
                        config_content.append(
                            f"  {key}: {value} # Triggers when the net loss reaches 2% of the XRP spent.\n")
                    else:
                        config_content.append(f"  {key}: {value}\n")

            config_content.append("wallet:\n")
            for key, value in current_config['wallet'].items():
                config_content.append(f"  {key}: {value}\n")

            # Dynamically construct the logging section
            logging_config = current_config['logging']
            config_content.append("\nlogging:\n")
            config_content.append(f"  version: {logging_config['version']}\n")
            config_content.append(
                f"  disable_existing_loggers: {str(logging_config['disable_existing_loggers']).lower()}\n")

            config_content.append("  formatters:\n")
            for formatter_name, formatter_details in logging_config['formatters'].items():
                config_content.append(f"    {formatter_name}:\n")
                config_content.append(f"      format: \"{formatter_details['format']}\"\n")
                config_content.append(f"      style: \"{formatter_details['style']}\"\n")

            config_content.append("  handlers:\n")
            for handler_name, handler_details in logging_config['handlers'].items():
                config_content.append(f"    {handler_name}:\n")
                for key, value in handler_details.items():
                    if key == 'filename':
                        config_content.append(f"      {key}: \"{value}\"  # Relative path; adjust as needed\n")
                    else:
                        config_content.append(f"      {key}: \"{value}\"\n")

            config_content.append("  loggers:\n")
            for logger_name, logger_details in logging_config['loggers'].items():
                if logger_name == 'httpx':
                    config_content.append(f"    {logger_name}: # Add this to silence httpx logs\n")
                else:
                    config_content.append(f"    {logger_name}:\n")
                if logger_name == 'xrpl_trading_bot' and 'handlers' in logger_details:
                    handlers_str = '["' + '", "'.join(logger_details['handlers']) + '"]'
                    config_content.append(
                        f"      handlers: {handlers_str}  # Add \"console\" if you want console output\n")
                elif 'handlers' in logger_details:
                    handlers_str = '[ ]' if not logger_details['handlers'] else '["' + '", "'.join(
                        logger_details['handlers']) + '"]'
                    config_content.append(
                        f"      handlers: {handlers_str}  # No handlers; effectively silences it unless propagated\n")
                for key, value in logger_details.items():
                    if key != 'handlers':
                        if key == 'level' and logger_name == 'httpx':
                            config_content.append(f"      {key}: \"{value}\"  # Only log WARNING and above\n")
                        elif key == 'propagate' and logger_name == 'httpx':
                            config_content.append(
                                f"      {key}: {str(value).lower()}  # Prevent propagation to root logger\n")
                        else:
                            config_content.append(f"      {key}: \"{value}\"\n" if isinstance(value,
                                                                                              str) else f"      {key}: {str(value).lower()}\n")

            # Write the updated config back to the file
            with open("config/trading_bot_config.yaml", 'w') as f:
                f.writelines(config_content)

            self.config = current_config  # Update the bot's config object
            logger.info(f"Configuration updated and saved to file: {new_config}")

            if new_config['remove_trust_line'] and new_config['remove_trust_line'] == 'true':
                for meme in removed_meme_coins:
                    if await self.remove_trust_line(meme['currency'], meme['issuer']):
                        logger.info("Trust line removed")
                    else:
                        logger.error("Trust line removal failed")

            return {'status': 'success', 'message': 'Configuration updated successfully'}
        except Exception as e:
            logger.error(f"Update config error: {str(e)}")
            self.metrics['runtime_errors'] += 1
            return {'status': 'error', 'message': str(e)}
        finally:
            log_leaving_function('update_config', start_time, logger, INFO)

    async def load_wallet(self):
        start_time = time.time()
        logger.info(ENTERING_FUNCTION_LOG.format('load_wallet'))

        request_id = f"load_wallet_{self.request_counter}"
        self.active_requests.add(request_id)
        self.request_counter += 1

        for attempt in range(self.max_retries):
            try:
                wallet_secret = self.config['wallet']['xaman_seed']
                wallet = Wallet.from_seed(wallet_secret)
                if wallet.classic_address != self.config['wallet']['xaman_address']:
                    raise ValueError("Seed does not match Xaman wallet address")
                logger.info(f"Wallet loaded: {wallet.classic_address}")
                return wallet
            except Exception as e:
                wait_time = 2 ** attempt
                logger.error(f"Wallet load failed (attempt {attempt + 1}/{self.max_retries}): {e}. Retrying in {wait_time}s")
                self.metrics['runtime_errors'] += 1
                if attempt == self.max_retries - 1:
                    logger.error(f"Failed load wallet. Error: {str(e)}")
                    await send_alert(self, "Error loading wallet. The Bot is toast", logger)
                    raise
                await asyncio.sleep(wait_time)
            finally:
                self.active_requests.remove(request_id)
                log_leaving_function('load_wallet', start_time, logger, INFO)

    async def get_current_fee(self):
        start_time = time.time()
        log_entering_function('get_current_fee', logger, DEBUG)

        request_id = f"get_current_fee_{self.request_counter}"
        self.active_requests.add(request_id)
        self.request_counter += 1

        for attempt in range(self.max_retries):
            try:
                async with self.request_semaphore:
                    fee_response = await self.client.request(Fee())
                    median_fee_drops = int(fee_response.result["drops"]["median_fee"])
                    fee_xrp = median_fee_drops / 1000000
                    logger.debug(f"Median fee from network: {median_fee_drops} drops, {fee_xrp:.10f} XRP")
                    return max(fee_xrp, 0.000012)  # Mainnet min fee (0.000012)
            except Exception as e:
                wait_time = 2 ** attempt
                logger.warning(f"Fee fetch failed (attempt {attempt + 1}/{self.max_retries}): {e}. Retrying in {wait_time}s")
                self.metrics['runtime_errors'] += 1
                if attempt == self.max_retries - 1:
                    logger.error(f"Failed to get fee after retries. Error: {str(e)}")
                    await send_alert(self, "Error getting current network fee. The Bot is toast", logger)
                    raise
                await asyncio.sleep(wait_time)
            finally:
                self.active_requests.remove(request_id)
                log_leaving_function('get_current_fee', start_time, logger, DEBUG)

    async def check_trust_line(self, currency, issuer):
        start_time = time.time()
        logger.info(ENTERING_FUNCTION_LOG.format('check_trust_line'))

        request_id = f"check_trust_line_{self.request_counter}"
        self.active_requests.add(request_id)
        self.request_counter += 1
        decoded_currency = None
        trust_line_found = False
        for attempt in range(self.max_retries):
            try:
                async with self.request_semaphore:
                    account_lines_response = await self.client.request(prepare_account_lines(self.wallet.classic_address, "validated"))

                for line in account_lines_response.result.get("lines", []):
                    decoded_currency = decode_currency(line["currency"])
                    if decoded_currency == currency and line["account"] == issuer:
                        logger.info(f"Trust Line Found - Currency: {decoded_currency} - {line['currency']}, Issuer: {line['account']}")
                        logger.info(f"Limit: {line['limit']} {currency}")
                        logger.info(f"Balance: {line['balance']} {currency}")
                        trust_line_found = True
                        return True

                if not trust_line_found or decoded_currency is None:
                    logger.info(f"No {currency} trust line to issuer {issuer} found.")
                    return False

                logger.info(f"No {currency} trust line to issuer {issuer} found.")
                logger.info("Setting trust line...")
                bot_wallet = Wallet.from_seed(self.config['wallet']['xaman_seed'])
                trust_line_request = prepare_trust_set(self.wallet.classic_address, decoded_currency, issuer, str(self.trust_line_max))
                submit_result = await submit_and_wait(trust_line_request, self.client, bot_wallet)
                logger.info(f"Trust line set result: {submit_result.result}")

                if submit_result.result['meta']['TransactionResult'] == "tesSUCCESS":
                    logger.info("Trust line set successful")
                else:
                    logger.info("Trust line set failed")
            except Exception as e:
                wait_time = 2 ** attempt
                logger.warning(f"Check trust lines failed (attempt {attempt + 1}/{self.max_retries}): {e}. Retrying in {wait_time}s")
                self.metrics['runtime_errors'] += 1
                if attempt == self.max_retries - 1:
                    logger.error(f"Failed to get fee after retries. Error: {str(e)}")
                    await send_alert(self, "Error checking trust lines. The Bot is toast", logger)
                    raise
                await asyncio.sleep(wait_time)
            finally:
                self.active_requests.remove(request_id)
                log_leaving_function('check_trust_line', start_time, logger, INFO)

    async def remove_trust_line(self, currency, issuer):
        start_time = time.time()
        logger.info(ENTERING_FUNCTION_LOG.format('remove_trust_line'))

        request_id = f"remove_trust_line_{self.request_counter}"
        self.active_requests.add(request_id)
        self.request_counter += 1
        decoded_currency = None
        trust_line_found = False

        for attempt in range(self.max_retries):
            try:
                async with self.request_semaphore:
                    account_lines_response = await self.client.request(prepare_account_lines(self.wallet.classic_address, "validated"))

                # Look for trust line to the issuer
                for line in account_lines_response.result.get("lines", []):
                    decoded_currency = decode_currency(line["currency"])
                    if decoded_currency == currency and line["account"] == issuer:
                        logger.info(f"Trust Line Found - Currency: {decoded_currency} - {line['currency']}, Issuer: {line['account']}")
                        logger.info(f"Limit: {line['limit']} {currency}")
                        logger.info(f"Balance: {line['balance']} {currency}")
                        trust_line_found = True
                        break

                if not trust_line_found or decoded_currency is None:
                    logger.info(f"No {decoded_currency} - {currency} trust line to issuer {issuer} found.")
                    return False

                logger.info("Removing trust line...")
                bot_wallet = Wallet.from_seed(self.config['wallet']['xaman_seed'])
                encoded_currency = encode_currency(currency)
                trust_line_request = prepare_remove_trust_set(self.config['wallet']['xaman_address'], encoded_currency, issuer)
                submit_result = await submit_and_wait(trust_line_request, self.client, bot_wallet)
                logger.info(f"Trust line removed result: {submit_result.result}")

                if submit_result.result['meta']['TransactionResult'] == "tesSUCCESS":
                    logger.info(f"Trust line removed for {currency}")
                    return True
                logger.error(f"Trust line removal failed: {submit_result.result}")
                return False
            except Exception as e:
                wait_time = 2 ** attempt
                logger.warning(f"Remove trust lines failed (attempt {attempt + 1}/{self.max_retries}): {e}. Retrying in {wait_time}s")
                self.metrics['runtime_errors'] += 1
                if attempt == self.max_retries - 1:
                    logger.error(f"Failed to remove trust line after retries. Error: {str(e)}")
                    await send_alert(self, "Error removing trust lines. The Bot is toast", logger)
                    raise
                await asyncio.sleep(wait_time)
            finally:
                self.active_requests.remove(request_id)
                log_leaving_function('remove_trust_line', start_time, logger, INFO)

    async def get_balance(self, force_update: bool = False):
        """Get balances, using cached version if recent unless forced"""
        start_time = time.time()
        log_entering_function('get_balance', logger, DEBUG)

        # If we have fresh data (≤5 sec old) and not forced, return cached
        if not force_update and time.time() - self.last_balance_time < 5:
            logger.debug("Using cached balance")
            return

        logger.debug("Getting fresh balance")
        request_id = f"get_balance_{self.request_counter}"
        self.active_requests.add(request_id)
        self.request_counter += 1

        for attempt in range(self.max_retries):
            try:
                async with self.request_semaphore:
                    account_info = await self.client.request(prepare_account_info(self.wallet.classic_address,"validated"))
                xrp_balance = int(account_info.result["account_data"]["Balance"]) / 1000000
                self.owner_count = account_info.result["account_data"]["OwnerCount"]
                reserve = self.base_reserve + self.owner_count * self.incremental_reserve
                self.total_reserve = reserve
                self.balances["XRP"] = xrp_balance - reserve

                async with self.request_semaphore:
                    lines = await self.client.request(prepare_account_lines(self.wallet.classic_address, "validated"))
                logger.debug(f"AccountLines response: {lines.result}")

                for currency in self.meme_coins:
                    curr = currency['currency']
                    issuer = currency['issuer']
                    for line in lines.result.get("lines", []):
                        if line["currency"] == curr and line["account"] == issuer:
                            self.balances[curr] = float(line["balance"])
                            break
                    else:
                        self.balances[curr] = 0.0
                self.last_balance_time = time.time()
                logger.debug(f"Balances: XRP={self.balances['XRP']:.6f}, Reserve={reserve}")
                break
            except Exception as e:
                wait_time = 2 ** attempt
                logger.warning(f"Get balances failed (attempt {attempt + 1}/{self.max_retries}): {e}. Retrying in {wait_time}s")
                self.metrics['runtime_errors'] += 1
                if attempt == self.max_retries - 1:
                    logger.error(f"Failed to get balances after retries. Error: {str(e)}")
                    await send_alert(self, "Error getting balances. The Bot is toast", logger)
                    raise
                await asyncio.sleep(wait_time)
            finally:
                self.active_requests.remove(request_id)
                log_leaving_function('get_balance', start_time, logger, DEBUG)

    async def cancel_unused_offers(self):
        start_time = time.time()
        logger.info(ENTERING_FUNCTION_LOG.format('cancel_unused_offers'))

        request_id = f"cancel_unused_offers_{self.request_counter}"
        self.active_requests.add(request_id)
        self.request_counter += 1

        try:
            async with self.request_semaphore:
                response = await self.client.request(prepare_account_offers(self.wallet.classic_address, "validated"))
            offers = response.result.get('offers', [])
            if not offers:
                logger.info("No offers to cancel")
                return

            for offer in offers[:10]:  # Batch limit
                for attempt in range(self.max_retries):
                    try:
                        tx = prepare_offer_cancel(self.wallet.classic_address, offer['seq'])
                        async with httpx.AsyncClient(timeout=30.0) as custom_client:
                            self.client._client = custom_client  # Temporarily override client
                            signed_tx = await autofill_and_sign(tx, self.client, self.wallet)
                            result = await submit(signed_tx, self.client)
                            if result.result["engine_result"] == "tesSUCCESS":
                                logger.info(f"Cancelled offer {offer['seq']}")
                                break  # Success, move to next offer
                    except httpx.ConnectTimeout as e:
                        wait_time = 2 ** attempt  # Exponential backoff: 1s, 2s, 4s
                        logger.warning(f"Timeout cancelling offer {offer['seq']} (attempt {attempt + 1}/{self.max_retries}): {str(e)}. Retrying in {wait_time}s")
                        if attempt == self.max_retries - 1:
                            logger.error(f"Failed to cancel offer {offer['seq']} after {self.max_retries} attempts")
                            await send_alert(self, f"Failed to cancel offer {offer['seq']} after {self.max_retries} retries due to timeout", logger)
                            break  # Give up after max retries
                        await asyncio.sleep(wait_time)
                    except Exception as e:
                        logger.error(f"Unexpected error cancelling offer {offer['seq']}: {str(e)}")
                        break  # Exit on non-timeout errors
                await asyncio.sleep(self.run_pause)  # Brief pause between cancellations
        except Exception as e:
            logger.error(f"Cancel offers error: {str(e)}")
            self.metrics['runtime_errors'] += 1
            await send_alert(self, "Error cancelling unused offers. The Bot is toast", logger)
            raise
        finally:
            self.active_requests.remove(request_id)
            log_leaving_function('cancel_unused_offers', start_time, logger, INFO)

    async def fetch_buy_offers(self, currency, issuer):
        start_time = time.time()
        log_entering_function('fetch_buy_offers', logger, DEBUG)

        request_id = f"fetch_buy_offers_{self.request_counter}"
        self.active_requests.add(request_id)
        self.request_counter += 1

        max_retries = self.buy_sell_offers_retry
        limit = self.buy_sell_offers_limit
        logger.debug(f"currency before encoding: {currency}")
        currency = encode_currency(currency)
        logger.debug(f"currency: {currency}")

        try:
            for attempt in range(max_retries):
                try:
                    async with self.request_semaphore:
                        # async with httpx.AsyncClient(timeout=30.0) as custom_client:
                        async with AsyncWebsocketClient("wss://s1.ripple.com") as client:
                            self.client._client = client  # Temporarily override client
                            taker_gets = {"currency": currency, "issuer": issuer}
                            taker_pays = {"currency": XRP}
                            logger.debug(f"Preparing BookOffers for buy: taker_gets: {taker_gets} taker_pays: {taker_pays}")
                            response = await self.client.request(BookOffers(taker_gets=taker_pays, taker_pays=taker_gets, ledger_index="validated", limit=limit))
                            logger.info(f"Buy offers fetched at {time.time()} ledger_index: {response.result.get('ledger_index')}")
                            offers = response.result.get('offers', [])
                            for offer in offers:
                                logger.info(f"Taker gets: {offer['TakerGets']} Taker pays: {offer['TakerPays']['value']}")
                            return response  # Success, exit with result
                except httpx.ConnectTimeout as e:
                    wait_time = 2 ** attempt  # Exponential backoff: 1s, 2s, 4s
                    logger.warning(f"Timeout fetching buy offers for {currency} issuer {issuer} (attempt {attempt + 1}/{max_retries}): {str(e)}. Retrying in {wait_time}s")
                    if attempt == max_retries - 1:
                        logger.error(f"Failed to fetch buy offers for {currency} after {max_retries} attempts")
                        await send_alert(self,f"Failed to fetch buy offers for {currency} after {max_retries} retries due to timeout", logger)
                        return None  # Final failure, return None
                    await asyncio.sleep(wait_time)
                except Exception as e:
                    logger.error(f"Unexpected error fetching buy offers for {currency} issuer {issuer}: {str(e)}")
                    self.metrics['runtime_errors'] += 1
                    await send_alert(self, f"Error fetching buy offers for {currency}: {str(e)}. The Bot is toast", logger)
                    raise  # Non-timeout errors are fatal, re-raise
        finally:
            self.active_requests.remove(request_id)
            log_leaving_function('fetch_buy_offers', start_time, logger, DEBUG)

    async def fetch_sell_offers(self, currency, issuer):
        start_time = time.time()
        log_entering_function('fetch_sell_offers', logger, DEBUG)

        request_id = f"fetch_sell_offers_{self.request_counter}"
        self.active_requests.add(request_id)
        self.request_counter += 1

        max_retries = self.buy_sell_offers_retry
        limit = self.buy_sell_offers_limit
        logger.debug(f"currency before encoding: {currency}")
        currency = encode_currency(currency)
        logger.debug(f"currency: {currency}")

        try:
            for attempt in range(max_retries):
                try:
                    async with self.request_semaphore:
                        # async with httpx.AsyncClient(timeout=30.0) as custom_client:
                        async with AsyncWebsocketClient("wss://s1.ripple.com") as client:
                            # self.client._client = custom_client  # Temporarily override client
                            self.client._client = client  # Temporarily override client
                            taker_gets = {"currency": currency, "issuer": issuer}
                            taker_pays = {"currency": XRP}
                            logger.debug(f"Preparing BookOffers for sell: taker_gets: {taker_gets} taker_pays: {taker_pays}")
                            response = await self.client.request(BookOffers(taker_gets=taker_gets, taker_pays=taker_pays, ledger_index="validated", limit=limit))
                            logger.info(f"Sell offers fetched at {time.time()} ledger_index: {response.result.get('ledger_index')}")
                            offers = response.result.get('offers', [])
                            for offer in offers:
                                logger.info(f"Taker gets: {offer['TakerGets']['value']} Taker pays: {offer['TakerPays']}")
                            return response  # Success, exit with result
                except httpx.ConnectTimeout as e:
                    wait_time = 2 ** attempt  # Exponential backoff: 1s, 2s, 4s
                    logger.warning(f"Timeout fetching sell offers for {currency} issuer {issuer} (attempt {attempt + 1}/{max_retries}): {str(e)}. Retrying in {wait_time}s")
                    if attempt == max_retries - 1:
                        logger.error(f"Failed to fetch sell offers for {currency} after {max_retries} attempts")
                        await send_alert(self,f"Failed to fetch sell offers for {currency} after {max_retries} retries due to timeout",logger)
                        return None  # Final failure, return None
                    await asyncio.sleep(wait_time)
                except Exception as e:
                    logger.error(f"Unexpected error fetching sell offers for {currency} issuer {issuer}: {str(e)}")
                    self.metrics['runtime_errors'] += 1
                    await send_alert(self, f"Error fetching sell offers for {currency}: {str(e)}. The Bot is toast", logger)
                    raise  # Non-timeout errors are fatal, re-raise
        finally:
            self.active_requests.remove(request_id)
            log_leaving_function('fetch_sell_offers', start_time, logger, DEBUG)

    async def find_arbitrage(self, currency, issuer):
        start_time = time.time()
        log_entering_function('find_arbitrage', logger, DEBUG)

        request_id = f"find_arbitrage_{self.request_counter}"
        self.active_requests.add(request_id)
        self.request_counter += 1
        logger.debug(f"currency: {currency}")

        for attempt in range(self.max_retries):
            try:
                await self.get_balance(force_update=True)

                # Get trade amount from config (1000 for PHNIX/SOLO, else default)
                trade_amount = next((meme['trade_amount'] for meme in self.meme_coins if meme['currency'] == currency), self.default_trade_amount)
                logger.debug(f"trade_amount: {trade_amount}")
                reserve = self.base_reserve + self.owner_count * self.incremental_reserve
                logger.debug(f"reserve: {reserve}")

                # Use dynamic fee, assume 0.00001 XRP typical unless overridden
                self.ledger_fee = await self.get_current_fee()
                total_fee = self.ledger_fee * 2  # Buy + sell transactions
                logger.debug(f"ledger_fee: {self.ledger_fee}, total_fee: {total_fee}")

                # Check sufficient XRP for reserve and fees
                if self.balances["XRP"] < (reserve + total_fee + 0.01):
                    logger.info(f"Insufficient funds for {currency}: XRP={self.balances['XRP']:.6f}, {currency}={self.balances[currency]}")
                    return False, 0, 0, None, None, None, None

                # Fetch offers
                buy_task, sell_task = await asyncio.gather(
                    self.fetch_buy_offers(currency, issuer),
                    self.fetch_sell_offers(currency, issuer)
                )

                buy_offers = buy_task.result.get("offers", []) if buy_task else []
                sell_offers = sell_task.result.get("offers", []) if sell_task else []
                logger.debug(f"Top 3 buy offers: {buy_offers[:3]}")
                logger.debug(f"Top 3 sell offers: {sell_offers[:3]}")

                if not buy_offers or not sell_offers:
                    logger.info(f"No offers available or fetch failed for {currency}")
                    return False, 0, 0, None, None, None, None

                # Best sell offer: lowest XRP/ARMY to buy ARMY
                best_sell_offer = min(sell_offers, key=lambda o: float(o["TakerPays"]) / float(o["TakerGets"]["value"]))
                market_buy_price = float(best_sell_offer["TakerPays"]) / float(best_sell_offer["TakerGets"]["value"]) / 1000000

                # Best buy offer: highest XRP/ARMY to sell ARMY
                best_buy_offer = max(buy_offers, key=lambda o: float(o["TakerGets"]) / float(o["TakerPays"]["value"]))
                market_sell_price = float(best_buy_offer["TakerGets"]) / float(best_buy_offer["TakerPays"]["value"]) / 1000000

                # Cap trade amount by offer sizes
                trade_amount = min(trade_amount, float(best_sell_offer["TakerGets"]["value"]), float(best_buy_offer["TakerPays"]["value"]))
                logger.info(f"Market Buy Price: {market_buy_price:.10f}, Market Sell Price: {market_sell_price:.10f} Adjusted trade_amount: {trade_amount}")

                # Skip if spread is zero or negative
                spread = market_sell_price - market_buy_price
                if spread <= 0:
                    logger.info(f"Negative or zero spread detected ({spread:.10f}), skipping trade for {currency}")
                    return False, 0, 0, None, None, None, None

                # Apply config discounts/premiums
                config_buy_price = market_buy_price * self.buy_discount  # 0.995
                config_sell_price = market_sell_price * self.sell_premium  # 1.005
                config_profit = (config_sell_price - config_buy_price) * trade_amount - total_fee

                logger.info(f"Config pricing: Buy: {config_buy_price:.10f}, Sell: {config_sell_price:.10f}, Profit: {config_profit:.10f} XRP")

                # Check if profit meets minimum threshold
                if config_profit <= self.min_profit_xrp:  # 0.000001 XRP
                    logger.info(f"Profit ({config_profit:.10f}) below minimum ({self.min_profit_xrp}), skipping trade")
                    return False, 0, 0, None, None, None, None

                # Verify spread covers fees and adjustments
                min_required_spread = total_fee / trade_amount
                if spread < min_required_spread:
                    logger.info(f"Spread ({spread:.10f}) below minimum required ({min_required_spread:.10f}), skipping trade")
                    return False, 0, 0, None, None, None, None

                # Trade is profitable
                logger.info(f"{'*' * 60} Trading opportunity found! Potential profit: {config_profit:.10f} {'*' * 60}")
                return True, config_buy_price, config_sell_price, config_profit, market_buy_price, best_buy_offer, best_sell_offer

            except Exception as e:
                wait_time = 2 ** attempt
                logger.warning(f"Find arbitrage failed (attempt {attempt + 1}/{self.max_retries}): {e}. Retrying in {wait_time}s")
                self.metrics['trade_errors'] += 1
                if attempt == self.max_retries - 1:
                    await send_alert(self, "Error finding arbitrage. The Bot is toast", logger)
                    raise
                await asyncio.sleep(wait_time)
            finally:
                self.active_requests.remove(request_id)
                log_leaving_function('find_arbitrage', start_time, logger, DEBUG)

        # request_id = f"find_arbitrage_{self.request_counter}"
        # self.active_requests.add(request_id)
        # self.request_counter += 1
        # logger.debug(f"currency: {currency}")
        #
        # for attempt in range(self.max_retries):
        #     try:
        #         await self.get_balance(force_update=True)
        #
        #         trade_amount = next((meme['trade_amount'] for meme in self.meme_coins if meme['currency'] == currency), self.default_trade_amount)
        #         logger.debug(f"trade_amount: {trade_amount}")
        #         logger.debug(f"base_reserve: {self.base_reserve}")
        #         logger.debug(f"owner_count: {self.owner_count}")
        #         logger.debug(f"incremental_reserve: {self.incremental_reserve}")
        #         reserve = self.base_reserve + self.owner_count * self.incremental_reserve
        #         logger.debug(f"reserve: {reserve}")
        #
        #         self.ledger_fee = await self.get_current_fee()
        #         if self.balances["XRP"] < (reserve + (self.ledger_fee * 2) + 0.01):
        #             logger.info(f"Insufficient funds for {currency}: XRP={self.balances['XRP']:.6f}, {currency}={self.balances[currency]}")
        #             return False, 0, 0, None, None, None, None
        #
        #         buy_task, sell_task = await asyncio.gather(
        #             self.fetch_buy_offers(currency, issuer),
        #             self.fetch_sell_offers(currency, issuer)
        #         )
        #
        #
        #         buy_offers = buy_task.result.get("offers", []) if buy_task else []
        #         sell_offers = sell_task.result.get("offers", []) if sell_task else []
        #         logger.debug(f"Top 3 buy offers: {buy_offers[:3]}")
        #         logger.debug(f"Top 3 sell offers: {sell_offers[:3]}")
        #
        #         print(f"\traw buy offer: {buy_offers}")
        #         logger.debug(f"raw buy offer: {buy_offers}")
        #         print(f"\traw sell offer: {sell_offers}")
        #         logger.debug(f"\traw sell offer: {sell_offers}")
        #
        #         if not buy_offers or not sell_offers:
        #             logger.info(f"No offers available or fetch failed for {currency}")
        #             print(f"\tInsufficient offers for arbitrage for {currency}")
        #             return False, 0, 0, None, None, None, None
        #
        #         # Corrected logic:
        #         # Best sell offer: lowest price you pay to buy ARMY (XRP/ARMY)
        #         best_sell_offer = min(sell_offers, key=lambda o: float(o["TakerPays"]) / float(o["TakerGets"]["value"]))
        #         market_buy_price = float(best_sell_offer["TakerPays"]) / float(best_sell_offer["TakerGets"]["value"]) / 1000000  # XRP per ARMY to buy
        #
        #         # Best buy offer: highest price you receive to sell ARMY (XRP/ARMY)
        #         best_buy_offer = max(buy_offers, key=lambda o: float(o["TakerGets"]) / float(o["TakerPays"]["value"]))
        #         market_sell_price = float(best_buy_offer["TakerGets"]) / float(best_buy_offer["TakerPays"]["value"]) / 1000000  # XRP per ARMY to sell
        #
        #         if market_sell_price <= market_buy_price:
        #             logger.info("Negative spread detected, skipping trade.")
        #             return False, 0, 0, None, None, None, None
        #
        #         # trade_amount = min(trade_amount, float(best_sell_offer["TakerGets"]["value"]), float(best_buy_offer["TakerPays"]["value"]))
        #         trade_amount = min(float(best_sell_offer['TakerGets']['value']), float(best_buy_offer['TakerPays']['value']))
        #         logger.debug(f"best_buy_offer: {best_buy_offer} market_sell_price: {market_sell_price} best_sell_offer: {best_sell_offer} market_buy_price: {market_buy_price} incremental_reserve: {trade_amount}")
        #
        #         # Log market prices
        #         logger.info(f"Market Buy Price: {market_buy_price:.10f}, Market Sell Price: {market_sell_price:.10f}")
        #
        #         config_buy_price = market_buy_price * self.buy_discount
        #         config_sell_price = market_sell_price * self.sell_premium
        #         config_profit = (config_sell_price - config_buy_price) * trade_amount - self.ledger_fee
        #         logger.info(f"Config pricing: Buy: {config_buy_price:.10f}, Sell: {config_sell_price:.10f}, Profit: {config_profit:.10f} XRP")
        #         print(f"\tMin profit needed: {self.min_profit_xrp:.15f}")
        #
        #         if config_profit > self.min_profit_xrp:
        #             print(f"\tConfig pricing: Buy: {config_buy_price:.10f}, Sell: {config_sell_price:.10f}, Profit: {config_profit:.10f} XRP")
        #             logger.info(f"{'*' * 60} Trading opportunity found! Potential profit: {config_profit:.10f} {'*' * 60}")
        #             print(f"{'*' * 30} Trading opportunity found! Potential profit: {config_profit:.10f} {'*' * 30}")
        #             return True, config_buy_price, config_sell_price, config_profit, market_buy_price, best_buy_offer, best_sell_offer
        #
        #         spread = market_sell_price - market_buy_price
        #         min_required_spread = (self.ledger_fee / trade_amount) + (market_buy_price * (1 - self.buy_discount)) + (market_sell_price * (self.sell_premium - 1))
        #         logger.info(f"spread: {spread:.10f}, min_required_spread: {min_required_spread:.10f}")
        #
        #         if spread < min_required_spread:
        #             dynamic_buy_discount = max(self.buy_discount, min(0.99, 1 - spread / market_buy_price * 1.5))
        #             dynamic_sell_premium = min(1.10, max(self.sell_premium, 1 + spread / market_sell_price * 2))
        #             discounted_buy_price = market_buy_price * dynamic_buy_discount
        #             sell_price = market_sell_price * dynamic_sell_premium
        #         else:
        #             discounted_buy_price = config_buy_price
        #             sell_price = config_sell_price
        #
        #         fee = self.ledger_fee * 2  # Two transactions
        #         logger.info(f"XRP fee: {fee}")
        #         profit = (sell_price - discounted_buy_price) * trade_amount - fee
        #
        #         # Log adjusted prices and spread
        #         logger.info(f"Adjusted Buy: {discounted_buy_price:.10f}, Adjusted Sell: {sell_price:.10f}, Spread: {market_sell_price - market_buy_price:.10f}")
        #         print(f"\tBest buy price: {discounted_buy_price:.10f}, Best sell price: {sell_price:.10f}")
        #         logger.info(f"Best buy price: {discounted_buy_price:.10f}, Best sell price: {sell_price:.10f}")
        #         print(f"\tProfit: {profit:.10f} XRP")
        #         logger.info(f"Profit: {profit:.10f} XRP")
        #         print(f"\tMin profit needed: {self.min_profit_xrp:.15f}")
        #
        #         if profit > self.min_profit_xrp:
        #             logger.info(f"{'*' * 60} Trading opportunity found! Potential profit: {profit:.10f} {'*' * 60}")
        #             print(f"{'*' * 30} Trading opportunity found! Potential profit: {profit:.10f} {'*' * 30}")
        #             return True, discounted_buy_price, sell_price, profit, market_buy_price, best_buy_offer, best_sell_offer
        #         else:
        #             print(f"\tNo profitable opportunity (min profit needed: {self.min_profit_xrp} XRP)")
        #             logger.warning(f"No profitable opportunity (min profit needed: {self.min_profit_xrp} XRP)")
        #             return False, 0, 0, None, None, None, None
        #     except Exception as e:
        #         wait_time = 2 ** attempt
        #         logger.warning(f"Find arbitrage failed (attempt {attempt + 1}/{self.max_retries}): {e}. Retrying in {wait_time}s")
        #         self.metrics['trade_errors'] += 1
        #         if attempt == self.max_retries - 1:
        #             await send_alert(self, "Error finding arbitrage. The Bot is toast", logger)
        #             raise
        #         await asyncio.sleep(wait_time)
        #     finally:
        #         self.active_requests.remove(request_id)
        #         log_leaving_function('find_arbitrage', start_time, logger, DEBUG)

    # async def find_arbitrage(self, currency, issuer):
    #     start_time = time.time()
    #     log_entering_function('find_arbitrage', logger, DEBUG)
    #
    #     request_id = f"find_arbitrage_{self.request_counter}"
    #     self.active_requests.add(request_id)
    #     self.request_counter += 1
    #     logger.debug(f"currency: {currency}")
    #
    #     for attempt in range(self.max_retries):
    #         try:
    #             await self.get_balance(force_update=True)
    #
    #             trade_amount = next((meme['trade_amount'] for meme in self.meme_coins if meme['currency'] == currency), self.default_trade_amount)
    #             logger.debug(f"trade_amount: {trade_amount}")
    #             logger.debug(f"base_reserve: {self.base_reserve}")
    #             logger.debug(f"owner_count: {self.owner_count}")
    #             logger.debug(f"incremental_reserve: {self.incremental_reserve}")
    #             reserve = self.base_reserve + self.owner_count * self.incremental_reserve
    #             logger.debug(f"reserve: {reserve}")
    #
    #             self.ledger_fee = await self.get_current_fee()
    #             # if self.balances["XRP"] < (reserve + 0.01) or self.balances[currency] < trade_amount:
    #             if self.balances["XRP"] < (reserve + (self.ledger_fee * 2) + 0.01):
    #                 logger.info(f"Insufficient funds for {currency}: XRP={self.balances['XRP']:.6f}, {currency}={self.balances[currency]}")
    #                 return False, 0, 0, None, None, None, None
    #
    #             buy_task, sell_task = await asyncio.gather(
    #                 self.fetch_buy_offers(currency, issuer),
    #                 self.fetch_sell_offers(currency, issuer)
    #             )
    #
    #             buy_offers = buy_task.result.get("offers", []) if buy_task else []
    #             sell_offers = sell_task.result.get("offers", []) if sell_task else []
    #             print(f"\traw buy offer: {buy_offers}")
    #             logger.debug(f"raw buy offer: {buy_offers}")
    #             print(f"\traw sell offer: {sell_offers}")
    #             logger.debug(f"\traw sell offer: {sell_offers}")
    #
    #             if not buy_offers or not sell_offers:
    #                 logger.info(f"No offers available or fetch failed for {currency}")
    #                 print(f"\tInsufficient offers for arbitrage for {currency}")
    #                 return False, 0, 0, None, None, None, None
    #
    #             # best_buy_offer = max(buy_offers, key=lambda o: float(o["TakerGets"]) / float(o["TakerPays"]["value"]))
    #             best_buy_offer = max(buy_offers, key=lambda o: float(o["TakerGets"]) / float(o["TakerPays"]["value"]))
    #             # market_sell_price = float(best_buy_offer["TakerGets"]) / float(best_buy_offer["TakerPays"]["value"]) / 1000000
    #             market_sell_price = float(best_buy_offer["TakerGets"]) / float(best_buy_offer["TakerPays"]["value"]) / 1000000  # XRP per ARMY to sell
    #             # best_sell_offer = min(sell_offers, key=lambda o: float(o["TakerPays"]) / float(o["TakerGets"]["value"]))
    #             best_sell_offer = min(sell_offers, key=lambda o: float(o["TakerPays"]) / float(o["TakerGets"]["value"]))  # Correct
    #             # market_buy_price = float(best_sell_offer["TakerPays"]) / float(best_sell_offer["TakerGets"]["value"]) / 1000000
    #             market_buy_price = float(best_sell_offer["TakerPays"]) / float(best_sell_offer["TakerGets"]["value"]) / 1000000  # XRP per ARMY to buy
    #             trade_amount = min(trade_amount, float(best_sell_offer["TakerGets"]["value"]), float(best_buy_offer["TakerPays"]["value"]))
    #
    #             logger.debug(f"best_buy_offer: {best_buy_offer} market_sell_price: {market_sell_price} best_sell_offer: {best_sell_offer} market_buy_price: {market_buy_price} incremental_reserve: {trade_amount}")
    #             logger.info(f"Market Buy Price: {market_buy_price:.10f}, Market Sell Price: {market_sell_price:.10f}")
    #             print(f"best_buy_offer: {best_buy_offer} market_sell_price: {market_sell_price} best_sell_offer: {best_sell_offer} market_buy_price: {market_buy_price} incremental_reserve: {trade_amount}")
    #             print(f"Market Buy Price: {market_buy_price:.10f}, Market Sell Price: {market_sell_price:.10f}")
    #
    #             config_buy_price = market_buy_price * self.buy_discount
    #             config_sell_price = market_sell_price * self.sell_premium
    #             # config_profit = (config_sell_price - config_buy_price) * trade_amount - 0.000020
    #             config_profit = (config_sell_price - config_buy_price) * trade_amount - self.ledger_fee
    #             logger.info(f"Config pricing: Buy: {config_buy_price:.10f}, Sell: {config_sell_price:.10f}, Profit: {config_profit:.10f} XRP")
    #             print(f"\tMin profit needed: {self.min_profit_xrp:.15f}")
    #             print("\tYOOOOOOOOOOO")
    #
    #             if config_profit > self.min_profit_xrp:
    #                 print(f"\tConfig pricing: Buy: {config_buy_price:.10f}, Sell: {config_sell_price:.10f}, Profit: {config_profit:.10f} XRP")
    #                 logger.info(f"{'*' * 60} Trading opportunity found! Potential profit: {config_profit:.10f} {'*' * 60}")
    #                 print(f"{'*' * 30} Trading opportunity found! Potential profit: {config_profit:.10f} {'*' * 30}")
    #                 return True, config_buy_price, config_sell_price, config_profit, market_buy_price, best_buy_offer, best_sell_offer
    #
    #             spread = market_sell_price - market_buy_price
    #             # min_required_spread = (0.000020 / trade_amount) + (market_buy_price * (1 - self.buy_discount)) + (market_sell_price * (self.sell_premium - 1))
    #             min_required_spread = (self.ledger_fee / trade_amount) + (market_buy_price * (1 - self.buy_discount)) + (market_sell_price * (self.sell_premium - 1))
    #             # logger.info(f"spread: {spread:.10f}, min_required_spread: {min_required_spread:.10f}, min_required_spread_with_fees: {min_required_spread_with_fees}")
    #             logger.info(f"spread: {spread:.10f}, min_required_spread: {min_required_spread:.10f}")
    #
    #             if spread < min_required_spread:
    #                 dynamic_buy_discount = max(self.buy_discount, min(0.99, 1 - spread / market_buy_price * 1.5))
    #                 dynamic_sell_premium = min(1.10, max(self.sell_premium, 1 + spread / market_sell_price * 2))
    #                 discounted_buy_price = market_buy_price * dynamic_buy_discount
    #                 sell_price = market_sell_price * dynamic_sell_premium
    #             else:
    #                 discounted_buy_price = config_buy_price
    #                 sell_price = config_sell_price
    #
    #             print(f"Adjusted Buy: {discounted_buy_price:.10f}, Adjusted Sell: {sell_price:.10f}, Spread: {market_sell_price - market_buy_price:.10f}")
    #
    #             fee = self.ledger_fee * 2  # Two transactions
    #             logger.info(f"XRP fee: {fee}")
    #             profit = (sell_price - discounted_buy_price) * trade_amount - fee
    #             # profit = (sell_price - discounted_buy_price) * trade_amount - 0.000020
    #
    #             print(f"\tBest buy price: {discounted_buy_price:.10f}, Best sell price: {sell_price:.10f}")
    #             logger.info(f"Best buy price: {discounted_buy_price:.10f}, Best sell price: {sell_price:.10f}")
    #             print(f"\tProfit: {profit:.10f} XRP")
    #             logger.info(f"Profit: {profit:.10f} XRP")
    #             print(f"\tMin profit needed: {self.min_profit_xrp:.15f}")
    #
    #             if profit > self.min_profit_xrp:
    #                 logger.info(f"{'*' * 60} Trading opportunity found! Potential profit: {profit:.10f} {'*' * 60}")
    #                 print(f"{'*' * 30} Trading opportunity found! Potential profit: {profit:.10f} {'*' * 30}")
    #                 return True, discounted_buy_price, sell_price, profit, market_buy_price, best_buy_offer, best_sell_offer
    #             else:
    #                 print(f"\tNo profitable opportunity (min profit needed: {self.min_profit_xrp/1000000} XRP)")
    #                 logger.warning(f"No profitable opportunity (min profit needed: {self.min_profit_xrp/1000000} XRP)")
    #                 return False, 0, 0, None, None, None, None
    #         except Exception as e:
    #             wait_time = 2 ** attempt
    #             logger.warning(f"Find arbitrage failed (attempt {attempt + 1}/{self.max_retries}): {e}. Retrying in {wait_time}s")
    #             self.metrics['trade_errors'] += 1
    #             if attempt == self.max_retries - 1:
    #                 await send_alert(self, "Error finding arbitrage. The Bot is toast", logger)
    #                 raise
    #             await asyncio.sleep(wait_time)
    #         finally:
    #             self.active_requests.remove(request_id)
    #             log_leaving_function('find_arbitrage', start_time, logger, DEBUG)

    # async def execute_trade(self, discounted_buy_price, sell_price, profit, buy_price, sell_offer, buy_offer=None,
    #                         currency=None, issuer=None):
    #     start_time = time.time()
    #     logger.info(ENTERING_FUNCTION_LOG.format('execute_trade'))
    #     request_id = f"execute_trade_{self.request_counter}"
    #     self.active_requests.add(request_id)
    #     self.request_counter += 1
    #     max_retries = self.buy_sell_offers_retry
    #
    #     try:
    #         # Pre-trade checks
    #         if self.owner_count >= self.owner_count_limit:
    #             logger.info(
    #                 f"Skipping trade for {currency}: OwnerCount {self.owner_count} exceeds limit of {self.owner_count_limit}")
    #             return
    #
    #         if abs(discounted_buy_price - buy_price) / buy_price > self.slippage_tolerance:
    #             logger.warning(f"Excessive slippage on buy: {discounted_buy_price} vs {buy_price}")
    #             return
    #
    #         # Log pre-trade state
    #         logger.info(
    #             f"Executing trade - Pre-trade XRP={self.balances['XRP']:.6f}, {currency}={self.balances[currency]:.2f}")
    #         print(f"\tPre-trade XRP: {self.balances['XRP']:.6f}, {currency}={self.balances[currency]:.2f}")
    #
    #         buy_amount = float(buy_offer["TakerGets"]["value"])
    #         trade_amount = min(buy_amount,
    #                            next((meme['trade_amount'] for meme in self.meme_coins if meme['currency'] == currency),
    #                                 self.default_trade_amount))
    #         buy_amount_xrp = discounted_buy_price * trade_amount
    #
    #         expected_owner_count = self.owner_count
    #         self.pre_trade_balances = {curr['currency']: self.balances[curr['currency']] for curr in self.meme_coins}
    #         self.pre_trade_balances['XRP'] = self.balances['XRP']
    #
    #         print(f"\ttrade amount: {trade_amount} buy amount: {buy_amount}")
    #         print(f"\tbuy_amount_xrp: {buy_amount_xrp:.10f}")
    #         print(f"\tpre trade balances: {self.pre_trade_balances}")
    #         print(f"\texpected owner count: {expected_owner_count}")
    #
    #         # Buy transaction with retry logic
    #         buy_result = None
    #         async with self.tx_semaphore:
    #             for attempt in range(max_retries):
    #                 try:
    #                     tx_buy = prepare_offer_create_get_xrp(self.wallet.classic_address,
    #                                                           str(int(buy_amount_xrp * 1000000)), currency, issuer,
    #                                                           str(trade_amount))
    #                     async with httpx.AsyncClient(timeout=30.0) as custom_client:
    #                         self.client._client = custom_client
    #                         buy_result = await submit_and_wait(tx_buy, self.client, self.wallet)
    #                     # Check meta.TransactionResult instead of engine_result
    #                     if buy_result.result['meta']['TransactionResult'] == "tesSUCCESS":
    #                         tx_hash = buy_result.result['hash']
    #                         if await confirm_transaction(self, tx_hash, logger):
    #                             logger.info(f"Buy transaction validated: {tx_hash}")
    #                             break
    #                     else:
    #                         raise Exception(
    #                             f"Buy submission failed: {buy_result.result['meta']['TransactionResult']} - {buy_result.result.get('engine_result_message', 'No message')}")
    #                 except httpx.ConnectTimeout as e:
    #                     wait_time = 2 ** attempt
    #                     logger.warning(f"Buy attempt {attempt + 1}/{max_retries} timed out for {currency}: {str(e)}. Retrying in {wait_time}s")
    #                     if attempt == max_retries - 1:
    #                         logger.error(f"Buy failed for {currency} after {max_retries} retries due to timeout")
    #                         await send_alert(self, f"Buy failed for {currency} after {max_retries} retries due to timeout", logger)
    #                         return
    #                     await asyncio.sleep(wait_time)
    #                 except Exception as e:
    #                     logger.error(f"Buy attempt {attempt + 1}/{max_retries} failed for {currency}: {str(e)}")
    #                     if "tec" in str(e).upper() or "sequence" not in str(e).lower():  # Non-retryable error
    #                         raise
    #                     wait_time = 2 ** attempt
    #                     logger.warning(f"Retryable error on buy attempt {attempt + 1}/{max_retries}: {str(e)}. Retrying in {wait_time}s")
    #                     if attempt == max_retries - 1:
    #                         logger.error(f"Buy failed for {currency} after {max_retries} retries: {str(e)}")
    #                         await send_alert(self, f"Buy failed for {currency} after {max_retries} retries: {str(e)}", logger)
    #                         return
    #                     await asyncio.sleep(wait_time)
    #
    #         if not buy_result or buy_result.result['meta']['TransactionResult'] != "tesSUCCESS":
    #             raise Exception(
    #                 f"Buy failed for {currency}: {buy_result.result['meta']['TransactionResult'] if buy_result else 'No result'}")
    #
    #         logger.debug(f"Buy result: {buy_result.result}")
    #         print(f"\tBuy result: {buy_result.result}")
    #
    #         self.metrics["buy_trades_executed"] += 1
    #         self.total_xrp_spent += buy_amount_xrp
    #         logger.info(f"Buy confirmed for {currency}, Total XRP spent: {self.total_xrp_spent:.6f}")
    #         store_trade(self, logger, trade_type='buy', currency=currency, price=discounted_buy_price,
    #                     amount=trade_amount, xrp_amount=buy_amount_xrp, tx_hash=buy_result.result['hash'],
    #                     status=buy_result.result['meta']['TransactionResult'])
    #         self.trade_history.append({
    #             'type': 'buy', 'currency': currency, 'price': discounted_buy_price, 'amount': trade_amount,
    #             'xrp_spent': buy_amount_xrp, 'timestamp': time.strftime('%Y-%m-%d %H:%M:%S'),
    #             'status': buy_result.result['meta']['TransactionResult']
    #         })
    #
    #         await asyncio.sleep(self.run_pause)
    #
    #         # Sell transaction with retry logic
    #         market_sell_price = float(sell_offer["TakerGets"]) / float(sell_offer["TakerPays"]["value"]) / 1000000
    #         sell_price = market_sell_price * self.sell_premium
    #         sell_amount_xrp = sell_price * trade_amount
    #
    #         prelim_result = None
    #         async with self.tx_semaphore:
    #             for attempt in range(max_retries):
    #                 try:
    #                     tx_sell = prepare_offer_create_get_meme(self.wallet.classic_address, currency, issuer,
    #                                                             str(trade_amount), str(int(sell_amount_xrp * 1000000)))
    #                     async with httpx.AsyncClient(timeout=30.0) as custom_client:
    #                         self.client._client = custom_client
    #                         prelim_result = await submit_and_wait(tx_sell, self.client, self.wallet)
    #                     if prelim_result.result['meta']['TransactionResult'] == "tesSUCCESS":
    #                         tx_hash = prelim_result.result['hash']
    #                         if await confirm_transaction(self, tx_hash, logger):
    #                             logger.info(f"Sell transaction validated: {tx_hash}")
    #                             break
    #                     else:
    #                         raise Exception(
    #                             f"Sell submission failed: {prelim_result.result['meta']['TransactionResult']} - {prelim_result.result.get('engine_result_message', 'No message')}")
    #                 except httpx.ConnectTimeout as e:
    #                     wait_time = 2 ** attempt
    #                     logger.warning(
    #                         f"Sell attempt {attempt + 1}/{max_retries} timed out for {currency}: {str(e)}. Retrying in {wait_time}s")
    #                     if attempt == max_retries - 1:
    #                         logger.error(f"Sell failed for {currency} after {max_retries} retries due to timeout")
    #                         await send_alert(self,
    #                                          f"Sell failed for {currency} after {max_retries} retries due to timeout",
    #                                          logger)
    #                         await self.cancel_unused_offers()
    #                         return
    #                     await asyncio.sleep(wait_time)
    #                 except Exception as e:
    #                     logger.error(f"Sell attempt {attempt + 1}/{max_retries} failed for {currency}: {str(e)}")
    #                     if "tec" in str(e).upper() or "sequence" not in str(e).lower():
    #                         raise
    #                     wait_time = 2 ** attempt
    #                     logger.warning(
    #                         f"Retryable error on sell attempt {attempt + 1}/{max_retries}: {str(e)}. Retrying in {wait_time}s")
    #                     if attempt == max_retries - 1:
    #                         logger.error(f"Sell failed for {currency} after {max_retries} retries: {str(e)}")
    #                         await send_alert(self, f"Sell failed for {currency} after {max_retries} retries: {str(e)}",
    #                                          logger)
    #                         await self.cancel_unused_offers()
    #                         return
    #                     await asyncio.sleep(wait_time)
    #
    #         if not prelim_result or prelim_result.result['meta']['TransactionResult'] != "tesSUCCESS":
    #             await self.cancel_unused_offers()
    #             raise Exception(
    #                 f"Sell failed for {currency}: {prelim_result.result['meta']['TransactionResult'] if prelim_result else 'No result'}")
    #
    #         logger.debug(f"Sell result: {prelim_result.result}")
    #         print(f"\tSell result: {prelim_result.result}")
    #
    #         self.metrics["sell_trades_executed"] += 1
    #         self.total_xrp_received += sell_amount_xrp
    #         logger.info(f"Sell confirmed for {currency}, Total XRP received: {self.total_xrp_received:.6f}")
    #         store_trade(self, logger, trade_type='sell', currency=currency, price=sell_price, amount=trade_amount,
    #                     xrp_amount=sell_amount_xrp, tx_hash=prelim_result.result['hash'],
    #                     status=prelim_result.result['meta']['TransactionResult'])
    #         self.trade_history.append({
    #             'type': 'sell', 'currency': currency, 'price': sell_price, 'amount': trade_amount,
    #             'xrp_received': sell_amount_xrp, 'timestamp': time.strftime('%Y-%m-%d %H:%M:%S'),
    #             'status': prelim_result.result['meta']['TransactionResult']
    #         })
    #
    #         await asyncio.sleep(self.run_pause)
    #
    #         # Check if sell offer was consumed
    #         sell_consumed = False
    #         for _ in range(3):
    #             offers_response = await self.client.request(
    #                 prepare_account_offers(self.wallet.classic_address, "validated"))
    #             offers = offers_response.result.get('offers', [])
    #             if not any(o['seq'] == prelim_result.result['tx_json']['Sequence'] for o in offers):
    #                 logger.info("Sell offer consumed")
    #                 print("\tSell offer consumed")
    #                 sell_consumed = True
    #                 break
    #             print("\tLooping again....")
    #             await asyncio.sleep(self.run_pause)
    #
    #         if not sell_consumed:
    #             market_sell_price = float(sell_offer["TakerGets"]) / float(sell_offer["TakerPays"]["value"]) / 1000000
    #             logger.info(
    #                 f"Sell offer {prelim_result.result['tx_json']['Sequence']} not consumed, adjusting price to {market_sell_price:.10f}")
    #             print(
    #                 f"\tSell offer {prelim_result.result['tx_json']['Sequence']} not consumed, adjusting price to {market_sell_price:.10f}")
    #
    #             async with self.tx_semaphore:
    #                 tx_cancel = prepare_offer_cancel(self.wallet.classic_address,
    #                                                  prelim_result.result['tx_json']['Sequence'])
    #                 cancel_result = await submit_and_wait(tx_cancel, self.client, self.wallet)
    #                 logger.info(
    #                     f"Cancelled unconsumed sell offer {prelim_result.result['tx_json']['Sequence']}: {cancel_result.result}")
    #                 print(
    #                     f"\tCancelled unconsumed sell offer {prelim_result.result['tx_json']['Sequence']}: {cancel_result.result}")
    #
    #             sell_amount_xrp = market_sell_price * trade_amount
    #             async with self.tx_semaphore:
    #                 for attempt in range(max_retries):
    #                     try:
    #                         tx_sell_retry = prepare_offer_create_get_meme(self.wallet.classic_address, currency, issuer,
    #                                                                       str(trade_amount),
    #                                                                       str(int(sell_amount_xrp * 1000000)))
    #                         async with httpx.AsyncClient(timeout=30.0) as custom_client:
    #                             self.client._client = custom_client
    #                             retry_result = await submit_and_wait(tx_sell_retry, self.client, self.wallet)
    #                         if retry_result.result["engine_result"] == "tesSUCCESS" and await confirm_transaction(self, retry_result.result['hash'], logger):
    #                             self.metrics["sell_trades_executed"] += 1
    #                             sell_consumed = True
    #                             store_trade(self, logger, trade_type='sell', currency=currency, price=market_sell_price,
    #                                         amount=trade_amount, xrp_amount=sell_amount_xrp,
    #                                         tx_hash=retry_result.result['tx_json']['hash'],
    #                                         status=retry_result.result["engine_result"])
    #                             break
    #                     except Exception as e:
    #                         wait_time = 2 ** attempt
    #                         logger.warning(
    #                             f"Sell retry attempt {attempt + 1}/{max_retries} failed: {str(e)}. Retrying in {wait_time}s")
    #                         if attempt == max_retries - 1:
    #                             logger.error(f"Sell retry failed after {max_retries} attempts: {str(e)}")
    #                             raise Exception("Retry sell failed")
    #                         await asyncio.sleep(wait_time)
    #
    #         print(f"\tsell_consumed: {sell_consumed}")
    #
    #         if self.owner_count > self.owner_count_limit:
    #             await self.cancel_unused_offers()
    #
    #         fee_per_tx = 0.000010
    #         # fee_per_tx = await self.get_current_fee()
    #         if sell_consumed:
    #             realized_profit = round(sell_amount_xrp - buy_amount_xrp - (2 * fee_per_tx), 6)
    #             update_trade(self, logger, realized_profit, currency)
    #         else:
    #             realized_profit = round(-buy_amount_xrp - (2 * fee_per_tx), 6)
    #
    #         logger.info(f"Reserve change: {(self.owner_count - expected_owner_count) * self.incremental_reserve}")
    #         self.metrics["profit_xrp"] += realized_profit
    #         logger.info(f"Trade completed: Profit={realized_profit:.6f} XRP")
    #         print(f"\tTrade completed: Profit: {realized_profit:.6f} XRP UI XRP: {self.metrics['profit_xrp']}")
    #     except Exception as e:
    #         logger.error(f"Execute trade error: {str(e)}")
    #         self.metrics['trade_errors'] += 1
    #         await send_alert(self, "Error executing trades. The Bot is toast", logger)
    #         raise
    #     finally:
    #         self.active_requests.remove(request_id)
    #         log_leaving_function('execute_trade', start_time, logger)

    async def execute_trade(self, discounted_buy_price, sell_price, profit, buy_price, sell_offer, buy_offer=None, currency=None, issuer=None):
        start_time = time.time()
        logger.info(ENTERING_FUNCTION_LOG.format('execute_trade'))
        request_id = f"execute_trade_{self.request_counter}"
        self.active_requests.add(request_id)
        self.request_counter += 1
        try:
            if self.owner_count >= self.owner_count_limit:
                logger.info(f"Skipping trade for {currency}: OwnerCount {self.owner_count} exceeds limit of {self.owner_count_limit}")
                return

            if abs(discounted_buy_price - buy_price) / buy_price > self.slippage_tolerance:
                logger.warning(f"Excessive slippage on buy: {discounted_buy_price} vs {buy_price}")
                return

            logger.info(f"Executing trade - Pre-trade XRP={self.balances['XRP']:.6f}, {currency}={self.balances[currency]:.2f}")
            print(f"\tPre-trade XRP: {self.balances['XRP']:.6f}, {currency}={self.balances[currency]:.2f}")

            buy_amount = float(buy_offer["TakerGets"]["value"])
            trade_amount = min(buy_amount, next((meme['trade_amount'] for meme in self.meme_coins if meme['currency'] == currency), self.default_trade_amount))
            buy_amount_xrp = discounted_buy_price * trade_amount

            expected_owner_count = self.owner_count
            self.pre_trade_balances = {curr['currency']: self.balances[curr['currency']] for curr in self.meme_coins}
            self.pre_trade_balances['XRP'] = self.balances['XRP']

            print(f"\ttrade amount: {trade_amount} buy amount: {buy_amount}")
            print(f"\tbuy_amount_xrp: {buy_amount_xrp:.10f}")
            print(f"\tpre trade balances: {self.pre_trade_balances}")
            print(f"\texpected owner count: {expected_owner_count}")

            async with self.tx_semaphore:
                for attempt in range(self.buy_sell_offers_retry):
                    try:
                        tx_buy = prepare_offer_create_get_xrp(self.wallet.classic_address, str(int(buy_amount_xrp * 1000000)), currency, issuer, str(trade_amount))
                        signed_tx_buy = await autofill_and_sign(tx_buy, self.client, self.wallet)
                        buy_result = await submit(signed_tx_buy, self.client)
                        if buy_result.result["engine_result"] == "tesSUCCESS":
                            if buy_result.result['tx_json']['hash']:
                                tx_hash = buy_result.result['tx_json']['hash']
                                if await confirm_transaction(self, tx_hash, logger):
                                    break
                    except Exception as e:
                        if "sequence" in str(e).lower():
                            logger.warning(f"Sequence error on buy attempt {attempt + 1}: {e}. Retrying...")
                            await asyncio.sleep(2 ** attempt)
                        else:
                            raise

            logger.debug(f"Buy result: {buy_result.result}")
            print(f"\tBuy result: {buy_result.result}")

            if buy_result.result["engine_result"] == "tesSUCCESS":
                self.metrics["buy_trades_executed"] += 1
                self.total_xrp_spent += buy_amount_xrp
                logger.info(f"Buy confirmed for {currency}, Total XRP spent: {self.total_xrp_spent:.6f}")

                store_trade(self, logger,
                            trade_type='buy',
                            currency=currency,
                            price=discounted_buy_price,
                            amount=trade_amount,
                            xrp_amount=buy_amount_xrp,
                            tx_hash=buy_result.result['tx_json']['hash'],
                            status=buy_result.result["engine_result"]
                            )

                self.trade_history.append({
                    'type': 'buy',
                    'currency': currency,
                    'price': discounted_buy_price,
                    'amount': trade_amount,
                    'xrp_spent': buy_amount_xrp,
                    'timestamp': time.strftime('%Y-%m-%d %H:%M:%S'),
                    'status': buy_result.result["engine_result"],
                })
            else:
                raise Exception(f"Buy failed for {currency}: {buy_result.result['engine_result_message']}")

            await asyncio.sleep(self.run_pause)
            market_sell_price = float(sell_offer["TakerGets"]) / float(sell_offer["TakerPays"]["value"]) / 1000000
            sell_price = market_sell_price * self.sell_premium
            sell_amount_xrp = sell_price * trade_amount

            async with self.tx_semaphore:
                for attempt in range(self.buy_sell_offers_retry):
                    try:
                        tx_sell = prepare_offer_create_get_meme(self.wallet.classic_address, currency, issuer, str(trade_amount), str(int(sell_amount_xrp * 1000000)))
                        signed_tx_sell = await autofill_and_sign(tx_sell, self.client, self.wallet)
                        logger.debug(f"Submitting sell tx: {signed_tx_sell.to_dict()}")
                        print(f"\tSubmitting sell tx: {signed_tx_sell.to_dict()}")
                        prelim_result = await submit(signed_tx_sell, self.client)
                        if buy_result.result["engine_result"] == "tesSUCCESS":
                            if buy_result.result['tx_json']['hash']:
                                tx_hash = buy_result.result['tx_json']['hash']
                                if await confirm_transaction(self, tx_hash, logger):
                                    break
                    except Exception as e:
                        if "sequence" in str(e).lower():
                            logger.warning(f"Sequence error on buy attempt {attempt + 1}: {e}. Retrying...")
                            await asyncio.sleep(2 ** attempt)
                        else:
                            raise

            if prelim_result.result["engine_result"] == "tesSUCCESS":
                self.metrics["sell_trades_executed"] += 1
                self.total_xrp_received += sell_amount_xrp
                logger.info(f"Sell confirmed for {currency}, Total XRP received: {self.total_xrp_received:.6f}")

                # Store preliminary sell trade (will update with profit later)
                store_trade(self, logger,
                            trade_type='sell',
                            currency=currency,
                            price=sell_price,
                            amount=trade_amount,
                            xrp_amount=sell_amount_xrp,
                            tx_hash=buy_result.result['tx_json']['hash'],
                            status=prelim_result.result["engine_result"]
                            )

                self.trade_history.append({
                    'type': 'sell',
                    'currency': currency,
                    'price': sell_price,
                    'amount': trade_amount,
                    'xrp_received': sell_amount_xrp,
                    'timestamp': time.strftime('%Y-%m-%d %H:%M:%S'),
                    'status': prelim_result.result["engine_result"],
                })
            else:
                await self.cancel_unused_offers()
                raise Exception(f"Sell failed for {currency}")

            await asyncio.sleep(self.run_pause)

            sell_consumed = False
            for _ in range(3):
                offers_response = await self.client.request(
                    prepare_account_offers(self.wallet.classic_address, "validated"))
                offers = offers_response.result.get('offers', [])
                if not any(o['seq'] == signed_tx_sell.sequence for o in offers):
                    logger.info("Sell offer consumed")
                    print("\tSell offer consumed")
                    sell_consumed = True
                    break
                print("\tLooping again....")
                await asyncio.sleep(self.run_pause)

                if not sell_consumed:
                    market_sell_price = float(sell_offer["TakerGets"]) / float(sell_offer["TakerPays"]["value"]) / 1000000
                    logger.info(f"Sell offer {signed_tx_sell.sequence} not consumed, adjusting price to {market_sell_price:.10f}")
                    print(f"\tSell offer {signed_tx_sell.sequence} not consumed, adjusting price to {market_sell_price:.10f}")

                    tx_cancel = prepare_offer_cancel(self.wallet.classic_address, signed_tx_sell.sequence)
                    signed_tx_cancel = await autofill_and_sign(tx_cancel, self.client, self.wallet)
                    cancel_result = await submit(signed_tx_cancel, self.client)

                    logger.info(f"Cancelled unconsumed sell offer {signed_tx_sell.sequence}: {cancel_result.result}")
                    print(f"\tCancelled unconsumed sell offer {signed_tx_sell.sequence}: {cancel_result.result}")

                    for attempt in range(self.buy_sell_offers_retry):
                        try:
                            tx_sell_retry = prepare_offer_create_get_meme(self.wallet.classic_address, currency, issuer, str(trade_amount), str(int(sell_amount_xrp * 1000000)))
                            signed_tx_sell_retry = await autofill_and_sign(tx_sell_retry, self.client, self.wallet)
                            print(f"\tSubmitting retry sell tx at market price: {signed_tx_sell_retry.to_dict()}")
                            retry_result = await submit(signed_tx_sell_retry, self.client)
                            print(f"\tRetry sell result: {retry_result.result}")
                            break
                        except Exception as e:
                            logger.error(f"Buy failed in prepare_offer_create_get_meme for {currency}: {e}")

                    if retry_result.result["engine_result"] == "tesSUCCESS":
                        self.metrics["sell_trades_executed"] += 1
                        sell_consumed = True
                        store_trade(self, logger,
                                    trade_type='sell',
                                    currency=currency,
                                    price=market_sell_price,
                                    amount=trade_amount,
                                    xrp_amount=sell_amount_xrp,
                                    tx_hash=retry_result.result['tx_json']['hash'],
                                    status=retry_result.result["engine_result"]
                                    )
                    else:
                        logger.warning("Retry sell failed, TST balance not re-adjusted")
                        raise Exception("Retry sell failed")

            print(f"\tsell_consumed: {sell_consumed}")

            if self.owner_count > self.owner_count_limit:
                await self.cancel_unused_offers()

            fee_per_tx = 0.000010
            # fee_per_tx = await self.get_current_fee()
            if sell_consumed:
                realized_profit = round(sell_amount_xrp - buy_amount_xrp - (2 * fee_per_tx), 6)
                update_trade(self, logger, realized_profit, currency)
            else:
                realized_profit = round(-buy_amount_xrp - (2 * fee_per_tx), 6)

            logger.info(f"Reserve change: {(self.owner_count - expected_owner_count) * self.incremental_reserve}")
            self.metrics["profit_xrp"] += realized_profit
            logger.info(f"Trade completed: Profit: {realized_profit:.6f} XRP UI XRP: {self.metrics['profit_xrp']}")
            print(f"\tTrade completed: Profit: {realized_profit:.6f} XRP UI XRP: {self.metrics['profit_xrp']}")
        except Exception as e:
            logger.error(f"Execute trade error: {str(e)}")
            self.metrics['trade_errors'] += 1
            await send_alert(self, "Error executing trades. The Bot is toast", logger)
            raise
        finally:
            self.active_requests.remove(request_id)
            log_leaving_function('execute_trade', start_time, logger, INFO)

    async def check_stop_loss(self):
        start_time = time.time()
        logger.info(ENTERING_FUNCTION_LOG.format('check_stop_loss'))

        request_id = f"check_stop_loss_{self.request_counter}"
        self.active_requests.add(request_id)
        self.request_counter += 1

        for attempt in range(self.max_retries):
            try:
                """Check if the net loss exceeds the stop-loss threshold."""
                if self.total_xrp_spent == 0:
                    return False
                await self.get_balance(force_update=True)
                total_unrealized_value = 0
                for meme in self.meme_coins:
                    price = await self.get_current_market_price(meme['currency'], meme['issuer'])
                    total_unrealized_value += self.balances[meme['currency']] * price
                net_pnl = (self.total_xrp_received - self.total_xrp_spent) + total_unrealized_value
                loss_percentage = net_pnl / self.total_xrp_spent if self.total_xrp_spent > 0 else 0

                logger.info(f"Net PnL: {net_pnl:.6f} XRP, Loss %: {loss_percentage:.2%}, Threshold: {self.stop_loss}")
                if loss_percentage <= self.stop_loss:
                    for meme in self.meme_coins:
                        await self.liquidate_position(meme['currency'], meme['issuer'])
                    await send_alert(self, f"Stop-loss triggered: {net_pnl:.6f} XRP", logger)
                    return True
                return False
            except Exception as e:
                wait_time = 2 ** attempt
                logger.warning(f"Check stop loss failed (attempt {attempt + 1}/{self.max_retries}): {e}. Retrying in {wait_time}s")
                self.metrics['runtime_errors'] += 1
                if attempt == self.max_retries - 1:
                    await send_alert(self, "Error checking stop loss. The Bot is toast", logger)
                    raise
                await asyncio.sleep(wait_time)
            finally:
                self.active_requests.remove(request_id)
                log_leaving_function('check_stop_loss', start_time, logger, INFO)

    async def get_current_market_price(self, currency, issuer):
        start_time = time.time()
        logger.info(ENTERING_FUNCTION_LOG.format('get_current_market_price'))

        request_id = f"get_current_market_price_{self.request_counter}"
        self.active_requests.add(request_id)
        self.request_counter += 1
        # currency = encode_currency(currency)
        logger.debug(f"currency: {currency}")

        for attempt in range(self.max_retries):
            try:
                sell_offers_response = await self.fetch_sell_offers(currency, issuer)
                sell_offers = sell_offers_response.result.get("offers", []) if sell_offers_response else []
                if sell_offers:
                    best_offer = min(sell_offers, key=lambda o: float(o["TakerPays"]) / float(o["TakerGets"]["value"]))
                    price = float(best_offer["TakerPays"]) / float(best_offer["TakerGets"]["value"]) / 1000000
                    self.last_known_price[currency] = price
                    return price
                return self.last_known_price.get(currency, 0)
            except Exception as e:
                wait_time = 2 ** attempt
                logger.warning(f"Get market price failed (attempt {attempt + 1}/{self.max_retries}): {e}. Retrying in {wait_time}s")
                self.metrics['runtime_errors'] += 1
                if attempt == self.max_retries - 1:
                    await send_alert(self, "Error getting current market price. The Bot is toast", logger)
                    raise
                await asyncio.sleep(wait_time)
            finally:
                self.active_requests.remove(request_id)
                log_leaving_function('get_current_market_price', start_time, logger, INFO)

    async def liquidate_position(self, currency, issuer):
        start_time = time.time()
        logger.info(ENTERING_FUNCTION_LOG.format('liquidate_position'))
        request_id = f"liquidate_position_{self.request_counter}"
        self.active_requests.add(request_id)
        self.request_counter += 1
        # currency = encode_currency(currency)
        logger.debug(f"currency: {currency}")

        try:
            await self.get_balance(force_update=True)
            balance = self.balances.get(currency, 0)
            if balance <= 0:
                logger.info(f"No {currency} to liquidate")
                return

            market_price = await self.get_current_market_price(currency, issuer)
            limit_price = market_price * 0.95
            sell_xrp = int(balance * limit_price * 1000000)

            logger.info(f"Liquidating {balance} {currency} at Limit price: {limit_price} at Market Price: {market_price} XRP/{currency} at {sell_xrp} XRP")

            for attempt in range(self.max_retries):
                try:
                    tx_sell = prepare_offer_create_get_meme(self.wallet.classic_address, currency, issuer, str(balance), str(sell_xrp))
                    result = await submit_and_wait(tx_sell, self.client, self.wallet)
                    if result.result['meta']['TransactionResult'] == "tesSUCCESS":
                        self.total_xrp_received += sell_xrp / 1000000
                        self.metrics["sell_trades_executed"] += 1
                        logger.info(f"Liquidated {balance} {currency}")
                except Exception as e:
                    wait_time = 2 ** attempt  # Exponential backoff: 1s, 2s, 4s
                    logger.warning(f"Error liquidating offers for {currency} issuer {issuer} (attempt {attempt + 1}/{self.max_retries}): {str(e)}. Retrying in {wait_time}s")
                    self.metrics['runtime_errors'] += 1
                    if attempt == self.max_retries - 1:
                        logger.error(f"Failed to liquidate offers for {currency} after {self.max_retries} attempts")
                        await send_alert(self, f"Failed to liquidate offers for {currency} after {self.max_retries} retries.", logger)
                        raise
                    await asyncio.sleep(wait_time)
        except Exception as e:
            logger.error(f"Liquidate error: {str(e)}")
            self.metrics['runtime_errors'] += 1
            await send_alert(self, "Error liquidating positions. The Bot is toast", logger)
            raise
        finally:
            log_leaving_function('liquidate_position', start_time, logger, INFO)

    async def run(self):
        start_time = time.time()
        logger.info(ENTERING_FUNCTION_LOG.format('run'))

        iteration = 0
        await self.load_config()

        try:
            while self.running:
                iteration += 1
                self.metrics['bot_iterations'] += 1
                logger.info(f"{'*' * 3} Bot iteration {iteration} {'*' * 3}")
                # print(f"Bot iteration {iteration}")

                if await self.check_stop_loss():
                    logger.info("Stop-loss triggered, halting bot")
                    self.running = False
                    break

                await self.get_balance(force_update=True)
                if self.owner_count >= self.owner_count_limit or any(self.balances[m['currency']] > self.max_meme_amount_to_hold for m in self.meme_coins):
                    logger.info(f"Too many offers or {self.currency} accumulation, cancelling before trade")
                    try:
                        await self.cancel_unused_offers()
                    except Exception as e:
                        logger.error(f"Failed to cancel offers: {str(e)}. Continuing to next iteration")
                        await send_alert(self, f"Error cancelling unused offers in iteration {iteration}: {str(e)}", logger)

                    await asyncio.sleep(self.bot_sleep)

                # print(f"\tNumber of active request before find_arbitrage: {len(bot.active_requests)}")
                logger.info(f"Number of active request before find_arbitrage: {len(bot.active_requests)}")

                tasks = [self.find_arbitrage(meme['currency'], meme['issuer']) for meme in self.meme_coins if self.balances[meme['currency']] <= self.max_meme_amount_to_hold]
                results = await asyncio.gather(*tasks, return_exceptions=True)

                for i, result in enumerate(results):
                    if isinstance(result, Exception):
                        logger.error(f"Arbitrage error for {self.meme_coins[i]['currency']}: {result}")
                        continue

                    has_opportunity, discounted_buy_price, sell_price, profit, buy_price, sell_offer, buy_offer = result
                    if has_opportunity:
                        logger.info(f"********* Trading opportunity found for {self.meme_coins[i]['currency']}! Potential profit: {profit} XRP *********")
                        try:
                            pass
                            # await self.execute_trade(discounted_buy_price, sell_price, profit, buy_price, sell_offer, buy_offer, self.meme_coins[i]['currency'], self.meme_coins[i]['issuer'])
                        except Exception as e:
                            logger.error(f"Failed to execute trade: {str(e)}. Continuing to next iteration")
                    else:
                        logger.info(f"No profitable opportunity for {self.meme_coins[i]['currency']} (min profit needed: {self.min_profit_xrp:.6f} XRP)")

                await asyncio.sleep(self.run_pause)
        except Exception as e:
            logger.error(f"Run error in iteration {iteration}: {str(e)}", exc_info=True)
            self.metrics['runtime_errors'] += 1
            await send_alert(self, "Error in run. Sleeping.... Check logs for issues", logger)
            await asyncio.sleep(self.bot_sleep)
        finally:
            log_leaving_function('run', start_time, logger, INFO)

    async def cleanup(self):
        """Clean up resources before shutdown."""
        start_time = time.time()
        logger.info(ENTERING_FUNCTION_LOG.format('cleanup'))
        try:
            # Check if self.client exists and has an _client attribute
            if self.client and hasattr(self.client, '_client') and self.client._client is not None:
                await self.client._client.aclose()
                logger.info("HTTP client closed successfully")
                self.client._client = None  # Clear the reference
            else:
                logger.debug("No HTTP client to close")
            self.client = None  # Clear the AsyncJsonRpcClient reference
        except Exception as e:
            logger.error(f"Cleanup error: {str(e)}")
        finally:
            log_leaving_function('cleanup', start_time, logger, INFO)

bot = TradingBot()

@app.route('/')
async def index():
    start_time = time.time()
    log_entering_function('index', logger, DEBUG)
    try:
        logger.info("Rendering index page...")

        # Check if the bot is initialized
        if not hasattr(bot, 'wallet') or bot.wallet is None:
            logger.error("Bot wallet is not initialized.")
            return "Bot is not initialized. Please try again later.", 503

        # Generate QR code
        logger.info("Generating QR code...")
        if not bot.wallet_qr_codes:
            for meme in bot.meme_coins:
                qr = qrcode.QRCode()
                qr.add_data(meme['issuer'])
                qr_buffer = BytesIO()
                qr.make_image().save(qr_buffer)
                qr_data = base64.b64encode(qr_buffer.getvalue()).decode()
                bot.wallet_qr_codes.append(
                {
                    'qr_data': qr_data,
                    'currency': meme['currency'],
                    'issuer': meme['issuer'],
                })

        qr = qrcode.QRCode()
        qr.add_data(bot.wallet.classic_address)
        qr_buffer = BytesIO()
        qr.make_image().save(qr_buffer)
        qr_data = base64.b64encode(qr_buffer.getvalue()).decode()
        logger.info("QR code generated successfully.")

        # Prepare balances
        logger.info("Preparing balances...")
        logger.info(f"Balances prepared: {bot.balances}")

        # Render the template
        logger.info("Rendering template...")
        return await render_template(
            'index.html',
            metrics=bot.metrics,
            balances=bot.balances,
            address=bot.wallet.classic_address,
            qr_code=qr_data,
            running=bot.running,
            currency=bot.currency,
            config=bot.config,
            meme_coins=bot.meme_coins,
            wallet_qr_codes=bot.wallet_qr_codes,
            ledger_fee=bot.ledger_fee
        )
    except Exception as e:
        logger.error(f"Index error: {str(e)}", exc_info=True)
        return "Internal Server Error", 500
    finally:
        log_leaving_function('index', start_time, logger, DEBUG)

@app.route('/update_config', methods=['POST'])
async def update_config():
    start_time = time.time()
    log_entering_function('update_config', logger, INFO)
    try:
        data = await request.json
        result = await bot.update_config(data)
        # load config to pick up config changes.
        await bot.load_config()
        return jsonify(result)
    except Exception as e:
        logger.error(f"Update config error: {str(e)}", exc_info=True)
        return jsonify({'status': 'error', 'message': 'Internal Server Error'}), 500
    finally:
        log_leaving_function('update_config', start_time, logger, INFO)

@app.route('/stop', methods=['POST'])
async def stop_bot():
    start_time = time.time()
    logger.info(ENTERING_FUNCTION_LOG.format('stop_bot'))
    try:
        if bot.running:
            bot.running = False
            if bot.task:  # Cancel the bot.run() task if it exists
                bot.task.cancel()
                try:
                    await bot.task  # Wait for the task to be cancelled
                except asyncio.CancelledError:
                    logger.info("Bot task was cancelled successfully")

            # Wait for all active XRPL requests to complete
            # timeout = 20  # seconds
            while bot.active_requests and (time.time() - start_time) < bot.bot_timeout:
                logger.info(f"Waiting for {len(bot.active_requests)} active requests to complete...")
                await asyncio.sleep(bot.bot_sleep)  # Brief sleep to avoid busy-waiting

            if bot.active_requests:
                logger.warning(f"Timeout reached, {len(bot.active_requests)} requests still active")

            logger.info("Bot stopped")
            return jsonify({'status': 'success', 'message': 'Bot 2 is sleeping'})
        return jsonify({'status': 'error', 'message': 'Bot not running'})
    except Exception as e:
        logger.error(f"Stop bot error: {str(e)}", exc_info=True)
        return "Internal Server Error", 500
    finally:
        log_leaving_function('stop_bot', start_time, logger, INFO)

@app.route('/kill', methods=['POST'])
async def kill_bot():
    start_time = time.time()
    logger.info(ENTERING_FUNCTION_LOG.format('kill_bot'))
    try:
        logger.info("Shutting down the application...")
        # Stop the bot if it's running
        if bot.running:
            bot.running = False
            if bot.task:
                bot.task.cancel()
                try:
                    await bot.task
                except asyncio.CancelledError:
                    logger.info("Bot task was cancelled successfully")

            # Cancel background tasks
            for task in bot.background_tasks:
                task.cancel()
                try:
                    await task
                except asyncio.CancelledError:
                    pass

            # Wait for all active XRPL requests to complete
            while bot.active_requests and (time.time() - start_time) < bot.bot_timeout:
                logger.info(f"Waiting for {len(bot.active_requests)} active requests to complete...")
                await asyncio.sleep(bot.bot_sleep)  # Brief sleep to avoid busy-waiting

            if bot.active_requests:
                logger.warning(f"Timeout reached, {len(bot.active_requests)} requests still active")

        # Clean up the client
        await bot.cleanup()

        # Send a response to the client before shutting down
        response = jsonify({'status': 'success', 'message': 'The Bot is toast'})

        # Schedule a background task to shut down the server after the response is sent
        """Shut down the server gracefully."""
        logger.info("Shutting down the server...")
        asyncio.get_event_loop().create_task(app.shutdown())

        return response
    except Exception as e:
        logger.error(f"Kill bot error: {str(e)}", exc_info=True)
        return "Internal Server Error", 500
    finally:
        log_leaving_function('kill_bot', start_time, logger, INFO)

@app.route('/status', methods=['GET'])
async def get_status():
    start_time = time.time()
    log_entering_function('get_status', logger, DEBUG)
    request_id = f"get_status_{bot.request_counter}"
    await bot.get_balance()
    bot.active_requests.add(request_id)
    bot.request_counter += 1
    try:
        async with bot.request_semaphore:
            open_offers_response = await bot.client.request(prepare_account_offers(bot.wallet.classic_address, "validated"))
        open_offers = open_offers_response.result.get('offers', [])

        # Ensure wallet_qr_codes is up-to-date with meme_coins
        current_currencies = {qr['currency'] for qr in bot.wallet_qr_codes}
        new_currencies = {meme['currency'] for meme in bot.meme_coins}
        if current_currencies != new_currencies:
            bot.wallet_qr_codes = []
            for meme in bot.meme_coins:
                qr = qrcode.QRCode()
                qr.add_data(meme['issuer'])
                qr_buffer = BytesIO()
                qr.make_image().save(qr_buffer)
                qr_data = base64.b64encode(qr_buffer.getvalue()).decode()
                bot.wallet_qr_codes.append({
                    'currency': meme['currency'],
                    'issuer': meme['issuer'],
                    'qr_data': qr_data
                })

        # db_trade_history = get_trade_history(bot, logger, 1000)
        # print(f"trade_history: {db_trade_history}")

        return jsonify({
            'running': bot.running,
            'metrics': bot.metrics,
            'balances': bot.balances,
            'open_offers': len(open_offers),
            'trade_history': bot.trade_history[-1000:],
            'total_xrp_spent': bot.total_xrp_spent,  # Add total XRP spent
            'total_xrp_received': bot.total_xrp_received,  # Add total XRP received
            'total_reserve': bot.total_reserve,
            'meme_coins': [m['currency'] for m in bot.meme_coins],  # Add list of currencies
            'wallet_qr_codes': bot.wallet_qr_codes  # Add this
        })
    except Exception as e:
        logger.error(f"Status error: {str(e)}", exc_info=True)
        return "Internal Server Error", 500
    finally:
        bot.active_requests.remove(request_id)
        log_leaving_function('get_status', start_time, logger, DEBUG)

@app.route('/start', methods=['POST'])
async def start_bot():
    start_time = time.time()
    logger.info(ENTERING_FUNCTION_LOG.format('start_bot'))
    try:
        if not bot.running:
            bot.running = True
            bot.task = asyncio.create_task(bot.run())  # Run the bot asynchronously
            logger.info("Bot started")
            return jsonify({'status': 'success', 'message': 'Bot started'})
        return jsonify({'status': 'error', 'message': 'Bot already running'})
    except Exception as e:
        logger.error(f"Start bot error: {str(e)}", exc_info=True)
        return "Internal Server Error", 500
    finally:
        log_leaving_function('start_bot', start_time, logger, INFO)

async def initialize_bot():
    start_time = time.time()
    logger.info(ENTERING_FUNCTION_LOG.format('initialize_bot'))
    try:
        await bot.initialize()
        logger.info("Bot initialized successfully.")
        logger.info(f"Wallet address: {bot.wallet.classic_address}")
        logger.info(f"Balances: {bot.balances}")
    except Exception as e:
        logger.error(f"Initialize bot error: {str(e)}", exc_info=True)
        raise
    finally:
        log_leaving_function('initialize_bot', start_time, logger, INFO)

if __name__ == "__main__":
    logger.info("Initializing bot...")
    os.makedirs(os.path.join(BASE_DIR, 'logs'), exist_ok=True)

    asyncio.run(initialize_bot())  # Call initialize_bot() to initialize the bot

    logger.info("Starting Quart application with Hypercorn")
    from hypercorn.config import Config
    from hypercorn.asyncio import serve

    # Create a Hypercorn config
    config = Config()
    config.bind = ["127.0.0.1:5000"]  # Bind to the same address and port
    config.use_reloader = False  # Disable reloader in production

    # Run the app with Hypercorn
    asyncio.run(serve(app, config))


# import base64
# import os
# import time
# from io import BytesIO
#
# import httpx
# import qrcode
# import yaml
# from logging.config import dictConfig
# from flask import render_template, jsonify
# import asyncio
# from xrpl.asyncio.clients import AsyncJsonRpcClient
# from xrpl.asyncio.transaction import autofill_and_sign, submit, submit_and_wait
# from xrpl.models import Fee
# from xrpl.wallet import Wallet
# from quart import Quart, render_template, jsonify, request
# import logging
#
# from db_operations.db_trades import initialize_database, store_trade, update_trade
# from utils.constants import JSON_RPC_URL, ENTERING_FUNCTION_LOG
# from utils.utilities import log_leaving_function, prepare_account_lines, prepare_trust_set, prepare_account_info, \
#     prepare_account_offers, prepare_offer_cancel, prepare_fetch_sell_offer_generic_object, \
#     prepare_buy_offer_generic_object, prepare_offer_create_get_xrp, prepare_offer_create_get_meme, \
#     prepare_remove_trust_set, send_alert, confirm_transaction
#
# BASE_DIR = os.path.dirname(os.path.abspath(__file__))
# logging.basicConfig(level=logging.INFO)
# logger = logging.getLogger('xrpl_trading_bot')
#
# app = Quart(__name__)
#
# class TradingBot:
#     def __init__(self):
#         self.slippage_tolerance = None
#         self.background_tasks = None
#         self.buy_sell_offers_limit = None
#         self.buy_sell_offers_retry = None
#         self.alert_phone_email = None
#         self.email_password = None
#         self.email_address = None
#         self.db_path = os.path.join(BASE_DIR, 'trades.db')
#         initialize_database(self, logger)
#         self.run_pause = None
#         self.trust_line_max = None
#         self.bot_timeout = None
#         self.bot_sleep = None
#         self.max_meme_amount_to_hold = None
#         self.last_balance_time = 0
#         self.owner_count_limit = None
#         self.client = None
#         self.wallet = None
#         self.pre_trade_balances = 0
#         self.min_profit_xrp = None
#         self.buy_discount = None
#         self.sell_premium = None
#         self.config = None
#         self.incremental_reserve = None
#         self.base_reserve = None
#         self.default_trade_amount = None
#         self.issuer_address = None
#         self.currency = None
#         self.running = False # Track if the bot is running
#         self.task = None  # Track the bot.run() task
#         self.request_semaphore = asyncio.Semaphore(10)  # Limit concurrent requests
#         self.tx_semaphore = asyncio.Semaphore(2)  # Limit to 2 concurrent transactions
#         self.meme_coins = []  # List of {'currency': str, 'issuer': str}
#         self.last_known_price = {}  # Cache last known prices
#         self.trade_history = []
#         self.wallet_qr_codes = []
#         self.metrics = {'buy_trades_executed': 0, 'sell_trades_executed':0, 'trade_errors': 0, 'profit_xrp': 0, 'runtime_errors': 0, 'bot_iterations':0}
#         self.balances = {'XRP': 0}
#         self.owner_count = None
#         self.active_requests = set()  # Track active network requests
#         self.request_counter = 0  # Unique ID for each request
#         self.total_xrp_spent = 0  # Total XRP spent on buys
#         self.total_xrp_received = 0  # Total XRP received from sells
#         self.stop_loss = None  # Loaded from config
#
#     async def initialize(self):
#         global logger  # If logger is global; otherwise, define in class
#         start_time = time.time()
#         logger.info(ENTERING_FUNCTION_LOG.format('initialize'))
#         try:
#             self.client = AsyncJsonRpcClient(JSON_RPC_URL)
#             self.client._client = httpx.AsyncClient(
#                 limits=httpx.Limits(max_connections=100, max_keepalive_connections=20),
#                 timeout=30.0
#             )
#             await self.load_config()
#             self.wallet = await self.load_wallet()
#             for meme in self.meme_coins:
#                 await self.check_trust_line(meme['currency'], meme['issuer'])
#                 self.balances[meme['currency']] = 0
#             await self.get_balance(force_update=True)
#             await self.cancel_unused_offers()
#             # Start background tasks
#             self.background_tasks = [
#                 asyncio.create_task(self.background_balance_updater())
#             ]
#             logger.info(f"Bot initialized: {self.wallet.classic_address}")
#         except Exception as e:
#             logger.error(f"Initialization failed: {str(e)}", exc_info=True)
#             raise
#         finally:
#             log_leaving_function('initialize', start_time, logger)
#
#     async def background_balance_updater(self):
#         """Periodically update balances in the background"""
#         while self.running:
#             try:
#                 await self.get_balance(force_update=True)
#                 await asyncio.sleep(5)  # Update every 5 seconds
#             except Exception as e:
#                 logger.error(f"Balance updater error: {e}")
#                 await asyncio.sleep(self.bot_sleep)
#
#     async def load_config(self):
#         global logger
#         start_time = time.time()
#         logger.info(ENTERING_FUNCTION_LOG.format('load_config'))
#         try:
#             with open("config/trading_bot_config.yaml", 'r') as f:
#                 self.config = yaml.safe_load(f)
#             logging_config = self.config.get('logging', {})
#             if logging_config:
#                 # Adjust the filename to be absolute based on BASE_DIR
#                 file_handler = logging_config['handlers'].get('file', {})
#                 if 'filename' in file_handler:
#                     file_handler['filename'] = os.path.join(BASE_DIR, file_handler['filename'])
#                 dictConfig(logging_config)
#                 logger = logging.getLogger('xrpl_trading_bot')
#
#             self.meme_coins = self.config['meme_coins']
#             self.currency = self.config['meme_coins'][0]['currency']
#             self.issuer_address = self.config['meme_coins'][0]['issuer']
#             self.default_trade_amount = float(self.config['settings']['trade_amount'])  # Default trade amount
#             self.base_reserve = float(self.config['settings']['base_reserve'])
#             self.incremental_reserve = float(self.config['settings']['incremental_reserve'])
#             self.stop_loss = float(self.config['settings']['stop_loss'])
#             self.buy_discount = float(self.config['settings']['buy_discount'])
#             self.sell_premium = float(self.config['settings']['sell_premium'])
#             self.min_profit_xrp = float(self.config['settings']['min_profit_xrp'])
#             self.owner_count_limit = self.config['settings']['owner_count_limit']
#             self.max_meme_amount_to_hold = self.config['settings']['max_meme_amount_to_hold']
#             self.bot_sleep = self.config['settings']['bot_sleep']
#             self.run_pause = self.config['settings']['run_pause']
#             self.bot_timeout = self.config['settings']['bot_timeout']
#             self.trust_line_max = self.config['settings']['trust_line_max']
#             self.email_address = self.config['settings']['email_address']
#             self.email_password = self.config['settings']['email_password']
#             self.alert_phone_email = self.config['settings']['alert_phone_email']
#             self.buy_sell_offers_retry = self.config['settings']['buy_sell_offers_retry']
#             self.buy_sell_offers_limit = self.config['settings']['buy_sell_offers_limit']
#             self.slippage_tolerance = self.config['settings']['slippage_tolerance']
#             # Set trade_amount per meme coin, falling back to default
#             for meme in self.meme_coins:
#                 meme['trade_amount'] = float(meme.get('trade_amount', self.default_trade_amount))
#             logger.info(f"Config loaded: Trading {len(self.meme_coins)} meme coins - {self.meme_coins}")
#         except Exception as e:
#             logger.error(f"Config load error: {str(e)}")
#             raise
#         finally:
#             log_leaving_function('load_config', start_time, logger)
#
#     async def update_config(self, new_config):
#         start_time = time.time()
#         logger.info(ENTERING_FUNCTION_LOG.format('update_config'))
#         try:
#             # Read the existing config file to preserve other settings
#             with open("config/trading_bot_config.yaml", 'r') as f:
#                 current_config = yaml.safe_load(f)
#
#             # Identify removed meme coins
#             current_currencies = {meme['currency'] for meme in current_config['meme_coins']}
#             new_currencies = {meme['currency'] for meme in new_config['meme_coins']}
#             removed_currencies = current_currencies - new_currencies
#             removed_meme_coins = [
#                 meme for meme in current_config['meme_coins']
#                 if meme['currency'] in removed_currencies
#             ]
#
#             # Update the bot's internal state
#             self.meme_coins = new_config['meme_coins']
#             for meme in self.meme_coins:
#                 if meme['currency'] not in self.balances:
#                     await self.check_trust_line(meme['currency'], meme['issuer'])
#                     self.balances[meme['currency']] = 0
#             current_currencies = {meme['currency'] for meme in self.meme_coins}
#             for currency in list(self.balances.keys()):
#                 if currency != 'XRP' and currency not in current_currencies:
#                     del self.balances[currency]
#
#             self.min_profit_xrp = new_config['min_profit_xrp']
#             self.buy_discount = new_config['buy_discount']
#             self.sell_premium = new_config['sell_premium']
#
#             # Update the parsed config object
#             current_config['meme_coins'] = new_config['meme_coins']
#             current_config['settings']['min_profit_xrp'] = new_config['min_profit_xrp']
#             current_config['settings']['buy_discount'] = new_config['buy_discount']
#             current_config['settings']['sell_premium'] = new_config['sell_premium']
#
#             # Build the config file content
#             config_content = [
#                 "meme_coins:\n"
#             ]
#             for meme in new_config['meme_coins']:
#                 config_content.append(f"  - currency: {meme['currency']}\n")
#                 config_content.append(f"    issuer: {meme['issuer']}\n")
#                 config_content.append(f"    trade_amount: {meme['trade_amount']}\n")
#             for meme in removed_meme_coins:
#                 config_content.append(f"  # - currency: {meme['currency']}\n")
#                 config_content.append(f"  #   issuer: {meme['issuer']}\n")
#                 config_content.append(f"  #   trade_amount: {meme['trade_amount']}\n")
#
#             config_content.append("settings:\n")
#             for key, value in current_config['settings'].items():
#                 if key in ['min_profit_xrp', 'buy_discount', 'sell_premium']:
#                     if key == 'min_profit_xrp':
#                         config_content.append(f"  {key}: {value:.6f}\n")
#                     else:
#                         config_content.append(f"  {key}: {value}\n")
#                 else:
#                     if key == 'check_interval':
#                         config_content.append(f"  {key}: {value} # seconds to sleep the main bot\n")
#                     elif key == 'trade_amount':
#                         config_content.append(f"  {key}: {value}  # Amount of meme coin to trade\n")
#                     elif key == 'stop_loss':
#                         config_content.append(
#                             f"  {key}: {value} # Triggers when the net loss reaches 2% of the XRP spent.\n")
#                     else:
#                         config_content.append(f"  {key}: {value}\n")
#
#             config_content.append("wallet:\n")
#             for key, value in current_config['wallet'].items():
#                 config_content.append(f"  {key}: {value}\n")
#
#             # Dynamically construct the logging section
#             logging_config = current_config['logging']
#             config_content.append("\nlogging:\n")
#             config_content.append(f"  version: {logging_config['version']}\n")
#             config_content.append(
#                 f"  disable_existing_loggers: {str(logging_config['disable_existing_loggers']).lower()}\n")
#
#             config_content.append("  formatters:\n")
#             for formatter_name, formatter_details in logging_config['formatters'].items():
#                 config_content.append(f"    {formatter_name}:\n")
#                 config_content.append(f"      format: \"{formatter_details['format']}\"\n")
#                 config_content.append(f"      style: \"{formatter_details['style']}\"\n")
#
#             config_content.append("  handlers:\n")
#             for handler_name, handler_details in logging_config['handlers'].items():
#                 config_content.append(f"    {handler_name}:\n")
#                 for key, value in handler_details.items():
#                     if key == 'filename':
#                         config_content.append(f"      {key}: \"{value}\"  # Relative path; adjust as needed\n")
#                     else:
#                         config_content.append(f"      {key}: \"{value}\"\n")
#
#             config_content.append("  loggers:\n")
#             for logger_name, logger_details in logging_config['loggers'].items():
#                 if logger_name == 'httpx':
#                     config_content.append(f"    {logger_name}: # Add this to silence httpx logs\n")
#                 else:
#                     config_content.append(f"    {logger_name}:\n")
#                 if logger_name == 'xrpl_trading_bot' and 'handlers' in logger_details:
#                     handlers_str = '["' + '", "'.join(logger_details['handlers']) + '"]'
#                     config_content.append(
#                         f"      handlers: {handlers_str}  # Add \"console\" if you want console output\n")
#                 elif 'handlers' in logger_details:
#                     handlers_str = '[ ]' if not logger_details['handlers'] else '["' + '", "'.join(
#                         logger_details['handlers']) + '"]'
#                     config_content.append(
#                         f"      handlers: {handlers_str}  # No handlers; effectively silences it unless propagated\n")
#                 for key, value in logger_details.items():
#                     if key != 'handlers':
#                         if key == 'level' and logger_name == 'httpx':
#                             config_content.append(f"      {key}: \"{value}\"  # Only log WARNING and above\n")
#                         elif key == 'propagate' and logger_name == 'httpx':
#                             config_content.append(
#                                 f"      {key}: {str(value).lower()}  # Prevent propagation to root logger\n")
#                         else:
#                             config_content.append(f"      {key}: \"{value}\"\n" if isinstance(value,
#                                                                                               str) else f"      {key}: {str(value).lower()}\n")
#
#             # Write the updated config back to the file
#             with open("config/trading_bot_config.yaml", 'w') as f:
#                 f.writelines(config_content)
#
#             self.config = current_config  # Update the bot's config object
#             logger.info(f"Configuration updated and saved to file: {new_config}")
#
#             if new_config['remove_trust_line'] and new_config['remove_trust_line'] == 'true':
#                 for meme in removed_meme_coins:
#                     if await self.remove_trust_line(meme['currency'], meme['issuer']):
#                         logger.info("Trust line removed")
#                     else:
#                         logger.error("Trust line removal failed")
#
#             return {'status': 'success', 'message': 'Configuration updated successfully'}
#         except Exception as e:
#             logger.error(f"Update config error: {str(e)}")
#             self.metrics['runtime_errors'] += 1
#             return {'status': 'error', 'message': str(e)}
#         finally:
#             log_leaving_function('update_config', start_time, logger)
#
#     async def load_wallet(self):
#         start_time = time.time()
#         logger.info(ENTERING_FUNCTION_LOG.format('load_wallet'))
#         try:
#             wallet_secret = self.config['wallet']['xaman_seed']
#             wallet = Wallet.from_seed(wallet_secret)
#             if wallet.classic_address != self.config['wallet']['xaman_address']:
#                 raise ValueError("Seed does not match Xaman wallet address")
#             logger.info(f"Wallet loaded: {wallet.classic_address}")
#             return wallet
#         except Exception as e:
#             logger.error(f"Wallet load error: {str(e)}")
#             self.metrics['runtime_errors'] += 1
#             raise
#         finally:
#             log_leaving_function('load_wallet', start_time, logger)
#
#     async def get_current_fee(self):
#         start_time = time.time()
#         logger.info(ENTERING_FUNCTION_LOG.format('get_current_fee'))
#         try:
#             async with self.request_semaphore:
#                 fee_response = await self.client.request(Fee())
#                 return max(int(fee_response.result["drops"]["median_fee"]) / 1000000, 0.000010)
#         except Exception as e:
#             logger.error(f"Getting network fee error: {str(e)}")
#             self.metrics['runtime_errors'] += 1
#             await send_alert(self, "Error getting current network fee. The Bot is toast", logger)
#             raise
#         finally:
#             log_leaving_function('get_current_fee', start_time, logger)
#
#     async def check_trust_line(self, currency, issuer):
#         start_time = time.time()
#         logger.info(ENTERING_FUNCTION_LOG.format('check_trust_line'))
#         request_id = f"check_trust_line_{self.request_counter}"
#         self.active_requests.add(request_id)
#         self.request_counter += 1
#         try:
#             async with self.request_semaphore:
#                 account_lines_response = await self.client.request(prepare_account_lines(self.wallet.classic_address, "validated"))
#
#             for line in account_lines_response.result.get("lines", []):
#                 if line["currency"] == currency and line["account"] == issuer:
#                     print(f"Trust Line Found - Currency: {line['currency']}, Issuer: {line['account']}")
#                     print(f"Limit: {line['limit']} {currency}")
#                     print(f"Balance: {line['balance']} {currency}")
#                     return True
#
#             logger.info(f"No {currency} trust line to issuer {issuer} found.")
#             logger.info("Setting trust line...")
#             bot_wallet = Wallet.from_seed(self.config['wallet']['xaman_seed'])
#             trust_line_request = prepare_trust_set(self.wallet.classic_address, currency, issuer, str(self.trust_line_max))
#             trust_line_response = await autofill_and_sign(trust_line_request, self.client, bot_wallet)
#             submit_result = await submit(trust_line_response, self.client)
#             logger.info(f"Trust line set result: {submit_result.result}")
#
#             if submit_result.result["engine_result"] == "tesSUCCESS":
#                 logger.info("Trust line set successful")
#             else:
#                 logger.info("Trust line set failed")
#         except Exception as e:
#             logger.error(f"Check trust line error: {str(e)}")
#             self.metrics['runtime_errors'] += 1
#             await send_alert(self, "Error checking trust lines. The Bot is toast", logger)
#             raise
#         finally:
#             self.active_requests.remove(request_id)
#             log_leaving_function('check_trust_line', start_time, logger)
#
#     async def remove_trust_line(self, currency, issuer):
#         start_time = time.time()
#         logger.info(ENTERING_FUNCTION_LOG.format('remove_trust_line'))
#         request_id = f"remove_trust_line_{self.request_counter}"
#         self.active_requests.add(request_id)
#         self.request_counter += 1
#         try:
#             async with self.request_semaphore:
#                 account_lines_response = await self.client.request(prepare_account_lines(self.wallet.classic_address, "validated"))
#
#             trust_line_found = False
#             # Look for trust line to the issuer
#             for line in account_lines_response.result.get("lines", []):
#                 if line["currency"] == currency and line["account"] == issuer:
#                     print(f"Trust Line Found - Currency: {line['currency']}, Issuer: {line['account']}")
#                     print(f"Limit: {line['limit']} {currency}")
#                     print(f"Balance: {line['balance']} {currency}")
#                     trust_line_found = True
#                     break
#
#             if not trust_line_found:
#                 logger.info(f"No {currency} trust line to issuer {issuer} found.")
#                 return False
#
#             logger.info("Removing trust line...")
#             bot_wallet = Wallet.from_seed(self.config['wallet']['xaman_seed'])
#             trust_line_request = prepare_remove_trust_set(self.config['wallet']['xaman_address'], currency, issuer)
#             trust_line_response = await autofill_and_sign(trust_line_request, self.client, bot_wallet)
#             submit_result = await submit(trust_line_response, self.client)
#             logger.info(f"Trust line removed result: {submit_result.result}")
#
#             if submit_result.result["engine_result"] == "tesSUCCESS":
#                 logger.info(f"Trust line removed for {currency}")
#                 return True
#             logger.error(f"Trust line removal failed: {submit_result.result}")
#             return False
#         except Exception as e:
#             logger.error(f"Remove trust line error: {str(e)}")
#             self.metrics['runtime_errors'] += 1
#             await send_alert(self, "Error removing trust lines. The Bot is toast", logger)
#             raise
#         finally:
#             self.active_requests.remove(request_id)
#             log_leaving_function('remove_trust_line', start_time, logger)
#
#     async def get_balance(self, force_update: bool = False):
#         """Get balances, using cached version if recent unless forced"""
#
#         start_time = time.time()
#         logger.info(ENTERING_FUNCTION_LOG.format('get_balance'))
#
#         # If we have fresh data (≤10 sec old) and not forced, return cached
#         if not force_update and time.time() - self.last_balance_time < 10:
#             logger.info("Using cached balance")
#             return
#
#         request_id = f"get_balance_{self.request_counter}"
#         self.active_requests.add(request_id)
#         self.request_counter += 1
#         try:
#             async with self.request_semaphore:
#                 account_info = await self.client.request(prepare_account_info(self.wallet.classic_address,"validated"))
#             xrp_balance = int(account_info.result["account_data"]["Balance"]) / 1000000
#             self.owner_count = account_info.result["account_data"]["OwnerCount"]
#             reserve = self.base_reserve + self.owner_count * self.incremental_reserve
#             self.balances["XRP"] = xrp_balance - reserve
#
#             async with self.request_semaphore:
#                 lines = await self.client.request(prepare_account_lines(self.wallet.classic_address, "validated"))
#             logger.debug(f"AccountLines response: {lines.result}")
#
#             for currency in self.meme_coins:
#                 curr = currency['currency']
#                 issuer = currency['issuer']
#                 for line in lines.result.get("lines", []):
#                     if line["currency"] == curr and line["account"] == issuer:
#                         self.balances[curr] = float(line["balance"])
#                         break
#                 else:
#                     self.balances[curr] = 0.0
#             self.last_balance_time = time.time()
#             logger.info(f"Balances: XRP={self.balances['XRP']:.6f}, Reserve={reserve}")
#         except Exception as e:
#             logger.error(f"Get balance error: {str(e)}")
#             self.metrics['runtime_errors'] += 1
#             await send_alert(self, "Error getting balances. The Bot is toast", logger)
#             raise
#         finally:
#             self.active_requests.remove(request_id)
#             log_leaving_function('get_balance', start_time, logger)
#
#     async def cancel_unused_offers(self):
#         start_time = time.time()
#         logger.info(ENTERING_FUNCTION_LOG.format('cancel_unused_offers'))
#         request_id = f"cancel_unused_offers_{self.request_counter}"
#         self.active_requests.add(request_id)
#         self.request_counter += 1
#         try:
#             async with self.request_semaphore:
#                 response = await self.client.request(prepare_account_offers(self.wallet.classic_address, "validated"))
#             offers = response.result.get('offers', [])
#             if not offers:
#                 logger.info("No offers to cancel")
#                 return
#
#             max_retries = 3
#             for offer in offers[:10]:  # Batch limit
#                 for attempt in range(max_retries):
#                     try:
#                         tx = prepare_offer_cancel(self.wallet.classic_address, offer['seq'])
#                         # Increase timeout for the HTTP client
#                         async with httpx.AsyncClient(timeout=30.0) as custom_client:
#                             self.client._client = custom_client  # Temporarily override client
#                             signed_tx = await autofill_and_sign(tx, self.client, self.wallet)
#                             result = await submit(signed_tx, self.client)
#                             if result.result["engine_result"] == "tesSUCCESS":
#                                 logger.info(f"Cancelled offer {offer['seq']}")
#                                 break  # Success, move to next offer
#                     except httpx.ConnectTimeout as e:
#                         wait_time = 2 ** attempt  # Exponential backoff: 1s, 2s, 4s
#                         logger.warning(
#                             f"Timeout cancelling offer {offer['seq']} (attempt {attempt + 1}/{max_retries}): {str(e)}. Retrying in {wait_time}s")
#                         if attempt == max_retries - 1:
#                             logger.error(f"Failed to cancel offer {offer['seq']} after {max_retries} attempts")
#                             await send_alert(self, f"Failed to cancel offer {offer['seq']} after {max_retries} retries due to timeout", logger)
#                             break  # Give up after max retries
#                         await asyncio.sleep(wait_time)
#                     except Exception as e:
#                         logger.error(f"Unexpected error cancelling offer {offer['seq']}: {str(e)}")
#                         break  # Exit on non-timeout errors
#                 await asyncio.sleep(self.run_pause)  # Brief pause between cancellations
#         except Exception as e:
#             logger.error(f"Cancel offers error: {str(e)}")
#             self.metrics['runtime_errors'] += 1
#             await send_alert(self, "Error cancelling unused offers. The Bot is toast", logger)
#             raise
#         finally:
#             self.active_requests.remove(request_id)
#             log_leaving_function('cancel_unused_offers', start_time, logger)
#
#     # async def fetch_buy_offers(self, currency, issuer):
#     #     start_time = time.time()
#     #     function_name = 'fetch_buy_offers'
#     #     logger.info(ENTERING_FUNCTION_LOG.format(function_name))
#     #
#     #     request_id = f"{function_name}_{self.request_counter}"
#     #     self.active_requests.add(request_id)
#     #     self.request_counter += 1
#     #
#     #     max_retries = self.buy_sell_offers_retry
#     #     limit = self.buy_sell_offers_limit
#     #
#     #     try:
#     #         for attempt in range(self.buy_sell_offers_retry):
#     #             try:
#     #                 async with self.request_semaphore:
#     #                     async with httpx.AsyncClient(timeout=30.0) as custom_client:
#     #                         self.client._client = custom_client  # Temporarily override client
#     #                         response = await self.client.request(
#     #                             prepare_buy_offer_generic_object("book_offers", currency, issuer, limit)
#     #                         )
#     #                         return response  # Success, exit with result
#     #             except httpx.ConnectTimeout as e:
#     #                 wait_time = 2 ** attempt  # Exponential backoff: 1s, 2s, 4s
#     #                 logger.warning(f"Timeout fetching buy offers for {currency} issuer {issuer} (attempt {attempt + 1}/{max_retries}): {str(e)}. Retrying in {wait_time}s")
#     #                 if attempt == max_retries - 1:
#     #                     logger.error(f"Failed to fetch buy offers for {currency} after {max_retries} attempts")
#     #                     await send_alert(self,f"Failed to fetch buy offers for {currency} after {max_retries} retries due to timeout", logger)
#     #                     return None  # Final failure, return None
#     #                 await asyncio.sleep(wait_time)
#     #             except Exception as e:
#     #                 logger.error(f"Unexpected error fetching buy offers for {currency} issuer {issuer}: {str(e)}")
#     #                 self.metrics['runtime_errors'] += 1
#     #                 await send_alert(self, f"Error fetching buy offers for {currency}: {str(e)}. The Bot is toast", logger)
#     #                 raise  # Non-timeout errors are fatal, re-raise
#     #     finally:
#     #         self.active_requests.remove(request_id)
#     #         log_leaving_function(function_name, start_time, logger)
#
#     async def fetch_buy_offers(self, currency, issuer):
#         start_time = time.time()
#         function_name = 'fetch_buy_offers'
#         logger.info(ENTERING_FUNCTION_LOG.format(function_name))
#
#         # Assign a unique request ID
#         self.request_counter += 1
#         request_id = f"{function_name}_{self.request_counter}"
#         self.active_requests.add(request_id)
#
#         try:
#             for _ in range(self.buy_sell_offers_retry):
#                 async with self.request_semaphore:
#                     return await self.client.request(prepare_buy_offer_generic_object("book_offers", currency, issuer, self.buy_sell_offers_limit))
#         except httpx.ConnectTimeout as e:
#             logger.error(f"Connection timeout fetching buy offers for {currency} issuer {issuer}: {str(e)}")
#             return None  # Return None to indicate failure without crashing
#         except Exception as e:
#             logger.error(f"Error fetching buy offers for {currency} issuer {issuer}: {str(e)}")
#             self.metrics['runtime_errors'] += 1
#             await send_alert(self, "Error fetching buy offers. The Bot is toast", logger)
#             raise
#         finally:
#             # Remove the request from tracking once it completes
#             self.active_requests.remove(request_id)
#             log_leaving_function(function_name, start_time, logger)
#
#     # async def fetch_sell_offers(self, currency, issuer):
#     #     start_time = time.time()
#     #     function_name = 'fetch_sell_offers'
#     #     logger.info(ENTERING_FUNCTION_LOG.format(function_name))
#     #
#     #     request_id = f"{function_name}_{self.request_counter}"
#     #     self.active_requests.add(request_id)
#     #     self.request_counter += 1
#     #
#     #     max_retries = self.buy_sell_offers_retry
#     #     limit = self.buy_sell_offers_limit
#     #
#     #     try:
#     #         for attempt in range(max_retries):
#     #             try:
#     #                 async with self.request_semaphore:
#     #                     async with httpx.AsyncClient(timeout=30.0) as custom_client:
#     #                         self.client._client = custom_client  # Temporarily override client
#     #                         response = await self.client.request(
#     #                             prepare_fetch_sell_offer_generic_object("book_offers", currency, issuer, limit)
#     #                         )
#     #                         return response  # Success, exit with result
#     #             except httpx.ConnectTimeout as e:
#     #                 wait_time = 2 ** attempt  # Exponential backoff: 1s, 2s, 4s
#     #                 logger.warning(f"Timeout fetching sell offers for {currency} issuer {issuer} (attempt {attempt + 1}/{max_retries}): {str(e)}. Retrying in {wait_time}s")
#     #                 if attempt == max_retries - 1:
#     #                     logger.error(f"Failed to fetch sell offers for {currency} after {max_retries} attempts")
#     #                     await send_alert(self,f"Failed to fetch sell offers for {currency} after {max_retries} retries due to timeout",logger)
#     #                     return None  # Final failure, return None
#     #                 await asyncio.sleep(wait_time)
#     #             except Exception as e:
#     #                 logger.error(f"Unexpected error fetching sell offers for {currency} issuer {issuer}: {str(e)}")
#     #                 self.metrics['runtime_errors'] += 1
#     #                 await send_alert(self, f"Error fetching sell offers for {currency}: {str(e)}. The Bot is toast", logger)
#     #                 raise  # Non-timeout errors are fatal, re-raise
#     #     finally:
#     #         self.active_requests.remove(request_id)
#     #         log_leaving_function(function_name, start_time, logger)
#
#     async def fetch_sell_offers(self, currency, issuer):
#         start_time = time.time()
#         function_name = 'fetch_sell_offers'
#         logger.info(ENTERING_FUNCTION_LOG.format(function_name))
#
#         # Assign a unique request ID
#         self.request_counter += 1
#         request_id = f"{function_name}_{self.request_counter}"
#         self.active_requests.add(request_id)
#
#         try:
#             for _ in range(self.buy_sell_offers_retry):
#                 async with self.request_semaphore:
#                     return await self.client.request(prepare_fetch_sell_offer_generic_object("book_offers", currency, issuer, self.buy_sell_offers_limit))
#         except httpx.ConnectTimeout as e:
#             logger.error(f"Connection timeout fetching sell offers for {currency}: {str(e)}")
#             return None  # Return None to indicate failure without crashing
#         except Exception as e:
#             logger.error(f"Error fetching sell offers for {currency}: {str(e)}")
#             self.metrics['runtime_errors'] += 1
#             await send_alert(self, "Error fetching sell offers. The Bot is toast", logger)
#             raise
#         finally:
#             # Remove the request from tracking once it completes
#             self.active_requests.remove(request_id)
#             log_leaving_function(function_name, start_time, logger)
#
#     async def find_arbitrage(self, currency, issuer):
#         start_time = time.time()
#         logger.info(ENTERING_FUNCTION_LOG.format('find_arbitrage'))
#         request_id = f"find_arbitrage_{self.request_counter}"
#         self.active_requests.add(request_id)
#         self.request_counter += 1
#         try:
#             await self.get_balance(force_update=True)
#
#             trade_amount = next((meme['trade_amount'] for meme in self.meme_coins if meme['currency'] == currency), self.default_trade_amount)
#             reserve = self.base_reserve + self.owner_count * self.incremental_reserve
#
#             if self.balances["XRP"] < (reserve + 0.01) or self.balances[currency] < trade_amount:
#             # if self.balances["XRP"] < (reserve + (await self.get_current_fee() * 2) + 0.01):
#                 logger.info(f"Insufficient funds for {currency}: XRP={self.balances['XRP']:.6f}, {currency}={self.balances[currency]}")
#                 return False, 0, 0, None, None, None, None
#
#             buy_task, sell_task = await asyncio.gather(
#                 self.fetch_buy_offers(currency, issuer),
#                 self.fetch_sell_offers(currency, issuer)
#             )
#
#             buy_offers = buy_task.result.get("offers", []) if buy_task else []
#             sell_offers = sell_task.result.get("offers", []) if sell_task else []
#             print(f"\traw buy offer: {buy_offers}")
#             logger.debug(f"raw buy offer: {buy_offers}")
#             print(f"\traw sell offer: {sell_offers}")
#             logger.debug(f"\traw sell offer: {sell_offers}")
#
#             if not buy_offers or not sell_offers:
#                 logger.info(f"No offers available or fetch failed for {currency}")
#                 print(f"\tInsufficient offers for arbitrage for {currency}")
#                 return False, 0, 0, None, None, None, None
#
#             best_buy_offer = max(buy_offers, key=lambda o: float(o["TakerGets"]) / float(o["TakerPays"]["value"]))
#             market_sell_price = float(best_buy_offer["TakerGets"]) / float(best_buy_offer["TakerPays"]["value"]) / 1000000
#             best_sell_offer = min(sell_offers, key=lambda o: float(o["TakerPays"]) / float(o["TakerGets"]["value"]))
#             market_buy_price = float(best_sell_offer["TakerPays"]) / float(best_sell_offer["TakerGets"]["value"]) / 1000000
#             trade_amount = min(trade_amount, float(best_sell_offer["TakerGets"]["value"]), float(best_buy_offer["TakerPays"]["value"]))
#
#             config_buy_price = market_buy_price * self.buy_discount
#             config_sell_price = market_sell_price * self.sell_premium
#             config_profit = (config_sell_price - config_buy_price) * trade_amount - 0.000020
#
#             if config_profit > self.min_profit_xrp:
#                 print(f"\tConfig pricing: Buy: {config_buy_price:.10f}, Sell: {config_sell_price:.10f}, Profit: {config_profit:.10f} XRP")
#                 logger.info(f"Config pricing: Buy: {config_buy_price:.10f}, Sell: {config_sell_price:.10f}, Profit: {config_profit:.10f} XRP")
#                 logger.info(f"{'*' * 60} Trading opportunity found! Potential profit: {config_profit:.10f} {'*' * 60}")
#                 print(f"{'*' * 30} Trading opportunity found! Potential profit: {config_profit:.10f} {'*' * 30}")
#                 return True, config_buy_price, config_sell_price, config_profit, market_buy_price, best_buy_offer, best_sell_offer
#
#             spread = market_sell_price - market_buy_price
#             min_required_spread = (0.000020 / trade_amount) + (market_buy_price * (1 - self.buy_discount)) + (market_sell_price * (self.sell_premium - 1))
#
#             if spread < min_required_spread:
#                 dynamic_buy_discount = max(self.buy_discount, min(0.99, 1 - spread / market_buy_price * 1.5))
#                 dynamic_sell_premium = min(1.10, max(self.sell_premium, 1 + spread / market_sell_price * 2))
#                 discounted_buy_price = market_buy_price * dynamic_buy_discount
#                 sell_price = market_sell_price * dynamic_sell_premium
#             else:
#                 discounted_buy_price = config_buy_price
#                 sell_price = config_sell_price
#
#             # fee = await self.get_current_fee() * 2  # Two transactions
#             # logger.info(f"XRP fee: {fee}")
#             # profit = (sell_price - discounted_buy_price) * trade_amount - fee
#             profit = (sell_price - discounted_buy_price) * trade_amount - 0.000020
#
#             print(f"\tBest buy price: {discounted_buy_price:.10f}, Best sell price: {sell_price:.10f}")
#             print(f"\tProfit: {profit:.10f} XRP")
#
#             if profit > self.min_profit_xrp:
#                 logger.info(f"{'*' * 60} Trading opportunity found! Potential profit: {profit:.10f} {'*' * 60}")
#                 print(f"{'*' * 30} Trading opportunity found! Potential profit: {profit:.10f} {'*' * 30}")
#                 return True, discounted_buy_price, sell_price, profit, market_buy_price, best_buy_offer, best_sell_offer
#             else:
#                 print(f"\tNo profitable opportunity (min profit needed: {self.min_profit_xrp} XRP)")
#                 return False, 0, 0, None, None, None, None
#         except Exception as e:
#             logger.error(f"Find arbitrage error for {currency}: {str(e)}")
#             self.metrics['trade_errors'] += 1
#             await send_alert(self, "Error finding arbitrage. The Bot is toast", logger)
#             raise
#         finally:
#             self.active_requests.remove(request_id)
#             log_leaving_function('find_arbitrage', start_time, logger)
#
#     # async def execute_trade(self, discounted_buy_price, sell_price, profit, buy_price, sell_offer, buy_offer=None,
#     #                         currency=None, issuer=None):
#     #     start_time = time.time()
#     #     logger.info(ENTERING_FUNCTION_LOG.format('execute_trade'))
#     #     request_id = f"execute_trade_{self.request_counter}"
#     #     self.active_requests.add(request_id)
#     #     self.request_counter += 1
#     #     max_retries = self.buy_sell_offers_retry
#     #
#     #     try:
#     #         # Pre-trade checks
#     #         if self.owner_count >= self.owner_count_limit:
#     #             logger.info(
#     #                 f"Skipping trade for {currency}: OwnerCount {self.owner_count} exceeds limit of {self.owner_count_limit}")
#     #             return
#     #
#     #         if abs(discounted_buy_price - buy_price) / buy_price > self.slippage_tolerance:
#     #             logger.warning(f"Excessive slippage on buy: {discounted_buy_price} vs {buy_price}")
#     #             return
#     #
#     #         # Log pre-trade state
#     #         logger.info(
#     #             f"Executing trade - Pre-trade XRP={self.balances['XRP']:.6f}, {currency}={self.balances[currency]:.2f}")
#     #         print(f"\tPre-trade XRP: {self.balances['XRP']:.6f}, {currency}={self.balances[currency]:.2f}")
#     #
#     #         buy_amount = float(buy_offer["TakerGets"]["value"])
#     #         trade_amount = min(buy_amount,
#     #                            next((meme['trade_amount'] for meme in self.meme_coins if meme['currency'] == currency),
#     #                                 self.default_trade_amount))
#     #         buy_amount_xrp = discounted_buy_price * trade_amount
#     #
#     #         expected_owner_count = self.owner_count
#     #         self.pre_trade_balances = {curr['currency']: self.balances[curr['currency']] for curr in self.meme_coins}
#     #         self.pre_trade_balances['XRP'] = self.balances['XRP']
#     #
#     #         print(f"\ttrade amount: {trade_amount} buy amount: {buy_amount}")
#     #         print(f"\tbuy_amount_xrp: {buy_amount_xrp:.10f}")
#     #         print(f"\tpre trade balances: {self.pre_trade_balances}")
#     #         print(f"\texpected owner count: {expected_owner_count}")
#     #
#     #         # Buy transaction with retry logic
#     #         buy_result = None
#     #         async with self.tx_semaphore:
#     #             for attempt in range(max_retries):
#     #                 try:
#     #                     tx_buy = prepare_offer_create_get_xrp(self.wallet.classic_address,
#     #                                                           str(int(buy_amount_xrp * 1000000)), currency, issuer,
#     #                                                           str(trade_amount))
#     #                     async with httpx.AsyncClient(timeout=30.0) as custom_client:
#     #                         self.client._client = custom_client
#     #                         buy_result = await submit_and_wait(tx_buy, self.client, self.wallet)
#     #                     # Check meta.TransactionResult instead of engine_result
#     #                     if buy_result.result['meta']['TransactionResult'] == "tesSUCCESS":
#     #                         tx_hash = buy_result.result['hash']
#     #                         if await confirm_transaction(self, tx_hash, logger):
#     #                             logger.info(f"Buy transaction validated: {tx_hash}")
#     #                             break
#     #                     else:
#     #                         raise Exception(
#     #                             f"Buy submission failed: {buy_result.result['meta']['TransactionResult']} - {buy_result.result.get('engine_result_message', 'No message')}")
#     #                 except httpx.ConnectTimeout as e:
#     #                     wait_time = 2 ** attempt
#     #                     logger.warning(f"Buy attempt {attempt + 1}/{max_retries} timed out for {currency}: {str(e)}. Retrying in {wait_time}s")
#     #                     if attempt == max_retries - 1:
#     #                         logger.error(f"Buy failed for {currency} after {max_retries} retries due to timeout")
#     #                         await send_alert(self, f"Buy failed for {currency} after {max_retries} retries due to timeout", logger)
#     #                         return
#     #                     await asyncio.sleep(wait_time)
#     #                 except Exception as e:
#     #                     logger.error(f"Buy attempt {attempt + 1}/{max_retries} failed for {currency}: {str(e)}")
#     #                     if "tec" in str(e).upper() or "sequence" not in str(e).lower():  # Non-retryable error
#     #                         raise
#     #                     wait_time = 2 ** attempt
#     #                     logger.warning(f"Retryable error on buy attempt {attempt + 1}/{max_retries}: {str(e)}. Retrying in {wait_time}s")
#     #                     if attempt == max_retries - 1:
#     #                         logger.error(f"Buy failed for {currency} after {max_retries} retries: {str(e)}")
#     #                         await send_alert(self, f"Buy failed for {currency} after {max_retries} retries: {str(e)}", logger)
#     #                         return
#     #                     await asyncio.sleep(wait_time)
#     #
#     #         if not buy_result or buy_result.result['meta']['TransactionResult'] != "tesSUCCESS":
#     #             raise Exception(
#     #                 f"Buy failed for {currency}: {buy_result.result['meta']['TransactionResult'] if buy_result else 'No result'}")
#     #
#     #         logger.debug(f"Buy result: {buy_result.result}")
#     #         print(f"\tBuy result: {buy_result.result}")
#     #
#     #         self.metrics["buy_trades_executed"] += 1
#     #         self.total_xrp_spent += buy_amount_xrp
#     #         logger.info(f"Buy confirmed for {currency}, Total XRP spent: {self.total_xrp_spent:.6f}")
#     #         store_trade(self, logger, trade_type='buy', currency=currency, price=discounted_buy_price,
#     #                     amount=trade_amount, xrp_amount=buy_amount_xrp, tx_hash=buy_result.result['hash'],
#     #                     status=buy_result.result['meta']['TransactionResult'])
#     #         self.trade_history.append({
#     #             'type': 'buy', 'currency': currency, 'price': discounted_buy_price, 'amount': trade_amount,
#     #             'xrp_spent': buy_amount_xrp, 'timestamp': time.strftime('%Y-%m-%d %H:%M:%S'),
#     #             'status': buy_result.result['meta']['TransactionResult']
#     #         })
#     #
#     #         await asyncio.sleep(self.run_pause)
#     #
#     #         # Sell transaction with retry logic
#     #         market_sell_price = float(sell_offer["TakerGets"]) / float(sell_offer["TakerPays"]["value"]) / 1000000
#     #         sell_price = market_sell_price * self.sell_premium
#     #         sell_amount_xrp = sell_price * trade_amount
#     #
#     #         prelim_result = None
#     #         async with self.tx_semaphore:
#     #             for attempt in range(max_retries):
#     #                 try:
#     #                     tx_sell = prepare_offer_create_get_meme(self.wallet.classic_address, currency, issuer,
#     #                                                             str(trade_amount), str(int(sell_amount_xrp * 1000000)))
#     #                     async with httpx.AsyncClient(timeout=30.0) as custom_client:
#     #                         self.client._client = custom_client
#     #                         prelim_result = await submit_and_wait(tx_sell, self.client, self.wallet)
#     #                     if prelim_result.result['meta']['TransactionResult'] == "tesSUCCESS":
#     #                         tx_hash = prelim_result.result['hash']
#     #                         if await confirm_transaction(self, tx_hash, logger):
#     #                             logger.info(f"Sell transaction validated: {tx_hash}")
#     #                             break
#     #                     else:
#     #                         raise Exception(
#     #                             f"Sell submission failed: {prelim_result.result['meta']['TransactionResult']} - {prelim_result.result.get('engine_result_message', 'No message')}")
#     #                 except httpx.ConnectTimeout as e:
#     #                     wait_time = 2 ** attempt
#     #                     logger.warning(
#     #                         f"Sell attempt {attempt + 1}/{max_retries} timed out for {currency}: {str(e)}. Retrying in {wait_time}s")
#     #                     if attempt == max_retries - 1:
#     #                         logger.error(f"Sell failed for {currency} after {max_retries} retries due to timeout")
#     #                         await send_alert(self,
#     #                                          f"Sell failed for {currency} after {max_retries} retries due to timeout",
#     #                                          logger)
#     #                         await self.cancel_unused_offers()
#     #                         return
#     #                     await asyncio.sleep(wait_time)
#     #                 except Exception as e:
#     #                     logger.error(f"Sell attempt {attempt + 1}/{max_retries} failed for {currency}: {str(e)}")
#     #                     if "tec" in str(e).upper() or "sequence" not in str(e).lower():
#     #                         raise
#     #                     wait_time = 2 ** attempt
#     #                     logger.warning(
#     #                         f"Retryable error on sell attempt {attempt + 1}/{max_retries}: {str(e)}. Retrying in {wait_time}s")
#     #                     if attempt == max_retries - 1:
#     #                         logger.error(f"Sell failed for {currency} after {max_retries} retries: {str(e)}")
#     #                         await send_alert(self, f"Sell failed for {currency} after {max_retries} retries: {str(e)}",
#     #                                          logger)
#     #                         await self.cancel_unused_offers()
#     #                         return
#     #                     await asyncio.sleep(wait_time)
#     #
#     #         if not prelim_result or prelim_result.result['meta']['TransactionResult'] != "tesSUCCESS":
#     #             await self.cancel_unused_offers()
#     #             raise Exception(
#     #                 f"Sell failed for {currency}: {prelim_result.result['meta']['TransactionResult'] if prelim_result else 'No result'}")
#     #
#     #         logger.debug(f"Sell result: {prelim_result.result}")
#     #         print(f"\tSell result: {prelim_result.result}")
#     #
#     #         self.metrics["sell_trades_executed"] += 1
#     #         self.total_xrp_received += sell_amount_xrp
#     #         logger.info(f"Sell confirmed for {currency}, Total XRP received: {self.total_xrp_received:.6f}")
#     #         store_trade(self, logger, trade_type='sell', currency=currency, price=sell_price, amount=trade_amount,
#     #                     xrp_amount=sell_amount_xrp, tx_hash=prelim_result.result['hash'],
#     #                     status=prelim_result.result['meta']['TransactionResult'])
#     #         self.trade_history.append({
#     #             'type': 'sell', 'currency': currency, 'price': sell_price, 'amount': trade_amount,
#     #             'xrp_received': sell_amount_xrp, 'timestamp': time.strftime('%Y-%m-%d %H:%M:%S'),
#     #             'status': prelim_result.result['meta']['TransactionResult']
#     #         })
#     #
#     #         await asyncio.sleep(self.run_pause)
#     #
#     #         # Check if sell offer was consumed
#     #         sell_consumed = False
#     #         for _ in range(3):
#     #             offers_response = await self.client.request(
#     #                 prepare_account_offers(self.wallet.classic_address, "validated"))
#     #             offers = offers_response.result.get('offers', [])
#     #             if not any(o['seq'] == prelim_result.result['tx_json']['Sequence'] for o in offers):
#     #                 logger.info("Sell offer consumed")
#     #                 print("\tSell offer consumed")
#     #                 sell_consumed = True
#     #                 break
#     #             print("\tLooping again....")
#     #             await asyncio.sleep(self.run_pause)
#     #
#     #         if not sell_consumed:
#     #             market_sell_price = float(sell_offer["TakerGets"]) / float(sell_offer["TakerPays"]["value"]) / 1000000
#     #             logger.info(
#     #                 f"Sell offer {prelim_result.result['tx_json']['Sequence']} not consumed, adjusting price to {market_sell_price:.10f}")
#     #             print(
#     #                 f"\tSell offer {prelim_result.result['tx_json']['Sequence']} not consumed, adjusting price to {market_sell_price:.10f}")
#     #
#     #             async with self.tx_semaphore:
#     #                 tx_cancel = prepare_offer_cancel(self.wallet.classic_address,
#     #                                                  prelim_result.result['tx_json']['Sequence'])
#     #                 cancel_result = await submit_and_wait(tx_cancel, self.client, self.wallet)
#     #                 logger.info(
#     #                     f"Cancelled unconsumed sell offer {prelim_result.result['tx_json']['Sequence']}: {cancel_result.result}")
#     #                 print(
#     #                     f"\tCancelled unconsumed sell offer {prelim_result.result['tx_json']['Sequence']}: {cancel_result.result}")
#     #
#     #             sell_amount_xrp = market_sell_price * trade_amount
#     #             async with self.tx_semaphore:
#     #                 for attempt in range(max_retries):
#     #                     try:
#     #                         tx_sell_retry = prepare_offer_create_get_meme(self.wallet.classic_address, currency, issuer,
#     #                                                                       str(trade_amount),
#     #                                                                       str(int(sell_amount_xrp * 1000000)))
#     #                         async with httpx.AsyncClient(timeout=30.0) as custom_client:
#     #                             self.client._client = custom_client
#     #                             retry_result = await submit_and_wait(tx_sell_retry, self.client, self.wallet)
#     #                         if retry_result.result["engine_result"] == "tesSUCCESS" and await confirm_transaction(self, retry_result.result['hash'], logger):
#     #                             self.metrics["sell_trades_executed"] += 1
#     #                             sell_consumed = True
#     #                             store_trade(self, logger, trade_type='sell', currency=currency, price=market_sell_price,
#     #                                         amount=trade_amount, xrp_amount=sell_amount_xrp,
#     #                                         tx_hash=retry_result.result['tx_json']['hash'],
#     #                                         status=retry_result.result["engine_result"])
#     #                             break
#     #                     except Exception as e:
#     #                         wait_time = 2 ** attempt
#     #                         logger.warning(
#     #                             f"Sell retry attempt {attempt + 1}/{max_retries} failed: {str(e)}. Retrying in {wait_time}s")
#     #                         if attempt == max_retries - 1:
#     #                             logger.error(f"Sell retry failed after {max_retries} attempts: {str(e)}")
#     #                             raise Exception("Retry sell failed")
#     #                         await asyncio.sleep(wait_time)
#     #
#     #         print(f"\tsell_consumed: {sell_consumed}")
#     #
#     #         if self.owner_count > self.owner_count_limit:
#     #             await self.cancel_unused_offers()
#     #
#     #         fee_per_tx = await self.get_current_fee()
#     #         if sell_consumed:
#     #             realized_profit = round(sell_amount_xrp - buy_amount_xrp - (2 * fee_per_tx), 6)
#     #             update_trade(self, logger, realized_profit, currency)
#     #         else:
#     #             realized_profit = round(-buy_amount_xrp - (2 * fee_per_tx), 6)
#     #
#     #         logger.info(f"Reserve change: {(self.owner_count - expected_owner_count) * self.incremental_reserve}")
#     #         self.metrics["profit_xrp"] += realized_profit
#     #         logger.info(f"Trade completed: Profit={realized_profit:.6f} XRP")
#     #         print(f"\tTrade completed: Profit: {realized_profit:.6f} XRP UI XRP: {self.metrics['profit_xrp']}")
#     #     except Exception as e:
#     #         logger.error(f"Execute trade error: {str(e)}")
#     #         self.metrics['trade_errors'] += 1
#     #         await send_alert(self, "Error executing trades. The Bot is toast", logger)
#     #         raise
#     #     finally:
#     #         self.active_requests.remove(request_id)
#     #         log_leaving_function('execute_trade', start_time, logger)
#
#     async def execute_trade(self, discounted_buy_price, sell_price, profit, buy_price, sell_offer, buy_offer=None, currency=None, issuer=None):
#         start_time = time.time()
#         logger.info(ENTERING_FUNCTION_LOG.format('execute_trade'))
#         request_id = f"execute_trade_{self.request_counter}"
#         self.active_requests.add(request_id)
#         self.request_counter += 1
#         try:
#             if self.owner_count >= self.owner_count_limit:
#                 logger.info(
#                     f"Skipping trade for {currency}: OwnerCount {self.owner_count} exceeds limit of {self.owner_count_limit}")
#                 return
#
#             if abs(discounted_buy_price - buy_price) / buy_price > self.slippage_tolerance:
#                 logger.warning(f"Excessive slippage on buy: {discounted_buy_price} vs {buy_price}")
#                 return
#
#             logger.info(f"Executing trade - Pre-trade XRP={self.balances['XRP']:.6f}, {currency}={self.balances[currency]:.2f}")
#             print(f"\tPre-trade XRP: {self.balances['XRP']:.6f}, {currency}={self.balances[currency]:.2f}")
#
#             buy_amount = float(buy_offer["TakerGets"]["value"])
#             trade_amount = min(buy_amount, next((meme['trade_amount'] for meme in self.meme_coins if meme['currency'] == currency), self.default_trade_amount))
#             buy_amount_xrp = discounted_buy_price * trade_amount
#
#             expected_owner_count = self.owner_count
#             self.pre_trade_balances = {curr['currency']: self.balances[curr['currency']] for curr in self.meme_coins}
#             self.pre_trade_balances['XRP'] = self.balances['XRP']
#
#             print(f"\ttrade amount: {trade_amount} buy amount: {buy_amount}")
#             print(f"\tbuy_amount_xrp: {buy_amount_xrp:.10f}")
#             print(f"\tpre trade balances: {self.pre_trade_balances}")
#             print(f"\texpected owner count: {expected_owner_count}")
#
#             async with self.tx_semaphore:
#                 for attempt in range(self.buy_sell_offers_retry):
#                     try:
#                         tx_buy = prepare_offer_create_get_xrp(self.wallet.classic_address, str(int(buy_amount_xrp * 1000000)), currency, issuer, str(trade_amount))
#                         signed_tx_buy = await autofill_and_sign(tx_buy, self.client, self.wallet)
#                         buy_result = await submit(signed_tx_buy, self.client)
#                         if buy_result.result["engine_result"] == "tesSUCCESS":
#                             if buy_result.result['tx_json']['hash']:
#                                 tx_hash = buy_result.result['tx_json']['hash']
#                                 if await confirm_transaction(self, tx_hash, logger):
#                                     break
#                     except Exception as e:
#                         if "sequence" in str(e).lower():
#                             logger.warning(f"Sequence error on buy attempt {attempt + 1}: {e}. Retrying...")
#                             await asyncio.sleep(2 ** attempt)
#                         else:
#                             raise
#
#             logger.debug(f"Buy result: {buy_result.result}")
#             print(f"\tBuy result: {buy_result.result}")
#
#             if buy_result.result["engine_result"] == "tesSUCCESS":
#                 self.metrics["buy_trades_executed"] += 1
#                 self.total_xrp_spent += buy_amount_xrp
#                 logger.info(f"Buy confirmed for {currency}, Total XRP spent: {self.total_xrp_spent:.6f}")
#
#                 store_trade(self, logger,
#                     trade_type='buy',
#                     currency=currency,
#                     price=discounted_buy_price,
#                     amount=trade_amount,
#                     xrp_amount=buy_amount_xrp,
#                     tx_hash=buy_result.result['tx_json']['hash'],
#                     status=buy_result.result["engine_result"]
#                 )
#
#                 self.trade_history.append({
#                     'type': 'buy',
#                     'currency': currency,
#                     'price': discounted_buy_price,
#                     'amount': trade_amount,
#                     'xrp_spent': buy_amount_xrp,
#                     'timestamp': time.strftime('%Y-%m-%d %H:%M:%S'),
#                     'status': buy_result.result["engine_result"],
#                 })
#             else:
#                 raise Exception(f"Buy failed for {currency}: {buy_result.result['engine_result_message']}")
#
#             await asyncio.sleep(self.run_pause)
#             market_sell_price = float(sell_offer["TakerGets"]) / float(sell_offer["TakerPays"]["value"]) / 1000000
#             sell_price = market_sell_price * self.sell_premium
#             sell_amount_xrp = sell_price * trade_amount
#
#             async with self.tx_semaphore:
#                 for attempt in range(self.buy_sell_offers_retry):
#                     try:
#                         tx_sell = prepare_offer_create_get_meme(self.wallet.classic_address, currency, issuer, str(trade_amount), str(int(sell_amount_xrp * 1000000)))
#                         signed_tx_sell = await autofill_and_sign(tx_sell, self.client, self.wallet)
#                         logger.debug(f"Submitting sell tx: {signed_tx_sell.to_dict()}")
#                         print(f"\tSubmitting sell tx: {signed_tx_sell.to_dict()}")
#                         prelim_result = await submit(signed_tx_sell, self.client)
#                         # prelim_result = await submit_and_wait(tx_sell, self.client, self.wallet)
#                         if buy_result.result["engine_result"] == "tesSUCCESS":
#                             if buy_result.result['tx_json']['hash']:
#                                 tx_hash = buy_result.result['tx_json']['hash']
#                                 if await confirm_transaction(self, tx_hash, logger):
#                                     break
#                         # break
#                     except Exception as e:
#                         if "sequence" in str(e).lower():
#                             logger.warning(f"Sequence error on buy attempt {attempt + 1}: {e}. Retrying...")
#                             await asyncio.sleep(2 ** attempt)
#                         else:
#                             raise
#
#             if prelim_result.result["engine_result"] == "tesSUCCESS":
#                 self.metrics["sell_trades_executed"] += 1
#                 self.total_xrp_received += sell_amount_xrp
#                 logger.info(f"Sell confirmed for {currency}, Total XRP received: {self.total_xrp_received:.6f}")
#
#                 # Store preliminary sell trade (will update with profit later)
#                 store_trade(self, logger,
#                     trade_type='sell',
#                     currency=currency,
#                     price=sell_price,
#                     amount=trade_amount,
#                     xrp_amount=sell_amount_xrp,
#                     tx_hash=buy_result.result['tx_json']['hash'],
#                     status=prelim_result.result["engine_result"]
#                 )
#
#                 self.trade_history.append({
#                     'type': 'sell',
#                     'currency': currency,
#                     'price': sell_price,
#                     'amount': trade_amount,
#                     'xrp_received': sell_amount_xrp,
#                     'timestamp': time.strftime('%Y-%m-%d %H:%M:%S'),
#                     'status': prelim_result.result["engine_result"],
#                 })
#             else:
#                 await self.cancel_unused_offers()
#                 raise Exception(f"Sell failed for {currency}")
#
#             await asyncio.sleep(self.run_pause)
#
#             sell_consumed = False
#             for _ in range(3):
#                 offers_response = await self.client.request(
#                     prepare_account_offers(self.wallet.classic_address, "validated"))
#                 offers = offers_response.result.get('offers', [])
#                 if not any(o['seq'] == signed_tx_sell.sequence for o in offers):
#                     logger.info("Sell offer consumed")
#                     print("\tSell offer consumed")
#                     sell_consumed = True
#                     break
#                 print("\tLooping again....")
#                 await asyncio.sleep(self.run_pause)
#
#                 if not sell_consumed:
#                     market_sell_price = float(sell_offer["TakerGets"]) / float(
#                         sell_offer["TakerPays"]["value"]) / 1000000
#                     logger.info(
#                         f"Sell offer {signed_tx_sell.sequence} not consumed, adjusting price to {market_sell_price:.10f}")
#                     print(
#                         f"\tSell offer {signed_tx_sell.sequence} not consumed, adjusting price to {market_sell_price:.10f}")
#
#                     tx_cancel = prepare_offer_cancel(self.wallet.classic_address, signed_tx_sell.sequence)
#                     signed_tx_cancel = await autofill_and_sign(tx_cancel, self.client, self.wallet)
#                     cancel_result = await submit(signed_tx_cancel, self.client)
#
#                     logger.info(f"Cancelled unconsumed sell offer {signed_tx_sell.sequence}: {cancel_result.result}")
#                     print(f"\tCancelled unconsumed sell offer {signed_tx_sell.sequence}: {cancel_result.result}")
#
#                     for attempt in range(self.buy_sell_offers_retry):
#                         try:
#                             tx_sell_retry = prepare_offer_create_get_meme(self.wallet.classic_address, currency, issuer,str(trade_amount),str(int(sell_amount_xrp * 1000000)))
#                             signed_tx_sell_retry = await autofill_and_sign(tx_sell_retry, self.client, self.wallet)
#                             print(f"\tSubmitting retry sell tx at market price: {signed_tx_sell_retry.to_dict()}")
#                             retry_result = await submit(signed_tx_sell_retry, self.client)
#                             print(f"\tRetry sell result: {retry_result.result}")
#                             break
#                         except Exception as e:
#                             logger.error(f"Buy failed in prepare_offer_create_get_meme for {currency}: {e}")
#
#                     if retry_result.result["engine_result"] == "tesSUCCESS":
#                         self.metrics["sell_trades_executed"] += 1
#                         sell_consumed = True
#                         store_trade(self, logger,
#                             trade_type='sell',
#                             currency=currency,
#                             price=market_sell_price,
#                             amount=trade_amount,
#                             xrp_amount=sell_amount_xrp,
#                             tx_hash=retry_result.result['tx_json']['hash'],
#                             status=retry_result.result["engine_result"]
#                         )
#                     else:
#                         logger.warning("Retry sell failed, TST balance not re-adjusted")
#                         raise Exception("Retry sell failed")
#
#             print(f"\tsell_consumed: {sell_consumed}")
#
#             if self.owner_count > self.owner_count_limit:
#                 await self.cancel_unused_offers()
#
#             fee_per_tx = 0.000010
#             # fee_per_tx = await self.get_current_fee()
#             if sell_consumed:
#                 realized_profit = round(sell_amount_xrp - buy_amount_xrp - (2 * fee_per_tx), 6)
#                 update_trade(self, logger, realized_profit, currency)
#             else:
#                 realized_profit = round(-buy_amount_xrp - (2 * fee_per_tx), 6)
#
#             logger.info(f"Reserve change: {(self.owner_count - expected_owner_count) * self.incremental_reserve}")
#             self.metrics["profit_xrp"] += realized_profit
#             logger.info(f"Trade completed: Profit: {realized_profit:.6f} XRP UI XRP: {self.metrics['profit_xrp']}")
#             print(f"\tTrade completed: Profit: {realized_profit:.6f} XRP UI XRP: {self.metrics['profit_xrp']}")
#         except Exception as e:
#             logger.error(f"Execute trade error: {str(e)}")
#             self.metrics['trade_errors'] += 1
#             await send_alert(self, "Error executing trades. The Bot is toast", logger)
#             raise
#         finally:
#             self.active_requests.remove(request_id)
#             log_leaving_function('execute_trade', start_time, logger)
#
#     async def check_stop_loss(self):
#         start_time = time.time()
#         logger.info(ENTERING_FUNCTION_LOG.format('check_stop_loss'))
#         try:
#             """Check if the net loss exceeds the stop-loss threshold."""
#             if self.total_xrp_spent == 0:
#                 return False
#             await self.get_balance(force_update=True)
#             total_unrealized_value = 0
#             for meme in self.meme_coins:
#                 price = await self.get_current_market_price(meme['currency'], meme['issuer'])
#                 total_unrealized_value += self.balances[meme['currency']] * price
#             net_pnl = (self.total_xrp_received - self.total_xrp_spent) + total_unrealized_value
#             loss_percentage = net_pnl / self.total_xrp_spent if self.total_xrp_spent > 0 else 0
#
#             logger.info(f"Net PnL: {net_pnl:.6f} XRP, Loss %: {loss_percentage:.2%}, Threshold: {self.stop_loss}")
#             if loss_percentage <= self.stop_loss:
#                 for meme in self.meme_coins:
#                     await self.liquidate_position(meme['currency'], meme['issuer'])
#                 await send_alert(self, f"Stop-loss triggered: {net_pnl:.6f} XRP", logger)
#                 return True
#             return False
#         except Exception as e:
#             logger.error(f"Check stop loss error: {str(e)}")
#             self.metrics['runtime_errors'] += 1
#             await send_alert(self, "Error checking stop loss. The Bot is toast", logger)
#             raise
#         finally:
#             log_leaving_function('check_stop_loss', start_time, logger)
#
#     async def get_current_market_price(self, currency, issuer):
#         start_time = time.time()
#         logger.info(ENTERING_FUNCTION_LOG.format('get_current_market_price'))
#         try:
#             sell_offers_response = await self.fetch_sell_offers(currency, issuer)
#             sell_offers = sell_offers_response.result.get("offers", []) if sell_offers_response else []
#             if sell_offers:
#                 best_offer = min(sell_offers, key=lambda o: float(o["TakerPays"]) / float(o["TakerGets"]["value"]))
#                 price = float(best_offer["TakerPays"]) / float(best_offer["TakerGets"]["value"]) / 1000000
#                 self.last_known_price[currency] = price
#                 return price
#             return self.last_known_price.get(currency, 0)
#         except Exception as e:
#             logger.error(f"Get market price error: {str(e)}")
#             self.metrics['runtime_errors'] += 1
#             await send_alert(self, "Error getting current market price. The Bot is toast", logger)
#             raise
#         finally:
#             log_leaving_function('get_current_market_price', start_time, logger)
#
#     async def liquidate_position(self, currency, issuer):
#         start_time = time.time()
#         logger.info(ENTERING_FUNCTION_LOG.format('liquidate_position'))
#         try:
#             await self.get_balance(force_update=True)
#             balance = self.balances.get(currency, 0)
#             if balance <= 0:
#                 logger.info(f"No {currency} to liquidate")
#                 return
#             market_price = await self.get_current_market_price(currency, issuer)
#             limit_price = market_price * 0.95
#             sell_xrp = int(balance * limit_price * 1000000)
#             tx_sell = prepare_offer_create_get_meme(self.wallet.classic_address, currency, issuer, str(balance), str(sell_xrp))
#             signed_tx_sell = await autofill_and_sign(tx_sell, self.client, self.wallet)
#             logger.info(f"Liquidating {balance} {currency} at {limit_price} XRP/{currency}")
#             result = await submit(signed_tx_sell, self.client)
#             if result.result["engine_result"] == "tesSUCCESS":
#                 self.total_xrp_received += sell_xrp / 1000000
#                 self.metrics["sell_trades_executed"] += 1
#                 logger.info(f"Liquidated {balance} {currency}")
#         except Exception as e:
#             logger.error(f"Liquidate error: {str(e)}")
#             self.metrics['runtime_errors'] += 1
#             await send_alert(self, "Error liquidating positions. The Bot is toast", logger)
#             raise
#         finally:
#             log_leaving_function('liquidate_position', start_time, logger)
#
#     async def run(self):
#         start_time = time.time()
#         logger.info(ENTERING_FUNCTION_LOG.format('run'))
#
#         iteration = 0
#         await self.load_config()
#
#         try:
#             while self.running:
#                 iteration += 1
#                 self.metrics['bot_iterations'] += 1
#                 logger.info(f"{'*' * 3} Bot iteration {iteration} {'*' * 3}")
#                 print(f"Bot iteration {iteration}")
#
#                 if await self.check_stop_loss():
#                     logger.info("Stop-loss triggered, halting bot")
#                     self.running = False
#                     break
#
#                 await self.get_balance(force_update=True)
#                 if self.owner_count >= self.owner_count_limit or any(self.balances[m['currency']] > self.max_meme_amount_to_hold for m in self.meme_coins):
#                     logger.info(f"Too many offers or {self.currency} accumulation, cancelling before trade")
#
#                     try:
#                         await self.cancel_unused_offers()
#                     except Exception as e:
#                         logger.error(f"Failed to cancel offers: {str(e)}. Continuing to next iteration")
#                         await send_alert(self, f"Error cancelling unused offers in iteration {iteration}: {str(e)}", logger)
#
#                     await asyncio.sleep(self.bot_sleep)
#                 print(f"\tNumber of active request before find_arbitrage: {len(bot.active_requests)}")
#                 logger.info(f"Number of active request before find_arbitrage: {len(bot.active_requests)}")
#
#                 tasks = [self.find_arbitrage(meme['currency'], meme['issuer']) for meme in self.meme_coins if self.balances[meme['currency']] <= self.max_meme_amount_to_hold]
#                 results = await asyncio.gather(*tasks, return_exceptions=True)
#
#                 for i, result in enumerate(results):
#                     if isinstance(result, Exception):
#                         logger.error(f"Arbitrage error for {self.meme_coins[i]['currency']}: {result}")
#                         continue
#                     has_opportunity, discounted_buy_price, sell_price, profit, buy_price, sell_offer, buy_offer = result
#                     if has_opportunity:
#                         logger.info(f"********* Trading opportunity found for {self.meme_coins[i]['currency']}! Potential profit: {profit} XRP *********")
#                         try:
#                             await self.execute_trade(discounted_buy_price, sell_price, profit, buy_price, sell_offer, buy_offer, self.meme_coins[i]['currency'], self.meme_coins[i]['issuer'])
#                         except Exception as e:
#                             logger.error(f"Failed to execute trade: {str(e)}. Continuing to next iteration")
#                     else:
#                         logger.info(f"No profitable opportunity for {self.meme_coins[i]['currency']} (min profit needed: {self.min_profit_xrp:.6f} XRP)")
#
#                 await asyncio.sleep(self.run_pause)
#         except Exception as e:
#             logger.error(f"Run error in iteration {iteration}: {str(e)}", exc_info=True)
#             self.metrics['runtime_errors'] += 1
#             await send_alert(self, "Error in run. Sleeping.... Check logs for issues", logger)
#             await asyncio.sleep(self.bot_sleep)
#         finally:
#             log_leaving_function('run', start_time, logger)
#
# bot = TradingBot()
#
# @app.route('/')
# async def index():
#     start_time = time.time()
#     logger.info(ENTERING_FUNCTION_LOG.format('index'))
#     try:
#         logger.info("Rendering index page...")
#
#         # Check if the bot is initialized
#         if not hasattr(bot, 'wallet') or bot.wallet is None:
#             logger.error("Bot wallet is not initialized.")
#             return "Bot is not initialized. Please try again later.", 503
#
#         # Generate QR code
#         logger.info("Generating QR code...")
#         if not bot.wallet_qr_codes:
#             for meme in bot.meme_coins:
#                 qr = qrcode.QRCode()
#                 qr.add_data(meme['issuer'])
#                 qr_buffer = BytesIO()
#                 qr.make_image().save(qr_buffer)
#                 qr_data = base64.b64encode(qr_buffer.getvalue()).decode()
#                 bot.wallet_qr_codes.append(
#                 {
#                     'qr_data': qr_data,
#                     'currency': meme['currency'],
#                     'issuer': meme['issuer'],
#                 })
#
#         qr = qrcode.QRCode()
#         qr.add_data(bot.wallet.classic_address)
#         qr_buffer = BytesIO()
#         qr.make_image().save(qr_buffer)
#         qr_data = base64.b64encode(qr_buffer.getvalue()).decode()
#         logger.info("QR code generated successfully.")
#
#         # Prepare balances
#         logger.info("Preparing balances...")
#         logger.info(f"Balances prepared: {bot.balances}")
#
#         # Render the template
#         logger.info("Rendering template...")
#         return await render_template(
#             'index.html',
#             metrics=bot.metrics,
#             balances=bot.balances,
#             address=bot.wallet.classic_address,
#             qr_code=qr_data,
#             running=bot.running,
#             currency=bot.currency,
#             config=bot.config,
#             meme_coins=bot.meme_coins,
#             wallet_qr_codes=bot.wallet_qr_codes
#         )
#     except Exception as e:
#         logger.error(f"Index error: {str(e)}", exc_info=True)
#         return "Internal Server Error", 500
#     finally:
#         log_leaving_function('index', start_time, logger)
#
# @app.route('/update_config', methods=['POST'])
# async def update_config():
#     start_time = time.time()
#     logger.info(ENTERING_FUNCTION_LOG.format('update_config'))
#     try:
#         data = await request.json
#         result = await bot.update_config(data)
#         return jsonify(result)
#     except Exception as e:
#         logger.error(f"Update config error: {str(e)}", exc_info=True)
#         return jsonify({'status': 'error', 'message': 'Internal Server Error'}), 500
#     finally:
#         log_leaving_function('update_config', start_time, logger)
#
# @app.route('/stop', methods=['POST'])
# async def stop_bot():
#     start_time = time.time()
#     logger.info(ENTERING_FUNCTION_LOG.format('stop_bot'))
#     try:
#         if bot.running:
#             bot.running = False
#             if bot.task:  # Cancel the bot.run() task if it exists
#                 bot.task.cancel()
#                 try:
#                     await bot.task  # Wait for the task to be cancelled
#                 except asyncio.CancelledError:
#                     logger.info("Bot task was cancelled successfully")
#
#             # Wait for all active XRPL requests to complete
#             # timeout = 20  # seconds
#             while bot.active_requests and (time.time() - start_time) < bot.bot_timeout:
#                 logger.info(f"Waiting for {len(bot.active_requests)} active requests to complete...")
#                 await asyncio.sleep(bot.bot_sleep)  # Brief sleep to avoid busy-waiting
#
#             if bot.active_requests:
#                 logger.warning(f"Timeout reached, {len(bot.active_requests)} requests still active")
#
#             logger.info("Bot stopped")
#             return jsonify({'status': 'success', 'message': 'Bot 2 is sleeping'})
#         return jsonify({'status': 'error', 'message': 'Bot not running'})
#     except Exception as e:
#         logger.error(f"Stop bot error: {str(e)}", exc_info=True)
#         return "Internal Server Error", 500
#     finally:
#         log_leaving_function('stop_bot', start_time, logger)
#
# @app.route('/kill', methods=['POST'])
# async def kill_bot():
#     start_time = time.time()
#     logger.info(ENTERING_FUNCTION_LOG.format('kill_bot'))
#     try:
#         logger.info("Shutting down the application...")
#         # Stop the bot if it's running
#         if bot.running:
#             bot.running = False
#             if bot.task:
#                 bot.task.cancel()
#                 try:
#                     await bot.task
#                 except asyncio.CancelledError:
#                     logger.info("Bot task was cancelled successfully")
#
#             # Cancel background tasks
#             for task in bot.background_tasks:
#                 task.cancel()
#                 try:
#                     await task
#                 except asyncio.CancelledError:
#                     pass
#
#             # Wait for all active XRPL requests to complete
#             while bot.active_requests and (time.time() - start_time) < bot.bot_timeout:
#                 logger.info(f"Waiting for {len(bot.active_requests)} active requests to complete...")
#                 await asyncio.sleep(bot.bot_sleep)  # Brief sleep to avoid busy-waiting
#
#             if bot.active_requests:
#                 logger.warning(f"Timeout reached, {len(bot.active_requests)} requests still active")
#
#         # Send a response to the client before shutting down
#         response = jsonify({'status': 'success', 'message': 'The Bot is toast'})
#
#         # Schedule a background task to shut down the server after the response is sent
#         """Shut down the server gracefully."""
#         logger.info("Shutting down the server...")
#         asyncio.get_event_loop().create_task(app.shutdown())
#
#         return response
#     except Exception as e:
#         logger.error(f"Kill bot error: {str(e)}", exc_info=True)
#         return "Internal Server Error", 500
#     finally:
#         log_leaving_function('kill_bot', start_time, logger)
#
# @app.route('/status', methods=['GET'])
# async def get_status():
#     start_time = time.time()
#     logger.info(ENTERING_FUNCTION_LOG.format('get_status'))
#     request_id = f"get_status_{bot.request_counter}"
#     await bot.get_balance()
#     bot.active_requests.add(request_id)
#     bot.request_counter += 1
#     try:
#         async with bot.request_semaphore:
#             open_offers_response = await bot.client.request(prepare_account_offers(bot.wallet.classic_address, "validated"))
#         open_offers = open_offers_response.result.get('offers', [])
#
#         # Ensure wallet_qr_codes is up-to-date with meme_coins
#         current_currencies = {qr['currency'] for qr in bot.wallet_qr_codes}
#         new_currencies = {meme['currency'] for meme in bot.meme_coins}
#         if current_currencies != new_currencies:
#             bot.wallet_qr_codes = []
#             for meme in bot.meme_coins:
#                 qr = qrcode.QRCode()
#                 qr.add_data(meme['issuer'])
#                 qr_buffer = BytesIO()
#                 qr.make_image().save(qr_buffer)
#                 qr_data = base64.b64encode(qr_buffer.getvalue()).decode()
#                 bot.wallet_qr_codes.append({
#                     'currency': meme['currency'],
#                     'issuer': meme['issuer'],
#                     'qr_data': qr_data
#                 })
#
#         # db_trade_history = get_trade_history(bot, logger, 1000)
#         # print(f"trade_history: {db_trade_history}")
#
#         return jsonify({
#             'running': bot.running,
#             'metrics': bot.metrics,
#             'balances': bot.balances,
#             'open_offers': len(open_offers),
#             'trade_history': bot.trade_history[-1000:],
#             'total_xrp_spent': bot.total_xrp_spent,  # Add total XRP spent
#             'total_xrp_received': bot.total_xrp_received,  # Add total XRP received
#             'meme_coins': [m['currency'] for m in bot.meme_coins],  # Add list of currencies
#             'wallet_qr_codes': bot.wallet_qr_codes  # Add this
#         })
#     except Exception as e:
#         logger.error(f"Status error: {str(e)}", exc_info=True)
#         return "Internal Server Error", 500
#     finally:
#         bot.active_requests.remove(request_id)
#         log_leaving_function('get_status', start_time, logger)
#
# @app.route('/start', methods=['POST'])
# async def start_bot():
#     start_time = time.time()
#     logger.info(ENTERING_FUNCTION_LOG.format('start_bot'))
#     try:
#         if not bot.running:
#             bot.running = True
#             bot.task = asyncio.create_task(bot.run())  # Run the bot asynchronously
#             logger.info("Bot started")
#             return jsonify({'status': 'success', 'message': 'Bot started'})
#         return jsonify({'status': 'error', 'message': 'Bot already running'})
#     except Exception as e:
#         logger.error(f"Start bot error: {str(e)}", exc_info=True)
#         return "Internal Server Error", 500
#     finally:
#         log_leaving_function('start_bot', start_time, logger)
#
# async def initialize_bot():
#     start_time = time.time()
#     logger.info(ENTERING_FUNCTION_LOG.format('initialize_bot'))
#     try:
#         await bot.initialize()
#         logger.info("Bot initialized successfully.")
#         logger.info(f"Wallet address: {bot.wallet.classic_address}")
#         logger.info(f"Balances: {bot.balances}")
#     except Exception as e:
#         logger.error(f"Initialize bot error: {str(e)}", exc_info=True)
#         raise
#     finally:
#         log_leaving_function('initialize_bot', start_time, logger)
#
# if __name__ == "__main__":
#     logger.info("Initializing bot...")
#     os.makedirs(os.path.join(BASE_DIR, 'logs'), exist_ok=True)
#
#     asyncio.run(initialize_bot())  # Call initialize_bot() to initialize the bot
#
#     logger.info("Starting Quart application with Hypercorn")
#     from hypercorn.config import Config
#     from hypercorn.asyncio import serve
#
#     # Create a Hypercorn config
#     config = Config()
#     config.bind = ["127.0.0.1:5000"]  # Bind to the same address and port
#     config.use_reloader = False  # Disable reloader in production
#
#     # Run the app with Hypercorn
#     asyncio.run(serve(app, config))
#
#
