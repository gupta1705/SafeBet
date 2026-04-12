"""
SafeBet — Module 2 Contract Reader

Reads on-chain values from token contracts using minimal ABI fragments.
Every call wrapped in error handling — failed read returns (None, False), never crashes.
"""

import logging
from web3 import Web3
from eth_abi import decode as abi_decode

from blockchain.rpc_client import get_w3
from schemas.findings import OnChainRead, OnChainSnapshot

logger = logging.getLogger(__name__)

ZERO_ADDRESS = "0x0000000000000000000000000000000000000000"

SELECTORS = {
    "owner": "0x8da5cb5b",
    "tradingActive": "0xbbc0c742",
    "tradingOpen": "0xfd72e22a",
    "swapEnabled": "0x6ddd1713",
    "tradingEnabled": "0x4ada218b",
    "buyTax": "0x9bb0e21a",
    "sellTax": "0x61cd75da",
    "totalFees": "0x13114a9d",
    "_buyTax": "0xd7d7442f",
    "_sellTax": "0x4f7041a5",
    "buyTotalFees": "0x9c2e4ac6",
    "sellTotalFees": "0xe13b2007",
    "maxTxAmount": "0x8c0b5e22",
    "maxWallet": "0xf8b45b05",
    "maxTransactionAmount": "0xc8c8ebe4",
    "name": "0x06fdde03",
    "symbol": "0x95d89b41",
    "decimals": "0x313ce567",
    "totalSupply": "0x18160ddd",
}


def _safe_call(w3: Web3, contract_address: str, data: str) -> tuple[bytes | None, bool]:
    """Make a safe eth_call that never throws."""
    try:
        result = w3.eth.call({
            "to": Web3.to_checksum_address(contract_address),
            "data": data,
        })
        return result, True
    except Exception as e:
        logger.debug(f"Call to {contract_address} with {data[:10]}... failed: {e}")
        return None, False


def _call_and_decode_address(w3, token, selector):
    result, success = _safe_call(w3, token, selector)
    if not success or not result or len(result) < 32:
        return None, False
    try:
        addr = "0x" + result.hex()[-40:]
        return Web3.to_checksum_address(addr), True
    except Exception:
        return None, False


def _call_and_decode_uint(w3, token, selector):
    result, success = _safe_call(w3, token, selector)
    if not success or not result:
        return None, False
    try:
        decoded = abi_decode(["uint256"], result)
        return decoded[0], True
    except Exception:
        return None, False


def _call_and_decode_bool(w3, token, selector):
    result, success = _safe_call(w3, token, selector)
    if not success or not result:
        return None, False
    try:
        decoded = abi_decode(["bool"], result)
        return decoded[0], True
    except Exception:
        try:
            decoded = abi_decode(["uint256"], result)
            return decoded[0] != 0, True
        except Exception:
            return None, False


def _call_and_decode_string(w3, token, selector):
    result, success = _safe_call(w3, token, selector)
    if not success or not result:
        return None, False
    try:
        decoded = abi_decode(["string"], result)
        return decoded[0], True
    except Exception:
        try:
            text = result.decode("utf-8", errors="ignore").strip("\x00").strip()
            if text:
                return text, True
        except Exception:
            pass
        return None, False


def _make_read(func_name, value, success, error=None):
    return OnChainRead(function_name=func_name, value=value, call_success=success, raw_error=error)


def read_contract(token_address: str) -> OnChainSnapshot:
    """Read all relevant on-chain values from a token contract."""
    w3 = get_w3()
    snapshot = OnChainSnapshot()
    token = Web3.to_checksum_address(token_address)

    if not w3.is_connected():
        logger.warning("Web3 not connected — contract reads unavailable")
        return snapshot

    # Owner
    addr, ok = _call_and_decode_address(w3, token, SELECTORS["owner"])
    snapshot.owner = _make_read("owner", addr, ok)

    # Trading Flags
    for flag_name in ["tradingActive", "tradingOpen", "swapEnabled"]:
        val, ok = _call_and_decode_bool(w3, token, SELECTORS[flag_name])
        if ok:
            attr_name = flag_name.replace("tradingActive", "trading_active") \
                                  .replace("tradingOpen", "trading_open") \
                                  .replace("swapEnabled", "swap_enabled")
            setattr(snapshot, attr_name, _make_read(flag_name, val, ok))
            break

    if not snapshot.trading_active.call_success:
        val, ok = _call_and_decode_bool(w3, token, SELECTORS.get("tradingEnabled", ""))
        if ok:
            snapshot.trading_active = _make_read("tradingEnabled", val, ok)

    # Fee Values
    for getter in ["buyTax", "_buyTax", "buyTotalFees"]:
        if getter in SELECTORS:
            val, ok = _call_and_decode_uint(w3, token, SELECTORS[getter])
            if ok:
                snapshot.buy_tax = _make_read(getter, val, ok)
                break

    for getter in ["sellTax", "_sellTax", "sellTotalFees"]:
        if getter in SELECTORS:
            val, ok = _call_and_decode_uint(w3, token, SELECTORS[getter])
            if ok:
                snapshot.sell_tax = _make_read(getter, val, ok)
                break

    val, ok = _call_and_decode_uint(w3, token, SELECTORS["totalFees"])
    if ok:
        snapshot.total_fees = _make_read("totalFees", val, ok)

    # Limits
    for getter in ["maxTxAmount", "maxTransactionAmount"]:
        val, ok = _call_and_decode_uint(w3, token, SELECTORS[getter])
        if ok:
            snapshot.max_tx_amount = _make_read(getter, val, ok)
            break

    val, ok = _call_and_decode_uint(w3, token, SELECTORS["maxWallet"])
    if ok:
        snapshot.max_wallet = _make_read("maxWallet", val, ok)

    # Token Metadata
    name, ok = _call_and_decode_string(w3, token, SELECTORS["name"])
    snapshot.name = _make_read("name", name, ok)

    symbol, ok = _call_and_decode_string(w3, token, SELECTORS["symbol"])
    snapshot.symbol = _make_read("symbol", symbol, ok)

    decimals, ok = _call_and_decode_uint(w3, token, SELECTORS["decimals"])
    snapshot.decimals = _make_read("decimals", decimals if ok else 18, ok)

    supply, ok = _call_and_decode_uint(w3, token, SELECTORS["totalSupply"])
    snapshot.total_supply = _make_read("totalSupply", supply, ok)

    logger.info(f"Module 2 contract reads complete for {token_address}")
    return snapshot
