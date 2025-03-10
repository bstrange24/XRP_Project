from django.http import JsonResponse
from xrpl import XRPLException
from xrpl.asyncio.transaction import submit_and_wait
from xrpl.models import BookOffers, OfferCreate, AccountLines, AccountOffers, OfferCancel, TrustSet, \
    IssuedCurrencyAmount, AccountInfo

from ..errors.error_handling import process_unexpected_error


def check_balance(self, wallet):
    """Check XRP and USD balances for a wallet."""
    xrp_response = self.client.request(AccountInfo(account=wallet.classic_address, ledger_index="validated"))
    xrp_balance = float(xrp_response.result["account_data"]["Balance"]) / 1000000  # Convert drops to XRP

    usd_response = self.client.request(AccountLines(account=wallet.classic_address, ledger_index="validated"))
    usd_balance = 0.0
    for line in usd_response.result.get("lines", []):
        if line["currency"] == "USD":
            usd_balance = float(line["balance"])
    return {"xrp": xrp_balance, "usd": usd_balance}


def check_and_create_trustline(self, wallet, issuer_address):
    """Check if a trust line exists between wallet and issuer; create if not."""
    response = self.client.request(AccountLines(account=wallet.classic_address, ledger_index="validated"))
    trustlines = response.result.get("lines", [])
    has_trustline = any(
        line["account"] == issuer_address and line["currency"] == "USD"
        for line in trustlines
    )
    if not has_trustline:
        trust_tx = TrustSet(
            account=wallet.classic_address,
            limit_amount=IssuedCurrencyAmount(currency="USD", issuer=issuer_address, value="1000")
        )
        submit_and_wait(trust_tx, self.client, wallet)
        return True  # Trust line created
    return False  # Trust line already exists


def get_offer_status(self, wallet_address):
    """Get all active offers for a wallet."""
    response = self.client.request(AccountOffers(account=wallet_address, ledger_index="validated"))
    return response.result.get("offers", [])


# Ensure this function runs properly in Django's event loop
async def process_offer(signed_tx, client):
    try:
        result = await submit_and_wait(signed_tx, client)
    except XRPLException as e:
        process_unexpected_error(e)
    return result


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


def create_seller_account_response(result, trustline_created, balances_before, balances_after):
    return JsonResponse({
        "sequence": result["tx_json"]["Sequence"],
        "hash": result["hash"],
        "trustline_created": trustline_created,
        "balances_before": balances_before,
        "balances_after": balances_after,
        "metadata": result.get("meta", {})
    })


def create_buyer_account_response(result, trustline_created, balances_before, balances_after):
    return JsonResponse({
        "sequence": result["tx_json"]["Sequence"],
        "hash": result["hash"],
        "trustline_created": trustline_created,
        "balances_before": balances_before,
        "balances_after": balances_after,
        "metadata": result.get("meta", {})
    })


def create_taker_account_response(result, trustline_created, balances_before, balances_after):
    return JsonResponse({
        "sequence": result["tx_json"]["Sequence"],
        "hash": result["hash"],
        "trustline_created": trustline_created,
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


def prepare_cancel_offer(classic_address, sequence, offer_id, last_ledger_sequence, fee):
    return OfferCancel(
        account=classic_address,
        sequence=sequence,
        offer_sequence=offer_id,  # The sequence number of the offer to cancel
        last_ledger_sequence=last_ledger_sequence + 200,
        fee=fee
    )


def prepare_account_lines_for_offer(wallet_address):
    return AccountLines(
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
        limit=200,
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


def create_offer(wallet_address, we_want, we_spend):
    return OfferCreate(
        account=wallet_address,
        taker_gets=we_spend["value"],
        taker_pays=we_want["currency"].to_amount(we_want["value"]),
    )
