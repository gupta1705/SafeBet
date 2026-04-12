"""
Parses raw Solidity source code for dangerous patterns.
Runs after Etherscan gives us the source code.
Pure Python regex — no AI, no API.

ENHANCED:
- Detects delegatecall usage (proxy indicator)
- Detects Timelock patterns in source code
- Detects Multi-Sig references
- Distinguishes professional architecture from rug-pull patterns
"""

import re


def scan(source_code: str) -> dict:
    """
    Scans Solidity source code for dangerous function patterns.
    Returns a dict of boolean flags and extracted values.
    """
    if not source_code:
        return _empty_findings()

    findings = {}

    # ── Tax Manipulation ──────────────────────────────────────────────
    # Can the owner call a function to change buy/sell tax?
    findings["tax_flip_risk"] = bool(re.search(
        r'function\s+set(Sell|Buy|Transfer|Tax|Fee|Marketing|Dev|Liquidity)[A-Za-z]*\s*\(',
        source_code, re.IGNORECASE
    ))

    # What's the maximum possible tax the contract allows?
    # Look for require() statements that cap tax values
    max_tax_matches = re.findall(r'require\s*\([^)]*[<>]=?\s*(\d+)', source_code)
    tax_limits = [int(m) for m in max_tax_matches if 1 <= int(m) <= 10000]
    findings["max_possible_tax"] = max(tax_limits) / 100 if tax_limits else 100.0

    # ── Mint Capability ───────────────────────────────────────────────
    # Look for mint function — standard name across ERC20 extensions
    findings["has_mint"] = bool(re.search(
        r'function\s+(_)?mint\s*\(', source_code, re.IGNORECASE
    ))

    # ── Blacklist / Freeze ────────────────────────────────────────────
    # Multiple naming patterns across scam tokens
    findings["has_blacklist"] = bool(re.search(
        r'function\s+(blacklist|banAddress|blockWallet|addToBlacklist|setBlacklist|'
        r'addBlackList|addBot|setBots|blockAddress|isBot|_isBot|antiBot)\s*\(',
        source_code, re.IGNORECASE
    )) or bool(re.search(
        r'mapping\s*\(\s*address\s*=>\s*bool\s*\)\s*(public\s+)?(isBlacklisted|'
        r'_isBlacklisted|bots|isBot|blacklisted|blocked)',
        source_code, re.IGNORECASE
    ))

    # ── Max Transaction Control ───────────────────────────────────────
    # Classic rug setup: set maxTx to 0 after launch so nobody can sell
    findings["has_max_tx_control"] = bool(re.search(
        r'function\s+set(Max|Limit|_max|_limit)(Transaction|Tx|Wallet|Buy|Sell|Transfer)[A-Za-z]*\s*\(',
        source_code, re.IGNORECASE
    ))

    # ── Self Destruct ─────────────────────────────────────────────────
    findings["has_selfdestruct"] = bool(re.search(
        r'\bselfdestruct\b|\bsuicide\b', source_code, re.IGNORECASE
    ))

    # ── Hidden Ownership Transfer ─────────────────────────────────────
    # Detect owner assignment in non-standard functions (hiding backdoor ownership)
    suspicious = re.findall(
        r'function\s+(\w+)\s*\([^)]*\)[^{]*\{[^}]*\bowner\s*=[^=]',
        source_code, re.IGNORECASE
    )
    standard_ownership_fns = {"transferownership", "renounceownership", "constructor", "_transferownership"}
    findings["suspicious_ownership"] = any(
        fn.lower() not in standard_ownership_fns for fn in suspicious
    )

    # ── Trading Controls ──────────────────────────────────────────────
    # Can the owner enable/disable trading? Lets them block everyone from selling
    findings["has_trading_control"] = bool(re.search(
        r'function\s+(enableTrading|disableTrading|setTradingEnabled|openTrading|'
        r'setTrading|closeTrade|pauseTrading|unpauseTrading|tradingActive)\s*\(',
        source_code, re.IGNORECASE
    ))

    # ── External Call Patterns (potential rug vectors) ─────────────────
    # Detect delegatecall usage (can change contract behavior)
    findings["has_delegatecall"] = bool(re.search(
        r'\bdelegatecall\b', source_code, re.IGNORECASE
    ))

    # ══════════════════════════════════════════════════════════════════
    # PROFESSIONAL ARCHITECTURE DETECTION
    # These patterns indicate sophisticated, legitimate contract design
    # ══════════════════════════════════════════════════════════════════

    # ── Timelock Detection ────────────────────────────────────────────
    # Does the source code reference a timelock for upgrade delays?
    findings["has_timelock_pattern"] = bool(re.search(
        r'\b(TimelockController|Timelock|timelock|timeLock|'
        r'MINIMUM_DELAY|MAXIMUM_DELAY|GRACE_PERIOD|'
        r'queueTransaction|executeTransaction|cancelTransaction|'
        r'eta\s*[=<>]|delay\s*[=<>])\b',
        source_code
    )) or bool(re.search(
        r'require\s*\([^)]*block\.timestamp[^)]*delay',
        source_code, re.IGNORECASE
    )) or bool(re.search(
        r'require\s*\([^)]*delay[^)]*block\.timestamp',
        source_code, re.IGNORECASE
    ))

    # Extract minimum delay if present (in seconds)
    delay_matches = re.findall(
        r'(?:MINIMUM_DELAY|MIN_DELAY|minDelay|_delay)\s*=\s*(\d+)',
        source_code
    )
    if delay_matches:
        # Convert to hours for readability
        max_delay = max(int(d) for d in delay_matches)
        findings["timelock_delay_seconds"] = max_delay
        findings["timelock_delay_hours"] = round(max_delay / 3600, 1)
    else:
        findings["timelock_delay_seconds"] = 0
        findings["timelock_delay_hours"] = 0

    # ── Multi-Sig Detection ───────────────────────────────────────────
    # Does the source reference multi-signature governance?
    findings["has_multisig_pattern"] = bool(re.search(
        r'\b(GnosisSafe|SafeProxy|MultiSig|multisig|multiSig|'
        r'getOwners|getThreshold|addOwnerWithThreshold|'
        r'execTransaction|checkSignatures|'
        r'nonce\s*\+\+|requiredConfirmations|'
        r'isOwner\s*\[|owners\s*\[)\b',
        source_code
    ))

    # ── OpenZeppelin / Standard Library Usage ─────────────────────────
    # Professional contracts typically import from established libraries
    findings["uses_openzeppelin"] = bool(re.search(
        r'@openzeppelin|OpenZeppelin|import\s+["\']@openzeppelin',
        source_code
    ))

    # ── Access Control ────────────────────────────────────────────────
    # Professional access control (beyond simple Ownable)
    findings["has_role_based_access"] = bool(re.search(
        r'\b(AccessControl|hasRole|grantRole|revokeRole|'
        r'DEFAULT_ADMIN_ROLE|MINTER_ROLE|PAUSER_ROLE|'
        r'onlyRole|getRoleAdmin)\b',
        source_code
    ))

    # ── Governance Patterns ───────────────────────────────────────────
    findings["has_governance"] = bool(re.search(
        r'\b(Governor|GovernorAlpha|GovernorBravo|'
        r'propose|castVote|queue|execute|'
        r'votingDelay|votingPeriod|proposalThreshold)\b',
        source_code
    ))

    return findings


def _empty_findings() -> dict:
    """Default conservative values when source code is unavailable."""
    return {
        "tax_flip_risk": False,
        "max_possible_tax": 100.0,
        "has_mint": False,
        "has_blacklist": False,
        "has_max_tx_control": False,
        "has_selfdestruct": False,
        "suspicious_ownership": False,
        "has_trading_control": False,
        "has_delegatecall": False,
        "has_timelock_pattern": False,
        "timelock_delay_seconds": 0,
        "timelock_delay_hours": 0,
        "has_multisig_pattern": False,
        "uses_openzeppelin": False,
        "has_role_based_access": False,
        "has_governance": False,
    }
