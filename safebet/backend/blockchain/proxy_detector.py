"""
EIP-1967 Transparent Proxy Standard detection + Admin Intelligence.

Implementation address stored at specific predetermined storage slots.
If that slot has a non-zero address, this contract is a proxy (upgradeable).

ENHANCED:
- Reads the proxy admin address from the EIP-1967 admin slot
- Determines if the admin is a Multi-Sig wallet (Gnosis Safe)
- Detects Timelock contracts as admin
- Reports admin type for smarter risk assessment
"""

from .rpc_client import read_storage_slot, get_code

# Official EIP-1967 implementation slot
# keccak256("eip1967.proxy.implementation") - 1
EIP1967_IMPLEMENTATION_SLOT = (
    "0x360894a13ba1a3210667c828492db98dca3e2076cc3735a920a3ca505d382bbc"
)

# EIP-1967 beacon slot
# keccak256("eip1967.proxy.beacon") - 1
EIP1967_BEACON_SLOT = (
    "0xa3f0ad74e5423aebfd80d3ef4346578335a9a72aeaee59ff6cb3582b35133d50"
)

# EIP-1967 admin slot
# keccak256("eip1967.proxy.admin") - 1
EIP1967_ADMIN_SLOT = (
    "0xb53127684a568b3173ae13b9f8a6016e243e63b6e8ee1178d6a717850b5d6103"
)

# Older OpenZeppelin proxy slot (pre-EIP-1967)
# keccak256("org.zeppelinos.proxy.implementation")
OPENZEPPELIN_LEGACY_SLOT = (
    "0x7050c9e0f4ca769c69bd3a8ef740bc37934f8e2c036e5a723fd8ee048ed3f8c3"
)

ZERO_40 = "0" * 40

# ══════════════════════════════════════════════════════════════════
# KNOWN MULTI-SIG BYTECODE SIGNATURES
# Gnosis Safe contracts have recognizable bytecode patterns.
# We check the first few bytes of the admin's deployed code.
# ══════════════════════════════════════════════════════════════════
GNOSIS_SAFE_SIGNATURES = [
    b"\x60\x80\x60\x40",  # Standard Gnosis Safe proxy prefix
]

# Timelock contracts often contain these method signatures in their bytecode
# delay() selector: 0x6a42b8f8
# MINIMUM_DELAY selector: 0xb1b43ae5
# queueTransaction selector: 0x3a66f901
TIMELOCK_SELECTORS = [
    bytes.fromhex("6a42b8f8"),  # delay()
    bytes.fromhex("b1b43ae5"),  # MINIMUM_DELAY()
    bytes.fromhex("3a66f901"),  # queueTransaction()
    bytes.fromhex("c1a287e2"),  # GRACE_PERIOD()
    bytes.fromhex("7d645fab"),  # MAXIMUM_DELAY()
]

# Gnosis Safe method selectors
GNOSIS_SELECTORS = [
    bytes.fromhex("0d582f13"),  # addOwnerWithThreshold()
    bytes.fromhex("e009cfde"),  # removeOwner()
    bytes.fromhex("694e80c3"),  # changeThreshold()
    bytes.fromhex("a0e67e2b"),  # getOwners()
    bytes.fromhex("e75235b8"),  # getThreshold()
]


async def check_proxy(token_address: str) -> dict:
    """
    Reads proxy storage slots directly from the blockchain.
    Returns proxy status with implementation address, admin address,
    and admin type (EOA, MULTISIG, TIMELOCK, CONTRACT).
    """
    slots_to_check = [
        (EIP1967_IMPLEMENTATION_SLOT, "EIP-1967"),
        (EIP1967_BEACON_SLOT, "EIP-1967 Beacon"),
        (OPENZEPPELIN_LEGACY_SLOT, "OpenZeppelin Legacy"),
    ]

    for slot, proxy_type in slots_to_check:
        try:
            raw = await read_storage_slot(token_address, slot)
            implementation = "0x" + raw.hex()[-40:]

            if implementation != "0x" + ZERO_40:
                # Found a proxy — now check for the admin
                admin_info = await _detect_admin(token_address)

                return {
                    "is_proxy": True,
                    "implementation": implementation,
                    "proxy_type": proxy_type,
                    "admin_address": admin_info.get("admin_address"),
                    "admin_type": admin_info.get("admin_type", "UNKNOWN"),
                    "has_timelock": admin_info.get("has_timelock", False),
                    "has_multisig": admin_info.get("has_multisig", False),
                }
        except Exception:
            continue

    return {
        "is_proxy": False,
        "implementation": None,
        "proxy_type": None,
        "admin_address": None,
        "admin_type": None,
        "has_timelock": False,
        "has_multisig": False,
    }


async def _detect_admin(token_address: str) -> dict:
    """
    Read the EIP-1967 admin slot and classify the admin address.

    Classification:
    - EOA: Regular wallet (no bytecode) — instant upgrades, risky
    - MULTISIG: Gnosis Safe or similar — requires multiple approvals
    - TIMELOCK: TimelockController — enforces delay before execution
    - CONTRACT: Has bytecode but unrecognized pattern — could be anything
    - UNKNOWN: Couldn't determine
    """
    result = {
        "admin_address": None,
        "admin_type": "UNKNOWN",
        "has_timelock": False,
        "has_multisig": False,
    }

    try:
        # Read the admin slot
        raw = await read_storage_slot(token_address, EIP1967_ADMIN_SLOT)
        admin_address = "0x" + raw.hex()[-40:]

        if admin_address == "0x" + ZERO_40:
            return result

        result["admin_address"] = admin_address

        # Check if admin has bytecode (is it a contract or EOA?)
        code = await get_code(admin_address)

        if not code or code == b"" or code == b"\x00":
            # No bytecode = EOA (regular wallet) = instant upgrades
            result["admin_type"] = "EOA"
            return result

        # It's a contract — check if it's a known safe pattern
        code_hex = code.hex() if isinstance(code, bytes) else str(code)

        # Check for Timelock patterns
        is_timelock = any(
            selector.hex() in code_hex for selector in TIMELOCK_SELECTORS
        )
        if is_timelock:
            result["admin_type"] = "TIMELOCK"
            result["has_timelock"] = True

            # Check if the timelock itself is governed by a multisig
            # (This is the gold standard: Timelock → Multisig)
            # We'd need to check the timelock's admin, but that's
            # another layer — mark as timelock for now
            return result

        # Check for Gnosis Safe / Multi-Sig patterns
        is_multisig = any(
            selector.hex() in code_hex for selector in GNOSIS_SELECTORS
        )
        if is_multisig:
            result["admin_type"] = "MULTISIG"
            result["has_multisig"] = True
            return result

        # Has bytecode but unknown pattern
        result["admin_type"] = "CONTRACT"
        return result

    except Exception:
        return result
