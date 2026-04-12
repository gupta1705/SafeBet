"""
Dump Calculator — Uniswap V2 Constant Product AMM Simulation

Implements the formula: x * y = k
where:
    x = token reserve in the pool
    y = ETH reserve in the pool
    k = constant product (x * y must always equal k after any trade)

FIXES from original stub:
1. Holder tokens are now calculated from TOTAL SUPPLY, not pool reserves.
   The original used `pool_token_reserve * 10` which was arbitrary and wrong.
2. Supports multi-holder cumulative dump analysis (top 5 holders).
3. Applies Uniswap's 0.3% swap fee to the calculation for real-world accuracy.
4. Handles edge cases: zero reserves, infinite price impact, extremely low liquidity.
5. Optionally applies sell tax from Module 2 to reduce effective dump amount.

THE MATH EXPLAINED:
    Before dump:
        price_before = y / x  (ETH per token)

    After top holder dumps `d` tokens into pool:
        new_x = x + d
        new_y = k / new_x     (k stays constant)
        price_after = new_y / new_x

    Price impact = (price_before - price_after) / price_before * 100

    For the user's investment:
        investment_after_dump = investment * (1 - price_impact / 100)
"""

from typing import Optional

# Uniswap V2 swap fee: 0.3%
UNISWAP_V2_FEE = 0.003


def calculate(
    holders_data: list,
    pool_token_reserve: float,
    pool_eth_reserve: float,
    total_supply: float = 0.0,
    investment_amount: float = 100.0,
    sell_tax_percent: float = 0.0,
) -> dict:
    """
    Calculate the price impact if top holders dump their tokens.

    Args:
        holders_data: List of holder dicts with 'address', 'quantity', 'percent'
        pool_token_reserve: Tokens currently in the liquidity pool (human-readable)
        pool_eth_reserve: ETH currently in the liquidity pool (human-readable)
        total_supply: Total token supply (human-readable, already divided by 10^decimals)
        investment_amount: User's hypothetical investment in USD
        sell_tax_percent: Current sell tax % (from Module 2) — reduces effective dump

    Returns:
        Dict with price impact data, holder grade, and investment outcome
    """

    # ─── Guard: Can we even run the simulation? ───────────────────────
    if not holders_data or pool_token_reserve <= 0 or pool_eth_reserve <= 0:
        return _empty_result(investment_amount)

    top_holder = holders_data[0]
    top_holder_percent = top_holder.get("percent", 0)

    # ─── Calculate top holder's actual token count ────────────────────
    # This is the critical fix: use total_supply, not pool reserves
    if total_supply > 0:
        top_holder_tokens = (top_holder_percent / 100) * total_supply
    else:
        # Fallback: use the quantity from holder data directly
        top_holder_tokens = top_holder.get("quantity", 0)

    if top_holder_tokens <= 0:
        return _empty_result(investment_amount)

    # ─── Apply sell tax reduction ─────────────────────────────────────
    # If there's a sell tax, the effective dump is reduced
    if sell_tax_percent > 0:
        effective_tokens = top_holder_tokens * (1 - sell_tax_percent / 100)
    else:
        effective_tokens = top_holder_tokens

    # ─── Single holder dump simulation ────────────────────────────────
    primary_impact = _simulate_dump(
        dump_tokens=effective_tokens,
        pool_token_reserve=pool_token_reserve,
        pool_eth_reserve=pool_eth_reserve,
    )

    # ─── Multi-holder cumulative dump simulation ──────────────────────
    # What happens if the top 5 holders all sell?
    cumulative_impact = _simulate_cumulative_dump(
        holders_data=holders_data[:5],
        pool_token_reserve=pool_token_reserve,
        pool_eth_reserve=pool_eth_reserve,
        total_supply=total_supply,
        sell_tax_percent=sell_tax_percent,
    )

    # ─── Calculate investment outcome ─────────────────────────────────
    price_impact = primary_impact["price_impact_percent"]
    investment_after = investment_amount * (1 - price_impact / 100)

    # ─── Top 5 holder cumulative percent ──────────────────────────────
    top_5_percent = sum(h.get("percent", 0) for h in holders_data[:5])

    # ─── Pool depth ratio ─────────────────────────────────────────────
    # How much of the pool does the top holder represent?
    # > 100% means the holder owns MORE tokens than the entire pool.
    # This gives critical context: a 30% price impact from a holder who
    # is 200% of the pool means the pool is dangerously shallow.
    pool_depth_ratio = 0.0
    if pool_token_reserve > 0:
        pool_depth_ratio = (effective_tokens / pool_token_reserve) * 100

    # ─── Grade the holder concentration ───────────────────────────────
    grade = _grade_concentration(top_holder_percent, top_5_percent)

    return {
        # Primary (top holder) dump results
        "price_impact_percent": round(price_impact, 2),
        "investment_value_after_dump": round(max(0, investment_after), 2),
        "holder_grade": grade,
        "top_holder_tokens": round(top_holder_tokens, 4),
        "price_before": round(primary_impact["price_before"], 10),
        "price_after": round(primary_impact["price_after"], 10),

        # Multi-holder cumulative results
        "cumulative_dump_impact_percent": round(cumulative_impact["price_impact_percent"], 2),
        "cumulative_investment_after": round(
            max(0, investment_amount * (1 - cumulative_impact["price_impact_percent"] / 100)), 2
        ),
        "top_5_holder_percent": round(top_5_percent, 2),

        # Pool depth context
        "pool_depth_ratio": round(pool_depth_ratio, 2),
    }


