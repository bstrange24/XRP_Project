import asyncio
import binascii
import logging
import smtplib
import time
from email.mime.text import MIMEText

from xrpl.models import AccountLines, TrustSet, IssuedCurrencyAmount, AccountInfo, AccountOffers, OfferCancel, \
    OfferCreate, Tx, BookOffers

from utils.constants import (LEAVING_FUNCTION_LOG, XRP, ENTERING_FUNCTION_LOG, INFO, DEBUG, ERROR, WARNING, MIN5_VOLUME_MIN,
                             HOUR1_VOLUME_MIN, HOUR6_VOLUME_MIN, HOUR24_VOLUME_MIN, HOUR24_BUYS_AND_SELLS_MIN, HOUR6_BUYS_AND_SELLS_MIN,
                             HOUR1_BUYS_AND_SELLS_MIN, MIN5_BUYS_AND_SELLS_MIN)


def send_email_sync(smtp_server, smtp_port, email_address, email_password, msg):
    """Synchronous helper to send the email."""
    print(f"email_address: {email_address}")
    print(f"email_password: {email_password}")
    with smtplib.SMTP(smtp_server, smtp_port) as server:
        server.starttls()  # Enable TLS
        server.login(email_address, email_password)
        server.send_message(msg)


async def send_alert(self, message, logger):
    start_time = time.time()
    logger.info(ENTERING_FUNCTION_LOG.format('send_alert'))
    try:
        # Get email credentials from environment variables
        email_address = self.email_address
        email_password = self.email_password
        alert_phone_email = self.alert_phone_email

        if not email_address or not email_password:
            raise ValueError("Missing email credentials (EMAIL_ADDRESS, EMAIL_PASSWORD)")

        # Create the email
        msg = MIMEText(message)
        msg['Subject'] = 'XRPL Trading Bot Alert'
        msg['From'] = email_address
        msg['To'] = alert_phone_email

        # Gmail SMTP settings
        smtp_server = "smtp.mail.yahoo.com"
        smtp_port = 587

        # Run synchronous SMTP in a thread to keep async compatibility
        loop = asyncio.get_running_loop()
        await loop.run_in_executor(None, lambda: send_email_sync(
            smtp_server, smtp_port, email_address, email_password, msg
        ))
        logger.info(f"Email alert sent: {message}")
    except Exception as e:
        logger.error(f"Alert send error: {str(e)}")
        self.metrics['runtime_errors'] += 1
    finally:
        log_leaving_function('send_alert', start_time, logger, INFO)


async def get_next_sequence(self, logger):
    """Fetch the current sequence number from the ledger."""
    start_time = time.time()
    logger.info(ENTERING_FUNCTION_LOG.format('get_next_sequence'))
    try:
        async with self.request_semaphore:
            account_info = await self.client.request(prepare_account_info(self.wallet.classic_address, "validated"))
        sequence = account_info.result["account_data"]["Sequence"]
        self.current_sequence = sequence
        logger.info(f"Fetched sequence number: {sequence}")
        return sequence
    except Exception as e:
        logger.error(f"Error fetching sequence: {str(e)}")
        raise
    finally:
        log_leaving_function('get_next_sequence', start_time, logger, INFO)


async def confirm_transaction(self, tx_hash, logger):
    for _ in range(5):
        try:
            async with self.request_semaphore:
                tx_response = await self.client.request(Tx(transaction=tx_hash))
            if tx_response.result.get("validated"):
                return tx_response.result["meta"]["TransactionResult"] == "tesSUCCESS"
            await asyncio.sleep(2)
        except Exception as e:
            logger.warning(f"Error confirming tx {tx_hash}: {e}")
    logger.error(f"Transaction {tx_hash} not validated after retries")
    return False


def decode_currency(hex_currency: str) -> str:
    # Convert hex to bytes
    currency_bytes = binascii.unhexlify(hex_currency)

    # Strip trailing null bytes and decode
    return currency_bytes.rstrip(b'\x00').decode('utf-8')


def encode_currency(currency: str) -> str:
    # Convert currency to hex
    hex_currency = binascii.hexlify(currency.encode('utf-8')).decode('utf-8')

    # Pad with zeros to reach 40 hex characters (20 bytes)
    return hex_currency.ljust(40, '0')


