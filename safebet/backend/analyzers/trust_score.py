"""
Trust Score Calculator — Weighted 0-100 formula.

ENHANCED: Now factors in professional architecture signals:
- Timelock/Multi-Sig admin → reduces proxy penalty
- Known entity → score boost
- OpenZeppelin usage → minor positive signal
- Role-based access / governance → positive signal
"""

from services.ai_engine import check_known_entity


def calculate(f: dict) -> tuple[int, str]:
    """
    Takes all_findings dict, returns (score: 0-100, band: str).
    Higher score = safer token.
    """
    score = 100

    # ══════════════════════════════════════════════════════════════════
    # KNOWN ENTITY BOOST
    # If this is a whitelisted token, start from a higher baseline
    # ══════════════════════════════════════════════════════════════════
    token_address = f.get("token_address", "")
    known = check_known_entity(token_address)
    if known:
        # Known entities still get scanned but start with a floor
        # We'll compute the score normally and then apply a floor
        is_known = True
    else:
        is_known = False

    # ══════════════════════════════════════════════════════════════════
    # MODULE 1 — CONTRACT CONTROL (active)
    # ══════════════════════════════════════════════════════════════════

    # ── INSTANT DISQUALIFIERS ─────────────────────────────────────────
    if not f.get("is_open_source"):
        score -= 25  # Can't trust what you can't read

    # ── PROXY & UPGRADE RISK ──────────────────────────────────────────
    if f.get("is_proxy") and not f.get("ownership_renounced"):
        # Base penalty for upgradeable + active owner
        base_proxy_penalty = 25

        # Reduce penalty based on admin safeguards
        admin_type = f.get("admin_type", "UNKNOWN")
        if admin_type == "TIMELOCK":
            delay_hours = f.get("timelock_delay_hours", 0)
            if delay_hours >= 24:
                base_proxy_penalty = 5   # 24h+ delay = very safe
            elif delay_hours >= 6:
                base_proxy_penalty = 10  # 6h+ delay = decent
            else:
                base_proxy_penalty = 15  # Short delay = some protection
        elif admin_type == "MULTISIG":
            base_proxy_penalty = 10  # Multi-sig = good protection
        elif admin_type == "CONTRACT":
            base_proxy_penalty = 18  # Unknown contract = some hope
        # EOA or UNKNOWN stays at full 25

        # Source code timelock/multisig patterns also help
        if f.get("has_timelock_pattern"):
            base_proxy_penalty = max(base_proxy_penalty - 5, 5)
        if f.get("has_multisig_pattern"):
            base_proxy_penalty = max(base_proxy_penalty - 3, 5)

        score -= base_proxy_penalty
    elif f.get("is_proxy"):
        score -= 10  # Proxy alone is still a yellow flag

    # ── OWNERSHIP ─────────────────────────────────────────────────────
    if not f.get("ownership_renounced"):
        score -= 5   # Owner exists (not always bad, but less safe)

    # ── DANGEROUS FUNCTIONS ───────────────────────────────────────────
    if f.get("can_change_tax") or f.get("tax_is_changeable"):
        score -= 20
    if f.get("is_mintable"):
        score -= 15
    if f.get("has_blacklist"):
        score -= 12
    if f.get("has_trading_control"):
        score -= 15
    if f.get("suspicious_ownership"):
        score -= 20
    if f.get("has_max_tx_control"):
        score -= 8

    # ── PROFESSIONAL ARCHITECTURE BONUS ───────────────────────────────
    if f.get("uses_openzeppelin"):
        score += 3
    if f.get("has_role_based_access"):
        score += 2
    if f.get("has_governance"):
        score += 5

    # ── DEPLOYER HISTORY ──────────────────────────────────────────────
    dead_ratio = f.get("deployer_dead_ratio", 0)
    if dead_ratio > 0.7:
        score -= 15  # Serial rugger
    elif dead_ratio > 0.4:
        score -= 8

    total_deployed = f.get("deployer_total_tokens", 0)
    if total_deployed > 20:
        score -= 5   # Token factory wallet

    # ══════════════════════════════════════════════════════════════════
    # MODULE 2 — TRAP DETECTION (stubs, will activate later)
    # ══════════════════════════════════════════════════════════════════
    if f.get("is_honeypot"):
        score -= 60
    if f.get("has_selfdestruct"):
        score -= 40

    sell_tax = f.get("current_sell_tax", 0)
    if sell_tax > 25:
        score -= 20
    elif sell_tax > 10:
        score -= 10
    elif sell_tax > 5:
        score -= 5

    # ══════════════════════════════════════════════════════════════════
    # MODULE 3 — COLLAPSE SIMULATION (FULLY ACTIVE)
    # ══════════════════════════════════════════════════════════════════
    if not f.get("liquidity_locked"):
        liq = f.get("liquidity_usd", 0)
        if liq > 0:  # Only penalize if there IS liquidity to check
            # Check on-chain LP verification — if partially secured, reduce penalty
            lp_secured = f.get("lp_total_secured_percent", 0)
            if lp_secured >= 80:
                score -= 5   # Mostly secured on-chain even if DexScreener didn't flag it
            elif lp_secured >= 30:
                score -= 15  # Partially secured
            else:
                score -= 25  # Not secured at all

    days = f.get("days_until_unlock")
    if days is not None and 0 < days <= 7:
        score -= 20
    elif days is not None and 7 < days <= 30:
        score -= 10

    top_pct = f.get("top_holder_percent", 0)
    if top_pct > 50:
        score -= 25
    elif top_pct > 30:
        score -= 15
    elif top_pct > 15:
        score -= 8

    dump = f.get("dump_price_impact_percent", 0)
    if dump > 70:
        score -= 15
    elif dump > 40:
        score -= 8

    # Cumulative dump impact (top 5 holders cascade)
    cascade = f.get("cumulative_dump_impact_percent", 0)
    if cascade > 90:
        score -= 10
    elif cascade > 70:
        score -= 5

    # ── KNOWN ENTITY FLOOR ────────────────────────────────────────────
    if is_known:
        # Known entities get a minimum score of 70
        # Their flags are expected (mint for stablecoins, etc.)
        score = max(score, 70)

    # ── CLAMP & BAND ──────────────────────────────────────────────────
    score = max(0, min(100, score))

    if score >= 80:
        band = "LOW RISK"
    elif score >= 55:
        band = "MODERATE RISK"
    elif score >= 30:
        band = "HIGH RISK"
    else:
        band = "CRITICAL RISK"

    return score, band
