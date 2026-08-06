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
      params.json      <- parameter final yang dipakai (hasil grid search v04_backtest.ipynb)
    v05/                <- versi berikutnya kalau ada tuning ulang
      params.json
  m15_scalping/          <- strategi lain nanti, folder sendiri
    v01/
      params.json
```

## Isi `params.json`

- `signal_params` — parameter untuk `app.utils.signals.generate_signal()` (threshold skor, filter ADX/ATR/H1)
- `trade_params` — parameter eksekusi (TP/SL, position sizing, max hold)
- `backtest_metrics` — hasil backtest yang menghasilkan parameter ini (win rate, profit factor, dll),
  supaya riwayat performa tiap versi tersimpan bersama parameternya
- `notes` — konteks/alasan pemilihan parameter, termasuk trade-off dgn versi lain

## Model aktif saat ini

| Strategi | Versi | Status |
|---|---|---|
| `m5_scalping` | `v04` | Baseline terpilih — belum divalidasi di demo/live, backtest historis saja |
