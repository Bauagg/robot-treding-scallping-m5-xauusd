# robot-scalping

Robot trading otomatis untuk **XAUUSD (gold) di timeframe M5**: MetaTrader5 sebagai eksekusi order,
FastAPI sebagai API layer + scheduler polling, Pandas untuk data processing, dan Jupyter untuk
riset/backtest strategi.

## Struktur folder

Arsitektur **feature-based (vertical slice)**: setiap fitur punya folder sendiri di `app/features/<nama_fitur>/`
yang isinya lengkap — schema, repository, usecase, controller. Tidak dipisah per-layer horizontal,
supaya tiap fitur mudah ditelusuri dan gak saling menyebar ke banyak folder.

```
app/
  main.py                    # entry point FastAPI + scheduler polling live trading
  api.py                     # agregasi semua controller/router per-fitur
  core/                      # config (.env), logging — shared infra
  features/
    health/                  # GET /health
    mt5_connection/          # connect/disconnect MT5, GET /mt5/status (fail-fast di startup)
    m5_scalping/             # strategi live: generate sinyal, order otomatis, catat hasil
      schema.py               # TradeLogEntry, SignalCheckResult
      repository.py           # baca/tulis dataset/live/m5_scalping/trade_log.csv
      usecase.py               # fetch candle -> indikator -> generate_signal -> order -> log
      controller.py           # POST /m5-scalping/check, POST /m5-scalping/sync
  utils/
    indicators/               # 24 modul indikator teknikal (RSI, MACD, EMA, SMC, dll) + add_all_indicators
    signals/                  # scoring & decision engine (generate_signal) dipakai backtest & live
dataset/
  raw/                       # data mentah candle historis (CSV per simbol/timeframe/tahun)
  processed/<strategi>/vXX/  # hasil olahan tiap versi riset (indikator, trade log lengkap)
  exports/<strategi>/vXX/    # ringkasan tiap versi (metrics.txt, grafik, grid search)
  live/<strategi>/           # trade_log.csv hasil trading SUNGGUHAN (bukan backtest)
models/<strategi>/vXX/       # parameter/model hasil tuning tiap versi (params.json atau .joblib)
notebooks/<strategi>/        # riset & backtest per versi (v01_eda, v02_signal_research, dst)
scripts/                     # helper script
tests/
  unit/
  integration/
```

Cara nambah fitur baru (misalnya `orders`):
1. Buat folder `app/features/orders/`
2. `schema.py` — Pydantic model request/response
3. `repository.py` — akses sumber data (mis. MT5, CSV) kalau perlu
4. `usecase.py` — logic inti, pakai repository
5. `controller.py` — `APIRouter` yang manggil usecase
6. Daftarkan router-nya di `app/api.py`

## Setup

1. **Aktifkan virtual environment** (sudah dibuat di `.venv/`)

   ```powershell
   .venv\Scripts\Activate.ps1
   ```

2. **Install dependencies**

   ```powershell
   pip install -r requirements.txt
   ```

3. **Konfigurasi environment**

   Salin `.env.example` menjadi `.env`, isi kredensial MT5 (`MT5_LOGIN`, `MT5_PASSWORD`, `MT5_SERVER`)
   dan simbol/lot (`XAUUSD_SYMBOL`, `XAUUSD_LOT_SIZE`).

4. **Jalankan robot (live trading otomatis)**

   ```powershell
   uvicorn app.main:app --host 0.0.0.0 --port 8080 --reload
   ```

   Begitu start: connect ke MT5 (**fail-fast** — kalau gagal connect, server tidak jalan sama sekali),
   lalu scheduler polling **tiap 60 detik** otomatis di background (`app/features/m5_scalping/controller.py`,
   dipanggil dari `main.py` saat startup — tidak ada HTTP endpoint buat trigger manual, karena MT5 API-nya
   pull-based/tidak ada streaming): tiap tick, sinkronkan trade OPEN→CLOSED dari histori MT5 dulu, lalu cek
   sinyal terbaru — order otomatis ke MT5 kalau skor sinyal memenuhi threshold, catat hasil ke
   `dataset/live/m5_scalping/trade_log.csv`.

   Endpoint HTTP yang tersedia cuma buat cek status koneksi & health:
   - `GET /api/v1/mt5/status` — cek koneksi & saldo akun
   - `GET /api/v1/health` — health check

   Dokumentasi API: http://localhost:8000/docs

