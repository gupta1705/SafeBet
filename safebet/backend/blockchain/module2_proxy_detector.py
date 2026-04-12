"""
SafeBet — Module 2 Proxy Detector

Reads EIP-1967 storage slots directly to detect upgradeable proxy contracts.
Separate from SafeBet's existing proxy_detector.py (which is async with admin intelligence).
This one returns Module 2's ProxyInfo schema.
"""

import logging
from web3 import Web3

from blockchain.rpc_client import get_w3
from schemas.findings import ProxyInfo

logger = logging.getLogger(__name__)

IMPLEMENTATION_SLOT = "0x360894a13ba1a3210667c828492db98dca3e2076cc3735a920a3ca505d382bbc"
ADMIN_SLOT = "0xb53127684a568b3173ae13b9f8a6016e243e63b6e8ee1178d6a717850b5d6103"
UUPS_SLOT = "0xc5f16f0fcc639fa48a6947836d9850f504798523bf8c9a3a87d5876cf622bcf7"
ZERO_ADDRESS = "0x0000000000000000000000000000000000000000"


def _is_zero_address(address: str) -> bool:
    if not address:
        return True
    try:
        return address.lower() == ZERO_ADDRESS.lower() or int(address, 16) == 0
    except (ValueError, TypeError):
        return False


def _read_slot(w3: Web3, address: str, slot: str) -> str | None:
    """Read a storage slot and return the address stored there."""
    try:
        value = w3.eth.get_storage_at(Web3.to_checksum_address(address), int(slot, 16))
        hex_value = value.hex()

        if int(hex_value, 16) == 0:
            return None

        addr = "0x" + hex_value[-40:]
        if _is_zero_address(addr):
            return None

        return Web3.to_checksum_address(addr)
    except Exception as e:
        logger.debug(f"Failed to read slot {slot} from {address}: {e}")
        return None


def detect_proxy(token_address: str) -> ProxyInfo:
    """Detect if a contract is an upgradeable proxy. Returns ProxyInfo."""
    w3 = get_w3()

    if not w3.is_connected():
        logger.warning("Web3 not connected — proxy detection unavailable")
        return ProxyInfo()

    result = ProxyInfo()

    try:
        impl = _read_slot(w3, token_address, IMPLEMENTATION_SLOT)
        if not impl:
            impl = _read_slot(w3, token_address, UUPS_SLOT)

        if impl:
            result.is_proxy = True
            result.implementation_address = impl
            logger.info(f"Module 2 proxy detected! Implementation: {impl}")

        admin = _read_slot(w3, token_address, ADMIN_SLOT)
        if admin:
            result.admin_address = admin
            result.upgrade_authority_active = True
            logger.info(f"Module 2 proxy admin found: {admin}")

    except Exception as e:
        logger.error(f"Module 2 proxy detection failed for {token_address}: {e}")

    return result
