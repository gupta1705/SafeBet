"""
AI Engine — Single Claude call for generating plain English explanations.

SMART ANALYSIS FEATURES:
1. Known Entity Whitelist — recognizes USDC, USDT, DAI, WETH, LINK etc.
2. Proxy Intelligence — distinguishes multisig/timelock admins from instant upgrades
3. Power vs Malice — differentiates professional architecture from rug-pull patterns

When activated, takes all findings → returns verdict, the_catch, flag explanations.
One call. Structured JSON output.
"""

import json
import os

# Only import anthropic if we have a key
_client = None

# ══════════════════════════════════════════════════════════════════
# KNOWN ENTITY WHITELIST
# These are well-known contracts managed by regulated/reputable entities.
# Even if they have "scary" flags (mint, blacklist, proxy), context matters.
# ══════════════════════════════════════════════════════════════════
KNOWN_ENTITIES = {
    # Stablecoins
    "0xa0b86991c6218b36c1d19d4a2e9eb0ce3606eb48": {
        "name": "USD Coin",
        "symbol": "USDC",
        "entity": "Circle",
        "category": "stablecoin",
        "note": "This is USDC, a centralized stablecoin. While the developer (Circle) has admin control including mint, burn, and blacklist powers, it is managed by a regulated financial entity. These powers exist for legal compliance, not malice.",
    },
    "0xdac17f958d2ee523a2206206994597c13d831ec7": {
        "name": "Tether USD",
        "symbol": "USDT",
        "entity": "Tether",
        "category": "stablecoin",
        "note": "This is USDT, the largest stablecoin by market cap. Tether has full admin control including freeze and mint capabilities. These exist for regulatory compliance. Tether is centralized but widely used.",
    },
    "0x6b175474e89094c44da98b954eedeac495271d0f": {
        "name": "Dai",
        "symbol": "DAI",
        "entity": "MakerDAO",
        "category": "stablecoin",
        "note": "This is DAI, a decentralized stablecoin governed by MakerDAO. It uses proxy patterns and admin functions as part of its governance system, not for malicious purposes.",
    },
    "0xc02aaa39b223fe8d0a0e5c4f27ead9083c756cc2": {
        "name": "Wrapped Ether",
        "symbol": "WETH",
        "entity": "Canonical",
        "category": "wrapper",
        "note": "This is WETH (Wrapped Ether), the standard ETH wrapper contract. It is a core piece of DeFi infrastructure used by virtually every decentralized exchange.",
    },
    # Major tokens
    "0x514910771af9ca656af840dff83e8264ecf986ca": {
        "name": "Chainlink",
        "symbol": "LINK",
        "entity": "Chainlink Labs",
        "category": "infrastructure",
        "note": "This is Chainlink (LINK), a top-tier oracle infrastructure token. It is a legitimate, well-established project.",
    },
    "0x1f9840a85d5af5bf1d1762f925bdaddc4201f984": {
        "name": "Uniswap",
        "symbol": "UNI",
        "entity": "Uniswap Labs",
        "category": "defi",
        "note": "This is UNI, the governance token of Uniswap, the largest decentralized exchange. It is a legitimate, well-established project.",
    },
    "0x7d1afa7b718fb893db30a3abc0cfc608aacfebb0": {
        "name": "Polygon",
        "symbol": "MATIC",
        "entity": "Polygon Labs",
        "category": "infrastructure",
        "note": "This is MATIC/POL, the token for Polygon, a major Ethereum scaling solution. Legitimate project.",
    },
    "0x95ad61b0a150d79219dcf64e1e6cc01f0b64c4ce": {
        "name": "Shiba Inu",
        "symbol": "SHIB",
        "entity": "Community",
        "category": "meme",
        "note": "This is SHIB, a well-known meme token. While meme tokens are inherently risky, SHIB has an established market and community.",
    },
    "0x2260fac5e5542a773aa44fbcfedf7c193bc2c599": {
        "name": "Wrapped Bitcoin",
        "symbol": "WBTC",
        "entity": "BitGo",
        "category": "wrapper",
        "note": "This is WBTC (Wrapped Bitcoin), backed 1:1 by Bitcoin and custodied by BitGo, a regulated custodian.",
    },
    # DeFi blue chips
    "0x7fc66500c84a76ad7e9c93437bfc5ac33e2ddae9": {
        "name": "Aave",
        "symbol": "AAVE",
        "entity": "Aave DAO",
        "category": "defi",
        "note": "This is AAVE, the governance token of Aave, a leading DeFi lending protocol. Managed by decentralized governance.",
    },
    "0xd533a949740bb3306d119cc777fa900ba034cd52": {
        "name": "Curve DAO",
        "symbol": "CRV",
        "entity": "Curve Finance",
        "category": "defi",
        "note": "This is CRV, the governance token of Curve Finance, a major decentralized exchange for stablecoins.",
    },
    "0x9f8f72aa9304c8b593d555f12ef6589cc3a579a2": {
        "name": "Maker",
        "symbol": "MKR",
        "entity": "MakerDAO",
        "category": "defi",
        "note": "This is MKR, the governance token of MakerDAO, the protocol behind DAI stablecoin. Well-established DeFi governance.",
    },
}


