"""
Deployer Profiler — analyzes the wallet that deployed this token.
Checks how many contracts they've deployed and how many are now dead.

Uses Etherscan API to get transaction history.
"""

import httpx
import os
from datetime import datetime, timezone


async def analyze(deployer_address: str) -> dict:
    """
    Takes a deployer wallet address.
    Returns count of tokens deployed and how many are dead.
    """
    if not deployer_address:
        return _empty()

    api_key = os.getenv("ETHERSCAN_API_KEY")
    if not api_key:
        return _empty()

    try:
        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.get(
                "https://api.etherscan.io/api",
                params={
                    "module": "account",
                    "action": "txlist",
                    "address": deployer_address,
                    "startblock": 0,
                    "endblock": 99999999,
                    "sort": "desc",
                    "offset": 200,   # Last 200 transactions
                    "page": 1,
                    "apikey": api_key,
                }
            )
            data = resp.json()

        txs = data.get("result", [])
        if isinstance(txs, str):
            # Etherscan returns a string message on error
            return _empty()

        # Find contract creation transactions (to="" means contract creation)
        contract_creations = [
            tx for tx in txs
            if tx.get("to") == "" and tx.get("contractAddress")
        ]

        total = len(contract_creations)
        if total == 0:
            return {"total_tokens_deployed": 0, "dead_tokens": 0, "dead_ratio": 0.0}

        # Heuristic: a token is "dead" if it was created more than 60 days ago.
        # In a more complete version we'd check each contract's recent activity,
        # but that would require N additional API calls.
        now = datetime.now(timezone.utc).timestamp()
        dead_count = 0

        for tx in contract_creations:
            created_at = int(tx.get("timeStamp", 0))
            age_days = (now - created_at) / 86400
            if age_days > 60:
                dead_count += 1

        return {
            "total_tokens_deployed": total,
            "dead_tokens": dead_count,
            "dead_ratio": round(dead_count / total, 2) if total > 0 else 0.0,
        }

    except Exception:
        return _empty()


def _empty():
    return {"total_tokens_deployed": 0, "dead_tokens": 0, "dead_ratio": 0.0}