def _simulate_dump(
    dump_tokens: float,
    pool_token_reserve: float,
    pool_eth_reserve: float,
) -> dict:
    """
    Core AMM simulation: what happens when `dump_tokens` are sold into the pool.

    Uses the Constant Product formula: x * y = k
    with Uniswap V2's 0.3% fee applied to the input.
    """

    # The constant product
    k = pool_token_reserve * pool_eth_reserve

    # Price before the dump
    price_before = pool_eth_reserve / pool_token_reserve

    # Apply Uniswap 0.3% fee to the dump amount
    # The fee is taken from the input tokens
    effective_dump = dump_tokens * (1 - UNISWAP_V2_FEE)

    # After dump: new reserves
    new_token_reserve = pool_token_reserve + effective_dump
    new_eth_reserve = k / new_token_reserve

    # Price after the dump
    price_after = new_eth_reserve / new_token_reserve

    # Price impact percentage
    if price_before > 0:
        price_impact = ((price_before - price_after) / price_before) * 100
    else:
        price_impact = 0.0

    # Cap at 99.9% — can't go beyond total loss
    price_impact = min(price_impact, 99.9)

    return {
        "price_impact_percent": price_impact,
        "price_before": price_before,
        "price_after": price_after,
        "new_token_reserve": new_token_reserve,
        "new_eth_reserve": new_eth_reserve,
    }


def _simulate_cumulative_dump(
    holders_data: list,
    pool_token_reserve: float,
    pool_eth_reserve: float,
    total_supply: float,
    sell_tax_percent: float = 0.0,
) -> dict:
    """
    Simulate multiple holders selling sequentially.
    Each sale shifts the reserves, so subsequent sales face worse prices.
    This models a realistic "panic sell" cascade.
    """

    if not holders_data:
        return {"price_impact_percent": 0.0}

    current_token_reserve = pool_token_reserve
    current_eth_reserve = pool_eth_reserve
    original_price = pool_eth_reserve / pool_token_reserve if pool_token_reserve > 0 else 0

    for holder in holders_data:
        holder_pct = holder.get("percent", 0)
        if holder_pct <= 0:
            continue

        # Calculate this holder's tokens
        if total_supply > 0:
            holder_tokens = (holder_pct / 100) * total_supply
        else:
            holder_tokens = holder.get("quantity", 0)

        if holder_tokens <= 0:
            continue

        # Apply sell tax
        if sell_tax_percent > 0:
            holder_tokens *= (1 - sell_tax_percent / 100)

        # Simulate this holder's dump against current reserves
        result = _simulate_dump(
            dump_tokens=holder_tokens,
            pool_token_reserve=current_token_reserve,
            pool_eth_reserve=current_eth_reserve,
        )

        # Update reserves for the next holder's simulation
        current_token_reserve = result["new_token_reserve"]
        current_eth_reserve = result["new_eth_reserve"]

    # Final price after all holders have dumped
    final_price = current_eth_reserve / current_token_reserve if current_token_reserve > 0 else 0

    if original_price > 0:
        total_impact = ((original_price - final_price) / original_price) * 100
        total_impact = min(total_impact, 99.9)
    else:
        total_impact = 0.0

    return {"price_impact_percent": total_impact}


def _grade_concentration(top_holder_percent: float, top_5_percent: float = 0.0) -> str:
    """
    Grade holder concentration risk.

    Considers both the #1 holder AND cumulative top-5 concentration.
    A single whale with 60% is worse than 5 holders with 12% each,
    even though both sum to 60%.

    Grading:
        A — Healthy distribution, low concentration risk
        B — Moderate concentration, some risk
        C — High concentration, significant dump risk
        D — Very high concentration, major dump risk
        F — Extreme concentration, near-certain rug risk
    """
    # Primary factor: single holder dominance
    if top_holder_percent >= 50:
        return "F"
    if top_holder_percent >= 30:
        return "D"

    # Secondary factor: cumulative top-5 concentration
    if top_5_percent > 0:
        if top_holder_percent >= 15 and top_5_percent >= 60:
            return "D"
        if top_holder_percent >= 15:
            return "C"
        if top_5_percent >= 50:
            return "C"
        if top_holder_percent >= 5:
            return "B"
        return "A"

    # Fallback: only top holder data available
    if top_holder_percent >= 15:
        return "C"
    if top_holder_percent >= 5:
        return "B"
    return "A"


def _empty_result(investment_amount: float = 100.0) -> dict:
    """Default values when calculation cannot be performed."""
    return {
        "price_impact_percent": 0.0,
        "investment_value_after_dump": investment_amount,
        "holder_grade": "N/A",
        "top_holder_tokens": 0,
        "price_before": 0,
        "price_after": 0,
        "cumulative_dump_impact_percent": 0.0,
        "cumulative_investment_after": investment_amount,
        "top_5_holder_percent": 0.0,
        "pool_depth_ratio": 0.0,
    }
