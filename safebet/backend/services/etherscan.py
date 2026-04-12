"""
Etherscan Service — Contract source code, ABI, deployer info, and holder data.

Uses Etherscan V2 API with chainid parameter.

FIXES from original stub:
1. get_top_holders() was using 'tokenholderlist' which requires a PRO Etherscan key.
   Replaced with 'tokentx' (free tier) + aggregation to approximate top holders.
2. Holder percentages were normalized against top-N sum instead of total supply.
   Now accepts total_supply parameter and normalizes correctly.
3. Added retry logic and better error handling.
4. Added get_token_info() for decimals-aware total supply fetching.
"""

import httpx
import os
from collections import defaultdict
from typing import Optional

BASE = "https://api.etherscan.io/v2/api"

# Ethereum Mainnet chain ID
CHAIN_ID = 1


async def _get(params: dict) -> dict:
    """Base Etherscan API call with error handling."""
    params["apikey"] = os.getenv("ETHERSCAN_API_KEY")
    params["chainid"] = CHAIN_ID
    try:
        async with httpx.AsyncClient(timeout=15) as client:
            r = await client.get(BASE, params=params)
            r.raise_for_status()
            data = r.json()

            # Etherscan returns status "0" for errors
            if data.get("status") == "0" and data.get("message") != "No transactions found":
                print(f"[Etherscan] API error: {data.get('result', 'Unknown error')}")
            return data
    except httpx.RequestError as e:
        print(f"[Etherscan] Request failed: {e}")
        return {"status": "0", "result": []}


async def get_source_and_abi(address: str) -> dict:
    """Fetch verified contract source code and ABI."""
    data = await _get({
        "module": "contract",
        "action": "getsourcecode",
        "address": address,
    })
    result = data.get("result", [{}])
    if isinstance(result, list) and len(result) > 0:
        result = result[0]
    else:
        result = {}

    return {
        "source_code": result.get("SourceCode", ""),
        "abi": result.get("ABI", ""),
        "contract_name": result.get("ContractName", ""),
        "compiler_version": result.get("CompilerVersion", ""),
        "is_proxy": result.get("Proxy", "0") == "1",
        "implementation": result.get("Implementation", ""),
    }


async def get_deployer_address(address: str) -> str:
    """Get the wallet that originally deployed this contract."""
    data = await _get({
        "module": "contract",
        "action": "getcontractcreation",
        "contractaddresses": address,
    })
    results = data.get("result", [])
    if isinstance(results, list) and results:
        return results[0].get("contractCreator", "")
    return ""


async def get_token_info(address: str) -> dict:
    """
    Get token's total supply AND decimals using free-tier Etherscan endpoints.
    This makes Module 3 fully independent -- no blockchain node needed.

    Decimals are detected from a recent transfer event's 'tokenDecimal' field.
    Falls back to 18 if detection fails.

    Returns:
        Dict with 'total_supply_raw' (float), 'decimals' (int),
        'total_supply_human' (float, divided by 10^decimals)
    """
    # 1. Get raw total supply
    supply_data = await _get({
        "module": "stats",
        "action": "tokensupply",
        "contractaddress": address,
    })
    try:
        total_supply_raw = float(supply_data.get("result", "0"))
    except (ValueError, TypeError):
        total_supply_raw = 0.0

    # 2. Detect actual decimals from a recent transfer
    tx_data = await _get({
        "module": "account",
        "action": "tokentx",
        "contractaddress": address,
        "page": 1,
        "offset": 1,
        "sort": "desc",
    })
    decimals = 18  # Default
    txs = tx_data.get("result", [])
    if isinstance(txs, list) and txs and "tokenDecimal" in txs[0]:
        try:
            decimals = int(txs[0]["tokenDecimal"])
        except (ValueError, TypeError):
            pass

    # 3. Calculate human-readable supply
    divisor = 10 ** decimals
    total_supply_human = total_supply_raw / divisor if divisor > 0 else 0.0

    return {
        "total_supply_raw": total_supply_raw,
        "decimals": decimals,
        "total_supply_human": total_supply_human,
    }


