"""
POST /api/stellar/scan — Stellar issuer account flag scanner.

Reads the three native Stellar account flags (auth_required, auth_revocable,
auth_immutable) plus clawback from the issuer's Horizon account data.
Generates a plain-English risk report.
"""

import asyncio
import time
from fastapi import APIRouter, HTTPException
from models.schemas import (
    StellarScanRequest, StellarReport, StellarFlagsData, StellarAssetInfo
)
from blockchain import stellar_client

router = APIRouter()


@router.post("/stellar/scan", response_model=StellarReport)
async def scan_stellar_issuer(request: StellarScanRequest):
    issuer = request.issuer_address.strip()

    # Validate Stellar address format (starts with G, 56 characters, alphanumeric)
    if not issuer.startswith("G") or len(issuer) != 56:
        raise HTTPException(
            status_code=400,
            detail="Invalid Stellar address — must start with G and be 56 characters"
        )

    start_time = time.time()

    try:
        # ─── Fetch account flags and assets in parallel ───────
        flags_result, assets_list = await asyncio.gather(
            stellar_client.fetch_issuer_flags(issuer),
            stellar_client.fetch_issuer_assets(issuer),
        )

        if not flags_result.get("success"):
            raise HTTPException(
                status_code=404,
                detail=flags_result.get("error", "Failed to fetch Stellar account")
            )

        # ─── Build the flag explanations ──────────────────────
        risk_level = flags_result["risk_level"]
        risk_details = flags_result["risk_details"]

        # ─── Generate verdict and the_catch ───────────────────
        the_catch, verdict = _generate_verdict(flags_result, assets_list)

        scan_time = round(time.time() - start_time, 2)

        # ─── Build typed response ─────────────────────────────
        return StellarReport(
            issuer_address=issuer,
            home_domain=flags_result.get("home_domain"),
            flags=StellarFlagsData(
                auth_required=flags_result["auth_required"],
                auth_revocable=flags_result["auth_revocable"],
                auth_immutable=flags_result["auth_immutable"],
                auth_clawback_enabled=flags_result["auth_clawback_enabled"],
            ),
            assets=[
                StellarAssetInfo(
                    asset_code=a["asset_code"],
                    asset_type=a["asset_type"],
                    num_accounts=a.get("num_accounts", 0),
                    amount=a.get("amount", "0"),
                )
                for a in assets_list
            ],
            risk_level=risk_level,
            risk_details=risk_details,
            the_catch=the_catch,
            verdict=verdict,
            native_balance_xlm=flags_result.get("native_balance_xlm", "0"),
            num_signers=flags_result.get("num_signers", 0),
            is_multisig=flags_result.get("is_multisig", False),
            med_threshold=flags_result.get("med_threshold", 0),
            high_threshold=flags_result.get("high_threshold", 0),
            scan_duration_seconds=scan_time,
        )

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Stellar scan failed: {str(e)}")


def _generate_verdict(flags: dict, assets: list) -> tuple[str, str]:
    """
    Generates plain-English the_catch and verdict for Stellar flag scan.
    Returns (the_catch, verdict).
    """
    auth_required = flags["auth_required"]
    auth_revocable = flags["auth_revocable"]
    auth_immutable = flags["auth_immutable"]
    auth_clawback = flags["auth_clawback_enabled"]
    is_multisig = flags.get("is_multisig", False)
    home_domain = flags.get("home_domain")

    asset_count = len(assets)
    total_holders = sum(a.get("num_accounts", 0) for a in assets)

    # ── The Catch ─────────────────────────────────────────────
    if auth_clawback and not auth_immutable:
        the_catch = (
            "The issuer can take your tokens back at any time (clawback enabled), "
            "and this power is NOT permanently locked — the rules can still change."
        )
    elif auth_revocable and not auth_immutable:
        the_catch = (
            "The issuer can freeze your tokens AND hasn't locked their flags — "
            "meaning they could add even more dangerous permissions later."
        )
    elif auth_revocable and auth_immutable:
        the_catch = (
            "The issuer can freeze your tokens. This power is permanently locked in "
            "and can never be removed. For regulated assets this is expected; "
            "for everything else, understand what you're buying."
        )
    elif not auth_immutable:
        the_catch = (
            "The issuer hasn't locked their flags. While nothing looks dangerous right now, "
            "they could enable freeze or clawback powers at any time."
        )
    else:
        the_catch = (
            "The issuer has locked their flags permanently. "
            "No freeze, no clawback — the rules are set in stone."
        )

    # ── Verdict ───────────────────────────────────────────────
    # Sentence 1: What we found
    domain_str = f" ({home_domain})" if home_domain else ""
    found = f"This Stellar issuer account{domain_str} has issued {asset_count} asset{'s' if asset_count != 1 else ''}"
    if total_holders > 0:
        found += f" held across {total_holders:,} trustlines"
    found += "."

    # Sentence 2: Why it matters
    danger_flags = []
    safe_flags = []
    if auth_revocable:
        danger_flags.append("freeze tokens")
    if auth_clawback:
        danger_flags.append("claw back tokens")
    if auth_required:
        danger_flags.append("require approval for new holders")
    if not auth_immutable:
        danger_flags.append("change these permissions later")

    if auth_immutable and not auth_revocable and not auth_clawback:
        safe_flags.append("locked flags with no freeze or clawback")

    if danger_flags:
        matters = f"The issuer can: {', '.join(danger_flags)}."
    elif safe_flags:
        matters = f"Positive signals: {', '.join(safe_flags)}."
    else:
        matters = "No significant red flags detected in the account flags."

    # Sentence 3: What to do
    risk = flags["risk_level"]
    if risk == "HIGH":
        action = "Proceed with extreme caution — this issuer has significant power over your tokens."
    elif risk == "MODERATE":
        action = "The risk level is moderate — check if the issuer is a known, reputable entity before investing."
    elif risk == "LOW":
        action = "The flags look safe — but always verify the issuer's identity and reputation."
    else:
        action = "We couldn't fully assess the risk — do your own research."

    # Add multisig context
    if is_multisig:
        action += " The account uses multi-signature protection, which is a positive sign."

    verdict = f"{found} {matters} {action}"

    return the_catch, verdict