def _get_client():
    global _client
    if _client is None:
        try:
            import anthropic
            api_key = os.getenv("ANTHROPIC_API_KEY")
            if api_key and api_key != "your_key_here":
                _client = anthropic.AsyncAnthropic(api_key=api_key)
        except ImportError:
            pass
    return _client


def check_known_entity(address: str) -> dict | None:
    """Check if this token is a known, established entity."""
    return KNOWN_ENTITIES.get(address.lower())


def assess_proxy_sophistication(findings: dict) -> str:
    """
    Determines if a proxy setup looks professional or suspicious.

    ENHANCED with actual on-chain admin detection:
    - Reads proxy admin from EIP-1967 admin slot
    - Checks if admin is a Multi-Sig wallet (Gnosis Safe)
    - Checks if admin is a Timelock contract
    - Considers source code patterns (timelock, multisig references)

    Professional indicators:
    - Timelock on upgrades (delay before changes take effect)
    - Multi-sig admin (multiple people must approve changes)
    - Recognized proxy pattern (OpenZeppelin TransparentProxy, UUPS)
    - Role-based access control
    - Governance patterns

    Suspicious indicators:
    - Single EOA (regular wallet) as admin
    - No timelock
    - Proxy combined with hidden ownership transfer functions
    """
    if not findings.get("is_proxy"):
        return "NOT_PROXY"

    suspicious_signals = 0
    professional_signals = 0

    # ── On-chain admin analysis (highest confidence) ──────────────
    admin_type = findings.get("admin_type", "UNKNOWN")

    if admin_type == "TIMELOCK":
        professional_signals += 3  # Strong signal: upgrade delay enforced
    elif admin_type == "MULTISIG":
        professional_signals += 2  # Good: multiple approvals required
    elif admin_type == "EOA":
        suspicious_signals += 2     # Bad: single person can upgrade instantly
    elif admin_type == "CONTRACT":
        professional_signals += 1   # Neutral-positive: at least it's governed

    # ── Source code pattern analysis ──────────────────────────────
    if findings.get("has_timelock_pattern"):
        professional_signals += 2
        # Even better if there's a meaningful delay
        delay_hours = findings.get("timelock_delay_hours", 0)
        if delay_hours >= 24:
            professional_signals += 2  # 24h+ delay is gold standard
        elif delay_hours >= 6:
            professional_signals += 1  # 6h+ is decent

    if findings.get("has_multisig_pattern"):
        professional_signals += 1

    if findings.get("uses_openzeppelin"):
        professional_signals += 1  # Using standard, audited libraries

    if findings.get("has_role_based_access"):
        professional_signals += 1  # Sophisticated access control

    if findings.get("has_governance"):
        professional_signals += 2  # Full governance system

    # ── Existing heuristics ──────────────────────────────────────
    # Ownership renounced on a proxy is unusual but positive
    if findings.get("ownership_renounced"):
        professional_signals += 2

    # Known proxy types suggest professional architecture
    proxy_type = findings.get("proxy_type", "")
    if proxy_type in ("EIP-1967", "EIP-1967 Beacon"):
        professional_signals += 1  # Standard pattern

    # Suspicious ownership combined with proxy = trap
    if findings.get("suspicious_ownership"):
        suspicious_signals += 3

    # Has selfdestruct + proxy = extremely suspicious
    if findings.get("has_selfdestruct"):
        suspicious_signals += 3

    # Tax flip + proxy = can change fees through upgrade
    if findings.get("tax_is_changeable"):
        suspicious_signals += 1

    # Blacklist + proxy + active owner = dangerous combination
    if findings.get("has_blacklist") and not findings.get("ownership_renounced"):
        suspicious_signals += 2

    # Source code public + established patterns
    if findings.get("is_open_source"):
        professional_signals += 1

    # Low deployer dead ratio suggests legitimate developer
    if findings.get("deployer_dead_ratio", 0) < 0.2:
        professional_signals += 1

    if suspicious_signals >= 3:
        return "SUSPICIOUS"
    elif professional_signals >= 3:
        return "PROFESSIONAL"
    else:
        return "UNKNOWN"


