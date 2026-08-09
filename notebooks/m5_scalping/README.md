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
| `v05_ml_training.ipynb` | Eksperimen ML (Random Forest) menggantikan scoring rule-based — walk-forward + 3-way split (train/val/test) |
| `v06_backtest.ipynb` | Ganti TP/SL fixed poin (v04) jadi ATR-relatif, untuk atasi distribution shift yang ditemukan di live trading |

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

**v05 (ML, Random Forest, label simulasi TP/SL simetris 1xATR):** dicoba menggantikan scoring
rule-based dengan model ML, dengan walk-forward + 3-way split (train/validation/test) supaya threshold
probabilitas tidak dipilih dari data snooping di test set. Hasil: model jadi **SELL-only** — 78.8% label
awalnya condong SELL akibat TP/SL asimetris (diperbaiki jadi simetris), tapi model tetap bias SELL saat
dievaluasi di data 2025-2026 karena rezim harga saat itu ($2600-2789) berbeda dari rezim training
awal — pola *distribution shift* yang sama yang nanti juga ditemukan di masalah live trading v04.
**Keputusan: v05 TIDAK dipakai live** ("belum sempurna"), v04 (rule-based) tetap jadi baseline.
Disimpan di `models/m5_scalping/v05/` sbg riset.

**v06 (TP/SL ATR-relatif, fix distribution shift dari live trading):** Live demo test parameter v04
(TP=12pt/SL=6pt fixed) tanggal 7 Agustus 2026 hasilnya 67 LOSS/2 WIN dari 69 trade (semua BUY, dan
arah marketnya sendiri sebenarnya benar — harga naik $4318→$4354 selama window trading). Investigasi
menemukan akar masalah: v04 dituning di data 2025 pada harga XAUUSD ~$2600-2789, sedangkan live
terjadi di rezim harga ~$4300+ (Agustus 2026) — SL fixed 6 poin ternyata cuma ~0.6-1.5x ATR saat itu,
jadi kena stop oleh guncangan candle normal sebelum harga lanjut ke arah yang benar. Ini pola
*distribution shift* yang sama seperti yang ditemukan di v05.

Perbaikan: ganti TP/SL dari poin fixed menjadi **kelipatan ATR** (`SL = k1 x ATR`, `TP = k2 x ATR`,
dihitung ulang tiap sinyal dari ATR M5 saat itu) — otomatis menyesuaikan skala harga & volatilitas.
Grid search kombinasi SL/TP multiplier dievaluasi di DUA window: full period 2025-2026, dan khusus
periode 2026 (rezim harga tinggi, kondisi yang sama persis dengan live trading yang gagal) — kedua
window sepakat memilih kombinasi yang sama, `SL=2.0xATR, TP=4.0xATR (RR 1:2)`.

**Parameter terpilih v06: `SL=2.0xATR`, `TP=4.0xATR`, `MAX_HOLD_CANDLES=12`** (signal params sama
persis dgn v04, tidak diubah) → full period: win rate 50.2%, profit factor 1.35, avg $5.89/hari.
Khusus periode 2026 (evaluasi paling relevan krn ini kondisi live): win rate 51.3% vs v04 40.8%,
profit factor 1.40 vs 1.25, avg $9.17/hari vs $4.77/hari, max drawdown -34.3% vs -60.2% — v06 lebih
baik di semua metrik pada periode yang sama.

**Catatan kejujuran:** live test v04 (69 trade, win rate 2.9%) jauh lebih buruk dari simulasi v04 di
notebook untuk periode yang sama (win rate 40.8%) — karena 69 trade live itu semua terjadi dalam
window ~3 jam di satu hari (7 Agustus), bukan tersebar di 158 hari seperti backtest. Jadi selisihnya
kemungkinan kombinasi dari sampel kecil yang apes + masalah SL sempit yang memang nyata. v06 tidak
"membuktikan" akan selalu profit, tapi memperbaiki akar masalah terstruktur (SL tidak menyesuaikan
skala harga) yang tervalidasi lebih baik di 158 hari data 2026 — bukan cuma di 1 hari.

**Keputusan (2026-08-08):** user setuju v06 dipakai live, menggantikan v04.
`app/features/m5_scalping/usecase.py` diupdate untuk hitung SL/TP dari `ind_atr` candle M5 terkini
dikalikan `sl_atr_multiplier`/`tp_atr_multiplier` dari `models/m5_scalping/v06/params.json`.
