from xrpl.models import IssuedCurrency, XRP, BookOffers, IssuedCurrencyAmount
from xrpl.utils import xrp_to_drops


def buyer_create_issued_currency(wallet_address, currency, amount):
    return {
        "currency": IssuedCurrency(
            currency=currency,
            issuer=wallet_address
        ),
        "value": amount,
    }

def create_issued_currency_amount(issuer_address, currency, amount):
    return IssuedCurrencyAmount(
        currency=currency,
        issuer=issuer_address,
        value=str(amount)
    )


def create_amount_the_buyer_wants_to_spend():
    return {
        "currency": XRP(),
        # 25 TST * 10 XRP per TST * 15% financial exchange (FX) cost
        "value": xrp_to_drops(25 * 10 * 1.15),
    }

# def create_book_offer(wallet_address, we_want, we_spend):
#     return BookOffers(
#         taker=wallet_address,
#         ledger_index="current",
#         taker_gets=we_want["currency"],
#         taker_pays=we_spend["currency"],
#         limit=10,
#     )