def check_price_change_over_time(selected_pair):
    minute5_price_change = selected_pair.get("priceChange")['m5']
    if float(minute5_price_change) > 0:
        print(f"Last 5 minute priceChange is positive: {float(minute5_price_change)}")
    else:
        print(f"Last 5 minute priceChange is negative: {float(minute5_price_change)}")
        # return True

    hour1_price_change = selected_pair.get("priceChange")['h1']
    if float(hour1_price_change) > 0:
        print(f"Last 1 hour priceChange is positive: {float(hour1_price_change)}")
    else:
        print(f"Last 1 hour  priceChange is negative: {float(hour1_price_change)}")
        # return True

    hour6_price_change = selected_pair.get("priceChange")['h6']
    if float(hour6_price_change) > 0:
        print(f"Last 6 hour priceChange is positive: {float(hour6_price_change)}")
    else:
        print(f"Last 6 hour priceChange is negative: {float(hour6_price_change)}")
        # return True

    hour24_price_change = selected_pair.get("priceChange")['h24']
    if float(hour24_price_change) > 0:
        print(f"Last 24 hour priceChange is positive: {float(hour24_price_change)}")
    else:
        print(f"Last 24 hour priceChange is negative: {float(hour24_price_change)}")
        # return True
    return False


def check_volume_change_over_time(selected_pair):
    minute5_volume_change = selected_pair.get("volume")['m5']
    if float(minute5_volume_change) > MIN5_VOLUME_MIN:
        pass
        # print(f"Last 5 minute volume is greater than {MIN5_VOLUME_MIN} Volume: {float(minute5_volume_change)}")
    else:
        print(f"Last 5 minute volume is less than {MIN5_VOLUME_MIN} Volume: {float(minute5_volume_change)}")
        return True

    hour1_volume_change = selected_pair.get("volume")['h1']
    if float(hour1_volume_change) > HOUR1_VOLUME_MIN:
        pass
        # print(f"Last 1 hour volume is greater than {HOUR1_VOLUME_MIN} Volume: {float(hour1_volume_change)}")
    else:
        print(f"Last 1 hour volume is less than {HOUR1_VOLUME_MIN} Volume: {float(hour1_volume_change)}")
        return True

    hour6_volume_change = selected_pair.get("volume")['h6']
    if float(hour6_volume_change) > HOUR6_VOLUME_MIN:
        pass
        # print(f"Last 6 hour volume is greater than {HOUR6_VOLUME_MIN} Volume: {float(hour6_volume_change)}")
    else:
        print(f"Last 6 hour volume is less than {HOUR6_VOLUME_MIN} Volume: {float(hour6_volume_change)}")
        return True

    hour24_volume_change = selected_pair.get("volume")['h24']
    if float(hour24_volume_change) > HOUR24_VOLUME_MIN:
        pass
        # print(f"Last 24 hour volume is greater than {HOUR24_VOLUME_MIN} Volume: {float(hour24_volume_change)}")
    else:
        print(f"Last 24 hour volume is less than {HOUR24_VOLUME_MIN} Volume: {float(hour24_volume_change)}")
        return True
    return False


def check_buys_and_sells_over_time(selected_pair):
    txns = selected_pair.get("txns")
    minute5_buy = txns.get('m5')['buys']
    minute5_sell = txns.get('m5')['sells']
    minute5_buy_sell = {"buy": float(minute5_buy), "sell": float(minute5_sell)}
    if float(minute5_buy) > MIN5_BUYS_AND_SELLS_MIN and float(minute5_sell) > MIN5_BUYS_AND_SELLS_MIN:
        pass
        # print(f"Last 5 minute buys and sells is greater than {MIN5_BUYS_AND_SELLS_MIN} Buys: {float(minute5_buy)} Sells: {float(minute5_sell)}")
    else:
        print(f"Last 5 minute buys and sells is less than {MIN5_BUYS_AND_SELLS_MIN} Buys: {float(minute5_buy)} Sells: {float(minute5_sell)}")
        return True

    hour1_buy = txns.get('h1')['buys']
    hour1_sell = txns.get('h1')['sells']
    hour1_buy_sell = {"buy": float(hour1_buy), "sell": float(hour1_sell)}
    if float(hour1_buy) > HOUR1_BUYS_AND_SELLS_MIN and float(hour1_sell) > HOUR1_BUYS_AND_SELLS_MIN:
        pass
        # print(f"Last 1 hour buys and sells is greater than {HOUR1_BUYS_AND_SELLS_MIN} Buys: {float(hour1_buy)} Sells: {float(hour1_sell)}")
    else:
        print(f"Last 1 hour buys and sells is less than {HOUR1_BUYS_AND_SELLS_MIN} Buys: {float(hour1_buy)} Sells: {float(hour1_sell)}")
        return True

    hour6_buy = txns.get('h6')['buys']
    hour6_sell = txns.get('h6')['sells']
    hour6_buy_sell = {"buy": float(hour6_buy), "sell": float(hour6_sell)}
    if float(hour6_buy) > HOUR6_BUYS_AND_SELLS_MIN and float(hour6_sell) > HOUR6_BUYS_AND_SELLS_MIN:
        pass
        # print(f"Last 6 hour buys and sells is greater than {HOUR6_BUYS_AND_SELLS_MIN} Buys: {float(hour6_buy)} Sells: {float(hour6_sell)}")
    else:
        print(f"Last 6 hour buys and sells is less than {HOUR6_BUYS_AND_SELLS_MIN} Buys: {float(hour6_buy)} Sells: {float(hour6_sell)}")
        return True

    hour24_buy = txns.get('h24')['buys']
    hour24_sell = txns.get('h24')['sells']
    hour24_buy_sell = {"buy": float(hour24_buy), "sell": float(hour24_sell)}
    if float(hour24_buy) > HOUR24_BUYS_AND_SELLS_MIN and float(hour24_sell) > HOUR24_BUYS_AND_SELLS_MIN:
        pass
        # print(f"Last 24 hour buys and sells is greater than {HOUR24_BUYS_AND_SELLS_MIN} Buys: {float(hour24_buy)} Sells: {float(hour24_sell)}")
    else:
        print(f"Last 24 hour buys and sells is less than {HOUR24_BUYS_AND_SELLS_MIN} Buys: {float(hour24_buy)} Sells: {float(hour24_sell)}")
        return True
    return False


