"""
Stellar SDK Client — reads issuer account flags for any Stellar asset.

Uses the official stellar-sdk Python library to connect to the public
Stellar Horizon API (no key needed). Fetches the three native account
flags that control asset permissions:

  1. auth_required  — holders need issuer approval before they can hold the asset
  2. auth_revocable — the issuer can freeze/revoke the asset from any holder
  3. auth_immutable — the issuer's flags are permanently locked (can never change)
  4. auth_clawback  — the issuer can claw back tokens from holders

If auth_immutable is False AND auth_revocable is True, the issuer can
freeze your tokens at any time AND could later change that behavior.
"""

from stellar_sdk import ServerAsync
from stellar_sdk.exceptions import NotFoundError, BadResponseError

HORIZON_URL = "https://horizon.stellar.org"


async def fetch_issuer_flags(issuer_address: str) -> dict:
    """
    Fetches account flags for a Stellar issuer address using the Stellar SDK.

    Args:
        issuer_address: Stellar public key (starts with G, 56 characters)

    Returns:
        Dict with flag values, account metadata, and risk assessment.
    """
    try:
        async with ServerAsync(HORIZON_URL) as server:
            # ── Load the account via the SDK ──────────────────
            account_resp = await server.accounts().account_id(issuer_address).call()

        # ── Extract flags ─────────────────────────────────────
        flags = account_resp.get("flags", {})
        auth_required = flags.get("auth_required", False)
        auth_revocable = flags.get("auth_revocable", False)
        auth_immutable = flags.get("auth_immutable", False)
        auth_clawback = flags.get("auth_clawback_enabled", False)

        # ── Extract useful metadata ──────────────────────────
        balances = account_resp.get("balances", [])
        thresholds = account_resp.get("thresholds", {})
        signers = account_resp.get("signers", [])
        home_domain = account_resp.get("home_domain", None)
        num_subentries = account_resp.get("subentry_count", 0)
        data_attr = account_resp.get("data", {})
        last_modified_ledger = account_resp.get("last_modified_ledger", 0)
        sequence = account_resp.get("sequence", "0")

        # ── Parse balances ────────────────────────────────────
        native_balance = "0"
        non_native_balances = []
        for b in balances:
            if b.get("asset_type") == "native":
                native_balance = b.get("balance", "0")
            else:
                non_native_balances.append({
                    "asset_code": b.get("asset_code", ""),
                    "asset_issuer": b.get("asset_issuer", ""),
                    "balance": b.get("balance", "0"),
                    "limit": b.get("limit", "0"),
                })

        # ── Risk assessment ───────────────────────────────────
        risk_level, risk_details = _assess_flags(
            auth_required, auth_revocable, auth_immutable, auth_clawback
        )

        # ── Multi-sig detection ───────────────────────────────
        num_signers = len(signers)
        med_threshold = int(thresholds.get("med_threshold", 0))
        high_threshold = int(thresholds.get("high_threshold", 0))
        low_threshold = int(thresholds.get("low_threshold", 0))
        is_multisig = num_signers > 1 and (med_threshold > 1 or high_threshold > 1)

        # ── Signer details ────────────────────────────────────
        signer_details = [
            {"key": s.get("key", ""), "weight": s.get("weight", 0), "type": s.get("type", "")}
            for s in signers
        ]

        # ── Data entries ──────────────────────────────────────
        has_data_entries = len(data_attr) > 0

        return {
            "success": True,
            "error": None,
            "issuer_address": issuer_address,
            "home_domain": home_domain,

            # The core flags
            "auth_required": auth_required,
            "auth_revocable": auth_revocable,
            "auth_immutable": auth_immutable,
            "auth_clawback_enabled": auth_clawback,

            # Account metadata
            "native_balance_xlm": native_balance,
            "num_signers": num_signers,
            "signer_details": signer_details,
            "is_multisig": is_multisig,
            "med_threshold": med_threshold,
            "high_threshold": high_threshold,
            "low_threshold": low_threshold,
            "subentry_count": int(num_subentries),
            "last_modified_ledger": last_modified_ledger,
            "sequence": sequence,
            "has_data_entries": has_data_entries,

            # Non-native trustlines on this account
            "non_native_balances": non_native_balances,

            # Risk assessment
            "risk_level": risk_level,
            "risk_details": risk_details,
        }

    except NotFoundError:
        return _error("Account not found on the Stellar network. Check the address.")
    except BadResponseError as e:
        return _error(f"Horizon API returned an error: {str(e)}")
    except Exception as e:
        return _error(f"Failed to fetch Stellar account: {str(e)}")


