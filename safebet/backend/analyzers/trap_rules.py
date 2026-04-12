"""
SafeBet — Trap Rules Engine

The core intelligence of Module 2. Takes raw evidence from the source scanner,
on-chain reader, sell simulator, and Module 1 inputs, and produces structured
Finding objects with severity, confidence, and consequence sentences.

13 rules covering: honeypot, proxy trap, tax flip, confiscatory tax,
trading kill switch, wallet freeze, soft honeypot limits, cooldown,
destructive admin, mint risk, market data, chain mismatch, unverified source.
"""

import logging
from schemas.findings import (
    Finding, Severity, EvidenceType,
    SimulationResult, SimulationStatus,
    SourceScanResult, OnChainSnapshot,
    ProxyInfo, Module1Input, PairInfo,
)
from analyzers.revert_classifier import classify_revert

logger = logging.getLogger(__name__)

ZERO_ADDRESS = "0x0000000000000000000000000000000000000000"


def _is_zero_address(address: str) -> bool:
    """Check if an address is the zero address."""
    if not address:
        return True
    try:
        return address.lower() == ZERO_ADDRESS.lower() or int(address, 16) == 0
    except (ValueError, TypeError):
        return False


def _has_active_admin(
    on_chain: OnChainSnapshot,
    proxy_info: ProxyInfo,
    module1: Module1Input | None,
) -> bool:
    """Check if anyone still has admin powers over this contract."""
    if on_chain.owner.call_success and on_chain.owner.value:
        if not _is_zero_address(on_chain.owner.value):
            return True

    if proxy_info.admin_address and not _is_zero_address(proxy_info.admin_address):
        return True

    if module1:
        if module1.owner_address and not module1.owner_is_renounced:
            return True
        if module1.proxy_admin_address:
            return True

    return False


def _get_owner_address(
    on_chain: OnChainSnapshot,
    module1: Module1Input | None,
) -> str | None:
    """Get the owner address from available sources."""
    if on_chain.owner.call_success and on_chain.owner.value:
        return on_chain.owner.value
    if module1 and module1.owner_address:
        return module1.owner_address
    return None


def _source_has_category(scan: SourceScanResult, category: str) -> bool:
    """Check if the source scanner found matches in a specific category."""
    cat = scan.categories.get(category)
    return cat is not None and cat.found


def _get_source_snippets(scan: SourceScanResult, category: str) -> list[str]:
    cat = scan.categories.get(category)
    if not cat or not cat.matches:
        return []
    return [m.snippet for m in cat.matches if m.snippet]


def _get_source_match_names(scan: SourceScanResult, category: str) -> list[str]:
    cat = scan.categories.get(category)
    if not cat or not cat.matches:
        return []
    return [m.pattern_name for m in cat.matches]


