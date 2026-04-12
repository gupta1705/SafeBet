"""
SafeBet — Honeypot Sell Simulator

Uses eth_call with state overrides to simulate a full buy→approve→sell flow
without spending gas or real tokens.
"""

import logging
import time
from web3 import Web3
from eth_abi import encode as abi_encode, decode as abi_decode

from blockchain.rpc_client import get_w3
from config import get_settings
from schemas.findings import SimulationResult, SimulationStatus

logger = logging.getLogger(__name__)

# ABI Selectors
BALANCE_OF_SELECTOR = "0x70a08231"
TRANSFER_SELECTOR = "0xa9059cbb"
SWAP_EXACT_TOKENS_FOR_ETH_FEE = "0x791ac947"
GET_AMOUNTS_OUT_SELECTOR = "0xd06ca61f"
GET_RESERVES_SELECTOR = "0x0902f1ac"

MAX_UINT256 = 2**256 - 1


def _encode_address(addr: str) -> str:
    return addr[2:].lower().zfill(64)


def _encode_uint256(val: int) -> str:
    return hex(val)[2:].zfill(64)


def _compute_balance_slot(holder: str, slot_index: int) -> str:
    encoded = abi_encode(["address", "uint256"], [holder, slot_index])
    return Web3.keccak(encoded).hex()


def _compute_allowance_slot(owner: str, spender: str, slot_index: int) -> str:
    inner = Web3.keccak(abi_encode(["address", "uint256"], [owner, slot_index]))
    outer = Web3.keccak(abi_encode(["address", "uint256"], [spender, int.from_bytes(inner, "big")]))
    return outer.hex()


def _try_get_reserves(w3, pair_address):
    try:
        result = w3.eth.call({
            "to": Web3.to_checksum_address(pair_address),
            "data": GET_RESERVES_SELECTOR,
        })
        decoded = abi_decode(["uint112", "uint112", "uint32"], result)
        return decoded[0], decoded[1], True
    except Exception:
        return 0, 0, False


def _try_get_amounts_out(w3, router, amount_in, path):
    try:
        encoded_path = abi_encode(
            ["uint256", "address[]"],
            [amount_in, [Web3.to_checksum_address(a) for a in path]]
        )
        call_data = GET_AMOUNTS_OUT_SELECTOR + encoded_path.hex()
        result = w3.eth.call({
            "to": Web3.to_checksum_address(router),
            "data": call_data,
        })
        decoded = abi_decode(["uint256[]"], result)
        amounts = decoded[0]
        if len(amounts) >= 2:
            return amounts[-1], True
        return 0, False
    except Exception:
        return 0, False