def assess_intent(findings: dict) -> str:
    """
    Attempts to distinguish between:
    - RUG_PATTERN: generic rug-pull contract (many danger flags, low effort)
    - PROFESSIONAL: complex architecture with legitimate purpose
    - AMBIGUOUS: can't tell

    Key distinction: a rug-pull contract tends to have MANY cheap danger
    signals (mint + blacklist + hidden owner + tax), while a professional
    contract might have ONE powerful mechanism (proxy) with safeguards.

    ENHANCED: Now considers professional architecture signals from source code
    and on-chain admin detection.
    """
    danger_count = 0
    safeguard_count = 0

    # Count danger signals typical of rug-pulls
    if findings.get("is_mintable"):
        danger_count += 1
    if findings.get("has_blacklist"):
        danger_count += 1
    if findings.get("tax_is_changeable"):
        danger_count += 1
    if findings.get("has_trading_control"):
        danger_count += 1
    if findings.get("has_max_tx_control"):
        danger_count += 1
    if findings.get("suspicious_ownership"):
        danger_count += 2  # This is a strong signal
    if findings.get("has_selfdestruct"):
        danger_count += 2
    if not findings.get("is_open_source"):
        danger_count += 1

    # Count safeguards
    if findings.get("ownership_renounced"):
        safeguard_count += 2
    if findings.get("is_open_source"):
        safeguard_count += 1
    if findings.get("liquidity_locked"):
        safeguard_count += 1
    if findings.get("deployer_dead_ratio", 0) < 0.1:
        safeguard_count += 1
    if findings.get("deployer_total_tokens", 0) <= 3:
        safeguard_count += 1  # Not a token factory

    # ── Enhanced: professional architecture signals ───────────────
    if findings.get("admin_type") == "TIMELOCK":
        safeguard_count += 3  # Strong safeguard
    elif findings.get("admin_type") == "MULTISIG":
        safeguard_count += 2

    if findings.get("has_timelock_pattern"):
        safeguard_count += 1
        if findings.get("timelock_delay_hours", 0) >= 24:
            safeguard_count += 2  # 24h delay = strong safeguard

    if findings.get("has_multisig_pattern"):
        safeguard_count += 1

    if findings.get("uses_openzeppelin"):
        safeguard_count += 1

    if findings.get("has_role_based_access"):
        safeguard_count += 1

    if findings.get("has_governance"):
        safeguard_count += 2

    # Deployer history check
    if findings.get("deployer_dead_ratio", 0) > 0.5:
        danger_count += 2  # Serial rugger

    if danger_count >= 4 and safeguard_count <= 1:
        return "RUG_PATTERN"
    elif danger_count <= 1 and safeguard_count >= 3:
        return "PROFESSIONAL"
    else:
        return "AMBIGUOUS"


