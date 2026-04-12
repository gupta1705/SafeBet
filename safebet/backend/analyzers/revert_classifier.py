"""
SafeBet — Revert Classifier

Maps raw EVM revert reason strings to friendly categories and consequence
sentences. Used by the sell simulator and trap rules.
"""

import re
import logging

logger = logging.getLogger(__name__)


REVERT_CATEGORIES = {
    "transfer_failed": {
        "patterns": [
            r"transfer.*fail",
            r"TRANSFER_FAILED",
            r"TransferHelper.*TRANSFER_FROM_FAILED",
            r"SafeERC20.*low-level call failed",
        ],
        "label": "Transfer Blocked",
        "consequence": "The token's transfer function is actively blocking this transaction. Selling may be impossible.",
    },
    "trading_not_active": {
        "patterns": [
            r"trading\s*(is\s*)?not\s*(active|open|enabled)",
            r"trading\s*not\s*yet",
            r"trading\s*disabled",
            r"not\s*launched",
        ],
        "label": "Trading Disabled",
        "consequence": "The token has a trading switch that is currently turned off. The owner can enable or disable trading at will.",
    },
    "blacklisted": {
        "patterns": [
            r"blacklist",
            r"banned",
            r"blocked",
            r"is\s*bot",
            r"sniper",
            r"anti.?bot",
        ],
        "label": "Wallet Blacklisted",
        "consequence": "This address has been blacklisted. The contract can selectively freeze individual wallets from trading.",
    },
    "max_tx_exceeded": {
        "patterns": [
            r"max\s*tx",
            r"max\s*transaction",
            r"exceeds\s*max",
            r"amount\s*exceeds",
            r"transfer\s*amount\s*exceeds",
        ],
        "label": "Max Transaction Exceeded",
        "consequence": "The sell amount exceeds the maximum transaction limit. This can be set so low that selling meaningful amounts is practically impossible.",
    },
    "max_wallet_exceeded": {
        "patterns": [
            r"max\s*wallet",
            r"wallet\s*limit",
            r"exceeds\s*max\s*wallet",
        ],
        "label": "Max Wallet Exceeded",
        "consequence": "The receiving wallet would exceed the maximum wallet holding limit.",
    },
    "cooldown_active": {
        "patterns": [
            r"cooldown",
            r"transfer\s*delay",
            r"wait\s*before",
            r"too\s*soon",
            r"too\s*frequent",
        ],
        "label": "Cooldown Active",
        "consequence": "A cooldown timer is preventing this transaction. The contract enforces a waiting period between trades.",
    },
    "insufficient_output": {
        "patterns": [
            r"INSUFFICIENT_OUTPUT_AMOUNT",
            r"insufficient\s*output",
            r"slippage",
            r"K$",
        ],
        "label": "Insufficient Output",
        "consequence": "The effective tax or price impact is so high that the output amount is below the minimum.",
    },
    "paused": {
        "patterns": [
            r"paused",
            r"Pausable.*paused",
            r"contract\s*is\s*paused",
        ],
        "label": "Contract Paused",
        "consequence": "The token contract is currently paused. All transfers are blocked until the owner unpauses it.",
    },
    "ownable": {
        "patterns": [
            r"Ownable.*caller\s*is\s*not\s*the\s*owner",
            r"only\s*owner",
            r"not\s*authorized",
        ],
        "label": "Owner Only",
        "consequence": "This function is restricted to the contract owner only.",
    },
}


def classify_revert(revert_reason: str | None) -> tuple[str, str, str]:
    """
    Classify a revert reason string.

    Returns:
        Tuple of (category_id, label, consequence)
    """
    if not revert_reason:
        return (
            "unknown",
            "Unknown Revert",
            "The transaction failed for an unknown reason. The contract may be blocking sells."
        )

    reason_lower = revert_reason.lower()

    for cat_id, cat_info in REVERT_CATEGORIES.items():
        for pattern in cat_info["patterns"]:
            if re.search(pattern, reason_lower):
                return (cat_id, cat_info["label"], cat_info["consequence"])

    return (
        "unknown",
        "Unknown Revert",
        f"The transaction was rejected by the contract: \"{revert_reason[:100]}\". This may indicate the token prevents selling."
    )


def get_revert_severity(category: str) -> str:
    """Map revert category to severity level."""
    critical_categories = {"transfer_failed", "trading_not_active", "blacklisted", "paused"}
    high_categories = {"max_tx_exceeded", "max_wallet_exceeded", "cooldown_active"}

    if category in critical_categories:
        return "critical"
    elif category in high_categories:
        return "high"
    else:
        return "medium"
