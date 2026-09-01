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
| `v01_eda.ipynb` | Load semua CSV mentah XAUUSD **7 timeframe** (M1, M5, M15, M30, H1, H4, D1; 2019-2026), EDA kualitas data, hitung semua indikator, simpan dataset gabungan per timeframe |
| `v02_signal_research.ipynb` | Signal scoring (`app.utils.signals`) + backtest awal (score>=6, tanpa filter H1) + log lengkap trade+indikator M5&H1 |
| `v03_backtest.ipynb` | Grid search threshold sinyal x filter H1 trend alignment, cari parameter profitable secara sistematis |
| `v04_backtest.ipynb` | Grid search lebih luas (score x TP/SL x MAX_HOLD_CANDLES) untuk naikkan frekuensi tanpa turunkan profit factor |
| `v05_ml_training.ipynb` | Eksperimen ML (Random Forest) menggantikan scoring rule-based — walk-forward + 3-way split (train/val/test) |
| `v06_backtest.ipynb` | Ganti TP/SL fixed poin (v04) jadi ATR-relatif, untuk atasi distribution shift yang ditemukan di live trading |
| `v07_backtest.ipynb` | Coba entry breakout (pending stop order, bukan market langsung) saat sinyal muncul — **ditolak**, lebih buruk dari market order di semua metrik & window expiry |
| `v08_shakeout_analysis.ipynb` | Investigasi pola "shakeout" (SL kena dulu baru harga lanjut ke arah benar) — **tidak konsisten** di data historis (cuma 11.2% trade SL yang akhirnya sampai TP), bukan pola yang bisa diandalkan |
| `v09_drawdown_killswitch.ipynb` | Validasi threshold kill-switch drawdown harian/bulanan/total — nilai default 5/10/15% terbukti terlalu ketat (robot mati permanen di trade ke-102 dari 1664), direvisi ke 20/25/40% |
| `v10_ob_reversal.ipynb` | Order Block (SMC) lawan arah sinyal terbukti berkorelasi kuat dgn LOSS (57.8% dari semua LOSS v06). Coba 2 varian reverse (penuh & small-TP) — keduanya **overfitting** di test out-of-sample, akhirnya pakai **SKIP** (skip entry, bukan reverse) |
| `v11_trailing_stop.ipynb` | Coba trailing stop (kunci profit begitu unrealized profit capai threshold) di atas v06+SKIP — **ditolak**, konsisten merugikan net PnL di TRAIN & TEST meski win rate naik sedikit |
| `v12_deredundant_scoring.ipynb` | Breakdown skor v06 menemukan redundansi antar-oscillator bikin skor "palsu" tinggi — gabung cluster berkorelasi tinggi (oscillator, trend-follower) jadi skor komposit median per cluster |
| `v13_momentum_exhaustion.ipynb` | Momentum chain (`bull_chain`/`bear_chain`) di titik maksimum (8/8) ternyata win rate turun drastis (exhaustion) — bandingkan SKIP/REVERSE/SMALL-PROFIT, **SMALL-PROFIT** (SL/TP diperkecil, tetap searah sinyal) yang tervalidasi |
| `v14_monte_carlo.ipynb` | Analisis risiko (bukan riset strategi baru): reshuffle 10.000x urutan trade v13 di 3 dataset (TEST 196, full 721, full 2019-2026 lot-fixed 3056) buat cari distribusi max drawdown "worst case realistis" utk kill-switch total (sample terbesar paling ringan P95=-32.31%/breach 2.59%, TEST terkini lebih berat P95=-40.81%/breach 5.39%). Perluasan: kill-switch DAILY (20%) ternyata nyaris SELALU breach (100%) krn 1 trade tunggal (bukan akumulasi) bisa capai 37% dari modal $100 — tidak proporsional; monthly (25%, breach 38.63%) & total masih wajar |
| `v15_deflated_sharpe.ipynb` | Audit statistik multiple-testing (bukan riset strategi baru): apakah v13 "menang" dari 10 versi (v02-v13) krn beneran bagus atau kebetulan? Ditemukan v05 (ML, sudah ditolak dulu krn SELL-only bias) justru Sharpe/DSR tertinggi — investigasi ulang membuktikan itu MENYESATKAN (cacat model, bukan skill). Setelah v05 dikeluarkan dari kandidat valid, v13 Sharpe tertinggi di antara 9 versi dgn DSR=1.00 (signifikan, bukan cherry-picking) |
| `v16_regime_labeling.ipynb` | Analisis deskriptif (bukan riset strategi baru): apakah performa v13 konsisten di semua kondisi market (ADX trend x ATR% volatilitas), atau rata-rata menyembunyikan regime yang rugi? Diuji di 3 dataset — TIDAK ADA regime yang rugi (terlemah: Ranging/Low Vol 2019-2026, WR 57.7%/PF 1.95, tetap profitable), High Vol konsisten unggul dari Low Vol, pola ADX non-monoton (Q2 terlemah, bukan ADX terendah) |
| `v17_overfitting_diagnosis.ipynb` | Diagnosis (bukan riset strategi baru): apakah win rate naik 52.6%→74.0% (2019→2026) berarti parameter v13 "menghafal" TRAIN period (2025-01 s/d 2026-03)? TIDAK ada tanda overfitting kuat — bukti terkuat: performa TERUS NAIK jauh setelah TRAIN berakhir (2026Q2=74.1%, 2026Q3=85.7%, keduanya out-of-sample), bukan turun spt overfitting klasik. Masih ada sisa tren kecil marjinal (p=0.056) yang belum 100% dijelaskan ATR% saja — area abu-abu, jujur diakui |
| `v18_spread_adaptive.ipynb` | Investigasi realisme spread (bukan riset strategi baru): `SPREAD_POINTS=0.30` dipakai di SEMUA backtest sejak v02 ternyata tidak realistis — broker real MIFX (XAUUSD.m) spread=1.82 (6x lebih besar). Dgn spread real, strategi full period 2019-2026 jadi RUGI scr keseluruhan (PF 3.58→0.82), krn ATR kecil (rezim rendah) bikin SL/TP relatif-ATR "dimakan" spread. Filter adaptif `min_atr_over_spread>=3.0` memperbaiki metrik TEST (win rate 58%→69%, PF 2.13→2.69) TAPI perbandingan jujur (sama-sama spread real) menemukan Sharpe & total profit sedikit LEBIH RENDAH dgn filter — trade-off, bukan strict win — & filter itu scr efektif menghapus HAMPIR SELURUH era 2019-2024 (2019/2021 nol trade) |
| `v19_low_volatility_regime.ipynb` | Pencarian strategi terpisah utk rezim volatilitas rendah (2019-2024), lanjutan v18. Grid search 72 kombinasi (adx_min/min_signal_score/SL-TP multiplier/min_atr_over_spread) di TRAIN 2019-2023 pakai mesin scoring v12 + spread real 1.82 — **TIDAK SATU PUN mencapai profit factor >1.0** (terbaik PF=0.91, 436 trade). Hasil negatif yang valid: rezim volatilitas rendah TIDAK ADA edge yang bisa ditemukan lewat re-tuning mesin scoring v12 existing — akar masalah struktural (ATR terlalu kecil vs spread), bukan soal parameter |
| `v20_regime_switching.ipynb` | Regime-switching 4-kategori (Trending-Naik/Turun, Ranging-Tenang/Choppy) dari ADX+slope+whipsaw. v13 murni ternyata PALING KUAT di Ranging-Tenang (PF 7.32), bukan cuma di trending seperti dugaan awal. Eksplorasi mean-reversion (BB%B/RSI) utk Ranging-Tenang — **gagal** (PF terbaik 1.32, di bawah kriteria 1.5) |
| `v21_adaptive_regime_bos_fib.ipynb` | Coba BOS (Break of Structure) M5 sbg leading signal utk breakout awal (ADX msh rendah tp harga sudah bergerak) + Fibonacci S/R utk ranging — **keduanya gagal** (PF<1 semua kombinasi). BOS M5 murni terlalu banyak false-positive (52% breakout confirmed dlm 1 jam, pergerakan harga rata2 nyaris nol) |
| `v22_multi_timeframe_confirmation.ipynb` | Lanjutan v21: BOS dikonfirmasi H1 trend/H1 BOS/H4 trend/ADX H1 naik + S/R dari H1 (bukan cuma M5) + BB squeeze breakout. **BOS M5+BOS H1 bersamaan** kelihatan menjanjikan (win rate 36%→54.6%) tapi sample cuma 64 trade, terlalu kecil dipercaya |
| `v23_full_period_adaptive_simulation.ipynb` | Simulasi penuh 2019-2026 robot adaptif (v13 utk trend kuat + BOS_H1 utk zona transisi) — BOS_H1 dgn parameter tebakan awal **gagal jelas** (PF 0.52 gabungan, 0.17 di TRAIN out-of-sample) |
| `v24_grid_search_transition_signal.ipynb` | Grid search MENYELURUH 2304 kombinasi (rentang ADX transisi, SL/TP mult, syarat momentum chain, max_hold) utk cari BOS_H1 yang beneran cocok — **TIDAK ADA satupun dari 1008 kandidat bersample cukup mencapai PF>1.5** (terbaik PF 0.32). Lanjut coba RSI divergence (mean-reversion) sbg alternatif — **gagal lebih parah** (1200 kombinasi, terbaik PF 0.21, win rate 13-14%). Kesimpulan: >3500 kombinasi dicoba lintas 2 logika (breakout & mean-reversion), semua gagal menyeluruh utk zona transisi/ranging |
| `v25_adx_ceiling_exhaustion.ipynb` | Coba ADX ceiling (skip kalau ADX terlalu tinggi) + exhaustion-by-ADX (SL/TP kecil saat ADX tinggi) + geser adx_min lebih rendah — grid search 420 kombinasi, **0 kandidat robust** (unggul TRAIN & TEST). Cek pola dasar: win rate per bucket ADX TIDAK monoton/signifikan — ADX tinggi BUKAN prediktor loss yang bisa diandalkan |
| `v26_multi_timeframe_rsi_exhaustion.ipynb` | Investigasi RSI overbought/oversold M15/M30/H4/D1 bersamaan sbg filter exhaustion (dari pengamatan 3 loss beruntun live yang RSI-nya overbought di semua timeframe). Grid search 60 kombinasi — **1 kandidat lolos tapi dampaknya nyaris nol** (TRAIN PF 0.38→0.39, TEST PF 1.58→1.60). Pola dari 3 kejadian spesifik TIDAK general di 2282 trade TRAIN (selisih RSI WIN vs LOSS cuma 0.5-2.0 poin) |
| `v27_loss_pattern_deep_dive.ipynb` | Bedah menyeluruh 212 LOSS dari 721 trade v13 (bukan cari 1 filter, tapi petakan semua kemungkinan pola). Chi-square test: sesi, ADX bucket, arah, ATR quartile semua TIDAK signifikan. Yang SIGNIFIKAN: momentum chain (p=0.026, loss rate turun 42.1%→22.0% dari chain 4→8, KEBALIKAN dugaan) & exhaustion mode yang sudah ada (p=0.011, terbukti bekerja). TIMEOUT loss (73/212): 97% salah arah SEJAK AWAL (bukan "kurang waktu"). Losing streak max 5x, SEMUA akhirnya recovery (4-20 trade) — sistem terbukti sehat |
| `v28_support_resistance_proximity.ipynb` | **Isu #1 dari brief perbaikan v13** — robot belum sadar posisi harga vs Support/Resistance. Bangun modul S/R baru (`app/utils/indicators/support_resistance.py`, swing pivot H1/M15) + filter `check_sr_proximity()` bertingkat (skip / lolos kalau skor sangat kuat / lolos kalau ATR "bertenaga" — BUKAN skip biner). Investigasi: 83.5% trade dekat S/R H1 MANTUL (rugi); dari analisis Mann-Whitney U, SATU-SATUNYA faktor signifikan (p=0.0000) pembeda mantul/tembus adalah ATR (bukan jarak/skor). "TP dipangkas" TERBUKTI GAGAL (91.7% trade mantul salah arah SEJAK AWAL, via analisis MFE) — makanya keputusan murni SKIP. Grid search 198 kombinasi, validasi TRAIN/TEST + Monte Carlo + breakdown tahunan: full-period 2019-2026 v13 PF=0.87 (rugi) → v13+filter PF=**1.25** (untung), win rate 25.5%→35.6%, max DD 3.3x lebih ringan, losing streak 166→57 trade, unggul 6/8 tahun. **DITERAPKAN ke `usecase.py` live** (2026-09-01) meski Deflated Sharpe Ratio=0.0000 (blm terbukti signifikan scr statistik ketat) — atas keputusan eksplisit user, perlu dimonitor dari data live |
| `v29_regime_aware_sr_filter.ipynb` | **Isu #2 dari brief (percobaan 1)** — coba regime awareness (Trending vs Ranging, ADX H1/M15 pola v16) sbg PENGALI ketat filter S/R v28 (bukan filter regime berdiri sendiri, krn v20-v27 sudah 6x gagal coba itu). Cek pola dulu: performa v28 per regime ADX ternyata HAMPIR SAMA (Ranging PF 0.68 vs Trending PF 0.58 di TRAIN) — ADX rendah/tinggi BUKAN pembeda kuat. Grid search 48 kombinasi tetap nemu kandidat robust tapi efeknya TIPIS: PF full-period 1.25→1.31 (+4.8%). **TIDAK diterapkan** — perbaikan terlalu kecil utk nambah kompleksitas |
| `v30_whipsaw_aware_sr_filter.ipynb` | **Isu #2 dari brief (percobaan 2, definisi lebih presisi)** — user klarifikasi "sideways bahaya" itu bukan ADX rendah, tapi choppy/whipsaw (harga bolak-balik cepat tanpa arah bersih, confirmed dari contoh chart). Ukur pakai `whipsaw_score` (pola v20: proporsi candle ganti arah dlm 1 jam) sbg pemicu SKIP TOTAL (bukan cuma diperketat) saat choppy tinggi. Grid search 37 kombinasi: kandidat terbaik `skip_all_when_choppy=True` — PF full-period 1.25→**1.42** (+13.6%), max drawdown -116.84%→**-48.46%** (2.4x lebih ringan), TAPI net profit turun 15% ($2967→$2532, trade berkurang 47%) krn skip total korbankan volume. Robust 6/8 tahun. **TIDAK diterapkan** — trade-off (risiko lebih aman tapi profit lebih kecil) dinilai user tidak cukup signifikan utk nambah kompleksitas kode, v28 tetap yang aktif di live |
| `v31_post_tp_chasing.ipynb` | **Isu #3 dari brief (re-evaluasi sebelum re-entry) + investigasi loss beruntun live** — mulai dari hipotesis "chasing" (re-entry searah setelah TP, entry jauh dari entry sblmnya): TERBUKTI SALAH ARAH, re-entry searah setelah WIN justru win rate lebih tinggi (45% vs 32%), filter anti-chasing MEMPERBURUK semua kombinasi grid search. Coba Fibonacci sbg filter tambahan S/R (v28): TIDAK signifikan scr praktis (semua kombinasi TRAIN PF 0.54-0.61, tdk lebih baik dari baseline 0.60). Coba `adx_min` M5 dinamis berdasar ADX H1 (H1 sideways → adx_min lebih ketat): TIDAK ada perbaikan (TRAIN PF 0.60-0.62 semua, nyaris sama). **Titik balik**: cross-check trade log live HFM (5 dari 6 SELL beruntun 1 Sept 2026) vs data MT5 real — BUKAN H1 sideways (ADX H1 31-43, trending kuat) & BUKAN S/R proximity (jarak 3-11x ATR) — pola yang konsisten cuma **momentum chain exhaustion** (`bear_chain` 7-8/8 di 5/6 loss beruntun). Uji ulang mekanisme exhaustion v13 (SMALL-PROFIT/SL-TP diperkecil, cara lama) vs SKIP total: **SKIP menang di semua metrik** — TRAIN PF 0.58→0.64, TEST PF 1.68→**1.88**, net_pnl $4294.87→**$4462.92**, max DD -18.91%→**-15.27%**, full-period 2019-2026 PF 1.19→**1.33** (+12%), Monte Carlo P95 drawdown lebih ringan di semua persentil, **DSR=1.0000** (signifikan, N_TRIALS=2 krn keputusan biner bukan grid search besar). **DITERAPKAN ke `usecase.py` live** (2026-09-01) — ganti exhaustion dari "SL/TP diperkecil" jadi "skip total" |