async def generate(findings: dict) -> dict:
    """
    Generates beginner-friendly explanations from scan findings.
    Checks known entities and adds context intelligence before generating.
    Falls back to template-based output if AI is unavailable.
    """
    # ── Check if this is a known, trusted entity ──────────────
    token_address = findings.get("token_address", "")
    known = check_known_entity(token_address)

    # ── Assess proxy sophistication and intent ────────────────
    proxy_assessment = assess_proxy_sophistication(findings)
    intent_assessment = assess_intent(findings)

    # Inject these assessments into findings for AI and template use
    findings["_known_entity"] = known
    findings["_proxy_assessment"] = proxy_assessment
    findings["_intent_assessment"] = intent_assessment

    client = _get_client()

    if client is None:
        return _template_explanations(findings)

    try:
        prompt = _build_prompt(findings)

        message = await client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=1200,
            system="""You are SafeBet, a crypto safety tool for complete beginners.
Your job: explain crypto risks so clearly that someone who bought crypto yesterday understands them.

RULES:
- Never use technical jargon. Never say "reentrancy", "ABI", "ERC-20", "wei", "liquidity pool mechanics", "proxy pattern", "delegatecall", "storage slot"
- Always explain consequences in terms of actual money: "your $100 becomes $23"
- Be direct. Beginners need clarity, not hedging.
- The_catch should be one devastating sentence. Maximum impact.
- Verdict should be exactly 3 sentences: what we found, why it matters, what to do.

INTELLIGENCE RULES:
- If the token is a KNOWN ENTITY (like USDC, USDT, LINK), acknowledge it clearly. Explain that while the contract has admin powers, it's managed by a reputable/regulated organization. Don't scare users away from legitimate tokens.
- If the proxy setup looks PROFESSIONAL (timelock, multi-sig, standard patterns), explain that the upgrade ability exists for maintenance, not theft. Still mention the risk but provide context.
- If the admin is a TIMELOCK, explain that changes take time to go into effect (like a 24-hour delay), giving users time to exit. This is a SAFETY feature.
- If the admin is a MULTISIG, explain that multiple people must agree before any changes happen. No single person can make changes alone.
- If the admin is an EOA (regular wallet), warn that ONE person can make instant changes with no delay.
- Distinguish between POWER and MALICE. A stablecoin issuer having freeze powers is different from a random token having freeze powers. The same function in different contexts means very different things.
- If the contract looks like a generic RUG_PATTERN (many cheap danger signals stacked together), be much more aggressive in your warning.
- If the intent is AMBIGUOUS, say so honestly. "We can't be sure, but here's what we found."

- Respond ONLY with the JSON structure. No markdown, no backticks, no preamble.""",
            messages=[{"role": "user", "content": prompt}]
        )

        raw = message.content[0].text.strip()
        raw = raw.replace("```json", "").replace("```", "").strip()

        return json.loads(raw)

    except Exception:
        return _template_explanations(findings)


