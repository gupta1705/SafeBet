"""
SafeBet — Module 2 Runner (Orchestrator)

Coordinates the entire Module 2 trap detection pipeline:
1. Gather data from Etherscan + blockchain in parallel
2. Run source scan + on-chain reads
3. Resolve trading pair
4. Run honeypot simulation
5. Apply trap rules
6. Calculate score

This is the single function the scan endpoint calls.
"""

import asyncio
import logging
import time

from schemas.findings import (
    Module2Result, Module1Input, M2ScanRequest,
    SimulationResult, SimulationStatus,
    CheckStatus, PairInfo, ProxyInfo, OnChainSnapshot,
)
from blockchain.module2_contract_reader import read_contract
from blockchain.module2_proxy_detector import detect_proxy
from blockchain.pair_resolver import resolve_pair
from blockchain.sell_simulator import simulate_buy_and_sell
from analyzers.module2_source_scanner import scan_source
from analyzers.trap_rules import evaluate_traps
from analyzers.module2_score import calculate_score
from services import etherscan

from web3 import Web3

logger = logging.getLogger(__name__)


def _is_valid_address(address: str) -> bool:
    try:
        return Web3.is_address(address)
    except Exception:
        return False


async def run_module2(
    token_address: str,
    module1_data: Module1Input | None = None,
    source_code: str | None = None,
) -> Module2Result:
    """
    Execute the full Module 2 trap detection pipeline.

    Args:
        token_address: The token contract address.
        module1_data: Optional Module 1 results (owner, proxy, etc.)
        source_code: Optional source code (if already fetched by Module 1)

    Returns:
        Module2Result with all findings, score, verdict, and raw data.
    """
    start_time = time.time()
    result = Module2Result(token_address=token_address, chain_id=1)

    if not _is_valid_address(token_address):
        result.status = "error"
        result.errors.append(f"Invalid token address: {token_address}")
        return result

    token = Web3.to_checksum_address(token_address)

    # ─────────────────────────────────────────────────────────────────────
    # PHASE 1: Parallel data gathering
    # ─────────────────────────────────────────────────────────────────────
    logger.info(f"⚡ Module 2 starting for {token}")

    pair_task = asyncio.create_task(resolve_pair(token))

    loop = asyncio.get_event_loop()
    proxy_task = loop.run_in_executor(None, detect_proxy, token)
    contract_task = loop.run_in_executor(None, read_contract, token)

    # If no source code provided, fetch it from Etherscan
    if not source_code:
        etherscan_task = asyncio.create_task(_safe_etherscan(token))
    else:
        etherscan_task = None

    pair_info, proxy_info, on_chain = await asyncio.gather(
        pair_task,
        proxy_task,
        contract_task,
        return_exceptions=True,
    )

    etherscan_data = {}
    if etherscan_task:
        etherscan_data = await etherscan_task

    # Handle exceptions from gather
    if isinstance(pair_info, Exception):
        result.errors.append(f"Pair resolution failed: {pair_info}")
        pair_info = PairInfo()
    if isinstance(proxy_info, Exception):
        result.errors.append(f"Proxy detection failed: {proxy_info}")
        proxy_info = ProxyInfo()
    if isinstance(on_chain, Exception):
        result.errors.append(f"Contract reads failed: {on_chain}")
        on_chain = OnChainSnapshot()

    result.proxy_info = proxy_info
    result.pair_info = pair_info
    result.on_chain = on_chain

    if on_chain.name.call_success:
        result.token_name = on_chain.name.value
    if on_chain.symbol.call_success:
        result.token_symbol = on_chain.symbol.value

    # ─────────────────────────────────────────────────────────────────────
    # PHASE 2: Analysis (depends on Phase 1)
    # ─────────────────────────────────────────────────────────────────────
    if not source_code:
        source_code = etherscan_data.get("source_code")

    # If proxy and we got implementation, try to fetch implementation source too
    if proxy_info.is_proxy and proxy_info.implementation_address:
        impl_source = await _safe_impl_source(proxy_info.implementation_address)
        if impl_source:
            combined_source = (source_code or "") + "\n\n" + impl_source
            source_scan = scan_source(combined_source)
        else:
            source_scan = scan_source(source_code)
    else:
        source_scan = scan_source(source_code)

    result.source_scan = source_scan

    # Build Module 1 input from available data if not provided
    if not module1_data:
        module1_data = Module1Input(
            owner_address=on_chain.owner.value if on_chain.owner.call_success else None,
            owner_is_renounced=(
                on_chain.owner.call_success and
                on_chain.owner.value is not None and
                (on_chain.owner.value == "0x0000000000000000000000000000000000000000" or
                 int(on_chain.owner.value, 16) == 0)
            ) if on_chain.owner.call_success and on_chain.owner.value else False,
            is_proxy=proxy_info.is_proxy,
            implementation_address=proxy_info.implementation_address,
            proxy_admin_address=proxy_info.admin_address,
            source_code=source_code,
            is_verified=bool(source_code),
        )

    # ─────────────────────────────────────────────────────────────────────
    # PHASE 3: Honeypot Simulation
    # ─────────────────────────────────────────────────────────────────────
    is_ethereum = not (pair_info.chain_id and pair_info.chain_id != "ethereum") if hasattr(pair_info, 'chain_id') and pair_info.chain_id else True

    if pair_info.found and pair_info.pair_address and pair_info.router_address and is_ethereum:
        decimals = on_chain.decimals.value if on_chain.decimals.call_success else 18
        try:
            simulation = await asyncio.get_event_loop().run_in_executor(
                None,
                simulate_buy_and_sell,
                token,
                pair_info.pair_address,
                pair_info.router_address,
                decimals,
            )
            result.simulation = simulation
        except Exception as e:
            result.errors.append(f"Simulation failed: {e}")
            result.simulation = SimulationResult(
                status=SimulationStatus.ERROR,
                error_detail=str(e),
            )
    elif pair_info.found and not is_ethereum:
        result.simulation = SimulationResult(
            status=SimulationStatus.UNAVAILABLE,
            error_detail=f"Simulation not available for {pair_info.chain_id} chain (Ethereum-only)",
        )
    else:
        result.simulation = SimulationResult(
            status=SimulationStatus.NO_PAIR_FOUND,
            error_detail="No trading pair found for this token",
        )

    # ─────────────────────────────────────────────────────────────────────
    # PHASE 4: Check Status + Trap Rules + Scoring
    # ─────────────────────────────────────────────────────────────────────
    checks = CheckStatus()

    sim = result.simulation
    if sim.status == SimulationStatus.SELLABLE:
        checks.honeypot_simulation = "passed"
    elif sim.status in (SimulationStatus.CONFIRMED_BLOCKED, SimulationStatus.CONFISCATORY_TAX):
        checks.honeypot_simulation = "failed"
    else:
        checks.honeypot_simulation = "not_testable"

    checks.source_code_scan = "scanned" if result.source_scan.source_available else "unverified"
    checks.owner_read = "readable" if result.on_chain.owner.call_success else "not_readable"
    checks.pair_resolution = "found" if result.pair_info.found else "not_found"
    checks.proxy_check = "checked"

    if result.pair_info.found and result.pair_info.chain_id:
        checks.chain_match = "ethereum" if result.pair_info.chain_id == "ethereum" else "other_chain"
    else:
        checks.chain_match = "unknown"

    if result.source_scan.source_available:
        src_cats = result.source_scan.categories
        checks.tax_control = "detected" if src_cats.get("tax_control") and src_cats["tax_control"].found else "clean"
        checks.blacklist_control = "detected" if src_cats.get("blacklist_control") and src_cats["blacklist_control"].found else "clean"
        checks.mint_control = "detected" if src_cats.get("mint_control") and src_cats["mint_control"].found else "clean"
        checks.trading_control = "detected" if src_cats.get("trading_control") and src_cats["trading_control"].found else "clean"
    else:
        checks.tax_control = "unknown"
        checks.blacklist_control = "unknown"
        checks.mint_control = "unknown"
        checks.trading_control = "unknown"

    result.checks_status = checks

    # Evaluate trap rules
    findings = evaluate_traps(
        simulation=result.simulation,
        source_scan=result.source_scan,
        on_chain=result.on_chain,
        proxy_info=result.proxy_info,
        module1=module1_data,
        pair_info=result.pair_info,
    )
    result.findings = findings

    # Calculate score
    score, verdict, summary, data_confidence = calculate_score(findings, checks)
    result.score = score
    result.verdict = verdict
    result.summary = summary
    result.data_confidence = data_confidence

    # ─────────────────────────────────────────────────────────────────────
    # DONE
    # ─────────────────────────────────────────────────────────────────────
    elapsed_ms = int((time.time() - start_time) * 1000)
    result.scan_duration_ms = elapsed_ms

    logger.info(
        f"✅ Module 2 complete for {token}: "
        f"score={score}, verdict={verdict.value}, "
        f"confidence={data_confidence.value}, "
        f"findings={len(findings)}, time={elapsed_ms}ms"
    )

    return result


async def _safe_etherscan(token: str) -> dict:
    """Fetch Etherscan data with error handling."""
    try:
        return await etherscan.get_source_and_abi(token)
    except Exception as e:
        logger.error(f"Etherscan fetch failed: {e}")
        return {}


async def _safe_impl_source(impl_address: str) -> str | None:
    """Fetch implementation source code with error handling."""
    try:
        data = await etherscan.get_source_and_abi(impl_address)
        return data.get("source_code")
    except Exception as e:
        logger.error(f"Implementation source fetch failed: {e}")
        return None