## Dataset

CSV mentah XAUUSD **7 timeframe** (M1, M5, M15, M30, H1, H4, D1), per tahun (2019-2026), sudah ada
di `dataset/raw/`: `xauusd_<tf>_<tahun>.csv` (mis. `xauusd_m5_2025.csv`). Kolom: `timestamp, datetime,
open, high, low, close, volume`.

`v01_eda.ipynb` memproses ketujuh timeframe ini sekaligus dan menyimpan hasilnya (gabungan semua
tahun + semua indikator) ke `dataset/processed/m5_scalping/v01/xauusd_<tf>_full_indicators.csv`.
Strategi `m5_scalping` di repo ini makai M5 (sinyal) + H1 (konteks tren H1); timeframe lain (M1, M15,
M30, H4, D1) disiapkan sekalian supaya siap dipakai kalau ada riset/strategi baru nanti tanpa perlu
ulang proses load+validasi+indikator dari nol.

Catatan ukuran file: `xauusd_m1_full_indicators.csv` ~2.3 GB (2.7 juta candle M1 x 75 kolom) — cukup
besar, sesuai kebutuhan warm-up indikator (mis. `sma_200`) dijaga tetap sama di semua timeframe.

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

**v07 (entry breakout / pending stop order — ditolak):** user amati chart live: harga kadang
breakdown dulu sebelum breakout beneran, dugaan entry market langsung "kena jebak" di momen itu.
Dicoba: ganti market order jadi pending BUY STOP/SELL STOP di level high/low candle sinyal, dengan
window expiry (1/2/3/6/12 candle) sebelum order dibatalkan. **Hasil: semua kombinasi expiry lebih
buruk dari market order langsung** di semua metrik (win rate, profit factor, drawdown) — bahkan
expiry terbaik (2 candle) cuma dapat PF 1.28 vs PF 1.40 v06 murni di periode 2026, dan 31% sinyal
malah hangus (expired, gak pernah breakout). **Kesimpulan: filter H1 alignment + score>=9 sudah
cukup ketat menyaring momentum bagus — nambah syarat breakout confirmation malah nyaring lebih
banyak sinyal MENANG drpd sinyal jelek yang dihindari.** v07 tidak dipakai.

