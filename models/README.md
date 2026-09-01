# Models

Parameter/konfigurasi strategi yang sudah ditemukan lewat riset & backtest di `notebooks/`.

**Bukan model ML statistik** (belum ada training model machine learning di project ini) — isinya
parameter hasil tuning (threshold sinyal, TP/SL, filter, dll) dalam format JSON, supaya nanti kode
live trading tinggal load file ini alih-alih hardcode angka.

## Konvensi struktur

Sama seperti `dataset/processed/` dan `dataset/exports/`: dipisah per **strategi/timeframe** dulu,
baru di dalamnya per **versi**.

```
models/
  m5_scalping/
    v04/
      params.json      <- baseline lama (TP/SL fixed poin), disimpan sbg riset/referensi
    v05/
      random_forest.joblib, metadata.json  <- eksperimen ML, tidak dipakai live
    v06/
      params.json      <- superseded: TP/SL ATR-relatif, dasar utk v10/v12/v13
    v13/
      params.json      <- LIVE AKTIF: scoring de-redundant (v12) + filter Order Block (v10-SKIP)
                           + penanganan momentum exhaustion (v13)
  m15_scalping/          <- strategi lain nanti, folder sendiri
    v01/
      params.json
```

## Isi `params.json`

- `signal_engine` — path fungsi generate signal yang dipakai (mis. `app.utils.signals.generate_signal_v12`)
- `signal_params` — parameter untuk fungsi signal engine di atas (threshold skor, filter ADX/ATR/H1)
- `trade_params` — parameter eksekusi (TP/SL, position sizing, max hold)
- `order_block_filter` — skip entry kalau ada Order Block (SMC) M5/H1 melawan arah sinyal
- `sr_proximity_filter` — skip entry kalau harga dekat level Support/Resistance (H1/M15) berlawanan
  arah sinyal, kecuali skor sangat kuat atau ATR sudah "bertenaga" (indikasi breakout) — lihat
  `check_sr_proximity()` di `app/features/m5_scalping/usecase.py` & README root bagian
  "Filter Support/Resistance"
- `backtest_metrics` — hasil backtest yang menghasilkan parameter ini (win rate, profit factor, dll),
  supaya riwayat performa tiap versi tersimpan bersama parameternya
- `notes` — konteks/alasan pemilihan parameter, termasuk trade-off dgn versi lain

### Penting: `backtest_metrics` adalah hasil simulasi modal $100

Semua angka di `backtest_metrics` (`net_pnl_usd`, `final_equity_usd`, `avg_daily_pnl_usd`, dst) itu
hasil backtest yang **mulai dari modal simulasi $100** (`INITIAL_EQUITY = 100.0` di tiap notebook
`vXX_backtest.ipynb`) — bukan modal aktual akun live. Ini konvensi supaya angka antar versi/notebook
bisa dibandingkan apple-to-apple (semua mulai dari titik yang sama), dan supaya `max_drawdown_pct`/
`min_equity_usd` gampang diinterpretasi relatif ke modal kecil sesuai `.env` (`XAUUSD_LOT_SIZE=0.01`).

Modal akun live yang sesungguhnya **beda** dari $100 ini (naik seiring waktu trading — cek
`dataset/live/m5_scalping/trade_log_v13.csv` atau `mt5.account_info().balance` untuk saldo real). Kalau
mau proyeksikan hasil backtest ke modal live yang lebih besar, jangan kalikan linear begitu saja —
posisi sizing di live pakai **fixed lot** (`XAUUSD_LOT_SIZE` dari `.env`), bukan compounding %-risk
seperti simulasi backtest (`RISK_PCT = 0.01` dari equity, lot dihitung ulang tiap trade) — jadi
profil risk/reward-nya berbeda karakter, terutama di modal besar (lot fixed jadi proporsinya makin
kecil terhadap equity, sedangkan simulasi backtest lot-nya ikut membesar). Ekstrem-nya kelihatan di
`v13/params.json` bagian `full_period_2019_2026_stress_test`: `net_pnl_usd` meledak jutaan dolar akibat
compounding di rentang 7.6 tahun — angka itu **bukan** proyeksi realistis, cuma `win_rate_pct_by_year`
yang valid dibaca dari situ.

## Model aktif saat ini

| Strategi | Versi | Status |
|---|---|---|
| `m5_scalping` | `v13` (v12 scoring + v10-SKIP + exhaustion + v28 S/R filter) | **Live aktif** — scoring de-redundant (cluster oscillator & trend-follower digabung median) + skip entry saat ada Order Block (SMC) lawan arah sinyal + SL/TP diperkecil saat momentum chain exhaustion (8/8) + skip entry saat harga dekat Support/Resistance (H1/M15) berlawanan arah kecuali skor sangat kuat/ATR bertenaga (v28, ditambahkan 2026-09-01). Lihat `README.md` di root project & `notebooks/m5_scalping/README.md` untuk detail riset lengkap. |
| `m5_scalping` | `v06` | Superseded oleh v13 — TP/SL ATR-relatif murni tanpa filter Order Block/exhaustion, jadi dasar riset v10/v12/v13. Disimpan sbg riset/referensi. |
| `m5_scalping` | `v05` | Riset ML (Random Forest) — **tidak dipakai live**, jadi SELL-only akibat distribution shift ke rezim harga 2025-2026 |
| `m5_scalping` | `v04` | Baseline lama (TP/SL fixed poin) — digantikan v06 setelah live demo test 7 Agustus 2026 menunjukkan SL terlalu sempit utk rezim harga tinggi (~$4300+). Disimpan sbg riset/referensi. |
