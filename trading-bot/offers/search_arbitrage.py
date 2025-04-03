import xrpl
import datetime
from xrpl.clients import JsonRpcClient
from xrpl.models.requests import BookOffers

# XRPL JSON-RPC server URL
JSON_RPC_URL = "https://xrplcluster.com"  # Mainnet URL
client = JsonRpcClient(JSON_RPC_URL)


def get_known_tokens():
    """Returns a list of commonly traded tokens on XRPL."""
    return [
        "XRP",
        {"currency": "PHNIX", "issuer": "rDFXbW2ZZCG5WgPtqwNiA2xZokLMm9ivmN"},
        {"currency": "SOLO", "issuer": "rsoLo2S1kiGeCcn6hCUXVrCpGMWLrRrLZz"},
        {"currency": "RLUSD", "issuer": "rMxCKbEDwqr76QuheSUMdEGf4B9xJ8m5De"}
    ]


def get_order_book(base_currency, counter_currency):
    """Fetches the order book for a given currency pair and handles errors properly."""
    try:
        book_offers = BookOffers(
            taker_gets=base_currency,
            taker_pays=counter_currency
        )
        response = client.request(book_offers)
        offers = response.result.get("offers", [])
        if not offers:
            print(f"No offers found for {base_currency} / {counter_currency}")
        return offers
    except Exception as e:
        print(f"Error fetching order book for {base_currency}/{counter_currency}: {e}")
        return []


def find_best_trades():
    """Finds the best trading opportunities from order books."""
    best_trades = []
    current_time = datetime.datetime.now(datetime.UTC)

    tokens = get_known_tokens()

    for base in tokens:
        for counter in tokens:
            if base == counter:
                continue

            offers = get_order_book(base, counter)

            if not offers:
                continue

            best_bid = max((float(offer["TakerGets"]) / float(offer["TakerPays"]) for offer in offers if "TakerGets" in offer and "TakerPays" in offer), default=0)
            best_ask = min((float(offer["TakerPays"]) / float(offer["TakerGets"]) for offer in offers if "TakerGets" in offer and "TakerPays" in offer), default=float("inf"))

            if best_bid > best_ask:
                trade_info = {
                    "pair": f"{base}/{counter}",
                    "best_bid": best_bid,
                    "best_ask": best_ask,
                    "spread": best_bid - best_ask,
                    "timestamp": current_time.isoformat()
                }
                best_trades.append(trade_info)

    return best_trades


if __name__ == "__main__":
    trades = find_best_trades()

    if trades:
        print("Best trading opportunities found:")
        for trade in trades:
            print(trade)
    else:
        print("No profitable trading opportunities found.")


# import xrpl
# import time
# import datetime
# from xrpl.clients import JsonRpcClient
# from xrpl.models.requests import BookOffers, LedgerData
#
# # XRPL JSON-RPC server URL
# JSON_RPC_URL = "https://xrplcluster.com"  # Use Testnet URL
# client = JsonRpcClient(JSON_RPC_URL)
#
#
# def get_active_tokens():
#     """Fetches actively traded tokens from the XRPL ledger dynamically."""
#     try:
#         response = client.request(LedgerData())
#         tokens = set()
#         for entry in response.result.get("state", []):
#             if entry["LedgerEntryType"] == "Offer":
#                 taker_gets = entry["TakerGets"]
#                 taker_pays = entry["TakerPays"]
#
#                 if isinstance(taker_gets, dict):
#                     tokens.add(taker_gets.get("currency", "XRP"))
#                 else:
#                     tokens.add("XRP")
#
#                 if isinstance(taker_pays, dict):
#                     tokens.add(taker_pays.get("currency", "XRP"))
#                 else:
#                     tokens.add("XRP")
#         return list(tokens)
#     except Exception as e:
#         print(f"Error fetching active tokens: {e}")
#         return ["XRP"]
#
#
# def get_order_book(base_currency, counter_currency):
#     """Fetches the order book for a given currency pair."""
#     try:
#         book_offers = BookOffers(
#             taker_gets=base_currency,
#             taker_pays=counter_currency
#         )
#         response = client.request(book_offers)
#         return response.result.get("offers", [])
#     except Exception as e:
#         print(f"Error fetching order book: {e}")
#         return []
#
#
# def find_best_trades():
#     """Finds the best trading opportunities from order books."""
#     best_trades = []
#     current_time = datetime.datetime.now(datetime.UTC)
#
#     tokens = get_active_tokens()
#
#     for base in tokens:
#         for counter in tokens:
#             if base == counter:
#                 continue
#
#             offers = get_order_book(base, counter)
#
#             if not offers:
#                 continue
#
#             best_bid = max((float(offer["TakerGets"]) / float(offer["TakerPays"]) for offer in offers), default=0)
#             best_ask = min((float(offer["TakerPays"]) / float(offer["TakerGets"]) for offer in offers), default=float("inf"))
#
#             if best_bid > best_ask:
#                 trade_info = {
#                     "pair": f"{base}/{counter}",
#                     "best_bid": best_bid,
#                     "best_ask": best_ask,
#                     "spread": best_bid - best_ask,
#                     "timestamp": current_time.isoformat()
#                 }
#                 best_trades.append(trade_info)
#
#     return best_trades
#
#
# if __name__ == "__main__":
#     trades = find_best_trades()
#
#     if trades:
#         print("Best trading opportunities in the last 10 minutes:")
#         for trade in trades:
#             print(trade)
#     else:
#         print("No profitable trading opportunities found.")