def evaluate_traps(
    simulation: SimulationResult,
    source_scan: SourceScanResult,
    on_chain: OnChainSnapshot,
    proxy_info: ProxyInfo,
    module1: Module1Input | None = None,
    pair_info: PairInfo | None = None,
) -> list[Finding]:
    """
    Evaluate all trap rules and return a list of findings.
    """
    findings: list[Finding] = []
    has_admin = _has_active_admin(on_chain, proxy_info, module1)
    owner = _get_owner_address(on_chain, module1)

    # ─── Rule 1: Honeypot Confirmed ──────────────────────────────────────
    if simulation.status == SimulationStatus.CONFIRMED_BLOCKED:
        revert_cat, revert_label, revert_consequence = classify_revert(simulation.revert_reason)

        findings.append(Finding(
            id="honeypot_confirmed",
            severity=Severity.CRITICAL,
            evidence_type=EvidenceType.RUNTIME_CONFIRMED,
            title="Sell Transaction Failed in Simulation",
            what_we_saw=(
                f"We simulated selling this token through the DEX router and the "
                f"transaction was rejected. Revert reason: {revert_label}."
            ),
            consequence=(
                "You may be able to buy this token but NOT sell it. "
                "Your funds would be permanently trapped in the contract. "
                f"{revert_consequence}"
            ),
            confidence=0.95,
            evidence={
                "router": simulation.router,
                "pair": simulation.pair,
                "revert_reason": simulation.revert_reason,
                "revert_category": revert_cat,
                "sell_succeeded": False,
            },
        ))

    # ─── Rule 2: Confiscatory Tax ────────────────────────────────────────
    sell_tax_bps = simulation.effective_sell_tax_bps
    buy_tax_bps = simulation.effective_buy_tax_bps

    if not sell_tax_bps and on_chain.sell_tax.call_success and on_chain.sell_tax.value:
        sell_tax_bps = on_chain.sell_tax.value

    if sell_tax_bps is not None and sell_tax_bps > 1500:
        if sell_tax_bps > 5000:
            severity = Severity.CRITICAL
            tax_pct = sell_tax_bps / 100
            consequence = (
                f"The effective sell tax is {tax_pct:.0f}%. For every $100 you sell, "
                f"you lose ${tax_pct:.0f} to fees. This is effectively a honeypot."
            )
        elif sell_tax_bps > 3000:
            severity = Severity.HIGH
            tax_pct = sell_tax_bps / 100
            consequence = (
                f"The effective sell tax is {tax_pct:.0f}%. For every $100 you sell, "
                f"you only receive ${100 - tax_pct:.0f}. This is predatory."
            )
        else:
            severity = Severity.MEDIUM
            tax_pct = sell_tax_bps / 100
            consequence = (
                f"The sell tax is {tax_pct:.0f}%, which is above normal. "
                f"Most legitimate tokens have fees under 5%."
            )

        findings.append(Finding(
            id="confiscatory_tax",
            severity=severity,
            evidence_type=EvidenceType.RUNTIME_CONFIRMED if simulation.sell_succeeded else EvidenceType.ON_CHAIN_READ,
            title=f"Sell Tax is {sell_tax_bps / 100:.0f}%",
            what_we_saw=f"The effective sell tax is {sell_tax_bps} basis points ({sell_tax_bps / 100:.1f}%).",
            consequence=consequence,
            confidence=0.85 if simulation.sell_succeeded else 0.6,
            evidence={
                "sell_tax_bps": sell_tax_bps,
                "buy_tax_bps": buy_tax_bps,
                "source": "simulation" if simulation.sell_succeeded else "on_chain_read",
            },
        ))

    # ─── Rule 3: Proxy Trap ──────────────────────────────────────────────
    if proxy_info.is_proxy:
        if proxy_info.upgrade_authority_active or has_admin:
            findings.append(Finding(
                id="proxy_trap",
                severity=Severity.HIGH,
                evidence_type=EvidenceType.DERIVED_RISK,
                title="Upgradeable Contract with Active Admin",
                what_we_saw=(
                    f"This token is an upgradeable proxy contract. "
                    f"The implementation lives at {proxy_info.implementation_address}. "
                    f"{'The proxy admin at ' + proxy_info.admin_address + ' can upgrade it.' if proxy_info.admin_address else 'An admin may still be able to upgrade it.'}"
                ),
                consequence=(
                    "This token can be upgraded after launch, so a clean contract today "
                    "can become a trap tomorrow without buyers getting a new token address."
                ),
                confidence=0.9 if proxy_info.admin_address else 0.7,
                evidence={
                    "is_proxy": True,
                    "implementation": proxy_info.implementation_address,
                    "admin": proxy_info.admin_address,
                    "upgrade_authority_active": proxy_info.upgrade_authority_active,
                },
            ))
        else:
            findings.append(Finding(
                id="proxy_info",
                severity=Severity.LOW,
                evidence_type=EvidenceType.ON_CHAIN_READ,
                title="Upgradeable Contract (Admin Renounced)",
                what_we_saw="This token is a proxy contract, but no active upgrade admin was found.",
                consequence="The contract was deployed as upgradeable, but upgrade authority appears to have been removed.",
                confidence=0.6,
                evidence={"is_proxy": True, "implementation": proxy_info.implementation_address},
            ))

    # ─── Rule 4: Tax Flip Active Risk ────────────────────────────────────
    if _source_has_category(source_scan, "tax_control") and has_admin:
        match_names = _get_source_match_names(source_scan, "tax_control")
        snippets = _get_source_snippets(source_scan, "tax_control")

        findings.append(Finding(
            id="tax_flip_active_risk",
            severity=Severity.HIGH,
            evidence_type=EvidenceType.SOURCE_DETECTED,
            title="Owner Can Change Buy/Sell Taxes",
            what_we_saw=(
                f"The source code contains tax-changing functions: {', '.join(match_names[:3])}. "
                f"The contract still has an active owner/admin."
            ),
            consequence=(
                "The contract owner can change the buy or sell tax to any value at any time. "
                "A 0% fee today could become a 99% fee tomorrow with a single transaction."
            ),
            confidence=0.85,
            evidence={"functions_found": match_names, "owner": owner, "snippets": snippets[:2]},
        ))

    # ─── Rule 5: Trading Kill Switch ─────────────────────────────────────
    has_trading_toggle = _source_has_category(source_scan, "trading_control")
    trading_currently_on = None
    if on_chain.trading_active.call_success:
        trading_currently_on = on_chain.trading_active.value
    elif on_chain.trading_open.call_success:
        trading_currently_on = on_chain.trading_open.value
    elif on_chain.swap_enabled.call_success:
        trading_currently_on = on_chain.swap_enabled.value

    if has_trading_toggle:
        if trading_currently_on is False:
            findings.append(Finding(
                id="trading_disabled",
                severity=Severity.CRITICAL,
                evidence_type=EvidenceType.RUNTIME_CONFIRMED,
                title="Trading is Currently Disabled",
                what_we_saw="The contract has a trading toggle and it is currently set to OFF.",
                consequence="Trading is completely disabled. If you already hold tokens, you cannot sell until the owner turns trading back on.",
                confidence=0.95,
                evidence={"trading_active": False, "has_toggle_function": True},
            ))
        elif has_admin:
            findings.append(Finding(
                id="trading_kill_switch",
                severity=Severity.HIGH,
                evidence_type=EvidenceType.SOURCE_DETECTED,
                title="Owner Can Disable Trading",
                what_we_saw="The contract contains a trading enable/disable switch and the owner still has active control.",
                consequence="The owner can disable all trading with a single transaction. If you buy, you might not be able to sell.",
                confidence=0.8,
                evidence={
                    "trading_active": trading_currently_on,
                    "functions_found": _get_source_match_names(source_scan, "trading_control"),
                    "owner": owner,
                },
            ))

    # ─── Rule 6: Wallet Freeze Risk ──────────────────────────────────────
    if _source_has_category(source_scan, "blacklist_control"):
        match_names = _get_source_match_names(source_scan, "blacklist_control")
        severity = Severity.HIGH if has_admin else Severity.MEDIUM

        findings.append(Finding(
            id="wallet_freeze_risk",
            severity=severity,
            evidence_type=EvidenceType.SOURCE_DETECTED,
            title="Contract Can Blacklist Wallets",
            what_we_saw=f"The source code contains wallet-level control mechanisms: {', '.join(match_names[:3])}.",
            consequence="The contract contains wallet-level control logic which can be used to block specific holders from transferring or selling.",
            confidence=0.8 if has_admin else 0.5,
            evidence={"functions_found": match_names, "admin_active": has_admin, "owner": owner},
        ))

    # ─── Rule 7: Soft Honeypot Limits ────────────────────────────────────
    if _source_has_category(source_scan, "wallet_limits"):
        max_tx = None
        total_supply = None

        if on_chain.max_tx_amount.call_success and on_chain.max_tx_amount.value:
            max_tx = on_chain.max_tx_amount.value
        if on_chain.total_supply.call_success and on_chain.total_supply.value:
            total_supply = on_chain.total_supply.value

        if max_tx and total_supply and total_supply > 0:
            pct = (max_tx / total_supply) * 100

            if pct < 1.0:
                findings.append(Finding(
                    id="soft_honeypot_limits",
                    severity=Severity.HIGH,
                    evidence_type=EvidenceType.ON_CHAIN_READ,
                    title=f"Max Transaction is Only {pct:.2f}% of Supply",
                    what_we_saw=f"The max transaction amount is {max_tx} tokens, which is only {pct:.2f}% of the total supply.",
                    consequence=f"You can only sell {pct:.2f}% of the supply per transaction. This effectively makes the token unsellable for large holders.",
                    confidence=0.85,
                    evidence={"max_tx": max_tx, "total_supply": total_supply, "percentage": pct},
                ))
            elif pct < 5.0:
                findings.append(Finding(
                    id="restrictive_limits",
                    severity=Severity.MEDIUM,
                    evidence_type=EvidenceType.ON_CHAIN_READ,
                    title=f"Max Transaction is {pct:.1f}% of Supply",
                    what_we_saw=f"The max transaction amount is limited to {pct:.1f}% of supply.",
                    consequence=f"You can only sell {pct:.1f}% of the supply per transaction. This creates moderate exit friction.",
                    confidence=0.7,
                    evidence={"max_tx": max_tx, "total_supply": total_supply, "percentage": pct},
                ))
        elif has_admin:
            findings.append(Finding(
                id="limits_present",
                severity=Severity.MEDIUM,
                evidence_type=EvidenceType.SOURCE_DETECTED,
                title="Transaction Limits in Source Code",
                what_we_saw="The contract contains max transaction and/or max wallet limits.",
                consequence="Transaction limits exist and the owner may be able to set them to extremely low values.",
                confidence=0.5,
                evidence={"functions_found": _get_source_match_names(source_scan, "wallet_limits")},
            ))

    # ─── Rule 8: Cooldown Friction ───────────────────────────────────────
    if _source_has_category(source_scan, "cooldown_control"):
        findings.append(Finding(
            id="cooldown_friction",
            severity=Severity.MEDIUM if has_admin else Severity.LOW,
            evidence_type=EvidenceType.SOURCE_DETECTED,
            title="Transfer Cooldown Detected",
            what_we_saw="The contract implements a cooldown or transfer delay mechanism.",
            consequence="There is a waiting period between trades. Combined with other restrictions, this can make it difficult to exit quickly.",
            confidence=0.6,
            evidence={"functions_found": _get_source_match_names(source_scan, "cooldown_control"), "admin_active": has_admin},
        ))

    # ─── Rule 9: Destructive Admin Pattern ───────────────────────────────
    if _source_has_category(source_scan, "destructive_pattern"):
        match_names = _get_source_match_names(source_scan, "destructive_pattern")
        severity = Severity.HIGH if has_admin else Severity.MEDIUM
        has_selfdestruct = "selfdestruct" in match_names
        has_delegatecall = "delegatecall" in match_names

        what = []
        if has_selfdestruct:
            what.append("a selfdestruct instruction")
        if has_delegatecall:
            what.append("delegatecall capability")

        findings.append(Finding(
            id="destructive_admin",
            severity=severity,
            evidence_type=EvidenceType.SOURCE_DETECTED,
            title="Destructive Admin Pattern Detected",
            what_we_saw=(
                f"The contract contains {' and '.join(what)}. "
                f"{'An active admin could trigger this.' if has_admin else 'However, no active admin was found.'}"
            ),
            consequence="The contract contains code that could destroy or fundamentally alter it.",
            confidence=0.7 if has_admin else 0.4,
            evidence={"patterns": match_names, "admin_active": has_admin},
        ))

    # ─── Rule 10: Mint Risk ──────────────────────────────────────────────
    has_mint_source = _source_has_category(source_scan, "mint_control")
    has_mint_m1 = module1.has_mint if module1 else False

    if (has_mint_source or has_mint_m1) and has_admin:
        findings.append(Finding(
            id="mint_risk",
            severity=Severity.HIGH,
            evidence_type=EvidenceType.SOURCE_DETECTED,
            title="Owner Can Mint Unlimited Tokens",
            what_we_saw="The contract has a mint function and the owner still has active control.",
            consequence="The contract owner can create new tokens at will, diluting your holdings to zero.",
            confidence=0.85,
            evidence={"source_detected": has_mint_source, "module1_detected": has_mint_m1, "owner": owner},
        ))

    # ─── Rule 11: Market Data Red Flags ────────────────────────────────────
    if pair_info and pair_info.found:
        liquidity = pair_info.liquidity_usd or 0
        volume_24h = pair_info.volume_24h_usd or 0

        if liquidity < 1000:
            findings.append(Finding(
                id="dust_liquidity", severity=Severity.CRITICAL,
                evidence_type=EvidenceType.DERIVED_RISK,
                title=f"Liquidity is Only ${liquidity:,.0f}",
                what_we_saw=f"The total DEX liquidity for this token is ${liquidity:,.2f}.",
                consequence="With near-zero liquidity, even a tiny sell order would crash the price to nothing.",
                confidence=0.95,
                evidence={"liquidity_usd": liquidity, "volume_24h_usd": volume_24h, "dex": pair_info.dex_name},
            ))
        elif liquidity < 10000:
            findings.append(Finding(
                id="low_liquidity", severity=Severity.HIGH,
                evidence_type=EvidenceType.DERIVED_RISK,
                title=f"Very Low Liquidity (${liquidity:,.0f})",
                what_we_saw=f"The DEX liquidity pool holds only ${liquidity:,.0f}.",
                consequence="Low liquidity means high slippage on sells.",
                confidence=0.85,
                evidence={"liquidity_usd": liquidity, "dex": pair_info.dex_name},
            ))
        elif liquidity < 50000:
            findings.append(Finding(
                id="moderate_liquidity", severity=Severity.MEDIUM,
                evidence_type=EvidenceType.DERIVED_RISK,
                title=f"Below-Average Liquidity (${liquidity:,.0f})",
                what_we_saw=f"The liquidity pool has ${liquidity:,.0f}.",
                consequence="Moderate slippage risk on sells.",
                confidence=0.7,
                evidence={"liquidity_usd": liquidity, "dex": pair_info.dex_name},
            ))

        if volume_24h < 100 and liquidity > 0:
            findings.append(Finding(
                id="dead_volume", severity=Severity.HIGH,
                evidence_type=EvidenceType.DERIVED_RISK,
                title=f"Near-Zero Trading Volume (${volume_24h:,.0f}/24h)",
                what_we_saw=f"Only ${volume_24h:,.2f} in trades in the last 24 hours.",
                consequence="Nobody is trading this token. Dead volume often means the project has been abandoned.",
                confidence=0.9,
                evidence={"volume_24h_usd": volume_24h, "liquidity_usd": liquidity},
            ))
        elif volume_24h < 1000 and liquidity > 0:
            findings.append(Finding(
                id="low_volume", severity=Severity.MEDIUM,
                evidence_type=EvidenceType.DERIVED_RISK,
                title=f"Very Low Trading Volume (${volume_24h:,.0f}/24h)",
                what_we_saw=f"Only ${volume_24h:,.0f} traded in the last 24 hours.",
                consequence="Low trading volume suggests weak market interest.",
                confidence=0.7,
                evidence={"volume_24h_usd": volume_24h},
            ))

    # ─── Rule 12: Chain Mismatch Warning ──────────────────────────────────
    if pair_info and pair_info.found and pair_info.chain_id:
        if pair_info.chain_id != "ethereum":
            chain_name = pair_info.chain_id.upper()
            sim_failed = simulation.status in (SimulationStatus.UNAVAILABLE, SimulationStatus.ERROR, SimulationStatus.NO_PAIR_FOUND)

            findings.append(Finding(
                id="non_ethereum_chain",
                severity=Severity.HIGH if sim_failed else Severity.MEDIUM,
                evidence_type=EvidenceType.DERIVED_RISK,
                title=f"Token is on {chain_name}, Not Ethereum",
                what_we_saw=f"This token trades on {chain_name} (via {pair_info.dex_name}), not Ethereum mainnet.",
                consequence=f"Our honeypot simulation could not verify this token because it's on {chain_name}.",
                confidence=0.9,
                evidence={"detected_chain": pair_info.chain_id, "dex": pair_info.dex_name, "simulation_status": simulation.status.value},
            ))

    # ─── Rule 13: Unverified Source Code ──────────────────────────────────
    if not source_scan.source_available:
        findings.append(Finding(
            id="unverified_source",
            severity=Severity.HIGH,
            evidence_type=EvidenceType.DERIVED_RISK,
            title="Source Code Not Verified",
            what_we_saw="The contract source code is not published on Etherscan.",
            consequence="Without verified source code, we cannot check for hidden trap patterns. Most legitimate projects verify their source code.",
            confidence=0.8,
            evidence={"source_available": False},
        ))

    # Sort by severity
    severity_order = {Severity.CRITICAL: 0, Severity.HIGH: 1, Severity.MEDIUM: 2, Severity.LOW: 3, Severity.INFO: 4}
    findings.sort(key=lambda f: severity_order.get(f.severity, 5))

    logger.info(f"Trap rules produced {len(findings)} findings")
    return findings