**v08 (investigasi pola "shakeout" — tidak konsisten):** dari 534 trade v06 yang kena SL, dicek
apakah harga akhirnya "kembali" ke arah benar (sampai TP original) dalam 2 jam setelah SL —
hipotesis: kalau SL sedikit lebih lebar, trade itu jadi WIN bukan LOSS. **Hasil: cuma 11.2% (60 dari
534) yang akhirnya sampai TP** — 88.8% memang salah arah beneran, bukan shakeout sesaat. Simulasi
kasar melebarkan SL (2.5x-4x ATR) cuma menyelamatkan 7.3%-38.8% trade yg tadinya loss, dgn risiko
per trade lebih besar. **Kesimpulan: pola "kena SL dulu baru lanjut profit" yang kelihatan di 2-3
contoh chart itu survivorship bias, bukan pola sistematis** — SL v06 (2x ATR) sudah cukup wajar.

**v09 (validasi kill-switch drawdown — revisi threshold):** kode live sudah punya kill-switch
drawdown (`_check_drawdown_guard`) dgn default `.env.example` 5%/10%/15% (daily/monthly/total),
tapi belum divalidasi. Replay 1664 trade v06 dgn kill-switch: **threshold 5/10/15% bikin robot mati
PERMANEN di trade ke-102 dari 1664** (baru 6% jalan) — krn drawdown alami strategi v06 (-28.4%
historis) jauh melebihi 15%. Grid search 36 kombinasi (daily 3-10%, monthly 8-20%, total 12-30%)
semuanya tetap ke-trigger permanen di suatu titik. Baru di **total>=35%** kill-switch gak pernah
ke-trigger sama sekali (identik dgn tanpa kill-switch). **Parameter terpilih: daily=20%,
monthly=25%, total=40%** — tervalidasi tidak pernah ke-trigger di seluruh backtest, tetap jadi
jaring pengaman kalau live menyimpang jauh dari backtest (mis. bug, akun rusak).

