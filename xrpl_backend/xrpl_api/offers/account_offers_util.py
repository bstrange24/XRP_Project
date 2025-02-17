from django.http import JsonResponse
from xrpl.asyncio.transaction import submit_and_wait
from xrpl.models import BookOffers, OfferCreate


# Ensure this function runs properly in Django's event loop
async def process_offer(signed_tx, client):
    result = await submit_and_wait(signed_tx, client)
    return result


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


def create_account_offers_response(signed_tx, orderbook_info, result, acct_offers):
    return JsonResponse({
        "transaction_hash": signed_tx.get_hash(),
        "orderbook_info": orderbook_info.result,
        "transaction_status": "success" if result.is_successful() else "failed",
        'acct_offers.result': acct_offers.result
    })