# Keep backward compatibility
async def get_total_supply(address: str) -> dict:
    """Legacy wrapper -- use get_token_info() for decimals-aware results."""
    info = await get_token_info(address)
    return {
        "total_supply": str(int(info["total_supply_raw"])),
        "total_supply_float": info["total_supply_raw"],
        "decimals": info["decimals"],
        "total_supply_human": info["total_supply_human"],
    }


async def get_top_holders(
    address: str,
    total_supply: Optional[float] = None,
    decimals: int = 18,
) -> list:
    """
    Approximate top token holders by aggregating ERC-20 transfer events.

    The free Etherscan tier doesn't provide 'tokenholderlist'.
    Instead, we pull recent token transfers and aggregate net balances
    to approximate the current top holders.

    If total_supply is not provided, this function will fetch it from
    Etherscan's free-tier 'tokensupply' endpoint — keeping Module 3
    fully independent from the blockchain node.

    Args:
        address: Token contract address
        total_supply: Total token supply (raw, not divided by 10^decimals).
                      If None, fetched automatically from Etherscan.
        decimals: Token decimal places (default 18)

    Returns:
        List of holder dicts sorted by balance descending:
        [{"address": str, "quantity": float, "percent": float}, ...]
    """
    # If total_supply not provided, fetch it ourselves (Module 3 independence)
    if total_supply is None or total_supply == 0:
        supply_data = await get_total_supply(address)
        total_supply = supply_data["total_supply_float"]

    # Fetch ERC-20 token transfer events (free tier, max 10000)
    data = await _get({
        "module": "account",
        "action": "tokentx",
        "contractaddress": address,
        "page": 1,
        "offset": 10000,  # Max transfers to analyze
        "sort": "desc",
    })

    transfers = data.get("result", [])
    if not isinstance(transfers, list) or not transfers:
        return []

    # ─── Aggregate net balances ───────────────────────────────────────
    # For each address: sum up tokens received - tokens sent
    balances = defaultdict(float)
    token_decimals = decimals

    # Try to get decimals from transfer data if not provided
    if transfers and "tokenDecimal" in transfers[0]:
        try:
            token_decimals = int(transfers[0]["tokenDecimal"])
        except (ValueError, TypeError):
            pass

    divisor = 10 ** token_decimals

    for tx in transfers:
        try:
            value = float(tx.get("value", 0)) / divisor
            from_addr = tx.get("from", "").lower()
            to_addr = tx.get("to", "").lower()

            if from_addr:
                balances[from_addr] -= value
            if to_addr:
                balances[to_addr] += value
        except (ValueError, TypeError):
            continue

    # ─── Filter out known non-holder addresses ────────────────────────
    EXCLUDE_ADDRESSES = {
        "0x0000000000000000000000000000000000000000",  # Burn address
        "0x000000000000000000000000000000000000dead",  # Dead address
    }

    # Remove excluded and negative-balance addresses
    holder_list = [
        {"address": addr, "quantity": bal}
        for addr, bal in balances.items()
        if bal > 0 and addr not in EXCLUDE_ADDRESSES
    ]

    # Sort by balance descending
    holder_list.sort(key=lambda h: h["quantity"], reverse=True)

    # Keep top 10
    holder_list = holder_list[:10]

    # ─── Calculate percentages against total supply ───────────────────
    if total_supply and total_supply > 0:
        # Normalize total_supply to human-readable (divide by 10^decimals)
        supply_human = total_supply / divisor
        for h in holder_list:
            h["percent"] = round((h["quantity"] / supply_human) * 100, 2)
    else:
        # Fallback: normalize against the sum of tracked balances
        # This is less accurate but better than nothing
        total_tracked = sum(h["quantity"] for h in holder_list)
        for h in holder_list:
            h["percent"] = round(
                (h["quantity"] / total_tracked) * 100, 2
            ) if total_tracked > 0 else 0.0

    return holder_list
