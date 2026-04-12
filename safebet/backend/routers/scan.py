"""
POST /api/scan — The one endpoint.
Orchestrates all modules in parallel, assembles the report.
"""

import asyncio
import time
from fastapi import APIRouter, HTTPException
from models.schemas import ScanRequest, SafeBetReport, Module1Data, Module2Data, Module2Finding, Module3Data
from blockchain import rpc_client, proxy_detector, contract_reader, honeypot_simulator
from analyzers import source_scanner, dump_calculator, trust_score, deployer_profiler
from services import etherscan, dexscreener, ai_engine
from services import lp_verifier

router = APIRouter()


async def _lp_fallback():
    """Async no-op for when there's no pair address to verify."""
    return lp_verifier._empty("No pair address")


@router.post("/scan", response_model=SafeBetReport)
async def scan_token(request: ScanRequest):
    address = request.address.strip().lower()

    # Validate Ethereum address format
    if not address.startswith("0x") or len(address) != 42:
        raise HTTPException(status_code=400, detail="Invalid Ethereum address")

    # Verify it's actually a hex string
    try:
        int(address, 16)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid Ethereum address — not valid hex")

    start_time = time.time()

    try:
        # ─────────────────────────────────────────────────────
        # PHASE 1: Fan out all independent data gathering
        # ─────────────────────────────────────────────────────
        (
            source_data,
            dex_data,
            deployer_address,
            proxy_data,
            contract_values,
            token_info,
        ) = await asyncio.gather(
            etherscan.get_source_and_abi(address),
            dexscreener.get_market_data(address),
            etherscan.get_deployer_address(address),
            proxy_detector.check_proxy(address),
            contract_reader.read_contract_values(address),
            etherscan.get_token_info(address),
        )

        # ─────────────────────────────────────────────────────
        # PHASE 2: Work that depends on Phase 1 results
        # ─────────────────────────────────────────────────────
        # Pass total_supply & decimals to get_top_holders for accurate percentages
        total_supply_raw = token_info.get("total_supply_raw", 0)
        total_supply_human = token_info.get("total_supply_human", 0)
        token_decimals = token_info.get("decimals", 18)

        # Get pair_address for LP lock verification
        pair_address = dex_data.get("pair_address")

        # Run source scanner first (needed by honeypot_simulator for Module 2)
        source_code_raw = source_data.get("source_code", "")
        source_findings = source_scanner.scan(source_code_raw)

        # Module 1 findings dict for cross-module intelligence
        module1_findings_for_m2 = {
            "owner_address": contract_values.get("owner"),
            "ownership_renounced": contract_values.get("ownership_renounced", False),
            "is_proxy": proxy_data["is_proxy"],
            "proxy_implementation": proxy_data.get("implementation"),
            "admin_address": proxy_data.get("admin_address"),
            "is_open_source": bool(source_code_raw),
            "is_mintable": source_findings.get("has_mint", False),
            "can_change_tax": source_findings.get("tax_flip_risk", False),
            "has_blacklist": source_findings.get("has_blacklist", False),
        }

        (
            honeypot_result,
            deployer_history,
            holders_data,
            lp_lock_data,
        ) = await asyncio.gather(
            honeypot_simulator.simulate(
                address, dex_data,
                source_code=source_code_raw or None,
                module1_findings=module1_findings_for_m2,
            ),
            deployer_profiler.analyze(deployer_address),
            etherscan.get_top_holders(address, total_supply=total_supply_raw, decimals=token_decimals),
            lp_verifier.verify_lp_lock(pair_address) if pair_address else _lp_fallback(),
        )

        # ─────────────────────────────────────────────────────
        # PHASE 3: Pure math — no I/O, instant
        # ─────────────────────────────────────────────────────
        # Determine liquidity lock from on-chain verification first, DexScreener as fallback
        lp_locked_onchain = lp_lock_data.get("lp_locked", False)
        lp_locked_dex = dex_data.get("lp_locked", False)
        liquidity_locked = lp_locked_onchain or lp_locked_dex

        dump_result = dump_calculator.calculate(
            holders_data=holders_data,
            pool_token_reserve=dex_data.get("pool_token_reserve", 0),
            pool_eth_reserve=dex_data.get("pool_eth_reserve", 0),
            total_supply=total_supply_human,
            investment_amount=request.investment_amount,
            sell_tax_percent=contract_values.get("sell_tax", 0),
        )

        # ─────────────────────────────────────────────────────
        # PHASE 4: Assemble all findings into one dict
        # ─────────────────────────────────────────────────────

        # Use contract reader values for name/symbol as primary,
        # DexScreener as fallback
        token_name = contract_values.get("name") or dex_data.get("name")
        token_symbol = contract_values.get("symbol") or dex_data.get("symbol")

        all_findings = {
            # Module 1 — Control
            "is_proxy": proxy_data["is_proxy"],
            "proxy_implementation": proxy_data.get("implementation"),
            "proxy_type": proxy_data.get("proxy_type"),
            "admin_address": proxy_data.get("admin_address"),
            "admin_type": proxy_data.get("admin_type", "UNKNOWN"),
            "has_timelock": proxy_data.get("has_timelock", False),
            "has_multisig": proxy_data.get("has_multisig", False),
            "owner_address": contract_values.get("owner"),
            "ownership_renounced": contract_values.get("ownership_renounced", False),
            "can_change_tax": source_findings.get("tax_flip_risk", False),
            "is_mintable": source_findings.get("has_mint", False),
            "has_blacklist": source_findings.get("has_blacklist", False),
            "has_max_tx_control": source_findings.get("has_max_tx_control", False),
            "has_trading_control": source_findings.get("has_trading_control", False),
            "is_open_source": bool(source_data.get("source_code")),
            "deployer_address": deployer_address,
            "deployer_total_tokens": deployer_history["total_tokens_deployed"],
            "deployer_dead_tokens": deployer_history["dead_tokens"],
            "deployer_dead_ratio": deployer_history["dead_ratio"],

            # Enhanced source scanner findings
            "has_timelock_pattern": source_findings.get("has_timelock_pattern", False),
            "timelock_delay_seconds": source_findings.get("timelock_delay_seconds", 0),
            "timelock_delay_hours": source_findings.get("timelock_delay_hours", 0),
            "has_multisig_pattern": source_findings.get("has_multisig_pattern", False),
            "uses_openzeppelin": source_findings.get("uses_openzeppelin", False),
            "has_role_based_access": source_findings.get("has_role_based_access", False),
            "has_governance": source_findings.get("has_governance", False),
            "has_delegatecall": source_findings.get("has_delegatecall", False),

            # Module 2 — Traps (stubs for now)
            "is_honeypot": honeypot_result["is_honeypot"],
            "honeypot_reason": honeypot_result.get("reason"),
            "honeypot_confidence": honeypot_result["confidence"],
            "current_sell_tax": contract_values.get("sell_tax", 0),
            "current_buy_tax": contract_values.get("buy_tax", 0),
            "max_possible_tax": source_findings.get("max_possible_tax", 100),
            "tax_is_changeable": source_findings.get("tax_flip_risk", False),
            "proxy_trap_active": proxy_data["is_proxy"] and not contract_values.get("ownership_renounced", False),
            "has_selfdestruct": source_findings.get("has_selfdestruct", False),
            "has_suspicious_functions": source_findings.get("suspicious_ownership", False),

            # Module 3 — Collapse (FULLY WIRED)
            "liquidity_usd": dex_data.get("liquidity_usd", 0),
            "liquidity_locked": liquidity_locked,
            "lock_expiry_timestamp": dex_data.get("lock_expiry_timestamp"),
            "lock_expiry_readable": dex_data.get("lock_expiry_readable"),
            "days_until_unlock": dex_data.get("days_until_unlock"),
            "top_holder_address": holders_data[0]["address"] if holders_data else None,
            "top_holder_percent": holders_data[0]["percent"] if holders_data else 0,
            "top_5_holder_percent": dump_result.get("top_5_holder_percent", 0),
            "dump_price_impact_percent": dump_result["price_impact_percent"],
            "investment_value_after_dump": dump_result["investment_value_after_dump"],
            "holder_grade": dump_result["holder_grade"],
            "cumulative_dump_impact_percent": dump_result.get("cumulative_dump_impact_percent", 0),
            "cumulative_investment_after": dump_result.get("cumulative_investment_after", request.investment_amount),
            "pool_token_reserve": dex_data.get("pool_token_reserve", 0),
            "pool_eth_reserve": dex_data.get("pool_eth_reserve", 0),
            "pool_depth_ratio": dump_result.get("pool_depth_ratio", 0),
            "pair_address": pair_address,
            "data_status": dex_data.get("data_status", "OK"),

            # LP lock on-chain verification
            "lp_lock_method": lp_lock_data.get("lock_method", "unknown"),
            "lp_burned_percent": lp_lock_data.get("burned_percent", 0),
            "lp_locked_percent": lp_lock_data.get("locked_percent", 0),
            "lp_total_secured_percent": lp_lock_data.get("total_secured_percent", 0),
            "lp_locker_name": lp_lock_data.get("locker_name"),
            "lp_consequence": lp_lock_data.get("consequence", ""),

            # Meta
            "token_name": token_name,
            "token_symbol": token_symbol,
            "token_address": address,
            "investment_amount": request.investment_amount,
        }

        # ─────────────────────────────────────────────────────
        # PHASE 5: Calculate trust score
        # ─────────────────────────────────────────────────────
        score, band = trust_score.calculate(all_findings)
        all_findings["trust_score"] = score
        all_findings["score_band"] = band

        # ─────────────────────────────────────────────────────
        # PHASE 6: AI explanations (or template fallback)
        # ─────────────────────────────────────────────────────
        ai_output = await ai_engine.generate(all_findings)

        scan_time = round(time.time() - start_time, 2)

        # ─────────────────────────────────────────────────────
        # Build typed response
        # ─────────────────────────────────────────────────────
        module1 = Module1Data(
            is_proxy=all_findings["is_proxy"],
            proxy_implementation=all_findings["proxy_implementation"],
            proxy_type=all_findings["proxy_type"],
            admin_address=all_findings["admin_address"],
            admin_type=all_findings["admin_type"],
            has_timelock=all_findings["has_timelock"],
            has_multisig=all_findings["has_multisig"],
            owner_address=all_findings["owner_address"],
            ownership_renounced=all_findings["ownership_renounced"],
            can_change_tax=all_findings["can_change_tax"],
            is_mintable=all_findings["is_mintable"],
            has_blacklist=all_findings["has_blacklist"],
            has_max_tx_control=all_findings["has_max_tx_control"],
            has_trading_control=all_findings["has_trading_control"],
            is_open_source=all_findings["is_open_source"],
            deployer_address=all_findings["deployer_address"],
            deployer_total_tokens=all_findings["deployer_total_tokens"],
            deployer_dead_tokens=all_findings["deployer_dead_tokens"],
            deployer_dead_ratio=all_findings["deployer_dead_ratio"],
            has_timelock_pattern=all_findings["has_timelock_pattern"],
            timelock_delay_hours=all_findings["timelock_delay_hours"],
            has_multisig_pattern=all_findings["has_multisig_pattern"],
            uses_openzeppelin=all_findings["uses_openzeppelin"],
            has_role_based_access=all_findings["has_role_based_access"],
            has_governance=all_findings["has_governance"],
        )

        # Extract Module 2 enhanced data from the runner result
        m2_result = honeypot_result.get("module2_result")
        m2_detailed_findings = []
        m2_score = 100
        m2_verdict = "inconclusive"
        m2_summary = ""
        m2_data_confidence = "low"
        m2_findings_count = 0
        m2_critical_count = 0
        m2_high_count = 0
        m2_sim_status = "unavailable"
        m2_honeypot_sim_status = "not_run"
        m2_source_scan_status = "not_run"
        m2_owner_read_status = "not_run"
        m2_pair_found = False
        m2_detected_chain = None
        m2_pair_address = None
        m2_router_address = None
        m2_dex_name = None
        m2_liquidity_usd = None
        m2_scan_duration_ms = None

        if m2_result:
            m2_score = m2_result.score
            m2_verdict = m2_result.verdict.value
            m2_summary = m2_result.summary
            m2_data_confidence = m2_result.data_confidence.value
            m2_findings_count = len(m2_result.findings)
            m2_critical_count = sum(1 for f in m2_result.findings if f.severity.value == "critical")
            m2_high_count = sum(1 for f in m2_result.findings if f.severity.value == "high")
            m2_sim_status = m2_result.simulation.status.value
            m2_scan_duration_ms = m2_result.scan_duration_ms

            m2_honeypot_sim_status = m2_result.checks_status.honeypot_simulation
            m2_source_scan_status = m2_result.checks_status.source_code_scan
            m2_owner_read_status = m2_result.checks_status.owner_read

            if m2_result.pair_info:
                m2_pair_found = m2_result.pair_info.found
                m2_pair_address = m2_result.pair_info.pair_address
                m2_router_address = m2_result.pair_info.router_address
                m2_dex_name = m2_result.pair_info.dex_name
                m2_liquidity_usd = m2_result.pair_info.liquidity_usd
                m2_detected_chain = m2_result.pair_info.chain_id

            m2_detailed_findings = [
                Module2Finding(
                    id=f.id,
                    severity=f.severity.value,
                    evidence_type=f.evidence_type.value,
                    title=f.title,
                    what_we_saw=f.what_we_saw,
                    consequence=f.consequence,
                    confidence=f.confidence,
                ) for f in m2_result.findings
            ]

        module2 = Module2Data(
            # Legacy fields
            is_honeypot=all_findings["is_honeypot"],
            honeypot_reason=all_findings["honeypot_reason"],
            honeypot_confidence=all_findings["honeypot_confidence"],
            current_sell_tax=all_findings["current_sell_tax"],
            current_buy_tax=all_findings["current_buy_tax"],
            max_possible_tax=all_findings["max_possible_tax"],
            tax_is_changeable=all_findings["tax_is_changeable"],
            proxy_trap_active=all_findings["proxy_trap_active"],
            has_selfdestruct=all_findings["has_selfdestruct"],
            has_suspicious_functions=all_findings["has_suspicious_functions"],
            # Module 2 enhanced fields
            simulation_status=m2_sim_status,
            m2_score=m2_score,
            m2_verdict=m2_verdict,
            m2_summary=m2_summary,
            data_confidence=m2_data_confidence,
            findings_count=m2_findings_count,
            critical_count=m2_critical_count,
            high_count=m2_high_count,
            detailed_findings=m2_detailed_findings,
            honeypot_sim_status=m2_honeypot_sim_status,
            source_scan_status=m2_source_scan_status,
            owner_read_status=m2_owner_read_status,
            pair_found=m2_pair_found,
            detected_chain=m2_detected_chain,
            pair_address=m2_pair_address,
            router_address=m2_router_address,
            dex_name=m2_dex_name,
            liquidity_usd=m2_liquidity_usd,
            m2_scan_duration_ms=m2_scan_duration_ms,
        )

        module3 = Module3Data(
            liquidity_usd=all_findings["liquidity_usd"],
            liquidity_locked=all_findings["liquidity_locked"],
            lock_expiry_timestamp=all_findings["lock_expiry_timestamp"],
            lock_expiry_readable=all_findings["lock_expiry_readable"],
            days_until_unlock=all_findings["days_until_unlock"],
            top_holder_address=all_findings["top_holder_address"],
            top_holder_percent=all_findings["top_holder_percent"],
            top_5_holder_percent=all_findings["top_5_holder_percent"],
            dump_price_impact_percent=all_findings["dump_price_impact_percent"],
            investment_value_after_dump=all_findings["investment_value_after_dump"],
            holder_grade=all_findings["holder_grade"],
            cumulative_dump_impact_percent=all_findings["cumulative_dump_impact_percent"],
            cumulative_investment_after=all_findings["cumulative_investment_after"],
            pool_token_reserve=all_findings["pool_token_reserve"],
            pool_eth_reserve=all_findings["pool_eth_reserve"],
            pool_depth_ratio=all_findings["pool_depth_ratio"],
            pair_address=all_findings["pair_address"],
            lp_lock_method=all_findings["lp_lock_method"],
            lp_burned_percent=all_findings["lp_burned_percent"],
            lp_locked_percent=all_findings["lp_locked_percent"],
            lp_total_secured_percent=all_findings["lp_total_secured_percent"],
            lp_locker_name=all_findings["lp_locker_name"],
            lp_consequence=all_findings["lp_consequence"],
            data_status=all_findings["data_status"],
        )

        return SafeBetReport(
            token_address=address,
            token_name=token_name,
            token_symbol=token_symbol,
            trust_score=score,
            score_band=band,
            the_catch=ai_output["the_catch"],
            verdict=ai_output["verdict"],
            module1=module1,
            module2=module2,
            module3=module3,
            flag_explanations=ai_output["flag_explanations"],
            scan_duration_seconds=scan_time,
        )

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Scan failed: {str(e)}")