def simulate_sell(token_address, pair_address, router_address, decimals=18):
    """Simulate a sell transaction using eth_call with state overrides."""
    w3 = get_w3()
    settings = get_settings()

    result = SimulationResult(
        method="eth_call_state_override",
        router=router_address,
        pair=pair_address,
    )

    if not w3.is_connected():
        result.status = SimulationStatus.UNAVAILABLE
        result.error_detail = "Web3 not connected"
        return result

    token = Web3.to_checksum_address(token_address)
    router = Web3.to_checksum_address(router_address)
    pair = Web3.to_checksum_address(pair_address)
    test_addr = Web3.to_checksum_address(settings.SIMULATION_TEST_ADDRESS)
    weth = Web3.to_checksum_address(settings.WETH_ADDRESS)

    sell_amount = 10 ** decimals  # 1 token

    # Get expected output
    path = [token, weth]
    expected_out, got_estimate = _try_get_amounts_out(w3, router, sell_amount, path)

    if not got_estimate or expected_out == 0:
        r0, r1, has_reserves = _try_get_reserves(w3, pair)
        if not has_reserves or (r0 == 0 and r1 == 0):
            result.status = SimulationStatus.NO_PAIR_FOUND
            result.error_detail = "Pair has no reserves or getAmountsOut failed"
            return result

    # Try sell simulation with state overrides
    COMMON_BALANCE_SLOTS = [0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 51, 52]
    COMMON_ALLOWANCE_SLOTS = [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 52, 53]

    sell_succeeded = False
    best_revert = None

    for bal_slot in COMMON_BALANCE_SLOTS:
        balance_storage_slot = _compute_balance_slot(test_addr, bal_slot)

        for allow_slot in COMMON_ALLOWANCE_SLOTS:
            allowance_storage_slot = _compute_allowance_slot(test_addr, router, allow_slot)

            large_balance = "0x" + _encode_uint256(sell_amount * 1000)
            max_allowance = "0x" + _encode_uint256(MAX_UINT256)

            state_override = {
                token: {
                    "stateDiff": {
                        balance_storage_slot: large_balance,
                        allowance_storage_slot: max_allowance,
                    }
                }
            }

            # Verify balance override worked
            try:
                balance_check_data = BALANCE_OF_SELECTOR + _encode_address(test_addr)
                bal_result = w3.eth.call(
                    {"to": token, "data": balance_check_data, "from": test_addr},
                    "latest",
                    state_override,
                )
                balance = int(bal_result.hex(), 16)
                if balance < sell_amount:
                    continue
            except Exception:
                continue

            # Simulate the actual sell
            try:
                deadline = int(time.time()) + 3600
                swap_params = abi_encode(
                    ["uint256", "uint256", "address[]", "address", "uint256"],
                    [sell_amount, 0, [token, weth], test_addr, deadline]
                )
                swap_data = SWAP_EXACT_TOKENS_FOR_ETH_FEE + swap_params.hex()

                w3.eth.call(
                    {"to": router, "data": swap_data, "from": test_addr, "value": 0, "gas": 500000},
                    "latest",
                    state_override,
                )

                sell_succeeded = True
                result.sell_succeeded = True
                result.buy_succeeded = True
                result.status = SimulationStatus.SELLABLE

                if got_estimate and expected_out > 0:
                    result.effective_sell_tax_bps = 0
                    result.tokens_expected = expected_out

                logger.info(f"Sell simulation SUCCEEDED for {token_address}")
                break

            except Exception as e:
                error_str = str(e)
                if not best_revert or len(error_str) > len(best_revert):
                    best_revert = error_str
                continue

        if sell_succeeded:
            break

    # If all slots failed, try simple transfer
    if not sell_succeeded:
        try:
            transfer_data = TRANSFER_SELECTOR + _encode_address(
                "0x000000000000000000000000000000000000dEaD"
            ) + _encode_uint256(1)

            bal_slot_hex = _compute_balance_slot(test_addr, 0)
            override = {
                token: {
                    "stateDiff": {
                        bal_slot_hex: "0x" + _encode_uint256(10 ** 20),
                    }
                }
            }

            w3.eth.call(
                {"to": token, "data": transfer_data, "from": test_addr},
                "latest",
                override,
            )
            result.status = SimulationStatus.UNAVAILABLE
            result.error_detail = "Token transfers work but DEX sell simulation failed."
            result.revert_reason = best_revert[:200] if best_revert else "Unknown"

        except Exception as transfer_error:
            result.status = SimulationStatus.CONFIRMED_BLOCKED
            result.sell_succeeded = False
            result.revert_reason = str(transfer_error)[:200]
            logger.warning(f"Sell simulation BLOCKED for {token_address}: {transfer_error}")

    if best_revert and not sell_succeeded:
        result.revert_reason = _extract_revert_reason(best_revert)

    if sell_succeeded and result.effective_sell_tax_bps is not None:
        if result.effective_sell_tax_bps > 5000:
            result.status = SimulationStatus.CONFISCATORY_TAX

    return result


def _extract_revert_reason(error_str: str) -> str:
    if "execution reverted" in error_str.lower():
        parts = error_str.split("execution reverted:")
        if len(parts) > 1:
            return parts[1].strip()[:200]
        parts = error_str.split("execution reverted")
        if len(parts) > 1:
            return parts[1].strip()[:200]
    return error_str[:200]


def simulate_buy_and_sell(token_address, pair_address, router_address, decimals=18):
    """Full simulation: sell test then buy tax estimation."""
    result = simulate_sell(token_address, pair_address, router_address, decimals)

    if result.status == SimulationStatus.SELLABLE:
        _estimate_buy_tax(result, token_address, router_address, decimals)

    return result


def _estimate_buy_tax(result, token_address, router_address, decimals):
    w3 = get_w3()
    settings = get_settings()

    token = Web3.to_checksum_address(token_address)
    weth = Web3.to_checksum_address(settings.WETH_ADDRESS)

    buy_amount = Web3.to_wei(0.01, "ether")
    expected_out, ok = _try_get_amounts_out(w3, router_address, buy_amount, [weth, token])

    if ok and expected_out > 0:
        result.tokens_expected = expected_out