**v10 (Order Block SMC lawan arah — SKIP dipilih, reverse ditolak 2x):** analisis trade_log_full.csv
v06 menemukan pola kuat: **57.8% dari semua LOSS v06 terjadi saat ada Order Block (SMC) M5/H1 yang
melawan arah sinyal** (padahal cuma 41% dari total trade) — kelompok ini rugi bersih -$2050 scr
agregat, sementara kelompok tanpa OB lawan arah untung +$4375. Kalau OB M5 & H1 aktif BERSAMAAN,
win rate anjlok ke 8.6% (vs 66.7% baseline). Dicoba 2 varian sblm SKIP:
1. **REVERSE PENUH** (balik arah sinyal, TP/SL sama besar 2x/4x ATR spt sinyal normal) — win rate
   trade reverse turun dari 56.8% (TRAIN) ke 51.2% (TEST out-of-sample, nyaris coin-flip), PF kalah
   dari SKIP. **Overfitting, ditolak.**
2. **SMALL-REVERSE** (balik arah, tapi TP/SL kecil buat scalp jendela reversal singkat yg terbukti
   ada di price path — 77.5% trade LOSS OB sempat searah dulu ~26% dari jarak SL sebelum berbalik)
   — grid search TRAIN pilih SL=0.5x/TP=2.0x ATR (RR 4:1, win rate cuma 29.1%), tapi net_pnl trade
   reverse ini +$2421 di TRAIN jadi **-$131 di TEST**. **Overfitting lagi, ditolak.**

**Keputusan: pakai SKIP** (skip entry kalau ada OB lawan arah, bukan reverse) — satu-satunya opsi
yang konsisten robust di TRAIN & TEST out-of-sample (PF 2.32 di TEST, vs REVERSE 2.08 & baseline
1.37). Diterapkan di `_has_opposing_order_block()` di `usecase.py`.

**Bug lookahead ditemukan (2026-08-15):** indikator `add_order_block()` pakai `.shift(-1/-2/-3)`
(candle 3 KE DEPAN) utk konfirmasi order block — valid di backtest (data historis lengkap), tapi di
**live, candle terakhir (yg dipakai sinyal) selalu `ob_bull=0, ob_bear=0`** krn belum ada "3 candle
ke depan"nya. Filter SKIP order block jadi tidak pernah aktif di live sejak diterapkan sampai
ditemukan. Belum diperbaiki di kode (perlu redesain jadi indikator yg gak lookahead, mis. deteksi
dari harga N candle ke BELAKANG bukan ke depan) — dicatat sbg technical debt.

**v11 (trailing stop — ditolak):** user amati live: trade WIN biasa profit $10-15 tapi sempat naik
lebih tinggi dulu sebelum closing — apakah SL perlu digeser naik (trailing) begitu profit unrealized
capai threshold, buat kunci sebagian profit? Analisis price path (di atas v06+SKIP): trade WIN
rata-rata sempat naik ~3x ATR sebelum exit (median 2.82x ATR) vs realized profit median cuma $6.70
— ada gap besar, konsisten dgn yang diamati user. Tapi grid search trailing (activate 1-3x ATR x
lock 0.25-1.5x ATR) di TRAIN, divalidasi di TEST: **net PnL turun konsisten** di TRAIN (-$408) & TEST
(-$318, net dampak trailing -$253.54) meski win rate naik sedikit (+0.5-1.6 poin). **Penyebab: RR
v06 sudah 2:1 (SL=2x/TP=4x) — begitu breakout arahnya benar, biasanya lanjut jauh; trailing yang
terlalu dini justru memotong potensi profit besar demi menyelamatkan sedikit trade kecil.** v11
tidak dipakai — baseline v06+SKIP tanpa trailing tetap lebih baik.

**v12 (de-redundant scoring — cluster oscillator & trend-follower digabung median):** analisis
breadth-vs-depth pada trade_log v06 menemukan skor tinggi krn kontribusi SMC (bobot besar, sinyal
"dalam") win rate 55.7%, sementara skor tinggi krn breadth/oscillator doang (banyak indikator
berkorelasi align bersamaan, bukan sinyal kuat sesungguhnya) cuma win rate 41.4% — indikasi skor
gabungan v06 "palsu" tinggi di sebagian trade. Analisis korelasi antar-indikator dalam 20 kategori
skor menemukan 2 cluster berkorelasi tinggi: oscillator (RSI/Stoch/Williams%R/CCI/BB/VWAP, korelasi
0.67-0.94) dan trend-follower (SMA/Ichimoku/Supertrend, korelasi 0.65-0.71). **Perbaikan:** dalam tiap
cluster, un-weight skor member lalu ambil median (bukan sum semua), baru re-weight jadi 1 skor
komposit per cluster — kategori independen (MACD, ADX, candle, dst) tetap dijumlah seperti biasa.

Grid search threshold (TRAIN) awalnya salah pilih `threshold=4.0` krn disortir pakai `final_equity`
(bias ke volume trade) — dikoreksi manual, `profit_factor` justru tertinggi di `threshold=9.0` (PF
2.90 TRAIN, kebetulan sama dgn v06, tapi kali ini dipilih via kriteria yang benar). **Keputusan:
pakai v12 (threshold=9.0) sbg pengganti scoring v06 murni**, tetap dikombinasikan dgn filter Order
Block (v10-SKIP) — validasi ablation menunjukkan tanpa filter OB, max_drawdown TEST melebar dari
-34% ke -87% meski scoring sudah de-redundant, jadi filter OB **wajib** tetap aktif.

**v13 (momentum chain exhaustion — SMALL-PROFIT dipilih, REVERSE ditolak):** analisis lanjutan pada
kombinasi v12+OB filter menemukan momentum chain (`bull_chain`/`bear_chain`, skala 0-8 dari
`add_momentum_chain`) yang mentok di titik MAKSIMUM (8/8) justru win rate anjlok ke **52.1%** vs
**76.7%** di chain 7/8 — chain penuh berarti momentum sudah "matang"/exhausted, bukan sinyal makin
kuat. Dicoba 3 perlakuan utk kondisi chain>=8: SKIP (skip entry sama sekali), REVERSE (balik arah,
TP/SL sama besar — win rate cuma 18-24% baik TRAIN maupun TEST, **ditolak, jauh lebih buruk**), dan
**SMALL-PROFIT** (tetap searah sinyal, tapi SL/TP diperkecil jadi 1.25x/1.0x ATR dari normal 2x/4x,
max_hold dipersingkat jadi 6 candle dari 12) — SMALL-PROFIT tervalidasi konsisten di TRAIN & TEST.

