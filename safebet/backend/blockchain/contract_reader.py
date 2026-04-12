"""
Directly calls read-only functions on the token contract via Web3.
Uses a minimal ABI covering standard ERC-20 + common tax/owner functions.
Each call is individually wrapped so one failure doesn't break the rest.
"""

import asyncio
from web3 import Web3
from .rpc_client import get_w3

# Minimal ABI — only the functions we want to read
MINIMAL_TOKEN_ABI = [
    # Standard ERC-20
    {"name": "name", "type": "function", "inputs": [], "outputs": [{"type": "string"}], "stateMutability": "view"},
    {"name": "symbol", "type": "function", "inputs": [], "outputs": [{"type": "string"}], "stateMutability": "view"},
    {"name": "decimals", "type": "function", "inputs": [], "outputs": [{"type": "uint8"}], "stateMutability": "view"},
    {"name": "totalSupply", "type": "function", "inputs": [], "outputs": [{"type": "uint256"}], "stateMutability": "view"},
    # Ownership
    {"name": "owner", "type": "function", "inputs": [], "outputs": [{"type": "address"}], "stateMutability": "view"},
    {"name": "getOwner", "type": "function", "inputs": [], "outputs": [{"type": "address"}], "stateMutability": "view"},
    # Tax (common naming patterns in fee-on-transfer tokens)
    {"name": "_taxFee", "type": "function", "inputs": [], "outputs": [{"type": "uint256"}], "stateMutability": "view"},
    {"name": "_sellTax", "type": "function", "inputs": [], "outputs": [{"type": "uint256"}], "stateMutability": "view"},
    {"name": "_buyTax", "type": "function", "inputs": [], "outputs": [{"type": "uint256"}], "stateMutability": "view"},
    {"name": "sellFee", "type": "function", "inputs": [], "outputs": [{"type": "uint256"}], "stateMutability": "view"},
    {"name": "buyFee", "type": "function", "inputs": [], "outputs": [{"type": "uint256"}], "stateMutability": "view"},
    {"name": "totalFees", "type": "function", "inputs": [], "outputs": [{"type": "uint256"}], "stateMutability": "view"},
]

ZERO_ADDRESS = "0x0000000000000000000000000000000000000000"
DEAD_ADDRESS = "0x000000000000000000000000000000000000dEaD"


async def read_contract_values(token_address: str) -> dict:
    """
    Reads on-chain values from the token contract.
    Returns owner, tax values, total supply, decimals.
    """
    def _read_all():
        w3 = get_w3()
        checksum = Web3.to_checksum_address(token_address)
        contract = w3.eth.contract(address=checksum, abi=MINIMAL_TOKEN_ABI)

        def safe_call(fn_name):
            try:
                return getattr(contract.functions, fn_name)().call()
            except Exception:
                return None

        result = {}

        # ── Owner ───────────────────────────────────────────
        owner = safe_call("owner") or safe_call("getOwner")
        result["owner"] = owner
        result["ownership_renounced"] = (
            owner is None
            or owner == ZERO_ADDRESS
            or owner.lower() == DEAD_ADDRESS.lower()
        )

        # ── Tax Values ──────────────────────────────────────
        # Try multiple common naming patterns
        sell_tax_raw = (
            safe_call("_sellTax")
            or safe_call("sellFee")
            or safe_call("_taxFee")
            or 0
        )
        buy_tax_raw = (
            safe_call("_buyTax")
            or safe_call("buyFee")
            or sell_tax_raw
            or 0
        )

        # Normalize: contracts often store tax * 100 (e.g. 300 = 3%)
        result["sell_tax"] = sell_tax_raw / 100 if sell_tax_raw > 100 else sell_tax_raw
        result["buy_tax"] = buy_tax_raw / 100 if buy_tax_raw > 100 else buy_tax_raw

        # ── Token Metadata ──────────────────────────────────
        result["total_supply"] = safe_call("totalSupply")
        result["decimals"] = safe_call("decimals") or 18
        result["name"] = safe_call("name")
        result["symbol"] = safe_call("symbol")

        return result

    return await asyncio.to_thread(_read_all)
