"""
LP Lock Verifier -- On-chain verification of LP token lock/burn status.

DexScreener labels are unreliable for LP lock detection. This module
checks the actual on-chain state by querying LP token balances at:
  1. Known burn addresses (0x0...dead, 0x0...0000)
  2. Known locker contracts (Unicrypt, PinkLock, Team Finance)
  3. LP token total supply to calculate lock percentage

This runs via Etherscan API (free tier) -- no blockchain node needed.
"""

import os
import httpx
from datetime import datetime, timezone

BASE = "https://api.etherscan.io/v2/api"
CHAIN_ID = 1

# Addresses where LP tokens are permanently destroyed
BURN_ADDRESSES = [
    "0x000000000000000000000000000000000000dead",
    "0x0000000000000000000000000000000000000000",
    "0x0000000000000000000000000000000000000001",  # Some protocols burn here
]

# Well-known locker contracts on Ethereum
LOCKER_CONTRACTS = {
    "0x663a5c229c09b049e36dcc11a9b0d4a8eb9db214": "Unicrypt",
    "0x71b5759d73262fbb223956913ecf4ecc51057641": "PinkLock V1",
    "0x407993575c91ce7643a4d4ccacc9a98c36f00290": "PinkLock V2",
    "0xe2fe530c047f2d85298b07d9333c05d6e0c8e7eb": "Team Finance",
    "0xdead000000000000000000000000000000000000": "Burn (alt dead)",
}


async def _etherscan_get(params: dict) -> dict:
    """Make an Etherscan API V2 call."""
    params["apikey"] = os.getenv("ETHERSCAN_API_KEY")
    params["chainid"] = CHAIN_ID
    try:
        async with httpx.AsyncClient(timeout=15) as client:
            r = await client.get(BASE, params=params)
            r.raise_for_status()
            return r.json()
    except Exception as e:
        print(f"[LP Verifier] API error: {e}")
        return {"result": "0"}


async def verify_lp_lock(pair_address: str) -> dict:
    """
    Check the on-chain LP lock/burn status for a Uniswap V2 pair.

    Args:
        pair_address: The Uniswap V2 pair contract address (LP token address)

    Returns:
        Dict with lock status, burn percentage, locker name, and details:
        {
            "lp_locked": bool,
            "lp_burned": bool,
            "lock_method": str,            # "burned" / "locked_unicrypt" / "locked_pinklock" / "none"
            "locked_percent": float,        # % of LP supply locked/burned
            "burned_percent": float,        # % specifically burned (subset of locked)
            "total_secured_percent": float, # burned + locked
            "locker_name": str | None,      # "Unicrypt", "PinkLock", etc.
            "locker_address": str | None,
            "lp_total_supply": float,
            "consequence": str,             # Human-readable consequence sentence
        }
    """
    if not pair_address:
        return _empty("No pair address provided")

    # Step 1: Get LP token total supply
    supply_data = await _etherscan_get({
        "module": "stats",
        "action": "tokensupply",
        "contractaddress": pair_address,
    })

    try:
        total_supply_raw = int(supply_data.get("result", "0"))
    except (ValueError, TypeError):
        total_supply_raw = 0

    if total_supply_raw <= 0:
        return _empty("Could not fetch LP token supply")

    total_supply = total_supply_raw / 1e18  # LP tokens use 18 decimals

    # Step 2: Check burn addresses
    burned_amount = 0
    for addr in BURN_ADDRESSES:
        bal_data = await _etherscan_get({
            "module": "account",
            "action": "tokenbalance",
            "contractaddress": pair_address,
            "address": addr,
        })
        try:
            bal = int(bal_data.get("result", "0"))
            burned_amount += bal
        except (ValueError, TypeError):
            continue

    burned_percent = (burned_amount / total_supply_raw * 100) if total_supply_raw > 0 else 0

    # Step 3: Check known locker contracts
    locked_amount = 0
    locker_name = None
    locker_address = None

    for addr, name in LOCKER_CONTRACTS.items():
        bal_data = await _etherscan_get({
            "module": "account",
            "action": "tokenbalance",
            "contractaddress": pair_address,
            "address": addr,
        })
        try:
            bal = int(bal_data.get("result", "0"))
            if bal > 0:
                locked_amount += bal
                # Track the largest locker
                if locker_name is None or bal > locked_amount - bal:
                    locker_name = name
                    locker_address = addr
        except (ValueError, TypeError):
            continue

    locked_percent = (locked_amount / total_supply_raw * 100) if total_supply_raw > 0 else 0
    total_secured_percent = burned_percent + locked_percent

    # Step 4: Determine status and build consequence sentence
    lp_burned = burned_percent >= 90
    lp_locked = locked_percent >= 50 or lp_burned or total_secured_percent >= 80

    if lp_burned:
        lock_method = "burned"
        consequence = (
            f"Liquidity is permanently safe. {burned_percent:.1f}% of LP tokens have been "
            f"burned (destroyed forever). The developer cannot withdraw liquidity."
        )
    elif locked_percent >= 50:
        lock_method = f"locked_{locker_name.lower().replace(' ', '_')}" if locker_name else "locked_unknown"
        consequence = (
            f"Liquidity is locked via {locker_name}. {locked_percent:.1f}% of LP tokens "
            f"are held in the locker contract. Check the locker for unlock date."
        )
    elif total_secured_percent >= 10:
        lock_method = "partially_secured"
        consequence = (
            f"Only {total_secured_percent:.1f}% of LP is secured ({burned_percent:.1f}% burned, "
            f"{locked_percent:.1f}% locked). The remaining {100 - total_secured_percent:.1f}% "
            f"can be withdrawn by the owner at any time."
        )
    else:
        lock_method = "none"
        consequence = (
            f"Liquidity is NOT locked or burned. The LP owner can withdraw all trading "
            f"liquidity at any moment, making your tokens unsellable."
        )

    return {
        "lp_locked": lp_locked,
        "lp_burned": lp_burned,
        "lock_method": lock_method,
        "locked_percent": round(locked_percent, 2),
        "burned_percent": round(burned_percent, 2),
        "total_secured_percent": round(total_secured_percent, 2),
        "locker_name": locker_name,
        "locker_address": locker_address,
        "lp_total_supply": round(total_supply, 4),
        "consequence": consequence,
    }


def _empty(reason: str = "Unknown") -> dict:
    return {
        "lp_locked": False,
        "lp_burned": False,
        "lock_method": "unknown",
        "locked_percent": 0.0,
        "burned_percent": 0.0,
        "total_secured_percent": 0.0,
        "locker_name": None,
        "locker_address": None,
        "lp_total_supply": 0.0,
        "consequence": f"LP lock status could not be verified: {reason}",
    }
