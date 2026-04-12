"""
DexScreener Service — Live market data, liquidity, and pool info.
No API key needed.

FIXES from original stub:
1. DexScreener's liquidity.base/quote are USD values, NOT raw token reserves.
   We now calculate actual reserves from price + liquidity data.
2. LP lock detection via string search was unreliable — replaced with
   proper label checking from DexScreener's pair labels/info.
3. Added proper error handling for tokens with no DEX pairs.
4. Added pair_address extraction for on-chain LP verification.
"""

import httpx
from datetime import datetime, timezone
from typing import Optional


async def get_market_data(token_address: str) -> dict:
    """
    Fetch market data from DexScreener for a given token address.
    Returns a dict with liquidity, reserves, price, and pair info.
    """
    url = f"https://api.dexscreener.com/latest/dex/tokens/{token_address}"

    try:
        async with httpx.AsyncClient(timeout=15) as client:
            r = await client.get(url)
            r.raise_for_status()
            data = r.json()
    except httpx.HTTPStatusError as e:
        print(f"[DexScreener] HTTP error: {e.response.status_code}")
        return _empty()
    except httpx.RequestError as e:
        print(f"[DexScreener] Request error: {e}")
        return _empty()
    except Exception as e:
        print(f"[DexScreener] Unexpected error: {e}")
        return _empty()

    pairs = data.get("pairs", [])
    if not pairs:
        result = _empty()
        result["data_status"] = "NO_PAIR"
        return result

    # ─── Select the best pair ─────────────────────────────────────────
    # Prefer Uniswap V2 pairs (simpler AMM math), fall back to highest liquidity
    v2_pairs = [p for p in pairs if "v2" in (p.get("dexId", "") or "").lower()]
    if v2_pairs:
        pair = max(v2_pairs, key=lambda p: p.get("liquidity", {}).get("usd", 0))
    else:
        pair = max(pairs, key=lambda p: p.get("liquidity", {}).get("usd", 0))

    # ─── Extract raw data ─────────────────────────────────────────────
    liquidity_usd = pair.get("liquidity", {}).get("usd", 0) or 0
    price_usd = float(pair.get("priceUsd", 0) or 0)
    price_native = float(pair.get("priceNative", 0) or 0)  # Price in quote token (e.g., ETH)

    # ─── Calculate actual pool reserves ───────────────────────────────
    # DexScreener gives us:
    #   - liquidity.usd = total pool value in USD
    #   - priceUsd = token price in USD
    #   - priceNative = token price in quote token (ETH for ETH pairs)
    #
    # For a balanced AMM pool:
    #   - Each side holds ~50% of total liquidity
    #   - token_reserve = (liquidity_usd / 2) / price_usd
    #   - eth_reserve = (liquidity_usd / 2) / eth_price_usd
    #
    # We can derive eth_price from: price_usd / price_native = eth_price_usd

    pool_token_reserve = 0.0
    pool_eth_reserve = 0.0
    quote_token_symbol = pair.get("quoteToken", {}).get("symbol", "").upper()

    if price_usd > 0 and price_native > 0 and liquidity_usd > 0:
        half_liquidity_usd = liquidity_usd / 2

        # Token side
        pool_token_reserve = half_liquidity_usd / price_usd

        # Quote side (ETH/WETH or stablecoin)
        eth_price_usd = price_usd / price_native if price_native > 0 else 0
        if eth_price_usd > 0:
            pool_eth_reserve = half_liquidity_usd / eth_price_usd

    # ─── LP Lock detection ────────────────────────────────────────────
    # DexScreener provides lock info in the pair's "labels" array
    # and in the "info" object. Check both.
    labels = pair.get("labels", [])
    lp_locked = False
    lock_expiry_timestamp = None
    lock_expiry_readable = None
    days_until_unlock = None

    # Check labels for lock indicators
    if labels:
        lp_locked = any(
            label.lower() in ("locked", "lp-locked", "lock")
            for label in labels
        )

    # Check info.extraInfo for lock data (some pairs have this)
    info = pair.get("info", {})
    if info:
        extra_info = info.get("extraInfo", {})
        if isinstance(extra_info, dict):
            lock_end = extra_info.get("lockEndDate")
            if lock_end:
                lp_locked = True
                try:
                    lock_expiry_timestamp = int(lock_end)
                    lock_dt = datetime.fromtimestamp(lock_expiry_timestamp, tz=timezone.utc)
                    lock_expiry_readable = lock_dt.strftime("%Y-%m-%d %H:%M UTC")
                    now = datetime.now(timezone.utc)
                    days_until_unlock = max(0, (lock_dt - now).days)
                except (ValueError, TypeError, OSError):
                    pass

    # ─── Token info ───────────────────────────────────────────────────
    token_info = pair.get("baseToken", {})

    # ─── Cross-pair liquidity aggregation ─────────────────────────────
    # Tokens trade across many pairs/DEXs. Show the full picture.
    total_liquidity_all_pairs = sum(
        p.get("liquidity", {}).get("usd", 0) for p in pairs
    )
    num_pairs = len(pairs)

    return {
        "name": token_info.get("name"),
        "symbol": token_info.get("symbol"),
        "liquidity_usd": liquidity_usd,
        "price_usd": price_usd,
        "price_native": price_native,
        "pool_token_reserve": pool_token_reserve,
        "pool_eth_reserve": pool_eth_reserve,
        "quote_token_symbol": quote_token_symbol,
        "lp_locked": lp_locked,
        "lock_expiry_timestamp": lock_expiry_timestamp,
        "lock_expiry_readable": lock_expiry_readable,
        "days_until_unlock": days_until_unlock,
        "volume_24h": pair.get("volume", {}).get("h24", 0),
        "price_change_24h": pair.get("priceChange", {}).get("h24", 0),
        "dex_id": pair.get("dexId"),
        "pair_address": pair.get("pairAddress"),
        "total_liquidity_all_pairs": total_liquidity_all_pairs,
        "num_pairs": num_pairs,
        "data_status": "LOW_LIQUIDITY" if liquidity_usd < 100 else "OK",
    }


def _empty() -> dict:
    """Default values when no DEX data is available."""
    return {
        "name": None,
        "symbol": None,
        "liquidity_usd": 0,
        "price_usd": 0,
        "price_native": 0,
        "pool_token_reserve": 0,
        "pool_eth_reserve": 0,
        "quote_token_symbol": "",
        "lp_locked": False,
        "lock_expiry_timestamp": None,
        "lock_expiry_readable": None,
        "days_until_unlock": None,
        "volume_24h": 0,
        "price_change_24h": 0,
        "dex_id": None,
        "pair_address": None,
        "total_liquidity_all_pairs": 0,
        "num_pairs": 0,
        "data_status": "NO_PAIR",
    }
