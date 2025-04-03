import binascii
import time

from xrpl.clients import JsonRpcClient
from xrpl.models.requests import BookOffers

# Connect to XRPL mainnet
MAINNET_URL = "https://s1.ripple.com:51234/"
client = JsonRpcClient(MAINNET_URL)

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

def get_order_book(base_currency, base_issuer, quote_currency="XRP"):
    print(f" currency: {decode_currency(base_currency)}")
    taker_gets = {"currency": base_currency, "issuer": base_issuer}
    taker_pays = {"currency": quote_currency}

    try:
        bid_request = BookOffers(taker_gets=taker_gets, taker_pays=taker_pays, ledger_index="validated", limit=10)
        bid_response = client.request(bid_request).result
    except Exception as e:
        print(f"Error fetching bids for {base_currency}.{base_issuer}: {e}")
        return None

    try:
        ask_request = BookOffers(taker_gets=taker_pays, taker_pays=taker_gets, ledger_index="validated", limit=10)
        ask_response = client.request(ask_request).result
    except Exception as e:
        print(f"Error fetching asks for {base_currency}.{base_issuer}: {e}")
        return None

    bids = bid_response.get("offers", [])
    asks = ask_response.get("offers", [])

    if not bids and not asks:
        print(f"No offers found for {base_currency}.{base_issuer}")
        return None

    # Calculate prices: bids (XRP per token), asks (XRP per token)
    top_bid = 1 / float(bids[0]["quality"]) if bids else 0  # Invert: XRP per token
    top_ask = float(asks[0]["quality"]) if asks else float("inf")  # Already XRP per token
    spread = top_ask - top_bid if top_bid and top_ask != float("inf") else float("inf")

    # Calculate liquidity in XRP
    bid_liquidity = 0
    if bids:
        for offer in bids:
            # Use funded amount if available, otherwise full amount
            taker_pays = offer.get("taker_pays_funded", offer.get("taker_pays"))
            if taker_pays:
                if isinstance(taker_pays, str):  # XRP in drops
                    bid_liquidity += int(taker_pays)
                elif isinstance(taker_pays, dict):  # IOU, convert via quality
                    bid_liquidity += int(float(taker_pays["value"]) / float(offer["quality"]) * 1_000_000)

    ask_liquidity = 0
    if asks:
        for offer in asks:
            # Use funded amount if available, otherwise full amount
            taker_gets = offer.get("taker_gets_funded", offer.get("taker_gets"))
            if taker_gets:
                if isinstance(taker_gets, str):  # XRP in drops
                    ask_liquidity += int(taker_gets)
                elif isinstance(taker_gets, dict):  # IOU, convert via quality
                    ask_liquidity += int(float(taker_gets["value"]) * float(offer["quality"]) * 1_000_000)

    total_liquidity = (bid_liquidity + ask_liquidity) / 1_000_000  # Convert drops to XRP

    timestamp = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime())
    ledger_index = bid_response.get("ledger_index", "unknown")

    return {
        "pair": f"XRP/{base_currency}.{base_issuer}",
        "top_bid": top_bid,
        "top_ask": top_ask,
        "spread": spread,
        "timestamp": timestamp,
        "ledger_index": ledger_index,
        "total_liquidity": total_liquidity,
        "bids": len(bids),
        "asks": len(asks)
    }

army_currency = encode_currency("ARMY")
bear_currency = encode_currency("BEAR")
phnix_currency = encode_currency("PHNIX")
solo_currency = encode_currency("SOLO")
rlusd_currency = encode_currency("RLUSD")
popular_tokens = [
    # {"currency": "USD", "issuer": "rvYAfWj5gh67oV6fW32ZzP3Aw4Eubs59B"},  # Bitstamp USD
    # {"currency": "BTC", "issuer": "rvYAfWj5gh67oV6fW32ZzP3Aw4Eubs59B"},  # Bitstamp BTC
    # {"currency": "SOLO", "issuer": "rsoLo2S1kiGeCcn6hCUXVrCpGMWLrRR4as"}, # Sologenic
    # {"currency": "CORE", "issuer": "rcoreNyawaoz2d9n5zE9Tj9wH8e8M3N8bH"}, # Coreum
    # {"currency": "CSC", "issuer": "rCSCManTZ8ME9EoLrSHga9j1q6iCWUtwP"},  # CasinoCoin
    # {"currency": "XDX", "issuer": "rXDXHubL8P2wQ3X3Q3i5T5uL6vX3i5T5uL"}, # XDX
    # {"currency": "PHNIX", "issuer": "r3qHPTAyvNxU3PvD8oqMg4g7mhA9e5hUHn"}, # PHNIX
    # {"currency": "ARMY", "issuer": "rarmyFENXERE2eRSDh6u9K9JEyjuV66D7"},   # ARMY
    # {"currency": bear_currency, "issuer": "rBEARGUAsyu7tUw53rufQzFdWmJHpJEqFW"},   # BEAR
    {"currency": phnix_currency, "issuer": "rDFXbW2ZZCG5WgPtqwNiA2xZokLMm9ivmN"},
    # {"currency": solo_currency, "issuer": "rsoLo2S1kiGeCcn6hCUXVrCpGMWLrRrLZz"},
    # {"currency": rlusd_currency, "issuer": "rMxCKbEDwqr76QuheSUMdEGf4B9xJ8m5De"},
    # {"currency": army_currency, "issuer": "r319FqohpKLwjtcV2mosyC5sy125fDk4uH"},  # ARMY

]

