from django.http import JsonResponse
from xrpl.models import IssuedCurrencyAmount, BookOffers


def create_book_offers_response(paginated_offers, paginator, taker_gets_currency, taker_pays_currency):
    return JsonResponse({
        'status': 'success',
        'message': 'Book Offers successfully retrieved.',
        "offers": paginated_offers.object_list,
        "page": paginated_offers.number,
        "total_pages": paginator.num_pages,
        "total_offers": paginator.count,
        "taker_gets_currency": taker_gets_currency,
        "taker_pays_currency": taker_pays_currency
    })


def prepare_book_offers(taker_gets_currency, taker_gets_issuer):
    return IssuedCurrencyAmount(
        currency=taker_gets_currency,
        issuer=taker_gets_issuer,
        value="0"  # Placeholder, not needed for BookOffers
    )

def prepare_book_offers_paginated(taker_gets, taker_pays, taker, marker):
    return BookOffers(
        taker_gets=taker_gets,
        taker_pays=taker_pays,
        taker=taker if taker else None,  # Optional taker
        limit=200  # Max offers per request
    )