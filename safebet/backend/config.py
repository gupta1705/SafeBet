"""
SafeBet — Configuration
Bridges Module 2's config system with SafeBet's existing .env.
"""

from pydantic_settings import BaseSettings
from functools import lru_cache
import os


class Settings(BaseSettings):
    # API Keys
    INFURA_API_KEY: str = ""
    ETHERSCAN_API_KEY: str = ""
    GEMINI_API_KEY: str = ""

    # Full Ethereum RPC URL (SafeBet uses full URLs, not just keys)
    INFURA_URL: str = ""

    # Chain config
    CHAIN_ID: int = 1

    # Common addresses (Ethereum mainnet)
    WETH_ADDRESS: str = "0xC02aaA39b223FE8D0A0e5C4F27eAD9083C756Cc2"
    UNISWAP_V2_ROUTER: str = "0x7a250d5630B4cF539739dF2C5dAcb4c659F2488D"
    UNISWAP_V2_FACTORY: str = "0x5C69bEe701ef814a2B6a3EDD4B1652CB9cc5aA6f"
    SUSHISWAP_ROUTER: str = "0xd9e1cE17f2641f24aE83637ab66a2cca9C378B9F"

    # Simulation config
    SIMULATION_AMOUNT_ETH: float = 0.01
    SIMULATION_TEST_ADDRESS: str = "0x0000000000000000000000000000000000C0FFEE"

    # API URLs
    ETHERSCAN_BASE_URL: str = "https://api.etherscan.io/v2/api"
    DEXSCREENER_BASE_URL: str = "https://api.dexscreener.com/latest/dex"

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"

    def get_rpc_url(self) -> str:
        """Get the Ethereum RPC URL — SafeBet stores the full URL in INFURA_URL."""
        if self.INFURA_URL:
            return self.INFURA_URL
        if self.INFURA_API_KEY and self.INFURA_API_KEY != "your_infura_api_key_here":
            return f"https://mainnet.infura.io/v3/{self.INFURA_API_KEY}"
        return ""


@lru_cache()
def get_settings() -> Settings:
    """Get cached settings instance."""
    return Settings()