**Keputusan (kombinasi final v12+OB filter+v13, disebut v13 di `models/m5_scalping/v13/`):** diuji
total order di kombinasi ini, lalu diterapkan ke live (`app/features/m5_scalping/usecase.py`,
`generate_signal_v12` + `has_opposing_order_block` + exhaustion-aware SL/TP). Diuji ulang di periode
TEST out-of-sample murni (196 trade, 2026-03 s/d 2026-08): win rate 75.0%, profit factor 3.57. Divalidasi
lebih lanjut di seluruh histori 2019-2026 (3056 trade, rentang harga XAUUSD $1300-$4500+) utk pastikan
strategi robust lintas rezim harga, bukan overfit ke kondisi 2025-2026 saja — win rate naik bertahap
dari 52.6% (2019) ke 74.0% (2026), menunjukkan strategi tetap berfungsi (walau lebih lemah) bahkan di
rezim harga yang jauh berbeda dari data tuning-nya.

**v14 (Monte Carlo simulation — analisis risiko, BUKAN riset strategi baru):** backtest v13 kasih
SATU angka max drawdown (-34.18% di TEST, 196 trade) dari SATU urutan trade spesifik yang kebetulan
terjadi. Pertanyaan: seberapa "beruntung" urutan itu, dan seberapa dalam drawdown bisa terjadi kalau
urutannya (bukan kualitas sinyalnya) sedikit berbeda? Metodologi: reshuffle (permutation, bukan
resample dgn penggantian — supaya distribusi menang/kalah/besaran PnL keseluruhan TIDAK berubah,
murni urutan yg diacak) 10.000x per dataset, hitung ulang max drawdown tiap kali. Diuji di **3
dataset**: TEST (196 trade, kondisi terkini), full 2025-2026 (721 trade, termasuk TRAIN), dan full
**2019-2026 dgn lot FIXED** (3056 trade, 7.6 tahun — di-generate ulang khusus dgn lot 0.01 konstan,
bukan compounding equity-based spt trade log v13 asli, supaya PnL antar-trade sepanjang periode
sebanding & reshuffle-nya adil, bukan didominasi trade-trade akhir yang lotnya sudah raksasa akibat
compounding 7.6 tahun).

**Temuan:** sample TERBESAR (2019-2026, 3056 trade) — paling stabil scr statistik — justru
menghasilkan gambaran risiko PALING RINGAN: persentil 95 (P95, worst case 1-dari-20 kemungkinan) di
**-32.31%**, MASIH DI BAWAH kill-switch 40%, dgn cuma **2.59%** skenario reshuffle yang menembusnya.
Sebaliknya, sample TEST (196 trade, paling representatif kondisi terkini) P95-nya **-40.81%**,
sedikit MELAMPAUI kill-switch 40% (breach rate 5.39%); full period 2025-2026 (721 trade) malah lebih
tinggi lagi (P95=-52.84%, breach rate 11.89%). Ini bukan kontradiksi — sample lebih kecil punya
varians lebih tinggi (lebih rentan ke urutan "buruk" yang kebetulan terjadi), sample besar meredam
itu lewat hukum bilangan besar & mencakup lebih banyak rezim harga ($1300-$4500+). Urutan kronologis
asli TEST (-34.18%) termasuk skenario relatif beruntung (cuma 10% reshuffle lebih buruk), tapi urutan
asli 2019-2026 (-11.72%) ternyata SANGAT beruntung (56.9% reshuffle lebih buruk dari itu).

**Perluasan (Section 9-11 di notebook): Monte Carlo untuk kill-switch DAILY & MONTHLY.** Kill-switch
total dihitung dari drawdown across seluruh periode (baseline = peak equity, tidak pernah reset) —
daily/monthly beda mekanisme (baseline reset tiap hari/bulan kalender baru). Percobaan pertama pakai
dataset 2019-2026 GAGAL: PnL per trade (lot fixed 0.01) melebar 8x antar tahun (std $1.74 di 2019 vs
$14.37 di 2026, krn harga emas beda drastis) — tidak valid dipakai utk kelompok kecil (2-37
trade/hari-bulan). Diperbaiki pakai dataset TEST (196 trade, semua dari 2026, skala konsisten).

**Temuan penting: kill-switch DAILY (20%) nyaris SELALU breach (100% dari 10.000 simulasi
reshuffle+regroup jadi kelompok "hari sintetis").** Penyebabnya BUKAN akumulasi banyak trade kecil
(spt kill-switch total), tapi **SATU TRADE TUNGGAL** yang ukurannya sendiri sudah mendekati/melebihi
threshold. Trade terburuk TEST set: SELL 2026-03-24, SL normal kena (`exit_reason=SL`, bukan
anomali/bug), ATR=$18.72, SL=2×ATR=$37.44 poin, lot 0.01 → pnl=-$37.44 (**37.4% dari modal $100
DALAM SATU TRADE**). Dengan cuma ~2 trade/hari, kill-switch daily 20% efektifnya jadi "kill-switch
per-trade", bukan "kill-switch akumulasi harian" seperti tujuan aslinya — TIDAK proporsional
terhadap risiko per-trade individual di rezim harga XAUUSD saat ini (~$4300+) dengan modal $100 &
lot fixed 0.01. Kill-switch **monthly (25%, breach 38.63%) TIDAK bermasalah** — breach-nya didorong
akumulasi wajar beberapa trade jelek dalam 1 bulan (37 trade/kelompok), sesuai tujuan aslinya.

**Keputusan:** v14 TIDAK mengubah `trade_params`/`signal_params` v13 ATAU nilai apa pun di `.env` —
murni analisis risiko, disimpan sbg field `monte_carlo_analysis` (termasuk sub-field
`daily_monthly_extension`) di `models/m5_scalping/v13/params.json`. Trade log lot-fixed 2019-2026
disimpan terpisah di `dataset/processed/m5_scalping/v14/trade_log_full_2019_2026_fixed_lot.csv` —
BUKAN pengganti `trade_log_full_2019_2026.csv` (v13, compounding) yang tetap jadi acuan
`win_rate_pct_by_year`. Rekomendasi (bukan keputusan otomatis): kill-switch daily kemungkinan perlu
dinaikkan (mis. ke 35-40%) ATAU modal ditingkatkan dari $100, sementara monthly & total tetap
proporsional — trade-off proteksi ekstra konservatif vs membiarkan strategi jalan diserahkan ke
preferensi risk-tolerance user. Catatan keterbatasan: Monte Carlo di sini cuma mengukur risiko
URUTAN/KONSENTRASI PER-TRADE (sequence & sizing risk), bukan risiko distribusi win rate/PnL itu
sendiri berubah di masa depan (mis. market regime shift spt v04→v06/v05) — risiko yang berbeda.

