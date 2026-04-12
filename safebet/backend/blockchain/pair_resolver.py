"""
SafeBet — Pair Resolver

Finds the primary trading pair for a token by:
1. Querying DexScreener API (fast, no RPC needed)
2. Falling back to Uniswap V2 factory getPair() on-chain
"""

import logging
import httpx
from web3 import Web3

from blockchain.rpc_client import get_w3
from config import get_settings
from schemas.findings import PairInfo

logger = logging.getLogger(__name__)

GET_PAIR_SELECTOR = "0xe6a43905"

KNOWN_ROUTERS = {
    "uniswap_v2": "0x7a250d5630B4cF539739dF2C5dAcb4c659F2488D",
    "sushiswap": "0xd9e1cE17f2641f24aE83637ab66a2cca9C378B9F",
}


async def resolve_pair_dexscreener(token_address: str) -> PairInfo | None:
    """Query DexScreener API to find the primary trading pair."""
    settings = get_settings()
    url = f"{settings.DEXSCREENER_BASE_URL}/tokens/{token_address}"

    try:
        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.get(url)
            resp.raise_for_status()
            data = resp.json()

        pairs = data.get("pairs", [])
        if not pairs:
            return None

        eth_pairs = [p for p in pairs if p.get("chainId") == "ethereum"]
        if not eth_pairs:
            eth_pairs = pairs

        eth_pairs.sort(key=lambda p: p.get("liquidity", {}).get("usd", 0), reverse=True)
        best = eth_pairs[0]

        pair_address = best.get("pairAddress", "")
        dex_id = best.get("dexId", "unknown")

        router = None
        if "uniswap" in dex_id.lower():
            router = KNOWN_ROUTERS["uniswap_v2"]
        elif "sushi" in dex_id.lower():
            router = KNOWN_ROUTERS["sushiswap"]
        else:
            router = KNOWN_ROUTERS["uniswap_v2"]

        return PairInfo(
            pair_address=pair_address,
            token0=best.get("baseToken", {}).get("address"),
            token1=best.get("quoteToken", {}).get("address"),
            router_address=router,
            dex_name=dex_id,
            liquidity_usd=best.get("liquidity", {}).get("usd"),
            price_usd=float(best.get("priceUsd", 0)) if best.get("priceUsd") else None,
            volume_24h_usd=best.get("volume", {}).get("h24"),
            chain_id=best.get("chainId"),
            found=True,
        )

    except Exception as e:
        logger.warning(f"DexScreener lookup failed: {e}")
        return None


def resolve_pair_onchain(token_address: str) -> PairInfo | None:
    """Fall back to on-chain pair resolution via Uniswap V2 Factory."""
    w3 = get_w3()
    settings = get_settings()

    if not w3.is_connected():
        return None

    try:
        token = Web3.to_checksum_address(token_address)
        weth = Web3.to_checksum_address(settings.WETH_ADDRESS)
        factory = Web3.to_checksum_address(settings.UNISWAP_V2_FACTORY)

        token_padded = token[2:].lower().zfill(64)
        weth_padded = weth[2:].lower().zfill(64)
        call_data = GET_PAIR_SELECTOR + token_padded + weth_padded

        result = w3.eth.call({"to": factory, "data": call_data})
        pair_addr = "0x" + result.hex()[-40:]

        if pair_addr == "0x" + "0" * 40 or int(pair_addr, 16) == 0:
            return None

        return PairInfo(
            pair_address=Web3.to_checksum_address(pair_addr),
            token0=token,
            token1=weth,
            router_address=settings.UNISWAP_V2_ROUTER,
            dex_name="uniswap_v2",
            found=True,
        )

    except Exception as e:
        logger.warning(f"On-chain pair resolution failed: {e}")
        return None


async def resolve_pair(token_address: str) -> PairInfo:
    """Try DexScreener first, then on-chain."""
    pair = await resolve_pair_dexscreener(token_address)
    if pair and pair.found:
        logger.info(f"Pair found via DexScreener: {pair.pair_address} on {pair.dex_name}")
        return pair

    pair = resolve_pair_onchain(token_address)
    if pair and pair.found:
        logger.info(f"Pair found on-chain: {pair.pair_address}")
        return pair

    logger.warning(f"No trading pair found for {token_address}")
    return PairInfo(found=False)
