"""
Honeypot Simulator — Bridge to Module 2

Runs the full Module 2 trap detection pipeline and maps results
back to the legacy dict format expected by scan.py.
"""

import logging
from module2_runner import run_module2
from schemas.findings import SimulationStatus, Module1Input

logger = logging.getLogger(__name__)


async def simulate(token_address: str, dex_data: dict, source_code: str = None, module1_findings: dict = None) -> dict:
    """
    Run Module 2 trap detection and return results in legacy format.

    Args:
        token_address: Token contract address
        dex_data: DexScreener data (for context)
        source_code: Optional source code if already fetched
        module1_findings: Optional Module 1 findings dict for cross-module intelligence

    Returns:
        Dict with is_honeypot, reason, confidence, and full module2_result
    """
    try:
        # Build Module 1 input if we have findings from Module 1
        module1_data = None
        if module1_findings:
            module1_data = Module1Input(
                owner_address=module1_findings.get("owner_address"),
                owner_is_renounced=module1_findings.get("ownership_renounced", False),
                is_proxy=module1_findings.get("is_proxy", False),
                implementation_address=module1_findings.get("proxy_implementation"),
                proxy_admin_address=module1_findings.get("admin_address"),
                source_code=source_code,
                is_verified=module1_findings.get("is_open_source", False),
                has_mint=module1_findings.get("is_mintable", False),
                has_tax_setter=module1_findings.get("can_change_tax", False),
                has_blacklist=module1_findings.get("has_blacklist", False),
            )

        # Run full Module 2 pipeline
        m2_result = await run_module2(
            token_address=token_address,
            module1_data=module1_data,
            source_code=source_code,
        )

        # Map to legacy format
        sim = m2_result.simulation
        is_honeypot = sim.status == SimulationStatus.CONFIRMED_BLOCKED
        is_confiscatory = sim.status == SimulationStatus.CONFISCATORY_TAX

        # Determine confidence level
        if sim.status in (SimulationStatus.SELLABLE, SimulationStatus.CONFIRMED_BLOCKED, SimulationStatus.CONFISCATORY_TAX):
            confidence = "HIGH"
        elif m2_result.data_confidence.value == "medium":
            confidence = "MEDIUM"
        elif m2_result.data_confidence.value == "high":
            confidence = "HIGH"
        else:
            confidence = "LOW"

        # Build reason string
        if is_honeypot:
            reason = f"Sell blocked: {sim.revert_reason or 'Transaction rejected'}"
        elif is_confiscatory:
            tax_pct = (sim.effective_sell_tax_bps or 0) / 100
            reason = f"Confiscatory sell tax: {tax_pct:.0f}%"
        elif sim.status == SimulationStatus.SELLABLE:
            reason = "Token is sellable — simulation confirmed"
        else:
            reason = f"Simulation {sim.status.value}: {sim.error_detail or 'See Module 2 details'}"

        return {
            "is_honeypot": is_honeypot or is_confiscatory,
            "reason": reason,
            "confidence": confidence,
            "module2_result": m2_result,
        }

    except Exception as e:
        logger.error(f"Module 2 simulation failed: {e}")
        return {
            "is_honeypot": False,
            "reason": f"Module 2 error: {str(e)[:200]}",
            "confidence": "LOW",
            "module2_result": None,
        }
