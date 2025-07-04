"""
Configuration settings for the Gilbarco SK700-II Control System
"""

import os
from typing import List, Tuple


class Config:
    """Application configuration"""

    # API Server Settings
    API_HOST = os.getenv("API_HOST", "127.0.0.1")
    API_PORT = int(os.getenv("API_PORT", "3000"))
    API_RELOAD = os.getenv("API_RELOAD", "True").lower() == "true"

    # Serial Communication Settings
    DEFAULT_BAUDRATE = int(os.getenv("SERIAL_BAUDRATE", "9600"))
    DEFAULT_TIMEOUT = float(os.getenv("SERIAL_TIMEOUT", "1.0"))
    DEFAULT_WRITE_TIMEOUT = float(os.getenv("SERIAL_WRITE_TIMEOUT", "1.0"))

    # Pump Discovery Settings
    DEFAULT_ADDRESS_RANGE = (
        int(os.getenv("MIN_PUMP_ADDRESS", "1")),
        int(os.getenv("MAX_PUMP_ADDRESS", "16")),
    )
    DISCOVERY_TIMEOUT = float(os.getenv("DISCOVERY_TIMEOUT", "2.0"))

    # Monitoring Settings
    MONITOR_INTERVAL = int(os.getenv("MONITOR_INTERVAL", "30"))
    STATUS_HISTORY_SIZE = int(os.getenv("STATUS_HISTORY_SIZE", "100"))

    # Logging Settings
    LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO").upper()
    LOG_FORMAT = os.getenv(
        "LOG_FORMAT", "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    )

    # Thread Pool Settings
    MAX_WORKERS = int(os.getenv("MAX_WORKERS", "10"))

    # Protocol Settings
    COMMAND_DELAY = float(os.getenv("COMMAND_DELAY", "0.1"))
    MAX_RETRIES = int(os.getenv("MAX_RETRIES", "5"))

    COM_PORT = os.getenv("COM_PORT", "")

    @classmethod
    def get_all_settings(cls) -> dict:
        """Get all configuration settings as a dictionary"""
        return {
            key: getattr(cls, key)
            for key in dir(cls)
            if not key.startswith("_") and not callable(getattr(cls, key))
        }

    def dict(self):
        """Return settings as dictionary (for compatibility with Pydantic settings)"""
        return self.get_all_settings()


settings = Config()