def find_best_pair():
    results = []
    print("Scanning XRPL DEX for XRP/token pairs...")
    for token in popular_tokens:
        order_book = get_order_book(token["currency"], token["issuer"])
        if order_book and order_book["total_liquidity"] > 0:
            print(f"Found viable pair: {order_book['pair']} (Liquidity: {order_book['total_liquidity']} XRP)")
            results.append(order_book)
        else:
            print(f"No liquidity or error for {token['currency']}.{token['issuer']}")

    if not results:
        print("No viable pairs found with sufficient liquidity.")
        return None

    best_pair = sorted(
        results,
        key=lambda x: x["total_liquidity"] / (x["spread"] if x["spread"] > 0 else 0.0001),
        reverse=True
    )[0]

    return best_pair

best_pair = find_best_pair()

if best_pair:
    print("\nBest XRP/Token Pair for Arbitrage:")
    print(f"Pair: {best_pair['pair']}")
    print(f"Top Bid: {best_pair['top_bid']} XRP per token")
    print(f"Top Ask: {best_pair['top_ask']} XRP per token")
    print(f"Spread: {best_pair['spread']} XRP")
    print(f"Timestamp: {best_pair['timestamp']} XRP")
    print(f"Ledger index: {best_pair['ledger_index']} XRP")
    print(f"Total Liquidity: {best_pair['total_liquidity']} XRP")
    print(f"Number of Bids: {best_pair['bids']}")
    print(f"Number of Asks: {best_pair['asks']}")
else:
    print("No suitable pairs found with sufficient liquidity.")

def get_order_book_24_hours(base_currency, base_issuer, quote_currency="XRP"):
    taker_gets = {"currency": base_currency, "issuer": base_issuer}
    taker_pays = {"currency": quote_currency}

    try:
        bid_request = BookOffers(taker_gets=taker_gets, taker_pays=taker_pays, ledger_index="validated", limit=20)
        bid_response = client.request(bid_request).result
    except Exception as e:
        print(f"Error fetching bids for {base_currency}.{base_issuer}: {e}")
        return None

    try:
        ask_request = BookOffers(taker_gets=taker_pays, taker_pays=taker_gets, ledger_index="validated", limit=20)
        ask_response = client.request(ask_request).result
    except Exception as e:
        print(f"Error fetching asks for {base_currency}.{base_issuer}: {e}")
        return None

    bids = bid_response.get("offers", [])
    asks = ask_response.get("offers", [])

    if not bids and not asks:
        print(f"No offers found for {base_currency}.{base_issuer}")
        return None

    # Calculate liquidity in XRP
    bid_liquidity = 0
    if bids:
        print("Bids:")
        for offer in bids:
            # print(f"Bid offer: {offer}")
            print(f"taker_pays: {float(offer['TakerPays'])/1000000} XRP taker_gets: {offer['TakerGets']['value']} PHINX")
            taker_pays = offer.get("taker_pays_funded", offer.get("taker_pays"))
            if taker_pays:
                if isinstance(taker_pays, str):  # XRP in drops
                    bid_liquidity += int(taker_pays)
                elif isinstance(taker_pays, dict):  # IOU, convert via quality
                    bid_liquidity += int(float(taker_pays["value"]) / float(offer["quality"]) * 1_000_000)

    ask_liquidity = 0
    if asks:
        print("Ask:")
        for offer in asks:
            # print(f"Ask offer: {offer}")
            print(f"taker_pays: {offer['TakerPays']['value']} PHNIX taker_gets: {float(offer['TakerGets'])/1000000} XRP")
            taker_gets = offer.get("taker_gets_funded", offer.get("taker_gets"))
            if taker_gets:
                if isinstance(taker_gets, str):  # XRP in drops
                    ask_liquidity += int(taker_gets)
                elif isinstance(taker_gets, dict):  # IOU, convert via quality
                    ask_liquidity += int(float(taker_gets["value"]) * float(offer["quality"]) * 1_000_000)

    total_liquidity = (bid_liquidity + ask_liquidity) / 1_000_000  # Convert drops to XRP

    timestamp = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime())
    ledger_index = bid_response.get("ledger_index", "unknown")

    return {
        "pair": f"XRP/{base_currency}.{base_issuer}",
        "total_liquidity": total_liquidity,
        "timestamp": timestamp,
        "ledger_index": ledger_index,
        "bids": len(bids),
        "asks": len(asks)
    }

def find_high_volume_tokens():
    results = []
    print("Scanning XRPL DEX for active XRP/token pairs...")
    for token in popular_tokens:
        order_book = get_order_book_24_hours(token["currency"], token["issuer"])
        if order_book and order_book["total_liquidity"] > 0:
            print(f"\nFound active pair: {order_book['pair']} (Liquidity: {order_book['total_liquidity']} XRP)")
            results.append(order_book)
        else:
            print(f"No liquidity for {token['currency']}.{token['issuer']}")

    if not results:
        print("No active pairs found with sufficient liquidity.")
        return []

    # Sort by total liquidity as a proxy for recent trading volume
    top_tokens = sorted(results, key=lambda x: x["total_liquidity"], reverse=True)[:5]  # Top 5
    return top_tokens

# Run the analysis
top_tokens = find_high_volume_tokens()

if top_tokens:
    print("\nTop XRP/Token Pairs by Current Liquidity (Proxy for 24h Volume):")
    for i, token in enumerate(top_tokens, 1):
        print(f"{i}. Pair: {token['pair']}")
        print(f"    Total Liquidity: {token['total_liquidity']} XRP")
        print(f"    Timestamp: {best_pair['timestamp']} XRP")
        print(f"    Ledger index: {best_pair['ledger_index']} XRP")
        print(f"    Number of Bids: {token['bids']}")
        print(f"    Number of Asks: {token['asks']}")
else:
    print("No suitable pairs found.")