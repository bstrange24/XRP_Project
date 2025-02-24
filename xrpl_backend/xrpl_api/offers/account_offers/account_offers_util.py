from django.http import JsonResponse
from xrpl.asyncio.transaction import submit_and_wait
from xrpl.models import BookOffers, OfferCreate, AccountLines, AccountOffers, OfferCancel


# Ensure this function runs properly in Django's event loop
async def process_offer(signed_tx, client):
    result = await submit_and_wait(signed_tx, client)
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
