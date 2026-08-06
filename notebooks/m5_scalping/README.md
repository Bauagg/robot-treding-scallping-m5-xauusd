# M5 Scalping — XAUUSD

Riset & development strategi scalping timeframe **M5** untuk XAUUSD.

Konvensi folder: `notebooks/<timeframe>_<gaya_strategi>/`. Kalau nanti dikembangkan strategi lain,
tambah folder baru di sebelahnya, contoh:

- `notebooks/m1_scalping/` — scalping M1
- `notebooks/h1_swing/` — swing trading H1
- `notebooks/m5_scalping/` — folder ini

## Konvensi versioning notebook

Tiap kali melakukan analisis/eksperimen baru, buat notebook dengan nomor versi baru — **jangan timpa
notebook versi lama**. Ini supaya ada log lengkap riset yang pernah dilakukan dan hasilnya bisa
dibandingkan antar versi.

```
v01_eda.ipynb                 <- EDA pertama (baseline)
v02_signal_research.ipynb     <- eksperimen sinyal pertama
v03_signal_research.ipynb     <- iterasi sinyal berikutnya (kalau v02 mau dicoba ulang dgn pendekatan beda)
v04_backtest.ipynb            <- backtest versi tertentu
...
```

Penomoran **berurutan secara global** (bukan per-topik) — jadi urutannya sekaligus jadi urutan
kronologis riset. Tiap notebook baru boleh reuse logic dari versi sebelumnya (copy sel yang relevan),
tapi tetap sebagai file baru.

## Output per strategi & versi

Struktur output: `dataset/processed/<nama_strategi>/<versi>/` dan `dataset/exports/<nama_strategi>/<versi>/`
— dipisah per **strategi/timeframe dulu** (nama folder ini, `m5_scalping`), baru di dalamnya per **versi**.
Ini supaya kalau nanti ada riset lain (mis. `m15_scalping`, `h1_swing`) hasilnya tidak tercampur dan
langsung jelas kepemilikannya.

- `dataset/processed/m5_scalping/vXX/` — data hasil olahan (mis. candle + indikator, hasil label, feature set)
- `dataset/exports/m5_scalping/vXX/` — hasil akhir (laporan backtest, metrik model, chart, ringkasan evaluasi)

Contoh: `v01_eda.ipynb` simpan candle+indikator ke `dataset/processed/m5_scalping/v01/`, `v03_backtest.ipynb`
simpan hasil backtest ke `dataset/exports/m5_scalping/v03/`.

Kalau nanti bikin folder notebook baru (mis. `notebooks/m15_scalping/`), ikuti pola yang sama:
outputnya ke `dataset/processed/m15_scalping/vXX/` dan `dataset/exports/m15_scalping/vXX/`.

## Isi folder saat ini

| Notebook | Deskripsi |
|---|---|
| `v01_eda.ipynb` | Load semua CSV mentah XAUUSD M5+H1 (2019-2026), EDA kualitas data, hitung semua indikator, simpan dataset gabungan |
| `v02_signal_research.ipynb` | Signal scoring (`app.utils.signals`) + backtest awal (score>=6, tanpa filter H1) + log lengkap trade+indikator M5&H1 |
| `v03_backtest.ipynb` | Grid search threshold sinyal x filter H1 trend alignment, cari parameter profitable secara sistematis |
| `v04_backtest.ipynb` | Grid search lebih luas (score x TP/SL x MAX_HOLD_CANDLES) untuk naikkan frekuensi tanpa turunkan profit factor |

## Dataset

CSV mentah XAUUSD M5 & H1 (per tahun, 2019-2026) sudah ada di `dataset/raw/`:
`xauusd_m5_<tahun>.csv`, `xauusd_h1_<tahun>.csv`. Kolom: `timestamp, datetime, open, high, low, close, volume`.

## Log keputusan strategi

**v02 (baseline, score>=6, tanpa filter H1):** win rate 36.4%, profit factor 0.99 — **belum
profitable** (rugi tipis setelah spread). Evaluasi mendalam trade_log_full.csv menemukan 2 pola kuat:
(1) trade searah trend H1 (EMA50 vs EMA200) jauh lebih baik dari yang melawan, (2) trade dengan
signal_score>=9 rata-rata profitable sedangkan score 6-9 rata-rata rugi.

**v03 (grid search score 6-11 x filter H1):** SEMUA kombinasi dengan score>=7 sudah profit factor >1
— bukan kebetulan satu titik. Parameter terbaik dari grid search: **MIN_SIGNAL_SCORE=11.0,
require_h1_alignment=True** → win rate 44.6%, profit factor 1.37, expectancy +$1.16/trade, avg
$2.44/hari, tapi cuma ~2.1 trade/hari dan max drawdown -33%.

**Keputusan (2026-08-06):** user memilih menerima frekuensi trading lebih rendah (~2 trade/hari)
demi profitability yang lebih pasti, daripada memaksakan frekuensi tinggi yang mengorbankan profit
factor. Target harian direvisi dari asumsi awal $10/hari (tidak realistis — cuma tercapai 26.8% hari)
menjadi ekspektasi **rata-rata ~$2-3/hari** (dievaluasi mingguan/bulanan, bukan target harian pasti).

Trade-off terbuka untuk v04+: cari cara menambah frekuensi trading tanpa menurunkan profit factor
(mis. tambah simbol lain, turunkan MAX_HOLD_CANDLES, atau strategi kedua yang saling melengkapi jam
trading v03 yang WAIT).

**v04 (grid search 32 kombinasi: score 7-10 x TP/SL 4 varian x MAX_HOLD 12/24 candle):** Analisis
funnel dulu menemukan bottleneck v03: `MIN_SIGNAL_SCORE=11` ada di persentil 99 distribusi skor
(median cuma 4.75) — itu sebabnya trade sangat jarang. Grid search membuktikan `MAX_HOLD_CANDLES=12`
(1 jam, bukan 2 jam) konsisten lebih baik dari 24 candle di semua kombinasi — modal lebih cepat
"bebas" untuk trade berikutnya (turnover lebih tinggi) tanpa mengorbankan kualitas.

**Parameter terpilih v04: `MIN_SIGNAL_SCORE=9.0`, `TP=12.0`, `SL=6.0`, `MAX_HOLD_CANDLES=12`,
`require_h1_alignment=True`** → win rate 44.5%, profit factor 1.27, avg $4.02/hari, **4.87
trade/hari** (naik 2.3x dari v03), max drawdown -37%, equity terendah $86.98 dari modal $100.

**Keputusan (2026-08-06):** user memilih parameter v04 di atas sebagai baseline baru — trade-off
frekuensi lebih tinggi (hampir 5 trade/hari, lebih sesuai gaya scalping) dengan profit factor sedikit
lebih rendah dari v03 (1.27 vs 1.37) dianggap sepadan karena PnL harian naik 65% ($2.44→$4.02).

Kandidat alternatif yang tidak dipilih tapi tercatat untuk referensi: `score>=9, TP16/SL6 (RR
1:2.67), hold<=12` — PF 1.30 (sedikit lebih tinggi), avg $4.82/hari, 4.70 trade/hari. Bisa dicoba lagi
di versi berikutnya kalau parameter v04 saat ini kurang memuaskan saat evaluasi live/demo.