def _build_prompt(f: dict) -> str:
    investment = f.get("investment_amount", 100)
    after_dump = f.get("investment_value_after_dump", investment)
    dump_impact = f.get("dump_price_impact_percent", 0)
    days_unlock = f.get("days_until_unlock")
    lock_str = (
        f"unlocks in {days_unlock} days" if days_unlock
        else ("NOT LOCKED" if not f.get("liquidity_locked") else "LOCKED")
    )

    # Known entity context
    known = f.get("_known_entity")
    known_section = ""
    if known:
        known_section = f"""
KNOWN ENTITY DETECTED:
- This is {known['name']} ({known['symbol']}), managed by {known['entity']}.
- Category: {known['category']}
- Context: {known['note']}
- IMPORTANT: Adjust your analysis to reflect that this is a known, established token. The flags below may look "scary" but have legitimate purposes in this context.
"""

    # Proxy assessment with admin intelligence
    proxy_assessment = f.get("_proxy_assessment", "NOT_PROXY")
    admin_type = f.get("admin_type", "UNKNOWN")
    proxy_section = ""
    if proxy_assessment == "PROFESSIONAL":
        admin_detail = ""
        if admin_type == "TIMELOCK":
            delay_hours = f.get("timelock_delay_hours", 0)
            admin_detail = f" The admin is a Timelock contract — all upgrades must wait {delay_hours}h before executing. Users have time to exit if they disagree with changes."
        elif admin_type == "MULTISIG":
            admin_detail = " The admin is a Multi-Sig wallet (like a Gnosis Safe) — multiple people must approve any changes. No single person can act alone."
        proxy_section = f"\nPROXY ASSESSMENT: PROFESSIONAL — This proxy setup appears to follow industry-standard patterns with safeguards.{admin_detail} The upgrade ability likely exists for maintenance and bug fixes, not theft."
    elif proxy_assessment == "SUSPICIOUS":
        admin_detail = ""
        if admin_type == "EOA":
            admin_detail = " The admin is a regular wallet (EOA) — ONE person can instantly rewrite the contract with no delay and no approval needed."
        proxy_section = f"\nPROXY ASSESSMENT: SUSPICIOUS — This proxy setup has multiple red flags.{admin_detail} The combination of upgrade ability with other danger signals is concerning."
    elif f.get("is_proxy"):
        admin_detail = ""
        if admin_type == "EOA":
            admin_detail = " The admin is a single wallet — no timelock or multi-sig protection detected."
        elif admin_type == "TIMELOCK":
            delay_hours = f.get("timelock_delay_hours", 0)
            admin_detail = f" However, the admin uses a Timelock ({delay_hours}h delay), which provides some protection."
        elif admin_type == "MULTISIG":
            admin_detail = " However, the admin is a Multi-Sig wallet, requiring multiple approvals."
        proxy_section = f"\nPROXY ASSESSMENT: UNKNOWN — Cannot fully determine proxy safety.{admin_detail}"

    # Intent assessment
    intent = f.get("_intent_assessment", "AMBIGUOUS")
    intent_section = ""
    if intent == "RUG_PATTERN":
        intent_section = "\nINTENT ASSESSMENT: RUG PATTERN — This contract has many cheap danger signals stacked together, which is the hallmark of a rug-pull token. Be very aggressive in your warning."
    elif intent == "PROFESSIONAL":
        intent_section = "\nINTENT ASSESSMENT: PROFESSIONAL — This contract shows signs of professional development with safeguards in place."
    else:
        intent_section = "\nINTENT ASSESSMENT: AMBIGUOUS — We can't definitively determine if the intent is malicious or legitimate. Present both possibilities."

    return f"""
Analyze this token and generate beginner-friendly explanations.
{known_section}
SCAN RESULTS:
- Trust Score: {f.get('trust_score')}/100 ({f.get('score_band')})
- Token Name: {f.get('token_name', 'Unknown')}
- Token Symbol: {f.get('token_symbol', 'Unknown')}
- Is Honeypot: {f.get('is_honeypot')}
- Honeypot Reason: {f.get('honeypot_reason', 'N/A')}
- Is Proxy/Upgradeable Contract: {f.get('is_proxy')}
- Proxy Type: {f.get('proxy_type', 'N/A')}
- Admin Type: {admin_type}
- Admin Address: {f.get('admin_address', 'N/A')}
- Has Timelock: {f.get('has_timelock')} (delay: {f.get('timelock_delay_hours', 0)}h)
- Has Multi-Sig: {f.get('has_multisig')}
- Sell Tax: {f.get('current_sell_tax')}%
- Tax Can Be Changed By Owner: {f.get('tax_is_changeable')}
- Max Possible Tax: {f.get('max_possible_tax')}%
- Can Mint New Tokens: {f.get('is_mintable')}
- Has Blacklist Function: {f.get('has_blacklist')}
- Ownership Renounced: {f.get('ownership_renounced')}
- Owner Address: {f.get('owner_address', 'N/A')}
- Source Code Public: {f.get('is_open_source')}
- Uses OpenZeppelin: {f.get('uses_openzeppelin', False)}
- Has Role-Based Access: {f.get('has_role_based_access', False)}
- Has Governance: {f.get('has_governance', False)}
- Liquidity: ${f.get('liquidity_usd', 0):,.0f}
- Liquidity Status: {lock_str}
- Top Holder Controls: {f.get('top_holder_percent')}% of supply
- Dump Price Impact: {dump_impact}%
- If Top Holder Sells: Your ${investment} becomes ${after_dump}
- Deployer Previous Tokens: {f.get('deployer_total_tokens')}
- Deployer Dead Tokens: {f.get('deployer_dead_tokens')}
- Has Trading Control: {f.get('has_trading_control')}
- Has Max TX Control: {f.get('has_max_tx_control')}
{proxy_section}
{intent_section}

Return ONLY this exact JSON:
{{
  "verdict": "Three sentences. What we found. Why it matters to their money. What they should do.",
  "the_catch": "The single biggest concern in one clear sentence. For known entities, this should be balanced — acknowledge the power but provide context.",
  "flag_explanations": {{
    "honeypot": "plain English only if is_honeypot is true, else null",
    "proxy_trap": "plain English about proxy situation with context. For known entities or professional setups, explain WHY the proxy exists. Mention timelock/multisig if detected.",
    "tax_flip": "plain English only if tax_is_changeable is true, else null",
    "mintable": "plain English only if is_mintable is true. For stablecoins, explain that minting is how new coins are created when people deposit dollars.",
    "blacklist": "plain English only if has_blacklist is true. For regulated stablecoins, explain this is for legal compliance (sanctions, fraud).",
    "liquidity_risk": "plain English about liquidity situation",
    "dump_risk": "plain English using the actual dollar numbers above",
    "deployer_risk": "plain English about deployer history if concerning, else null"
  }}
}}
"""


