from pydantic import BaseModel
from typing import Optional


class ScanRequest(BaseModel):
    address: str
    investment_amount: Optional[float] = 100.0   # Default $100 for calculations


class Module1Data(BaseModel):
    """Contract Control Analysis — who controls this token and what powers they have."""
    is_proxy: bool
    proxy_implementation: Optional[str] = None
    proxy_type: Optional[str] = None
    admin_address: Optional[str] = None
    admin_type: Optional[str] = None        # EOA, MULTISIG, TIMELOCK, CONTRACT, UNKNOWN
    has_timelock: bool = False
    has_multisig: bool = False
    owner_address: Optional[str] = None
    ownership_renounced: bool
    can_change_tax: bool
    is_mintable: bool
    has_blacklist: bool
    has_max_tx_control: bool
    has_trading_control: bool
    is_open_source: bool
    deployer_address: Optional[str] = None
    deployer_total_tokens: int
    deployer_dead_tokens: int
    deployer_dead_ratio: float
    # Professional architecture indicators
    has_timelock_pattern: bool = False
    timelock_delay_hours: float = 0
    has_multisig_pattern: bool = False
    uses_openzeppelin: bool = False
    has_role_based_access: bool = False
    has_governance: bool = False


class Module2Finding(BaseModel):
    """A single trap detection finding for frontend rendering."""
    id: str
    severity: str                    # critical / high / medium / low / info
    evidence_type: str               # runtime_confirmed / source_detected / derived_risk / on_chain_read
    title: str
    what_we_saw: str
    consequence: str
    confidence: float = 0.0


class Module2Data(BaseModel):
    """Trap Detection — Full Module 2 results."""
    # Legacy fields (kept for backward compatibility)
    is_honeypot: bool = False
    honeypot_reason: Optional[str] = None
    honeypot_confidence: str = "PENDING"         # PENDING / LOW / MEDIUM / HIGH
    current_sell_tax: float = 0
    current_buy_tax: float = 0
    max_possible_tax: float = 100
    tax_is_changeable: bool = False
    proxy_trap_active: bool = False
    has_selfdestruct: bool = False
    has_suspicious_functions: bool = False

    # Module 2 enhanced fields
    simulation_status: str = "unavailable"       # sellable / confirmed_blocked / confiscatory_tax / unavailable / no_pair_found / error
    m2_score: int = 100                          # 0-100 trap detection score
    m2_verdict: str = "inconclusive"             # low_concern / caution / danger / critical_danger / inconclusive
    m2_summary: str = ""                         # Plain English summary
    data_confidence: str = "low"                 # high / medium / low
    findings_count: int = 0
    critical_count: int = 0
    high_count: int = 0

    # Detailed findings (for frontend rendering)
    detailed_findings: list[Module2Finding] = []

    # Check execution status
    honeypot_sim_status: str = "not_run"         # passed / failed / not_testable / not_run
    source_scan_status: str = "not_run"          # scanned / unverified / not_run
    owner_read_status: str = "not_run"           # readable / not_readable / not_run
    pair_found: bool = False
    detected_chain: Optional[str] = None

    # DEX pair info
    pair_address: Optional[str] = None
    router_address: Optional[str] = None
    dex_name: Optional[str] = None
    liquidity_usd: Optional[float] = None

    # Module 2 scan duration
    m2_scan_duration_ms: Optional[int] = None


class Module3Data(BaseModel):
    """Collapse Simulation — Liquidity & Dump Risk Analysis."""
    # Liquidity health
    liquidity_usd: float = 0
    liquidity_locked: bool = False
    lock_expiry_timestamp: Optional[int] = None
    lock_expiry_readable: Optional[str] = None
    days_until_unlock: Optional[int] = None

    # Holder concentration — primary holder
    top_holder_address: Optional[str] = None
    top_holder_percent: float = 0

    # Holder concentration — cumulative (top 5)
    top_5_holder_percent: float = 0.0

    # Dump simulation results
    dump_price_impact_percent: float = 0
    investment_value_after_dump: float = 0
    holder_grade: str = "N/A"                  # A / B / C / D / F / N/A

    # Multi-holder cumulative dump results
    cumulative_dump_impact_percent: float = 0.0
    cumulative_investment_after: float = 0.0

    # Pool state
    pool_token_reserve: float = 0
    pool_eth_reserve: float = 0
    pool_depth_ratio: float = 0.0

    # DEX pair info (for linking/transparency)
    pair_address: Optional[str] = None

    # On-chain LP lock verification
    lp_lock_method: str = "unknown"            # burned / locked_unicrypt / none / unknown
    lp_burned_percent: float = 0.0
    lp_locked_percent: float = 0.0
    lp_total_secured_percent: float = 0.0
    lp_locker_name: Optional[str] = None
    lp_consequence: str = ""

    # Status flag — tells frontend if data was available
    data_status: str = "OK"                    # OK / NO_PAIR / LOW_LIQUIDITY / ERROR


class SafeBetReport(BaseModel):
    token_address: str
    token_name: Optional[str] = None
    token_symbol: Optional[str] = None
    trust_score: int
    score_band: str
    the_catch: str
    verdict: str
    module1: Module1Data
    module2: Module2Data
    module3: Module3Data
    flag_explanations: dict
    scan_duration_seconds: float


# ══════════════════════════════════════════════════════════════════
# STELLAR SCHEMAS
# ══════════════════════════════════════════════════════════════════

class StellarScanRequest(BaseModel):
    """Scan request for a Stellar asset issuer account."""
    issuer_address: str


class StellarFlagsData(BaseModel):
    """The three native Stellar issuer account flags."""
    auth_required: bool = False
    auth_revocable: bool = False
    auth_immutable: bool = False
    auth_clawback_enabled: bool = False


class StellarAssetInfo(BaseModel):
    """Info about an asset issued by the account."""
    asset_code: str
    asset_type: str
    num_accounts: int = 0
    amount: str = "0"


class StellarReport(BaseModel):
    """Full report for a Stellar issuer account scan."""
    issuer_address: str
    home_domain: Optional[str] = None
    flags: StellarFlagsData
    assets: list[StellarAssetInfo] = []
    risk_level: str          # LOW, MODERATE, HIGH, UNKNOWN
    risk_details: list[str]  # Plain-English explanations
    the_catch: str
    verdict: str
    # Account metadata
    native_balance_xlm: str = "0"
    num_signers: int = 0
    is_multisig: bool = False
    med_threshold: int = 0
    high_threshold: int = 0
    scan_duration_seconds: float

