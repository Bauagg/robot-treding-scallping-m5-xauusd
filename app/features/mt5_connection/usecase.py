import MetaTrader5 as mt5

from app.core.config import settings
from app.core.logging import logger
from app.features.mt5_connection.schema import MT5ConnectionStatus


def connect() -> None:
    """Connect ke terminal MT5. Raise RuntimeError kalau gagal — dipanggil saat startup app,
    dan kegagalan di sini harus menghentikan startup (fail-fast), bukan cuma di-log.
    """
    initialized = mt5.initialize(
        login=settings.mt5_login,
        password=settings.mt5_password,
        server=settings.mt5_server,
    )
    if not initialized:
        error = mt5.last_error()
        raise RuntimeError(f"Gagal connect ke MT5 (login={settings.mt5_login}, server={settings.mt5_server}): {error}")

    logger.info(f"Terhubung ke MT5: login={settings.mt5_login}, server={settings.mt5_server}")


def disconnect() -> None:
    mt5.shutdown()


def get_status() -> MT5ConnectionStatus:
    account_info = mt5.account_info()
    if account_info is None:
        return MT5ConnectionStatus(connected=False)

    return MT5ConnectionStatus(
        connected=True,
        login=account_info.login,
        server=account_info.server,
        balance=account_info.balance,
        equity=account_info.equity,
    )