def prepare_account_info(wallet, ledger_index_status):
    return AccountInfo(
        account=wallet,
        ledger_index=ledger_index_status
    )


def prepare_account_lines(wallet, ledger_index_status):
    return AccountLines(
        account=wallet,
        ledger_index=ledger_index_status
    )


def prepare_trust_set(wallet, currency, issuer, trust_line_max):
    return TrustSet(
        account=wallet,
        limit_amount=IssuedCurrencyAmount(
            currency=currency,
            issuer=issuer,
            value=trust_line_max
        )
    )


def prepare_remove_trust_set(wallet, currency, issuer):
    return TrustSet(
        account=wallet,
        limit_amount=IssuedCurrencyAmount(
            currency=currency,
            issuer=issuer,
            value=0
        )
    )


def prepare_account_offers(wallet, ledger_index_status):
    return AccountOffers(
        account=wallet,
        ledger_index=ledger_index_status
    )


def prepare_offer_cancel(wallet, sequence):
    return OfferCancel(
        account=wallet,
        offer_sequence=sequence
    )


def prepare_offer_create_get_xrp(wallet, buy_amount_xrp, currency, issuer, trade_amount):
    return OfferCreate(
        account=wallet,
        taker_gets=buy_amount_xrp,  # XRP in drops
        taker_pays=IssuedCurrencyAmount(
            currency=currency,
            issuer=issuer,
            value=str(trade_amount)
        ),
    )


def prepare_offer_create_get_meme(wallet, currency, issuer, trade_amount, sell_amount_xrp):
    return OfferCreate(
        account=wallet,
        taker_gets=IssuedCurrencyAmount(
            currency=currency,
            issuer=issuer,
            value=str(trade_amount)
        ),
        taker_pays=sell_amount_xrp,  # XRP in drops
    )


def prepare_buy_offer_generic_object(command, currency, issuer, limit):
    logging.info(f"prepare_buy_offer_generic_object: currency: {currency} issuer: {issuer}")
    taker_gets = {"currency": currency, "issuer": issuer}
    taker_pays = {"currency": XRP}
    return BookOffers(taker_gets=taker_pays, taker_pays=taker_gets, ledger_index="validated", limit=limit)


def prepare_fetch_sell_offer_generic_object(command, currency, issuer, limit):
    logging.info(f"prepare_fetch_sell_offer_generic_object: currency: {currency} issuer: {issuer}")
    taker_gets = {"currency": currency, "issuer": issuer}
    taker_pays = {"currency": XRP}

    return BookOffers(taker_gets=taker_gets, taker_pays=taker_pays, ledger_index="validated", limit=limit)
    # return GenericRequest(
    #     command=command,
    #     taker_gets={"currency": currency, "issuer": issuer},
    #     taker_pays={"currency": XRP},
    #     limit=limit
    # )


def log_entering_function(function_name, logger, level):
    if level == INFO:
        logger.info(ENTERING_FUNCTION_LOG.format(function_name))
    if level == DEBUG:
        logger.debug(ENTERING_FUNCTION_LOG.format(function_name))
    if level == ERROR:
        logger.error(ENTERING_FUNCTION_LOG.format(function_name))
    if level == WARNING:
        logger.warning(ENTERING_FUNCTION_LOG.format(function_name))


def log_leaving_function(function_name, start_time, logger, level):
    end_time = time.time()  # Capture the end time
    if level == INFO:
        logger.info(LEAVING_FUNCTION_LOG.format(function_name, int((end_time - start_time) * 1000)))
    if level == DEBUG:
        logger.debug(LEAVING_FUNCTION_LOG.format(function_name, int((end_time - start_time) * 1000)))
    if level == ERROR:
        logger.error(LEAVING_FUNCTION_LOG.format(function_name, int((end_time - start_time) * 1000)))
    if level == WARNING:
        logger.warning(LEAVING_FUNCTION_LOG.format(function_name, int((end_time - start_time) * 1000)))