**Update (2026-08-16):** kesimpulan kill-switch daily DITERAPKAN — `MAX_DAILY_DRAWDOWN_PCT`
direvisi 20% → 40% di `.env` & `.env.example`, `app/core/config.py` diupdate sesuai.

**v15 (Deflated Sharpe Ratio — audit multiple-testing, BUKAN riset strategi baru):** dari v02
sampai v13, ada **10 versi strategi** yang dicoba (v02-v07, v10-v13 — v01/v08/v09 dikecualikan
krn bukan versi strategi trading baru). Tiap kali versi "terbaik" dipilih dari backtest, itu
cherry-picking dari 10 percobaan — makin banyak percobaan, makin besar kemungkinan salah satu
menang murni krn kebetulan cocok data historis. **Deflated Sharpe Ratio (DSR)**, dari Bailey &
López de Prado (2014), mengoreksi Sharpe Ratio versi terbaik terhadap: (1) berapa banyak versi
dicoba, (2) panjang data, (3) skewness/kurtosis distribusi return — hasilnya probabilitas
(DSR>=0.5 = signifikan scr statistik, bukan cuma menang undian).

Metodologi: return HARIAN (basis $100) dari **TEST period yang SAMA** (2026-03-01 s/d 2026-08-06,
158 hari kalender) utk semua 10 versi — supaya perbandingan apple-to-apple, bukan dipengaruhi
rezim harga beda per versi (trade log v02-v07 aslinya full period 2025-2026, dipotong ke TEST
period sblm dihitung Sharpe-nya).

**Temuan mengejutkan di awal:** dari 10 versi, **v05 (ML Random Forest) punya Sharpe & DSR
TERTINGGI** (SR=0.94, DSR=1.00) — mengalahkan v13 (SR=0.39, DSR=0.42, DI BAWAH ambang
signifikan). Investigasi lanjutan mengungkap kenapa: v05 di TEST period **100% sinyal SELL, 0%
BUY** — cacat *distribution shift* yang SUDAH ditemukan & didokumentasikan sblm v15 dibuat
(lihat entri v05 di atas: "model jadi SELL-only... TIDAK dipakai live"). v05 kebetulan Sharpe
tinggi krn periode TEST (Mar-Agu 2026) XAUUSD net naik, & model yang SELALU bilang "turun"
kebetulan cocok arah minoritas trade yang menang — murni *statistical accident* dari model rusak,
BUKAN skill.

**Ini demonstrasi nyata keterbatasan DSR**: DSR mengukur SIGNIFIKANSI STATISTIK dari distribusi
return historis, TAPI TIDAK BISA mendeteksi apakah LOGIKA sinyal di baliknya valid/robust. DSR
harus dipakai SETELAH filter kualitatif (cek bias arah, cacat struktural), bukan pengganti filter
kualitatif — persis pola yang sudah menyelamatkan kita dari salah pilih v05 di riset dulu (v05
gugur duluan krn SELL-only bias, sebelum sempat dibandingkan Sharpe-nya scr adil).

**Setelah v05 dikeluarkan dari kandidat** (gugur di tahap kualitatif, bukan kalah bersaing scr
performa — N_valid=9): **v13 jadi Sharpe TERTINGGI (0.3949) dengan DSR=1.0000 (100% signifikan)**.
Ini jawaban yang benar utk pertanyaan asli: v13 signifikan lebih baik dari benchmark kebetulan
(E[max(SR)] dari 9 percobaan = 0.2057), bukan cuma menang undian. Sensitivity check (N_TRIALS
5-100) menunjukkan kesimpulan robust — tidak sensitif thd asumsi jumlah percobaan yang dihitung.

**Keputusan:** v13 valid secara statistik sbg pemenang seleksi 9 versi kandidat yang layak
dibandingkan — bukan cherry-picking beruntung. **Peringatan penting utk riset masa depan**: Sharpe/DSR
tinggi TIDAK CUKUP sbg kriteria terima strategi baru, WAJIB dikombinasikan dgn audit kualitatif
(arah sinyal masuk akal, tidak bias struktural spt SELL-only). Tidak ada perubahan
`trade_params`/`signal_params` v13 dari analisis ini — hasil lengkap tersimpan sbg field
`deflated_sharpe_ratio_analysis` di `models/m5_scalping/v13/params.json`.

