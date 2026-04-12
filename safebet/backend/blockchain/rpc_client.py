"""
Web3 connection singleton and helper wrappers.
All blockchain reads go through this module.
"""

import os
import asyncio
from web3 import Web3
from functools import lru_cache


@lru_cache(maxsize=1)
def get_w3() -> Web3:
    """Singleton Web3 connection — created once, reused everywhere."""
    url = os.getenv("INFURA_URL")
    if not url:
        raise EnvironmentError("INFURA_URL not set in .env")
    w3 = Web3(Web3.HTTPProvider(url, request_kwargs={"timeout": 15}))
    if not w3.is_connected():
        raise ConnectionError("Cannot connect to Ethereum node via Infura")
    return w3


async def call_contract_function(address: str, abi: list, function_name: str, *args):
    """
    Helper to call any read-only function on any contract.
    Runs synchronous Web3 call in a thread to not block the event loop.
    """
    def _call():
        w3 = get_w3()
        checksum = Web3.to_checksum_address(address)
        contract = w3.eth.contract(address=checksum, abi=abi)
        fn = getattr(contract.functions, function_name)
        return fn(*args).call()

    return await asyncio.to_thread(_call)


async def read_storage_slot(address: str, slot: str) -> bytes:
    """
    Read a raw storage slot from any contract.
    Used for proxy detection (EIP-1967 slots).
    """
    def _read():
        w3 = get_w3()
        checksum = Web3.to_checksum_address(address)
        return w3.eth.get_storage_at(checksum, slot)

    return await asyncio.to_thread(_read)


async def get_code(address: str) -> bytes:
    """Check if an address has deployed bytecode (is a contract)."""
    def _get():
        w3 = get_w3()
        checksum = Web3.to_checksum_address(address)
        return w3.eth.get_code(checksum)

    return await asyncio.to_thread(_get)