5. **Riset & backtest strategi di Jupyter**

   ```powershell
   jupyter lab
   ```

   Buka `notebooks/m5_scalping/`. Konvensi versioning: tiap eksperimen baru = notebook baru
   (`vXX_topik.ipynb`), tidak menimpa versi lama — supaya ada log riset lengkap. Detail & riwayat
   keputusan tiap versi ada di `notebooks/m5_scalping/README.md`.

## Strategi aktif saat ini

**v06** (rule-based scoring, `app.utils.signals.generate_signal`, TP/SL **ATR-relatif**) — parameter di
`models/m5_scalping/v06/params.json`:

- `MIN_SIGNAL_SCORE=9.0`, filter H1 trend alignment aktif, ADX≥18, ATR≥0.03%
- SL=2.0×ATR, TP=4.0×ATR (dihitung ulang tiap sinyal dari ATR M5 saat itu), max hold 12 candle M5

Hasil backtest (2025-01 s/d 2026-08, 107K+ candle): win rate 50.2%, profit factor 1.35, ~4.2 trade/hari,
avg $5.89/hari dari modal $100. Detail riset & perbandingan vs v04 di `notebooks/m5_scalping/v06_backtest.ipynb`.

**Kenapa v06 menggantikan v04 (TP=12pt/SL=6pt fixed)**: v04 dituning di data 2025 pada harga XAUUSD
~$2600-2789. Live demo test 7 Agustus 2026 (harga ~$4300+) hasilnya 67 LOSS/2 WIN dari 69 trade — root
cause: SL fixed 6 poin ternyata cuma ~0.6-1.5x ATR di rezim harga tinggi ini, jadi gampang kena stop
duluan sebelum harga lanjut ke arah yang benar (arah sinyalnya sendiri sebetulnya sudah tepat). v06
mengganti SL/TP fixed poin dengan kelipatan ATR supaya otomatis menyesuaikan skala harga & volatilitas,
divalidasi khusus di periode 2026 (kondisi live yg sama) sebelum dipakai live — hasilnya lebih baik di
semua metrik (win rate, profit factor, max drawdown) dibanding simulasi v04 pada periode yang sama.
v04 tetap tersimpan sbg riset di `models/m5_scalping/v04/`.

Model ML (v05, Random Forest) sempat dicoba tapi ternyata jadi SELL-only akibat *distribution shift*
ke rezim harga 2025-2026 — belum dipakai live, masih tersimpan sbg riset di `models/m5_scalping/v05/`.

**Evaluasi mingguan**: tarik `dataset/live/m5_scalping/trade_log.csv` (161 kolom: OHLC + 147 indikator
M5+H1 per trade — sama cakupannya dgn hasil backtest), bandingkan dgn hasil backtest, tuning ulang
parameter kalau perlu (buat notebook versi baru, misal `v07_...ipynb`), lalu update
`models/m5_scalping/vXX/params.json` dan `PARAMS_PATH` di `app/features/m5_scalping/usecase.py`.

## Catatan penting

- Package `MetaTrader5` hanya jalan di **Windows** dan environment tempat terminal MT5 ter-install,
  karena berkomunikasi langsung dengan aplikasi desktopnya.
- Tidak ada database — data disimpan/diproses lewat CSV (`dataset/`) dan Pandas. Log trade live juga CSV,
  bukan SQL.
- Modal kecil ($100) dgn fixed lot dari `.env` (`XAUUSD_LOT_SIZE`) — bukan position sizing dinamis
  berbasis % risk seperti di backtest, supaya perilaku live predictable & gampang dievaluasi.

## Testing

```powershell
pytest
```
