"""
SafeBet Module 2 — Findings Schema

Defines the data contract for trap detection findings, simulation results,
and the overall module output.
"""

from pydantic import BaseModel, Field
from typing import Optional, Any
from enum import Enum


# ─── Enums ────────────────────────────────────────────────────────────────────

class Severity(str, Enum):
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    INFO = "info"


class EvidenceType(str, Enum):
    RUNTIME_CONFIRMED = "runtime_confirmed"
    SOURCE_DETECTED = "source_detected"
    DERIVED_RISK = "derived_risk"
    ON_CHAIN_READ = "on_chain_read"


class SimulationStatus(str, Enum):
    SELLABLE = "sellable"
    CONFIRMED_BLOCKED = "confirmed_blocked"
    CONFISCATORY_TAX = "confiscatory_tax"
    UNAVAILABLE = "unavailable"
    NO_PAIR_FOUND = "no_pair_found"
    ERROR = "error"


class Verdict(str, Enum):
    LOW_CONCERN = "low_concern"
    CAUTION = "caution"
    DANGER = "danger"
    CRITICAL_DANGER = "critical_danger"
    INCONCLUSIVE = "inconclusive"


# ─── Source Scan Models ───────────────────────────────────────────────────────

class SourceMatch(BaseModel):
    """A single regex match found in the Solidity source code."""
    pattern_name: str
    matched_text: str
    line_number: Optional[int] = None
    snippet: str = ""


class SourceCategoryResult(BaseModel):
    """Results for one scan category (e.g., tax_control, blacklist_control)."""
    category: str
    found: bool = False
    matches: list[SourceMatch] = Field(default_factory=list)
    confidence: float = 0.0


class SourceScanResult(BaseModel):
    """Full output from the source code scanner."""
    source_available: bool = False
    source_length: int = 0
    categories: dict[str, SourceCategoryResult] = Field(default_factory=dict)


# ─── On-Chain Read Models ────────────────────────────────────────────────────

class OnChainRead(BaseModel):
    """Result of a single on-chain function call."""
    function_name: str
    value: Optional[Any] = None
    call_success: bool = False
    raw_error: Optional[str] = None


class OnChainSnapshot(BaseModel):
    """All on-chain reads collected for a token."""
    owner: OnChainRead = Field(default_factory=lambda: OnChainRead(function_name="owner"))
    trading_active: OnChainRead = Field(default_factory=lambda: OnChainRead(function_name="tradingActive"))
    trading_open: OnChainRead = Field(default_factory=lambda: OnChainRead(function_name="tradingOpen"))
    swap_enabled: OnChainRead = Field(default_factory=lambda: OnChainRead(function_name="swapEnabled"))
    buy_tax: OnChainRead = Field(default_factory=lambda: OnChainRead(function_name="buyTax"))
    sell_tax: OnChainRead = Field(default_factory=lambda: OnChainRead(function_name="sellTax"))
    total_fees: OnChainRead = Field(default_factory=lambda: OnChainRead(function_name="totalFees"))
    max_tx_amount: OnChainRead = Field(default_factory=lambda: OnChainRead(function_name="maxTxAmount"))
    max_wallet: OnChainRead = Field(default_factory=lambda: OnChainRead(function_name="maxWallet"))
    total_supply: OnChainRead = Field(default_factory=lambda: OnChainRead(function_name="totalSupply"))
    decimals: OnChainRead = Field(default_factory=lambda: OnChainRead(function_name="decimals"))
    name: OnChainRead = Field(default_factory=lambda: OnChainRead(function_name="name"))
    symbol: OnChainRead = Field(default_factory=lambda: OnChainRead(function_name="symbol"))


# ─── Proxy Models ─────────────────────────────────────────────────────────────

class ProxyInfo(BaseModel):
    """Proxy detection results from EIP-1967 slot reads."""
    is_proxy: bool = False
    implementation_address: Optional[str] = None
    admin_address: Optional[str] = None
    upgrade_authority_active: bool = False


# ─── Simulation Models ───────────────────────────────────────────────────────