def _template_explanations(f: dict) -> dict:
    """Template-based fallback when AI is unavailable."""
    score = f.get("trust_score", 0)
    band = f.get("score_band", "UNKNOWN")

    known = f.get("_known_entity")
    intent = f.get("_intent_assessment", "AMBIGUOUS")
    proxy_assessment = f.get("_proxy_assessment", "NOT_PROXY")
    admin_type = f.get("admin_type", "UNKNOWN")

    # ── Known entity shortcut ─────────────────────────────────
    if known:
        return {
            "verdict": (
                f"This is {known['name']} ({known['symbol']}), managed by {known['entity']}. "
                f"While the contract has admin capabilities that our scanner flags, these exist for "
                f"{'regulatory compliance and are standard for stablecoins' if known['category'] == 'stablecoin' else 'legitimate operational purposes'}. "
                f"This is a well-known, established token — proceed normally but understand it is {'centralized' if known['category'] in ('stablecoin', 'wrapper') else 'a legitimate project'}."
            ),
            "the_catch": known["note"],
            "flag_explanations": {
                "honeypot": None,
                "proxy_trap": (
                    f"This contract uses upgradeable patterns, which is standard for {known['entity']}'s infrastructure. "
                    "Updates go through governance processes, not a single developer's whim."
                    if f.get("is_proxy") else None
                ),
                "tax_flip": None,
                "mintable": (
                    f"Yes, {known['entity']} can mint new {known['symbol']}. For a stablecoin, this is how new coins "
                    "are created when customers deposit real dollars. It's a feature, not a bug."
                    if f.get("is_mintable") and known["category"] == "stablecoin"
                    else f"{known['name']} has mint capability as part of its token design."
                    if f.get("is_mintable") else None
                ),
                "blacklist": (
                    f"{known['entity']} can freeze specific wallets. For a regulated stablecoin, this is required by law "
                    "to comply with sanctions and freeze funds involved in crime. It's not used against regular users."
                    if f.get("has_blacklist") and known["category"] == "stablecoin"
                    else None
                ),
                "liquidity_risk": None,
                "dump_risk": None,
                "deployer_risk": None,
            },
        }

    # ── Rug pattern — aggressive warnings ─────────────────────
    if intent == "RUG_PATTERN":
        catches = []
        if f.get("is_honeypot"):
            catches.append("You can buy this token but you will never be able to sell it — your money is gone the moment you buy.")
        if f.get("suspicious_ownership"):
            catches.append("The contract has hidden backdoor functions that let the developer secretly reclaim control at any time.")
        if f.get("is_proxy") and not f.get("ownership_renounced"):
            catches.append("The developer can silently rewrite this contract's rules at any time — every safety check becomes worthless.")
        if f.get("can_change_tax") or f.get("tax_is_changeable"):
            catches.append(f"The developer can raise the sell fee to {f.get('max_possible_tax', 100)}% at any moment, trapping your money forever.")
        if f.get("is_mintable"):
            catches.append("The developer can print unlimited new tokens, instantly crashing the price to zero.")
        if f.get("has_blacklist"):
            catches.append("The developer can freeze your wallet so you can never sell your tokens.")
        if not f.get("is_open_source"):
            catches.append("The source code is completely hidden — there's no way to know what this contract actually does with your money.")

        the_catch = catches[0] if catches else "This token has multiple red flags consistent with a rug-pull scheme."

        verdict = (
            f"This token scored {score}/100 — placing it firmly in the {band} zone. "
            f"The contract has {sum([f.get('is_mintable', False), f.get('has_blacklist', False), f.get('tax_is_changeable', False), f.get('has_trading_control', False), not f.get('is_open_source', True)])} separate danger mechanisms, "
            f"which is the hallmark of a token designed to steal your money. Do not invest — this looks like a scam."
        )
    else:
        # ── Standard analysis ─────────────────────────────────
        catches = []
        if f.get("is_honeypot"):
            catches.append("You can buy this token but you will never be able to sell it — your money is gone the moment you buy.")
        if f.get("is_proxy") and not f.get("ownership_renounced"):
            if proxy_assessment == "PROFESSIONAL":
                if admin_type == "TIMELOCK":
                    delay = f.get("timelock_delay_hours", 0)
                    catches.append(f"The contract can be upgraded, but changes must wait {delay}h before taking effect — giving you time to exit if needed.")
                elif admin_type == "MULTISIG":
                    catches.append("The contract can be upgraded, but only when multiple people agree — no single person can make changes alone.")
                else:
                    catches.append("The contract can be upgraded by its admin. While this follows standard patterns, it means the rules can change after you invest.")
            else:
                if admin_type == "EOA":
                    catches.append("One single wallet can instantly rewrite this contract — no delay, no approval from anyone else. Everything you trust about this token can change in seconds.")
                else:
                    catches.append("The developer can silently rewrite this contract at any time, making every safety check worthless.")
        if f.get("can_change_tax") or f.get("tax_is_changeable"):
            catches.append(f"The developer can raise the sell fee to {f.get('max_possible_tax', 100)}% at any moment, trapping your money.")
        if f.get("is_mintable"):
            catches.append("The developer can create new tokens, which could dilute the value of yours.")
        if f.get("has_blacklist"):
            catches.append("The developer can freeze specific wallets from selling.")
        if not f.get("is_open_source"):
            catches.append("The source code is hidden — there's no way to verify what this contract does.")

        the_catch = catches[0] if catches else "No critical red flags were detected, but always do your own research."

        verdict = (
            f"This token scored {score}/100 on our safety check, placing it in the {band} category. "
            f"{'Multiple serious risk factors were detected that could result in total loss of your investment. ' if score < 55 else 'Some risk factors were detected. '}"
            f"{'We strongly recommend avoiding this token.' if score < 30 else 'Proceed with extreme caution and only invest what you can afford to lose.' if score < 55 else 'The token appears relatively safe but always do your own research.'}"
        )

    # Build flag explanations
    explanations = {
        "honeypot": (
            "You can buy this token but cannot sell it. Your investment would be permanently locked."
            if f.get("is_honeypot") else None
        ),
        "proxy_trap": _proxy_explanation(f, proxy_assessment, admin_type),
        "tax_flip": (
            f"The sell fee can be raised to {f.get('max_possible_tax', 100)}% at any moment by the contract owner."
            if f.get("can_change_tax") or f.get("tax_is_changeable") else None
        ),
        "mintable": (
            "The developer can print unlimited new tokens, crashing the price of existing ones."
            if f.get("is_mintable") else None
        ),
        "blacklist": (
            "The contract has a blacklist function — the developer can freeze specific wallets from selling."
            if f.get("has_blacklist") else None
        ),
        "liquidity_risk": (
            "Liquidity is not locked. The developer can drain all trading funds instantly."
            if not f.get("liquidity_locked") and f.get("liquidity_usd", 0) > 0
            else "Liquidity data not yet available."
        ),
        "dump_risk": (
            f"If the top holder sells, price drops {f.get('dump_price_impact_percent', 0)}%."
            if f.get("dump_price_impact_percent", 0) > 0 else None
        ),
        "deployer_risk": (
            f"This developer has deployed {f.get('deployer_total_tokens', 0)} tokens before, "
            f"and {f.get('deployer_dead_tokens', 0)} of them are now dead — a {f.get('deployer_dead_ratio', 0) * 100:.0f}% failure rate."
            if f.get("deployer_dead_ratio", 0) > 0.3 else None
        ),
    }

    return {
        "verdict": verdict,
        "the_catch": the_catch,
        "flag_explanations": explanations,
    }


