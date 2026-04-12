"""
SafeBet — Module 2 Source Scanner

Scans Solidity source code for dangerous patterns using grouped regex.
8 categories: tax_control, trading_control, blacklist_control, wallet_limits,
cooldown_control, upgradeability, destructive_pattern, mint_control.

Named module2_source_scanner to avoid collision with Module 1's source_scanner.
"""

import re
import logging
from dataclasses import dataclass

from schemas.findings import SourceScanResult, SourceCategoryResult, SourceMatch

logger = logging.getLogger(__name__)


@dataclass
class PatternDef:
    name: str
    pattern: str
    flags: int = re.IGNORECASE


SCAN_CATEGORIES: dict[str, list[PatternDef]] = {
    "tax_control": [
        PatternDef("setSellTax", r"function\s+set\w*[Ss]ell\w*[Tt]ax\w*\s*\("),
        PatternDef("setBuyTax", r"function\s+set\w*[Bb]uy\w*[Tt]ax\w*\s*\("),
        PatternDef("setFee", r"function\s+set\w*[Ff]ee[s]?\s*\("),
        PatternDef("updateFees", r"function\s+update\w*[Ff]ee[s]?\s*\("),
        PatternDef("setTaxes", r"function\s+set\w*[Tt]ax\w*\s*\("),
        PatternDef("taxFeeStorage", r"(?:uint\d*\s+(?:public|private|internal)\s+)?_(?:tax|marketing|liquidity|dev)[Ff]ee"),
        PatternDef("setMarketingFee", r"function\s+set\w*[Mm]arketing\w*[Ff]ee\w*\s*\("),
        PatternDef("setLiquidityFee", r"function\s+set\w*[Ll]iquidity\w*[Ff]ee\w*\s*\("),
        PatternDef("changeFee", r"function\s+change\w*[Ff]ee[s]?\s*\("),
    ],

    "trading_control": [
        PatternDef("enableTrading", r"function\s+enable[Tt]rading\s*\("),
        PatternDef("disableTrading", r"function\s+disable[Tt]rading\s*\("),
        PatternDef("openTrading", r"function\s+open[Tt]rading\s*\("),
        PatternDef("setTradingEnabled", r"function\s+set\w*[Tt]rading\w*\s*\("),
        PatternDef("tradingActiveVar", r"bool\s+(?:public\s+)?trading(?:Active|Open|Enabled)"),
        PatternDef("swapEnabledVar", r"bool\s+(?:public\s+)?swap(?:Enabled|Active)"),
        PatternDef("limitsInEffect", r"bool\s+(?:public\s+)?limitsInEffect"),
        PatternDef("pausable", r"function\s+(?:pause|unpause)\s*\("),
        PatternDef("whenNotPaused", r"modifier\s+whenNotPaused"),
    ],

    "blacklist_control": [
        PatternDef("blacklistFunc", r"function\s+(?:blacklist|addToBlacklist|setBlacklist|addBlacklist)\w*\s*\("),
        PatternDef("isBlacklisted", r"(?:mapping|bool).*(?:isBlacklisted|_isBlacklisted|blacklisted|isBlackListed)"),
        PatternDef("banAddress", r"function\s+(?:ban|block)\w*[Aa]ddress\w*\s*\("),
        PatternDef("isBot", r"(?:mapping|bool).*(?:isBot|_isBot|bots|_bots)"),
        PatternDef("setBots", r"function\s+set[Bb]ots?\s*\("),
        PatternDef("blockedMapping", r"mapping.*(?:blocked|_blocked|isBlocked)"),
        PatternDef("whitelistOnly", r"function\s+(?:whitelist|addToWhitelist|setWhitelist)\w*\s*\("),
        PatternDef("excludeFromMapping", r"mapping.*(?:isExcluded|_isExcluded|excludedFrom)"),
    ],

    "wallet_limits": [
        PatternDef("maxTxAmount", r"(?:uint\d*\s+)?(?:public\s+)?(?:_)?max(?:Tx|Transaction)Amount"),
        PatternDef("maxWallet", r"(?:uint\d*\s+)?(?:public\s+)?(?:_)?max(?:Wallet|WalletSize|WalletAmount)"),
        PatternDef("maxSell", r"(?:uint\d*\s+)?(?:public\s+)?(?:_)?maxSell(?:Amount)?"),
        PatternDef("setMaxTx", r"function\s+set\w*[Mm]ax\w*(?:[Tt]x|[Tt]ransaction)\w*\s*\("),
        PatternDef("setMaxWallet", r"function\s+set\w*[Mm]ax\w*[Ww]allet\w*\s*\("),
        PatternDef("removeLimits", r"function\s+remove[Ll]imits\s*\("),
    ],

    "cooldown_control": [
        PatternDef("cooldownMapping", r"mapping.*(?:cooldown|_cooldown|cooldowns)"),
        PatternDef("transferDelay", r"(?:uint\d*\s+)?(?:public\s+)?(?:_)?transferDelay"),
        PatternDef("buyCooldown", r"(?:uint\d*\s+)?(?:public\s+)?(?:_)?buyCooldown"),
        PatternDef("sellCooldown", r"(?:uint\d*\s+)?(?:public\s+)?(?:_)?sellCooldown"),
        PatternDef("setCooldown", r"function\s+set\w*[Cc]ooldown\w*\s*\("),
        PatternDef("blockDelay", r"require\s*\(.*block\.(?:number|timestamp)\s*[-+><]="),
    ],

    "upgradeability": [
        PatternDef("upgradeTo", r"function\s+upgradeTo\s*\("),
        PatternDef("upgradeToAndCall", r"function\s+upgradeToAndCall\s*\("),
        PatternDef("authorizeUpgrade", r"function\s+_authorizeUpgrade\s*\("),
        PatternDef("proxyImport", r"import.*(?:Proxy|UUPSUpgradeable|TransparentUpgradeable)"),
        PatternDef("initializable", r"import.*Initializable|contract\s+\w+\s+is.*Initializable"),
    ],

    "destructive_pattern": [
        PatternDef("selfdestruct", r"\bselfdestruct\s*\("),
        PatternDef("delegatecall", r"\.delegatecall\s*\("),
        PatternDef("renounceWithCondition", r"function\s+renounceOwnership.*require"),
    ],

    "mint_control": [
        PatternDef("mintFunction", r"function\s+mint\s*\("),
        PatternDef("mintInternal", r"function\s+_mint\s*\("),
        PatternDef("mintable", r"import.*Mintable|contract\s+\w+\s+is.*Mintable"),
    ],
}