class SimulationResult(BaseModel):
    """Result of the honeypot sell simulation."""
    status: SimulationStatus = SimulationStatus.UNAVAILABLE
    method: str = "eth_call_state_override"
    router: Optional[str] = None
    pair: Optional[str] = None
    buy_succeeded: Optional[bool] = None
    sell_succeeded: Optional[bool] = None
    revert_reason: Optional[str] = None
    revert_category: Optional[str] = None
    effective_buy_tax_bps: Optional[int] = None
    effective_sell_tax_bps: Optional[int] = None
    tokens_expected: Optional[int] = None
    tokens_received: Optional[int] = None
    error_detail: Optional[str] = None


# ─── Pair / Pool Models ──────────────────────────────────────────────────────

class PairInfo(BaseModel):
    """Resolved trading pair information."""
    pair_address: Optional[str] = None
    token0: Optional[str] = None
    token1: Optional[str] = None
    router_address: Optional[str] = None
    dex_name: Optional[str] = None
    liquidity_usd: Optional[float] = None
    price_usd: Optional[float] = None
    volume_24h_usd: Optional[float] = None
    chain_id: Optional[str] = None
    found: bool = False


# ─── Finding Model ────────────────────────────────────────────────────────────

class Finding(BaseModel):
    """A single trap detection finding."""
    id: str
    severity: Severity
    evidence_type: EvidenceType
    title: str
    what_we_saw: str
    consequence: str
    confidence: float = 0.0
    evidence: dict[str, Any] = Field(default_factory=dict)


# ─── Data Confidence ─────────────────────────────────────────────────────────

class DataConfidence(str, Enum):
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class CheckStatus(BaseModel):
    """Tracks which critical checks ran and which failed."""
    honeypot_simulation: str = "not_run"
    source_code_scan: str = "not_run"
    owner_read: str = "not_run"
    pair_resolution: str = "not_run"
    proxy_check: str = "not_run"
    chain_match: str = "not_run"
    tax_control: str = "unknown"
    blacklist_control: str = "unknown"
    mint_control: str = "unknown"
    trading_control: str = "unknown"


# ─── Module 1 Input ──────────────────────────────────────────────────────────

class Module1Input(BaseModel):
    """Data that Module 1 passes to Module 2."""
    owner_address: Optional[str] = None
    owner_is_renounced: bool = False
    is_proxy: bool = False
    implementation_address: Optional[str] = None
    proxy_admin_address: Optional[str] = None
    deployer_address: Optional[str] = None
    source_code: Optional[str] = None
    is_verified: bool = False
    has_mint: bool = False
    has_tax_setter: bool = False
    has_blacklist: bool = False


# ─── Module 2 Output ─────────────────────────────────────────────────────────

class Module2Result(BaseModel):
    """Complete Module 2 output — the final data package."""
    module: str = "trap_detection"
    status: str = "ok"
    score: int = 100
    verdict: Verdict = Verdict.LOW_CONCERN
    summary: str = ""
    token_address: str = ""
    token_name: Optional[str] = None
    token_symbol: Optional[str] = None

    data_confidence: DataConfidence = DataConfidence.LOW
    checks_status: CheckStatus = Field(default_factory=CheckStatus)

    simulation: SimulationResult = Field(default_factory=SimulationResult)
    proxy_info: ProxyInfo = Field(default_factory=ProxyInfo)
    pair_info: PairInfo = Field(default_factory=PairInfo)
    source_scan: SourceScanResult = Field(default_factory=SourceScanResult)
    on_chain: OnChainSnapshot = Field(default_factory=OnChainSnapshot)

    findings: list[Finding] = Field(default_factory=list)

    chain_id: int = 1
    scan_duration_ms: Optional[int] = None
    errors: list[str] = Field(default_factory=list)


# ─── Scan Request ─────────────────────────────────────────────────────────────

class M2ScanRequest(BaseModel):
    """Input to trigger a Module 2 scan."""
    token_address: str
    chain_id: int = 1
    investment_amount_usd: Optional[float] = None
    module1_data: Optional[Module1Input] = None