def _proxy_explanation(f: dict, proxy_assessment: str, admin_type: str = "UNKNOWN") -> str | None:
    """Generate contextual proxy explanation based on assessment and admin type."""
    if not f.get("is_proxy"):
        return None

    if f.get("ownership_renounced"):
        return "This contract uses an upgradeable pattern, but ownership has been renounced. Nobody can change the contract anymore."

    if proxy_assessment == "PROFESSIONAL":
        if admin_type == "TIMELOCK":
            delay = f.get("timelock_delay_hours", 0)
            return (
                f"This contract can be upgraded, but all changes must pass through a Timelock — "
                f"a mandatory {delay}-hour waiting period before any upgrade takes effect. "
                "This means if the team tries to make a harmful change, you'd have time to sell your tokens first. "
                "This is considered a best-practice security setup."
            )
        elif admin_type == "MULTISIG":
            return (
                "This contract can be upgraded, but only through a Multi-Sig wallet — "
                "meaning multiple team members must agree and approve before any change happens. "
                "No single person can upgrade the contract alone. This is an industry-standard safeguard."
            )
        else:
            return (
                "This contract can be upgraded by its admin. The setup follows industry-standard patterns, "
                "which suggests this is for maintenance and bug fixes rather than malicious purposes. "
                "However, the ability to change the contract still exists — monitor for any upgrades."
            )
    elif proxy_assessment == "SUSPICIOUS":
        if admin_type == "EOA":
            return (
                "The developer can change this contract's code instantly from a regular wallet. "
                "There is no timelock delay and no multi-sig protection — one person, one click, "
                "and every rule in this contract can change. Combined with other danger signals, this is a serious red flag."
            )
        else:
            return (
                "The developer can change this contract's code at any time, invalidating all safety checks. "
                "Combined with other danger signals, this is a serious red flag."
            )
    else:
        if admin_type == "TIMELOCK":
            delay = f.get("timelock_delay_hours", 0)
            return (
                f"The developer can change this contract's code, but there's a {delay}-hour delay before "
                "changes take effect. This gives you some protection but doesn't eliminate all risk."
            )
        elif admin_type == "MULTISIG":
            return (
                "The developer can change this contract's code, but through a multi-sig wallet — "
                "multiple people must approve. This provides some protection."
            )
        elif admin_type == "EOA":
            return (
                "The developer can change this contract's code from a single wallet with no delay. "
                "No timelock or multi-sig protection was detected. Proceed with caution."
            )
        else:
            return (
                "The developer can change this contract's code. We can't determine if the admin uses "
                "a timelock or multi-sig wallet. Proceed with caution."
            )
