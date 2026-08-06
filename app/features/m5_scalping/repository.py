import csv
from pathlib import Path

from app.features.m5_scalping.schema import TradeLogEntry

LIVE_DIR = Path("dataset") / "live" / "m5_scalping"
TRADE_LOG_PATH = LIVE_DIR / "trade_log.csv"

CORE_FIELDNAMES = [
    "ticket", "symbol", "direction", "lot", "entry_price", "sl", "tp",
    "signal_score", "entry_time", "exit_price", "exit_time", "result",
    "pnl", "status",
]


def _ensure_file(fieldnames: list[str]) -> None:
    LIVE_DIR.mkdir(parents=True, exist_ok=True)
    if not TRADE_LOG_PATH.exists():
        with open(TRADE_LOG_PATH, "w", newline="", encoding="utf-8") as f:
            csv.DictWriter(f, fieldnames=fieldnames).writeheader()


def _entry_to_row(entry: TradeLogEntry) -> dict:
    row = entry.model_dump(exclude={"indicators"})
    row["entry_time"] = entry.entry_time.isoformat()
    row["exit_time"] = entry.exit_time.isoformat() if entry.exit_time else ""
    for key in ("exit_price", "result", "pnl"):
        if row[key] is None:
            row[key] = ""
    for col, value in entry.indicators.items():
        row[f"ind_{col}"] = value
    return row


def append_trade(entry: TradeLogEntry) -> None:
    """Tambahkan baris trade baru (status OPEN) ke trade_log.csv, termasuk snapshot
    semua indikator M5+H1 saat entry (kolom ind_*). Header di-refresh kalau ada kolom
    indikator baru yang belum pernah muncul (mis. karena add_all_indicators berubah)."""
    row = _entry_to_row(entry)
    fieldnames = CORE_FIELDNAMES + [k for k in row if k not in CORE_FIELDNAMES]

    if not TRADE_LOG_PATH.exists():
        _ensure_file(fieldnames)
    else:
        existing_fieldnames = csv.DictReader(open(TRADE_LOG_PATH, encoding="utf-8")).fieldnames or []
        missing = [f for f in fieldnames if f not in existing_fieldnames]
        if missing:
            _rewrite_with_new_columns(list(existing_fieldnames) + missing)

    with open(TRADE_LOG_PATH, "r+", newline="", encoding="utf-8") as f:
        current_fieldnames = csv.DictReader(f).fieldnames or fieldnames
        f.seek(0, 2)  # end of file
        writer = csv.DictWriter(f, fieldnames=current_fieldnames)
        writer.writerow(row)


def _rewrite_with_new_columns(new_fieldnames: list[str]) -> None:
    rows = list(csv.DictReader(open(TRADE_LOG_PATH, encoding="utf-8")))
    with open(TRADE_LOG_PATH, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=new_fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def update_trade_close(
    ticket: int, exit_price: float, exit_time: str, result: str, pnl: float
) -> bool:
    """Update baris trade yang sudah ada (by ticket) jadi CLOSED dengan hasilnya.
    Return True kalau ticket ditemukan & diupdate, False kalau tidak ditemukan.
    """
    if not TRADE_LOG_PATH.exists():
        return False

    with open(TRADE_LOG_PATH, encoding="utf-8") as f:
        reader = csv.DictReader(f)
        fieldnames = reader.fieldnames or CORE_FIELDNAMES
        rows = list(reader)

    found = False
    for row in rows:
        if row["ticket"] == str(ticket):
            row["exit_price"] = str(exit_price)
            row["exit_time"] = exit_time
            row["result"] = result
            row["pnl"] = str(pnl)
            row["status"] = "CLOSED"
            found = True
            break

    if found:
        with open(TRADE_LOG_PATH, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(rows)

    return found


def list_open_tickets() -> list[int]:
    """Ambil semua ticket dengan status OPEN dari trade_log.csv."""
    if not TRADE_LOG_PATH.exists():
        return []
    rows = csv.DictReader(open(TRADE_LOG_PATH, encoding="utf-8"))
    return [int(row["ticket"]) for row in rows if row["status"] == "OPEN"]
