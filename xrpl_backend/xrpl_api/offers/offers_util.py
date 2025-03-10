import logging

from django.http import JsonResponse
from xrpl.asyncio.transaction import submit_and_wait
from xrpl.models import BookOffers, OfferCreate, AccountLines, AccountOffers, OfferCancel, TrustSet, \
    IssuedCurrencyAmount, AccountInfo

logger = logging.getLogger('xrpl_app')


def check_balance(self, wallet, currency_code):
    """Check XRP and currency code balances for a wallet."""
    try:
        xrp_response = self.client.request(prepare_account_info(wallet.classic_address))
        xrp_balance = float(xrp_response.result["account_data"]["Balance"]) / 1000000

        currency_response = self.client.request(prepare_account_lines(wallet.classic_address))
        currency_balance = 0.0
        for line in currency_response.result.get("lines", []):
            if currency_code is not None:
                if line["currency"] == currency_code:
                    currency_balance = float(line["balance"])

        logger.info(f"XRP balance: {xrp_balance} {currency_code} {currency_balance}")

        return {"xrp": xrp_balance, currency_code: currency_balance}

    except Exception as e:
        logger.error(f"Error getting balance: {str(e)}")
        logger.error(f"Setting XRP balance and currency balance to error")
        xrp_balance = str("Error")
        currency_balance = str("Error")
        return {"xrp": xrp_balance, currency_code: currency_balance}


def check_and_create_trust_line(self, wallet, issuer_address, currency_code, trust_line_limit_amount):
    """Check if a trust line exists between wallet and issuer; create if not."""
    try:
        response = self.client.request(prepare_account_lines(wallet.classic_address))
        trust_lines = response.result.get("lines", [])
        has_trust_line = any(
            line["account"] == issuer_address and line["currency"] == currency_code
            for line in trust_lines
        )
        if not has_trust_line:
            trust_tx = TrustSet(
                account=wallet.classic_address,
                limit_amount=IssuedCurrencyAmount(currency=currency_code, issuer=issuer_address,
                                                  value=str(trust_line_limit_amount))
            )
            submit_and_wait(trust_tx, self.client, wallet)
            return True  # Trust line created

        return False  # Trust line already exists
    except Exception as e:
        logger.error(f"Error checking or setting trust lines: {str(e)}")
        logger.error(f"Returning True")
        return True


def get_offer_status(self, wallet_address):
    """Get all active offers for a wallet."""
    response = self.client.request(prepare_account_offers(wallet_address))
    return response.result.get("offers", [])


def create_get_account_offers_response(paginated_transactions, paginator):
    return JsonResponse({
        "status": "success",
        "message": "Account offers successfully retrieved.",
        "offers": paginated_transactions.object_list,
        "page": paginated_transactions.number,
        "total_pages": paginator.num_pages,
        "total_offers": paginator.count
    })


def create_account_offers_paginated_response(orderbook_info, result, acct_offers):
    return JsonResponse({
        'status': 'success',
        'message': 'Offers successfully created.',
        'result': result.result,
        'orderbook_info': orderbook_info.result,
        'acct_offers': acct_offers.result,
    })


def create_account_offers_response(result, acct_offers):
    return JsonResponse({
        "transaction_status": "success" if result.is_successful() else "failed",
        'acct_offers': acct_offers.result
    })


def create_account_status_response(balances, offers, trustlines):
    return JsonResponse({
        "balances": balances,
        "offers": offers,
        "trustlines": trustlines
    })


def create_seller_account_response(result, trust_line_created, balances_before, balances_after):
    return JsonResponse({
        "sequence": result["tx_json"]["Sequence"],
        "hash": result["hash"],
        "trust_line_created": trust_line_created,
        "balances_before": balances_before,
        "balances_after": balances_after,
        "metadata": result.get("meta", {})
    })


def create_buyer_account_response(result, trust_line_created, balances_before, balances_after):
    return JsonResponse({
        "sequence": result["tx_json"]["Sequence"],
        "hash": result["hash"],
        "trust_line_created": trust_line_created,
        "balances_before": balances_before,
        "balances_after": balances_after,
        "metadata": result.get("meta", {})
    })


def create_taker_account_response(result, trust_line_created, balances_before, balances_after):
    return JsonResponse({
        "sequence": result["tx_json"]["Sequence"],
        "hash": result["hash"],
        "trust_line_created": trust_line_created,
        "balances_before": balances_before,
        "balances_after": balances_after,
        "metadata": result.get("meta", {})
    })


def create_cancel_account_status_response(result, balances_before, balances_after):
    return JsonResponse({
        "hash": result["hash"],
        "balances_before": balances_before,
        "balances_after": balances_after,
        "metadata": result.get("meta", {})
    })


def prepare_cancel_offer(classic_address, sequence):
    return OfferCancel(
        account=classic_address,
        sequence=sequence,
    )


def prepare_account_lines(wallet_address):
    return AccountLines(
        account=wallet_address,
        ledger_index="validated",
    )


def prepare_account_info(wallet_address):
    return AccountInfo(
        account=wallet_address,
        ledger_index="validated",
    )


def prepare_account_offers(wallet_address):
    return AccountOffers(
        account=wallet_address,
        ledger_index="validated",
    )


def prepare_account_offers_paginated(wallet_address, marker):
    return AccountOffers(
        account=wallet_address,
        limit=100,
        marker=marker,
        ledger_index="validated",
    )


def create_book_offer(wallet_address, we_want, we_spend):
    return BookOffers(
        taker=wallet_address,
        ledger_index="current",
        taker_gets=we_want["currency"],
        taker_pays=we_spend["currency"],
        limit=10,
    )


def create_buy_offer(account, currency_code, issuer_address, amount, xrp_amount):
    return OfferCreate(
        account=account,
        taker_gets=create_issued_currency_amount(currency_code, issuer_address, str(amount)),
        taker_pays=str(int(xrp_amount * 1000000))
    )


def create_sell_offer(account, xrp_amount, currency_code, issuer_address, amount):
    return OfferCreate(
        account=account,
        taker_gets=str(xrp_amount * 1000000),
        taker_pays=create_issued_currency_amount(currency_code, issuer_address, str(amount))
    )


def create_issued_currency_amount(currency_code, issuer_address, amount):
    return IssuedCurrencyAmount(currency=currency_code, issuer=issuer_address, value=str(amount))
