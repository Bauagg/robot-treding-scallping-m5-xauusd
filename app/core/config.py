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
    # Nama file CSV trade log live di dataset/live/m5_scalping/ -- diberi versi (bukan
    # trade_log.csv generik) krn tiap kali mekanisme pencatatan berubah (kolom baru, dst)
    # dipisah jadi file baru drpd auto-migrate baris lama. Ganti nilai ini (bukan edit
    # kode) kalau strategi live pindah versi & butuh file trade log baru -- dibaca juga
    # oleh app.features.bot_telegram (laporan & evaluasi kondisi market baca file yang sama).
    m5_scalping_trade_log_filename: str = "trade_log_v13.csv"

    # Drawdown kill-switch: robot auto-pause (skip entry baru) kalau equity turun dari
    # baseline melebihi persentase ini. Daily & monthly baseline reset otomatis tiap hari/
    # bulan kalender baru (UTC); total dihitung dari peak equity tertinggi yang pernah
    # tercatat & TIDAK reset otomatis -- perlu clear manual (hapus drawdown_state.json,
    # BUKAN trade_log.csv -- itu file histori trade terpisah, jangan disentuh) karena
    # itu sinyal akun rusak, bukan cuma bad day/bulan.
    # Nilai default divalidasi di notebooks/m5_scalping/v09_drawdown_killswitch.ipynb: max
    # drawdown historis strategi v06 (backtest 1664 trade, 2025-2026) = -28.4%. Threshold
    # 5/10/15 (dulu) selalu ke-trigger permanen di trade ke-102 dari 1664 (baru 6% jalan)
    # krn drawdown alami strategi ini jauh melebihi itu. 20/25/40 tervalidasi TIDAK PERNAH
    # ke-trigger di seluruh backtest -- cukup longgar utk gak ganggu operasi normal, tapi
    # tetap jadi jaring pengaman kalau kondisi live menyimpang jauh dari backtest.
    max_daily_drawdown_pct: float = 20.0
    max_monthly_drawdown_pct: float = 25.0
    max_total_drawdown_pct: float = 40.0

    # Telegram Bot: laporan trading (harian/mingguan/bulanan) + alert drawdown + kontrol
    # resume manual kill-switch harian/bulanan (bukan total, itu tetap permanen).
    telegram_chat_id: str = ""
    telegram_token_xauusd: str = ""
    # Cuma user Telegram dengan ID ini yang boleh pakai command sensitif (/start_tuning_*
    # & tombol resume) -- command dari user lain ditolak, supaya kill-switch drawdown gak
    # bisa di-override sembarang orang yang somehow bisa akses bot/channel.
    telegram_allowed_user_id: int = 0
    # Semua laporan otomatis jam 01:00 UTC = 08:00 WIB (permintaan user eksplisit).
    telegram_daily_report_hour_utc: int = 1
    telegram_weekly_report_hour_utc: int = 1
    telegram_weekly_report_weekday: int = 0  # 0=Senin (Python dt.weekday() convention)
    telegram_monthly_report_hour_utc: int = 1
    telegram_reports_enabled: bool = True

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
