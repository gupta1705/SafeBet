"""
SafeBet — Module 2 Scoring (Pessimistic)

Starts at 100, subtracts penalties for findings AND missing checks.
Caps score by confidence level. Maps to verdict.
"""

import logging
from schemas.findings import (
    Finding, Severity, Verdict,
    DataConfidence, CheckStatus,
)

logger = logging.getLogger(__name__)


PENALTY_TABLE: dict[str, int] = {
    "honeypot_confirmed": 70,
    "trading_disabled": 60,
    "confiscatory_tax": 40,
    "dust_liquidity": 35,
    "proxy_trap": 25,
    "trading_kill_switch": 25,
    "tax_flip_active_risk": 22,
    "wallet_freeze_risk": 20,
    "mint_risk": 20,
    "soft_honeypot_limits": 15,
    "low_liquidity": 15,
    "dead_volume": 15,
    "non_ethereum_chain": 15,
    "unverified_source": 15,
    "destructive_admin": 10,
    "moderate_liquidity": 10,
    "restrictive_limits": 10,
    "limits_present": 8,
    "cooldown_friction": 10,
    "low_volume": 8,
    "proxy_info": 5,
}

DEFAULT_SEVERITY_PENALTY: dict[Severity, int] = {
    Severity.CRITICAL: 50,
    Severity.HIGH: 20,
    Severity.MEDIUM: 10,
    Severity.LOW: 5,
    Severity.INFO: 0,
}

MISSING_CHECK_PENALTIES = {
    "honeypot_simulation": 15,
    "source_code_scan": 15,
    "owner_read": 10,
    "pair_resolution": 10,
}


def calculate_score(
    findings: list[Finding],
    checks: CheckStatus,
) -> tuple[int, Verdict, str, DataConfidence]:
    """
    Calculate the Module 2 score with pessimistic defaults.
    Returns: (score, verdict, summary, data_confidence)
    """
    score = 100
    penalties_applied: list[tuple[str, int]] = []

    # Step 1: Data confidence
    critical_checks_passed = 0
    if checks.honeypot_simulation in ("passed", "failed"):
        critical_checks_passed += 1
    if checks.source_code_scan == "scanned":
        critical_checks_passed += 1
    if checks.owner_read == "readable":
        critical_checks_passed += 1
    if checks.pair_resolution == "found":
        critical_checks_passed += 1
    if checks.proxy_check == "checked":
        critical_checks_passed += 1

    if critical_checks_passed >= 5:
        data_confidence = DataConfidence.HIGH
    elif critical_checks_passed >= 3:
        data_confidence = DataConfidence.MEDIUM
    else:
        data_confidence = DataConfidence.LOW

    # Step 2: Finding penalties
    for finding in findings:
        penalty = PENALTY_TABLE.get(finding.id, DEFAULT_SEVERITY_PENALTY.get(finding.severity, 10))
        adjusted_penalty = int(penalty * finding.confidence)
        score -= adjusted_penalty
        penalties_applied.append((finding.id, adjusted_penalty))

    # Step 3: Missing check penalties
    if checks.honeypot_simulation not in ("passed", "failed"):
        pen = MISSING_CHECK_PENALTIES["honeypot_simulation"]
        score -= pen
        penalties_applied.append(("missing:honeypot_sim", pen))

    if checks.source_code_scan != "scanned":
        pen = MISSING_CHECK_PENALTIES["source_code_scan"]
        score -= pen
        penalties_applied.append(("missing:source_code", pen))

    if checks.owner_read != "readable":
        pen = MISSING_CHECK_PENALTIES["owner_read"]
        score -= pen
        penalties_applied.append(("missing:owner_read", pen))

    if checks.pair_resolution != "found":
        pen = MISSING_CHECK_PENALTIES["pair_resolution"]
        score -= pen
        penalties_applied.append(("missing:pair_data", pen))

    # Step 4: Cap by confidence
    score = max(0, min(100, score))
    if data_confidence == DataConfidence.LOW:
        score = min(score, 50)
    elif data_confidence == DataConfidence.MEDIUM:
        score = min(score, 75)

    # Step 5: Verdict
    if data_confidence == DataConfidence.LOW:
        verdict = Verdict.INCONCLUSIVE
    elif score >= 80:
        verdict = Verdict.LOW_CONCERN
    elif score >= 50:
        verdict = Verdict.CAUTION
    elif score >= 20:
        verdict = Verdict.DANGER
    else:
        verdict = Verdict.CRITICAL_DANGER

    if data_confidence == DataConfidence.MEDIUM and len(findings) == 0:
        if critical_checks_passed < 4:
            verdict = Verdict.INCONCLUSIVE

    # Step 6: Summary
    summary = _generate_summary(findings, score, verdict, data_confidence, checks)

    logger.info(
        f"Module 2 score: {score}/100 ({verdict.value}), "
        f"confidence={data_confidence.value}, "
        f"checks={critical_checks_passed}/5. "
        f"Penalties: {penalties_applied}"
    )

    return score, verdict, summary, data_confidence


def _generate_summary(findings, score, verdict, confidence, checks):
    parts = []

    if verdict == Verdict.INCONCLUSIVE:
        missing = []
        if checks.honeypot_simulation not in ("passed", "failed"):
            missing.append("honeypot simulation")
        if checks.source_code_scan != "scanned":
            missing.append("source code analysis")
        if checks.owner_read != "readable":
            missing.append("owner/admin verification")
        if checks.pair_resolution != "found":
            missing.append("trading pair data")
        parts.append(f"⚠️ INCONCLUSIVE: Missing checks: {', '.join(missing)}.")

    critical = [f for f in findings if f.severity == Severity.CRITICAL]
    high = [f for f in findings if f.severity == Severity.HIGH]
    medium = [f for f in findings if f.severity == Severity.MEDIUM]

    if critical:
        parts.append(f"CRITICAL: {'; '.join(f.title for f in critical)}.")
    if high:
        parts.append(f"{len(high)} high-risk concern{'s' if len(high) != 1 else ''} detected.")
    if medium:
        parts.append(f"{len(medium)} moderate concern{'s' if len(medium) != 1 else ''} found.")

    if verdict == Verdict.CRITICAL_DANGER:
        parts.append("This token shows strong evidence of being a trap. Do NOT invest.")
    elif verdict == Verdict.DANGER:
        parts.append("This token has dangerous controls that could be used against holders.")
    elif verdict == Verdict.CAUTION:
        parts.append("This token has concerning controls. Proceed with extreme caution.")
    elif verdict == Verdict.INCONCLUSIVE:
        parts.append("Do not treat missing data as safety.")
    elif verdict == Verdict.LOW_CONCERN and not findings:
        parts.append("All critical checks passed. No trap mechanisms were detected.")

    return " ".join(parts)
