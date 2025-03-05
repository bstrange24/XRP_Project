from django.http import JsonResponse
from xrpl import XRPLException
from xrpl.asyncio.transaction import submit_and_wait
from xrpl.models import BookOffers, OfferCreate, AccountLines, AccountOffers

from xrpl_backend.xrpl_api.errors.error_handling import process_unexpected_error


# Ensure this function runs properly in Django's event loop
async def process_offer(signed_tx, client):
    try:
        result = await submit_and_wait(signed_tx, client)
    except XRPLException as e:
        process_unexpected_error(e)
    return result

def create_get_account_offers_response(paginated_transactions, paginator):
    return JsonResponse({
            "offers": paginated_transactions.object_list,
            "page": paginated_transactions.number,
            "total_pages": paginator.num_pages,
            "total_offers": paginator.count
        })

# def create_get_account_offers_response(paginated_transactions, paginator):
#     return JsonResponse({
#         "status": "success",
#         "message": "Account offers successfully retrieved.",
#         "account_offers": list(paginated_transactions),
#         "total_account_lines": paginator.count,
#         "pages": paginator.num_pages,
#         "current_page": paginated_transactions.number,
#     })

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

def create_account_offers_response(orderbook_info, result, acct_offers):
    return JsonResponse({
        'status': 'success',
        'message': 'Offers successfully created.',
        'result': result.result,
        'orderbook_info': orderbook_info.result,
        'acct_offers': acct_offers.result,
    })

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


def create_account_offers_response(result, acct_offers):
    return JsonResponse({
        "transaction_status": "success" if result.is_successful() else "failed",
        'acct_offers.result': acct_offers.result
    })