async def fetch_issuer_assets(issuer_address: str) -> list:
    """
    Fetches all assets issued by this account from Horizon using the SDK.
    Returns a list of {asset_code, asset_type, num_accounts, amount}.
    """
    try:
        async with ServerAsync(HORIZON_URL) as server:
            # ── Query assets by issuer via the SDK ────────────
            resp = await server.assets().for_issuer(issuer_address).limit(50).call()

        records = resp.get("_embedded", {}).get("records", [])

        assets = []
        for r in records:
            assets.append({
                "asset_code": r.get("asset_code", ""),
                "asset_type": r.get("asset_type", ""),
                "num_accounts": r.get("num_accounts", 0),
                "amount": r.get("amount", "0"),
                "flags": r.get("flags", {}),
            })

        return assets

    except Exception:
        return []


async def fetch_account_operations(issuer_address: str, limit: int = 10) -> list:
    """
    Fetches recent operations for this account from Horizon using the SDK.
    Returns a list of operation records for additional context.
    """
    try:
        async with ServerAsync(HORIZON_URL) as server:
            resp = await server.operations().for_account(issuer_address).limit(limit).order(desc=True).call()

        records = resp.get("_embedded", {}).get("records", [])

        operations = []
        for r in records:
            operations.append({
                "type": r.get("type", ""),
                "created_at": r.get("created_at", ""),
                "id": r.get("id", ""),
            })

        return operations

    except Exception:
        return []


async def fetch_account_effects(issuer_address: str, limit: int = 10) -> list:
    """
    Fetches recent effects for this account from Horizon using the SDK.
    Returns a list of effect records.
    """
    try:
        async with ServerAsync(HORIZON_URL) as server:
            resp = await server.effects().for_account(issuer_address).limit(limit).order(desc=True).call()

        records = resp.get("_embedded", {}).get("records", [])

        effects = []
        for r in records:
            effects.append({
                "type": r.get("type", ""),
                "created_at": r.get("created_at", ""),
            })

        return effects

    except Exception:
        return []


def _assess_flags(
    auth_required: bool,
    auth_revocable: bool,
    auth_immutable: bool,
    auth_clawback: bool,
) -> tuple[str, list]:
    """
    Assess the risk level based on the combination of flags.

    Returns: (risk_level: str, risk_details: list[str])
    """
    details = []

    # ── auth_immutable is the most important ──────────────────
    if auth_immutable:
        details.append(
            "FLAGS LOCKED: The issuer has permanently locked their account flags. "
            "They can never change these permissions — what you see is what you get forever."
        )
    else:
        details.append(
            "FLAGS NOT LOCKED: The issuer can change these permissions at any time. "
            "Even if things look safe now, the rules could change tomorrow."
        )

    # ── auth_revocable assessment ─────────────────────────────
    if auth_revocable:
        if auth_immutable:
            details.append(
                "FREEZE POWER (permanent): The issuer can freeze your tokens, and this power "
                "can never be removed because flags are locked. For regulated assets (like "
                "stablecoins), this is normal. For random tokens, it's a risk."
            )
        else:
            details.append(
                "FREEZE POWER (changeable): The issuer can freeze your tokens AND could "
                "change their permissions later. This is the most dangerous combination — "
                "the issuer has maximum flexibility to change the rules."
            )
    else:
        details.append(
            "NO FREEZE: The issuer cannot freeze or revoke your tokens. "
            "Once you hold them, they're yours."
        )

    # ── auth_required assessment ──────────────────────────────
    if auth_required:
        details.append(
            "APPROVAL NEEDED: You need the issuer's permission to hold this asset. "
            "They can refuse new holders. This is common for regulated securities/stablecoins."
        )
    else:
        details.append(
            "OPEN ACCESS: Anyone can hold this asset without issuer approval."
        )

    # ── auth_clawback assessment ──────────────────────────────
    if auth_clawback:
        details.append(
            "CLAWBACK ENABLED: The issuer can take back (claw back) tokens from your account. "
            "This is a stronger power than freeze — they can actually remove your tokens."
        )

    # ── Overall risk level ────────────────────────────────────
    if auth_immutable and not auth_revocable and not auth_clawback:
        risk_level = "LOW"
    elif auth_immutable and auth_revocable and not auth_clawback:
        risk_level = "MODERATE"
    elif not auth_immutable and not auth_revocable and not auth_clawback:
        risk_level = "MODERATE"
    elif not auth_immutable and auth_revocable:
        risk_level = "HIGH"
    elif auth_clawback:
        risk_level = "HIGH"
    else:
        risk_level = "MODERATE"

    return risk_level, details


def _error(message: str) -> dict:
    return {
        "success": False,
        "error": message,
        "issuer_address": None,
        "home_domain": None,
        "auth_required": False,
        "auth_revocable": False,
        "auth_immutable": False,
        "auth_clawback_enabled": False,
        "native_balance_xlm": "0",
        "num_signers": 0,
        "signer_details": [],
        "is_multisig": False,
        "med_threshold": 0,
        "high_threshold": 0,
        "low_threshold": 0,
        "subentry_count": 0,
        "last_modified_ledger": 0,
        "sequence": "0",
        "has_data_entries": False,
        "non_native_balances": [],
        "risk_level": "UNKNOWN",
        "risk_details": [message],
    }