**v16 (Regime Labeling — analisis deskriptif, BUKAN riset strategi baru):** angka agregat v13
(win rate 75% TEST, 52.6%→74.0% per tahun 2019-2026) itu RATA-RATA — bisa menyembunyikan bahwa
strategi cuma menang di SATU jenis kondisi market & rugi di kondisi lain (analogi dokter: "rata-rata
suhu pasien 37°C" bisa menyembunyikan separuh demam 40°C & separuh hipotermia 34°C). **Regime
labeling** memecah data berdasar kondisi market objektif — Trend (ADX≥25 Trending vs <25 Ranging)
x Volatilitas (ATR% tinggi/rendah, split median tiap dataset) — lalu hitung performa per kondisi
terpisah, bukan gabungan. Diuji di **3 dataset** (TEST 196 trade, full 2025-2026 721 trade, full
2019-2026 3056 trade — trade log 2019-2026 di-generate ulang khusus dgn kolom ADX/ATR/close per
trade, krn versi v14 sebelumnya tidak menyimpan kolom itu).

**Temuan utama — TIDAK seperti analogi dokter, TIDAK ADA regime yang rugi**: keempat kombinasi
regime (Trending/Ranging x High/Low Vol) semuanya profitable (win rate>50%, PF>1) di ketiga
dataset — regime terlemah (Ranging/Low Vol, dataset 2019-2026): win rate 57.7%, PF 1.95, masih
jelas untung. Pola konsisten di ketiga dataset: **High Vol SELALU mengalahkan Low Vol** (baik saat
Trending maupun Ranging) — volatilitas tinggi tampaknya lebih penting drpd arah trend semata.
Breakdown kuartil ADX (lebih halus dari split biner 25) menunjukkan pola TIDAK monoton — Q1 (ADX
terendah tapi di atas hard filter 18) justru sering JADI TERKUAT (PF 10.48 di TEST), sementara Q2
konsisten TERLEMAH di ketiga dataset, & Q4 (ADX tertinggi) TIDAK selalu terbaik — sejalan dgn
temuan v13 soal momentum chain exhaustion (ADX ekstrem = trend sudah matang, rawan reversal).

**Investigasi tren win rate 52.6%→74.0% (2019→2026): KEDUA penyebab berkontribusi, bukan cuma
satu.** (1) Komposisi regime berubah drastis — 2026 didominasi kondisi High Vol (94% trade, naik
dari campuran lebih merata di 2019). (2) TAPI win rate juga naik DALAM regime yang SAMA (Ranging:
49.2%→76.4%, Trending: 54.5%→72.3%) — bukan cuma soal komposisi regime berubah, performa
struktural pun membaik seiring waktu, kemungkinan krn XAUUSD di harga lebih tinggi ($4300+ vs
$1300) membuat SL/TP ATR-relatif v13 bekerja lebih efektif secara struktural.

**Keputusan:** TIDAK ADA regime yang perlu di-skip — semua kombinasi tetap profitable, filter
regime tambahan akan membuang 24-44% trade yang menguntungkan tanpa dasar kuat. Pola ADX
non-monoton (Q2 terlemah, bukan Q1) mengonfirmasi `adx_min=18` saat ini sudah cukup baik — menaikkan
threshold ADX minimum (mis. ke 25) BELUM TENTU membantu krn Q1 justru salah satu yang terkuat, bukan
terlemah. Tidak ada perubahan `trade_params`/`signal_params` v13 dari v16 — hasil lengkap
tersimpan sbg field `regime_labeling_analysis` di `models/m5_scalping/v13/params.json`. Catatan
keterbatasan: split volatilitas pakai median TIAP DATASET (bukan angka absolut sama, supaya adil
lintas rezim harga 2019 $1300 vs 2026 $4300+) & regime dihitung dari trade yang SUDAH LOLOS semua
filter v13, bukan gambaran regime market secara umum.

**v17 (Diagnosis overfitting — analisis lanjutan v16, BUKAN riset strategi baru):** user curiga
win rate naik konsisten 52.6% (2019) → 74.0% (2026) berarti parameter v13 (`min_signal_score=9.0`,
`adx_min=18`, SL/TP multiplier) "menghafal" TRAIN period (2025-01 s/d 2026-03, satu-satunya
window yang dilihat saat tuning) — 2019-2024 tidak pernah dilihat sama sekali. Kalau benar,
performa bagus di 2025-2026 cuma kebetulan cocok dgn data yang dipakai cari parameter, bukan edge
yang tahan lama.

**Metodologi**: (1) korelasi win rate tahunan vs ATR%/harga; (2) **uji kunci** — kontrol ATR%
SECARA ABSOLUT (bukan relatif per tahun spt v16), lihat apakah win rate DALAM bucket volatilitas
yang identik pun masih naik seiring tahun; (3) cek rasio besar win/loss (apakah TP jadi relatif
lebih gampang kena); (4) breakdown arah BUY vs SELL (apakah cuma "menumpang" tren panjang naik
XAUUSD); (5) **breakdown kuartalan di sekitar batas TRAIN** — pembeda paling langsung: lompatan
tajam pas masuk TRAIN = red flag overfitting kuat, tren gradual sejak jauh sebelumnya = lebih
konsisten dgn perubahan struktural market.

**Temuan: TIDAK ada tanda overfitting kuat, tapi area abu-abu yang jujur diakui, bukan hitam-putih.**
Bukti PALING KUAT melawan overfitting: **performa terus naik JAUH SETELAH TRAIN berakhir**
(2026Q2 win rate 74.1%, 2026Q3 85.7% — keduanya bagian TEST set out-of-sample, bukan TRAIN).
Overfitting klasik menunjukkan bagus IN-SAMPLE lalu JATUH begitu keluar window training — pola di
sini justru KEBALIKANNYA, terus naik. Juga tidak ada lompatan tajam di 2025Q1 (mulai TRAIN):
67.3% masih dalam rentang yang sudah pernah dicapai sebelumnya (2020Q3=68.0%, 2021Q3=68.0%).
Win/loss ratio TURUN seiring tahun (bukan naik) — menyingkirkan "TP jadi lebih gampang kena".
Kedua arah (BUY & SELL) sama-sama membaik, bukan cuma BUY yang numpang tren panjang naik.

**Tapi ada sisa yang belum 100% terjelaskan**: uji kunci (bucket ATR% 0.05-0.08% terkunci absolut
di 8 tahun) masih menunjukkan win rate naik 55.0%→75.0%, tapi **p=0.0557 — marjinal**, tepat di
ambang signifikansi (n=8 tahun, statistical power terbatas). Volatilitas menjelaskan SEBAGIAN
BESAR tren (korelasi r=0.878 dgn ATR% tahunan), mungkin tidak semuanya. Hipotesis: XAUUSD di
harga absolut lebih tinggi menghasilkan karakteristik price action berbeda per unit ATR% yang
sama (mis. spread/microstructure noise proporsinya makin kecil thd pergerakan harga) —
perubahan struktural market, bukan overfitting parameter ke window spesifik.

**Keputusan:** parameter v13 TIDAK direvisi berdasarkan v17 — tidak ada bukti kuat yang
mengharuskan tuning ulang. Rekomendasi kewaspadaan berkelanjutan: skenario XAUUSD turun tajam
kembali ke rezim harga rendah belum pernah terjadi di data manapun (2019-2026 seluruhnya net
naik) — pantau performa live secara berkala, terutama kalau harga suatu saat berbalik turun
drastis (early warning utk regime shift yang belum tercakup data historis manapun). Hasil lengkap
tersimpan sbg field `overfitting_diagnosis` di `models/m5_scalping/v13/params.json`.

**v18 (Spread adaptif — investigasi realisme spread, BUKAN riset strategi baru):** user minta
robot "baca volatilitas" & menyesuaikan diri drpd pakai 1 parameter tetap sepanjang rezim.
Investigasi dimulai dari akar: konstanta `SPREAD_POINTS=0.30` dipakai di **SEMUA** backtest sejak
v02 tapi tidak pernah divalidasi thd broker real. User pakai broker **MIFX** (lokal Indonesia) di
MT5, modal riil **$100**, leverage **1:100**.

**Temuan kritis: spread broker real (`XAUUSD.m`) = 1.82 poin, 6x lebih besar dari asumsi 0.30
yang dipakai selama ini.** Dgn spread real, performa full period 2019-2026 anjlok drastis: win
rate 62.14%→43.53%→24.91% & profit factor 3.58→1.60→**0.82** (uji 0.30→1.00→1.82) — pada spread
real, strategi jadi **RUGI scr keseluruhan** (PF<1). SEMUA tahun terdegradasi (2019 terparah,
52.6%→3.5%), bahkan 2026 (rezim tervalidasi live) turun signifikan (74.0%→58.6%). Akar masalah:
SL/TP dihitung sbg kelipatan ATR — saat ATR kecil (rezim volatilitas rendah), spread jadi porsi
besar dari jarak SL/TP, memakan margin profit sblm harga sempat bergerak.

**Mitigasi dicoba: filter adaptif `min_atr_over_spread`** (skip entry kalau `ATR/spread < N`) —
parameter tunggal, otomatis "baca" apakah volatilitas cukup tanpa re-tuning manual per rezim.
Grid search awal SEMPAT salah pilih `threshold=10.0` dari cuma 6 trade TRAIN (pola bug sama
persis yg pernah ditemukan di v12) — dikoreksi dgn syarat sample minimum (`MIN_SAMPLE_TRAIN=30`)
sblm validasi TEST. Threshold terkoreksi: `3.0` (91 trade TRAIN, PF=2.03). Validasi TEST: win
rate 58.03%→68.97%, PF 2.13→2.69, max drawdown -49.59%→-43.82% — kelihatan seperti kemenangan
jelas.

**User eksplisit minta perbandingan tidak bias** ("takut nya dia hanya uji menang doang") —
perbandingan apple-to-apple (SAMA-SAMA spread real 1.82, dgn vs tanpa filter) menemukan: **Sharpe
Ratio TANPA filter (0.268) sedikit LEBIH TINGGI drpd DENGAN filter (0.252)**, & **total net
profit TANPA filter ($733.88) LEBIH BESAR drpd DENGAN filter ($608.12)** — meski
win_rate/PF/drawdown filter lebih baik. Filter mengurangi risiko per-trade & konsistensi, tapi
juga memotong total volume peluang yang berkontribusi ke profit agregat — **trade-off, bukan
strict win di semua metrik.** Filter jg scr efektif menghapus **hampir seluruh era volatilitas
rendah**: full 2019-2026 dgn filter cuma hasilkan 189 trade dlm 7.6 tahun, 134 (71%) di 2026 saja,
2019 & 2021 **nol trade**.

**Keputusan:** TIDAK diterapkan ke `usecase.py` live — murni riset notebook. Temuan filter yang
menghapus hampir seluruh 2019-2024 memicu keputusan pindah arah riset: drpd memaksakan 1 strategi
(v13+filter) di semua rezim, cari strategi TERPISAH khusus rezim volatilitas rendah (→ v19).
Hasil lengkap tersimpan sbg field `spread_realism_analysis` di `models/m5_scalping/v13/params.json`.

**v19 (Strategi rezim volatilitas rendah — hasil NEGATIF, dilaporkan jujur):** lanjutan
langsung v18. User: "kalo rezim volalitas rendah gak treding kita bener2 ubah strategis aja
dengan kecocokan yang rezim volalitas rendaah kita cari pola yang cocok" — drpd memaksakan
filter yang menghapus era 2019-2024, cari strategi yang GENUINELY cocok utk rezim itu.

**Scope** (diklarifikasi dgn user sblm mulai): data basis 2019-2024 penuh, TRAIN (2019-2023,
351K candle) / TEST (2024, 60K candle) di dalamnya; metodologi reuse mesin scoring v12 yang
sama (bukan logika sinyal baru dari nol), re-tuning threshold (`adx_min`, `atr_min_pct`,
`min_signal_score`) & SL/TP multiplier scr menyeluruh, termasuk cari ulang `min_atr_over_spread`
— semua dgn spread real 1.82 (bukan 0.30).

**Baseline (parameter v13 asli dipaksakan ke rezim rendah)**: TRAIN win rate 11.58%, PF **0.24**
— sangat rugi, mengonfirmasi parameter v13 memang fundamental tidak cocok utk rezim ini.

**Grid search 72 kombinasi (TRAIN 2019-2023, syarat sample minimum 30 trade diterapkan
konsisten spt v18): TIDAK SATU PUN mencapai profit factor > 1.0.** Kandidat terbaik
(`adx_min=18, min_signal_score=9.0, sl_mult=3.0, tp_mult=6.0, min_atr_over_spread=1.5`) →
436 trade (sample besar, bukan kebetulan), win rate 44.95%, **PF=0.91** — masih rugi bersih.
Krn kriteria sukses (PF>1.5 di TEST) sudah gagal terpenuhi bahkan di TRAIN, **validasi TEST
sengaja TIDAK dilakukan** — melanjutkan tanpa kandidat layak cuma akan jadi fishing for
significance (mencari sampai kebetulan ketemu yang bagus di TEST, padahal TRAIN-nya sendiri
tidak solid).

**Kenapa ini hasil yang masuk akal (bukan kegagalan riset)**: konsisten dgn akar masalah yang
sudah dibuktikan v18 scr matematis — rata-rata ATR M5 di rezim rendah cuma $0.85-1.85, sementara
spread broker real 1.82. Bahkan dgn SL/TP dilebarkan 3x/6x ATR, margin thd spread tetap terlalu
tipis utk menang konsisten. Ini soal **struktur ekonomi trading M5 scalping** di volatilitas
serendah itu dgn spread broker lokal yang relatif lebar — bukan soal salah pilih parameter.

**Keputusan:** robot **seharusnya memang tidak trading sama sekali** kalau market kembali ke
rezim volatilitas serendah 2019-2024 — bukan krn bug, tapi krn tidak ada edge valid yang
ditemukan setelah pencarian menyeluruh (72 kombinasi, kriteria sample minimum, dibanding
baseline scr adil). Filter `min_atr_over_spread` (v18) yang otomatis skip entry di kondisi ini
berperilaku **benar**, bukan terlalu ketat. TIDAK ADA strategi baru ditambahkan ke `usecase.py`
dari v19 — hasil negatif ini sendiri berharga, mencegah pemaksaan strategi yang terlihat
"jalan" di TRAIN tapi sebenarnya cuma kebetulan (echo pelajaran v15/DSR). Kalau ada motivasi
kuat trading di rezim rendah di masa depan, jalur yang lebih masuk akal bukan re-tuning
parameter existing (sudah dicoba, gagal), tapi eksplorasi **logika sinyal berbeda scr
fundamental** (mis. mean-reversion/range-trading) — riset terpisah & lebih besar, di luar
cakupan v19. Hasil lengkap tersimpan sbg field `low_volatility_regime_analysis` di
`models/m5_scalping/v13/params.json`.

**Keterbatasan v19:** (a) grid search 72 kombinasi terarah scr teori, bukan full cartesian
exhaustive; (b) filter H1 trend alignment TIDAK diterapkan (cache data v19 tidak punya kolom H1
EMA) — biasanya mengurangi trade & menaikkan kualitas, tapi gap dari PF 0.91 ke 1.5 cukup jauh
shg kecil kemungkinan sendirian menutup gap; (c) exhaustion-mode (momentum chain 8/8) v13 belum
diuji eksplisit di rezim rendah.