def _strip_comments(source: str) -> str:
    """Remove single-line and multi-line comments from Solidity source."""
    source = re.sub(r"/\*.*?\*/", "", source, flags=re.DOTALL)
    source = re.sub(r"//[^\n]*", "", source)
    return source


def _get_snippet(lines: list[str], line_idx: int, context: int = 2) -> str:
    """Get a snippet of surrounding lines for context."""
    start = max(0, line_idx - context)
    end = min(len(lines), line_idx + context + 1)
    snippet_lines = lines[start:end]
    return "\n".join(snippet_lines).strip()


def scan_source(source_code: str | None) -> SourceScanResult:
    """
    Scan Solidity source code for dangerous patterns.

    Returns SourceScanResult with all category matches and confidence scores.
    """
    result = SourceScanResult()

    if not source_code or len(source_code.strip()) == 0:
        result.source_available = False
        return result

    result.source_available = True
    result.source_length = len(source_code)

    cleaned = _strip_comments(source_code)
    lines = cleaned.split("\n")
    original_lines = source_code.split("\n")

    for category_name, patterns in SCAN_CATEGORIES.items():
        cat_result = SourceCategoryResult(category=category_name)
        total_patterns = len(patterns)
        matched_patterns = 0

        for pdef in patterns:
            regex = re.compile(pdef.pattern, pdef.flags)

            for line_idx, line in enumerate(lines):
                match = regex.search(line)
                if match:
                    matched_patterns += 1
                    cat_result.found = True

                    snippet = _get_snippet(
                        original_lines,
                        min(line_idx, len(original_lines) - 1),
                        context=2
                    )

                    cat_result.matches.append(SourceMatch(
                        pattern_name=pdef.name,
                        matched_text=match.group(0).strip(),
                        line_number=line_idx + 1,
                        snippet=snippet,
                    ))
                    break

        if matched_patterns > 0:
            cat_result.confidence = min(1.0, 0.5 + (matched_patterns / total_patterns) * 0.5)
        else:
            cat_result.confidence = 0.0

        result.categories[category_name] = cat_result

    found_cats = [k for k, v in result.categories.items() if v.found]
    if found_cats:
        logger.info(f"Module 2 source scan found patterns in: {', '.join(found_cats)}")
    else:
        logger.info("Module 2 source scan: no dangerous patterns found")

    return result
