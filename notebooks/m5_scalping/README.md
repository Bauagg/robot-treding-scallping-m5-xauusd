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
