from functools import lru_cache

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # App
    app_name: str = "robot-scalping"
    app_env: str = "development"
    debug: bool = True
    log_level: str = "INFO"

    # API server
    api_host: str = "0.0.0.0"
    api_port: int = 8000

    # MetaTrader 5
    mt5_login: int | None = None
    mt5_password: str = ""
    mt5_server: str = ""

    # XAUUSD trading
    xauusd_symbol: str = "XAUUSD.m"
    xauusd_lot_size: float = 0.01
    # Override manual filling mode order ("FOK"/"IOC"/"RETURN") kalau auto-detect dari
    # symbol_info() salah untuk broker/simbol tertentu. Kosongkan buat auto-detect (default).
    mt5_filling_mode: str = ""

    @field_validator("mt5_login", mode="before")
    @classmethod
    def _empty_str_to_none(cls, value: object) -> object:
        if value == "":
            return None
        return value


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
