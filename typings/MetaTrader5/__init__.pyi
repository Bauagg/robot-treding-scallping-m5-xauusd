"""Type stub untuk package MetaTrader5 (dari mt5.__init__.py -> `from ._core import *`).

MetaTrader5 adalah C extension (_core.pyd) tanpa stub resmi, jadi Pylance tidak bisa
menganalisis atribut modulnya secara statis meskipun runtime-nya berfungsi normal. Stub
ini cuma mendeklarasikan signature fungsi yang dipakai/berpotensi dipakai project ini —
bukan port lengkap seluruh API MetaTrader5.

Referensi: https://www.mql5.com/en/docs/python_metatrader5
"""

from collections.abc import Sequence
from typing import Any, NamedTuple

# --- Timeframe constants ---
TIMEFRAME_M1: int
TIMEFRAME_M2: int
TIMEFRAME_M3: int
TIMEFRAME_M4: int
TIMEFRAME_M5: int
TIMEFRAME_M6: int
TIMEFRAME_M10: int
TIMEFRAME_M12: int
TIMEFRAME_M15: int
TIMEFRAME_M20: int
TIMEFRAME_M30: int
TIMEFRAME_H1: int
TIMEFRAME_H2: int
TIMEFRAME_H3: int
TIMEFRAME_H4: int
TIMEFRAME_H6: int
TIMEFRAME_H8: int
TIMEFRAME_H12: int
TIMEFRAME_D1: int
TIMEFRAME_W1: int
TIMEFRAME_MN1: int

# --- Order type constants ---
ORDER_TYPE_BUY: int
ORDER_TYPE_SELL: int
ORDER_TYPE_BUY_LIMIT: int
ORDER_TYPE_SELL_LIMIT: int
ORDER_TYPE_BUY_STOP: int
ORDER_TYPE_SELL_STOP: int

# --- Trade action / filling / time constants ---
TRADE_ACTION_DEAL: int
TRADE_ACTION_PENDING: int
TRADE_ACTION_SLTP: int
TRADE_ACTION_MODIFY: int
TRADE_ACTION_REMOVE: int
ORDER_FILLING_FOK: int
ORDER_FILLING_IOC: int
ORDER_FILLING_RETURN: int
ORDER_TIME_GTC: int
ORDER_TIME_DAY: int
TRADE_RETCODE_DONE: int

# --- Tick copy flags ---
COPY_TICKS_ALL: int
COPY_TICKS_INFO: int
COPY_TICKS_TRADE: int


class AccountInfo(NamedTuple):
    login: int
    trade_mode: int
    leverage: int
    limit_orders: int
    margin_so_mode: int
    trade_allowed: bool
    trade_expert: bool
    margin_mode: int
    currency_digits: int
    fifo_close: bool
    balance: float
    credit: float
    profit: float
    equity: float
    margin: float
    margin_free: float
    margin_level: float
    margin_so_call: float
    margin_so_so: float
    margin_initial: float
    margin_maintenance: float
    assets: float
    liabilities: float
    commission_blocked: float
    name: str
    server: str
    currency: str
    company: str


class TerminalInfo(NamedTuple):
    community_account: bool
    community_connection: bool
    connected: bool
    dlls_allowed: bool
    trade_allowed: bool
    tradeapi_disabled: bool
    email_enabled: bool
    ftp_enabled: bool
    notifications_enabled: bool
    mqid: bool
    build: int
    maxbars: int
    codepage: int
    ping_last: int
    community_balance: float
    retransmission: float
    company: str
    name: str
    language: str
    path: str
    data_path: str
    commondata_path: str


class SymbolInfoTick(NamedTuple):
    time: int
    bid: float
    ask: float
    last: float
    volume: int
    time_msc: int
    flags: int
    volume_real: float


class OrderSendResult(NamedTuple):
    retcode: int
    deal: int
    order: int
    volume: float
    price: float
    bid: float
    ask: float
    comment: str
    request_id: int
    retcode_external: int
    request: Any


class TradePosition(NamedTuple):
    ticket: int
    time: int
    time_msc: int
    time_update: int
    time_update_msc: int
    type: int
    magic: int
    identifier: int
    reason: int
    volume: float
    price_open: float
    sl: float
    tp: float
    price_current: float
    swap: float
    profit: float
    symbol: str
    comment: str
    external_id: str


def initialize(
    path: str = ...,
    *,
    login: int | None = ...,
    password: str = ...,
    server: str = ...,
    timeout: int = ...,
    portable: bool = ...,
) -> bool: ...


def login(
    login: int,
    *,
    password: str = ...,
    server: str = ...,
    timeout: int = ...,
) -> bool: ...


def shutdown() -> None: ...


def last_error() -> tuple[int, str]: ...


def version() -> tuple[int, int, str] | None: ...


def account_info() -> AccountInfo | None: ...


def terminal_info() -> TerminalInfo | None: ...


def symbol_info(symbol: str) -> Any | None: ...


def symbol_info_tick(symbol: str) -> SymbolInfoTick | None: ...


def symbol_select(symbol: str, enable: bool = ...) -> bool: ...


def symbols_get(group: str = ...) -> tuple[Any, ...] | None: ...


def copy_rates_from(
    symbol: str, timeframe: int, date_from: Any, count: int
) -> Any | None: ...


def copy_rates_from_pos(
    symbol: str, timeframe: int, start_pos: int, count: int
) -> Any | None: ...


def copy_rates_range(
    symbol: str, timeframe: int, date_from: Any, date_to: Any
) -> Any | None: ...


def copy_ticks_from(
    symbol: str, date_from: Any, count: int, flags: int
) -> Any | None: ...


def copy_ticks_range(
    symbol: str, date_from: Any, date_to: Any, flags: int
) -> Any | None: ...


def orders_total() -> int: ...


def orders_get(
    symbol: str = ..., *, group: str = ..., ticket: int = ...
) -> tuple[Any, ...] | None: ...


def order_check(request: dict[str, Any]) -> Any | None: ...


def order_send(request: dict[str, Any]) -> OrderSendResult | None: ...


def positions_total() -> int: ...


def positions_get(
    symbol: str = ..., *, group: str = ..., ticket: int = ...
) -> Sequence[TradePosition] | None: ...


def history_orders_total(date_from: Any, date_to: Any) -> int: ...


def history_orders_get(
    date_from: Any = ..., date_to: Any = ..., *, group: str = ..., ticket: int = ..., position: int = ...
) -> tuple[Any, ...] | None: ...


def history_deals_total(date_from: Any, date_to: Any) -> int: ...


def history_deals_get(
    date_from: Any = ..., date_to: Any = ..., *, group: str = ..., ticket: int = ..., position: int = ...
) -> tuple[Any, ...] | None: ...


def Buy(
    symbol: str, volume: float, price: float | None = ..., *, comment: str | None = ..., ticket: int | None = ...
) -> OrderSendResult | None: ...


def Sell(
    symbol: str, volume: float, price: float | None = ..., *, comment: str | None = ..., ticket: int | None = ...
) -> OrderSendResult | None: ...


def Close(
    symbol: str, *, comment: str | None = ..., ticket: int | None = ...
) -> bool | str | None: ...
