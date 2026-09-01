# robot-scalping

Robot trading otomatis untuk **XAUUSD (gold) di timeframe M5**: MetaTrader5 sebagai eksekusi order,
FastAPI sebagai API layer + scheduler polling, Pandas untuk data processing, Jupyter untuk
riset/backtest strategi, dan bot Telegram untuk laporan + kontrol kill-switch drawdown dari jarak jauh.

## Struktur folder

Arsitektur **feature-based (vertical slice)**: setiap fitur punya folder sendiri di `app/features/<nama_fitur>/`
yang isinya lengkap — schema, repository, usecase, controller. Tidak dipisah per-layer horizontal,
supaya tiap fitur mudah ditelusuri dan gak saling menyebar ke banyak folder.

```
app/
  main.py                    # entry point FastAPI + scheduler polling live trading + bot Telegram
  api.py                     # agregasi semua controller/router per-fitur
  core/                      # config (.env), logging — shared infra
  features/
    health/                  # GET /health
    mt5_connection/          # connect/disconnect MT5, GET /mt5/status (fail-fast di startup)
    m5_scalping/             # strategi live: generate sinyal, order otomatis, catat hasil
      schema.py               # TradeLogEntry, SignalCheckResult, DrawdownState
      repository.py           # baca/tulis dataset/live/m5_scalping/trade_log_v13.csv + drawdown_state.json
      usecase.py               # fetch candle -> indikator -> guard -> generate_signal_v12 -> order -> log
      controller.py           # scheduler polling background (bukan HTTP endpoint)
    bot_telegram/             # laporan trading + alert & override kill-switch drawdown via Telegram
      schema.py               # ReportPeriod, TradeSummary, DrawdownAlertEvent
      repository.py           # kirim pesan Telegram + baca trade_log_v13.csv (punya m5_scalping)
      usecase.py               # susun laporan, evaluasi kondisi market, proses override kill-switch
      controller.py           # lifecycle bot (polling) + scheduler laporan terjadwal + cek drawdown
  utils/
    indicators/               # 24 modul indikator teknikal (RSI, MACD, EMA, SMC, dll) + add_all_indicators
    signals/                  # scoring & decision engine (generate_signal / generate_signal_v12) dipakai backtest & live
dataset/
  raw/                       # data mentah candle historis (CSV per simbol/timeframe/tahun)
  processed/<strategi>/vXX/  # hasil olahan tiap versi riset (indikator, trade log lengkap)
  exports/<strategi>/vXX/    # ringkasan tiap versi (metrics.txt, grafik, grid search)
  live/<strategi>/           # trade_log_v13.csv + drawdown_state.json hasil trading SUNGGUHAN (bukan backtest)
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
   dan simbol/lot (`XAUUSD_SYMBOL`, `XAUUSD_LOT_SIZE`). Lihat juga bagian
   [Kill-switch drawdown](#kill-switch-drawdown) untuk `MAX_*_DRAWDOWN_PCT`, dan
   [Bot Telegram](#bot-telegram) untuk kredensial `TELEGRAM_*` (opsional — kalau kosong, bot
   Telegram otomatis tidak dijalankan, trading tetap jalan normal).

   **Penting — cek jam sistem laptop yang menjalankan robot** (`Get-Date` di PowerShell, bandingkan
   dgn UTC asli): pernah ditemukan drift ~3 jam yang bikin `entry_time`/guard weekend salah hitung
   (lihat [Catatan bug & fix penting](#catatan-bug--fix-penting)). Sinkronkan lewat Settings > Time
   & Language > sync now sebelum menjalankan live.

4. **Jalankan robot (live trading otomatis + bot Telegram)**

   ```powershell
   uvicorn app.main:app --host 0.0.0.0 --port 8080 --reload
   ```

   Begitu start: connect ke MT5 (**fail-fast** — kalau gagal connect, server tidak jalan sama sekali),
   lalu scheduler polling **tiap 60 detik** otomatis di background (`app/features/m5_scalping/controller.py`):
   tiap tick, sinkronkan trade OPEN→CLOSED dari histori MT5 dulu, lalu cek sinyal terbaru lewat
   serangkaian guard (lihat [Alur keputusan live](#alur-keputusan-live-tiap-polling)) — order otomatis
   ke MT5 kalau semua guard lolos, catat hasil ke `dataset/live/m5_scalping/trade_log_v13.csv`.

   Setelah trading polling jalan, bot Telegram ikut start (polling `getUpdates`, bukan webhook) — kirim
   laporan terjadwal & respon command (lihat [Bot Telegram](#bot-telegram)). Trading tidak pernah gagal
   start gara-gara Telegram bermasalah (token salah, network down) karena urutan startup-nya trading
   duluan, Telegram belakangan.

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

**v13** (`app.utils.signals.generate_signal_v12` + filter Order Block v10-SKIP + penanganan momentum
exhaustion) — parameter di `models/m5_scalping/v13/params.json`:

- **Scoring de-redundant (v12)**: skor 20 kategori indikator, tapi cluster yang berkorelasi tinggi
  (oscillator RSI/Stoch/Williams %R/CCI/BB/VWAP, dan trend-follower SMA/Ichimoku/Supertrend) digabung
  jadi 1 skor komposit median per cluster dulu, baru dijumlah dengan kategori independen lainnya — biar
  skor tinggi gak "palsu" cuma karena banyak oscillator kebetulan align bersamaan.
  `MIN_SIGNAL_SCORE=9.0`, filter H1 trend alignment aktif, ADX≥18, ATR≥0.03%.
- SL/TP **ATR-relatif**: SL=2.0×ATR, TP=4.0×ATR (max hold 12 candle M5). Kalau momentum chain
  (`bull_chain`/`bear_chain`) sudah mentok 8/8 (exhaustion — momentum "matang", rawan melambat/retrace),
  entry di-**skip total** — **bukan** entry dengan SL/TP diperkecil (cara lama sampai 2026-09-01) dan
  **bukan** membalik arah sinyal (opsi reverse terbukti gagal validasi, win rate cuma 18-24%). Diganti
  ke skip setelah investigasi loss beruntun live (1 Sept 2026) menemukan 5 dari 6 SELL beruntun terjadi
  persis saat chain sudah 7-8/8 — SL/TP yang diperkecil terbukti tidak cukup melindungi dari retrace
  saat tren sedang exhaustion (win rate trade exhausted cuma 47%, avg profit mendekati nol). Lihat
  `notebooks/m5_scalping/v31_post_tp_chasing.ipynb` & `momentum_exhaustion_skip_analysis` di
  `models/m5_scalping/v13/params.json`.
- **Skip entry** kalau ada Order Block (SMC) M5/H1 yang melawan arah sinyal (`has_opposing_order_block`
  di `usecase.py`) — filter ini **wajib tetap aktif**, lihat penjelasan di bawah.

Hasil backtest v13 di periode TEST out-of-sample (2026-03 s/d 2026-08, 196 trade, parameter TIDAK
di-tuning ulang di rentang ini): win rate **75.0%**, profit factor **3.57**, ~2.2 trade/hari, avg
$13.25/hari dari **modal simulasi $100**. Di periode penuh 2025-2026 (721 trade, termasuk data TRAIN):
win rate 70.6%, profit factor 3.66. Uji ketahanan lintas rezim harga 2019-2026 (3056 trade, XAUUSD
$1300→$4500+) menunjukkan win rate naik dari 52.6% (2019) ke 74.0% (2026) — strategi robust di berbagai
rezim harga, sedikit lebih kuat di kondisi harga terkini. Detail riset di
`notebooks/m5_scalping/v12_deredundant_scoring.ipynb` dan `v13_momentum_exhaustion.ipynb`.

> **Penting — semua angka backtest (v01-v13) di riset ini simulasi dari modal $100** (`INITIAL_EQUITY
> = 100.0` di tiap notebook), **bukan** saldo akun live yang sesungguhnya (yang naik seiring waktu
> trading — cek `dataset/live/m5_scalping/trade_log_v13.csv` atau `mt5.account_info().balance` untuk
> saldo real). Dipakai konsisten $100 di semua versi supaya hasil antar-notebook bisa dibandingkan
> apple-to-apple. Jangan proyeksikan linear ke modal live yang lebih besar — posisi sizing backtest
> pakai compounding %-risk (`RISK_PCT=0.01` dari equity, lot dihitung ulang tiap trade), sedangkan
> live pakai **fixed lot** dari `.env` (`XAUUSD_LOT_SIZE`), jadi karakter risk/reward-nya beda. Uji
> stress 2019-2026 malah net_pnl-nya TIDAK realistis (meledak jutaan dolar akibat compounding di
> rentang 7.6 tahun) — cuma win_rate per tahun yang valid dibaca dari situ. Detail lebih lengkap di
> `models/README.md`.

### Indikator yang benar-benar dipakai untuk sinyal

`app/utils/indicators/` punya puluhan indikator, tapi `trade_log_v13.csv` mencatat SEMUANYA sbg
snapshot (buat evaluasi/riset), bukan berarti semuanya menentukan keputusan trading. Yang benar-benar
dipakai `generate_signal_v12()` (`app/utils/signals/`) cuma yang di bawah ini:

**20 kategori skor** (cluster berkorelasi tinggi digabung jadi skor komposit median dulu — lihat
`app/utils/signals/scoring_v12.py` — baru dijumlah semua kategori jadi `final_score`; BUY kalau
`final_score >= MIN_SIGNAL_SCORE`, SELL kalau `<= -MIN_SIGNAL_SCORE`, `WAIT` kalau di antaranya):

| Kategori | Indikator | Cara gabung |
|---|---|---|
| Cluster oscillator | RSI, Stochastic, Williams %R, CCI, Bollinger Bands, VWAP | median 1 skor komposit |
| Cluster trend-follower | SMA (50/200), Ichimoku, Supertrend | median 1 skor komposit |
| Momentum (independen) | MACD, MFI | skor sendiri-sendiri |
| Trend (independen) | ADX+DI, PSAR | skor sendiri-sendiri |
| Volume | OBV | skor sendiri |
| Struktur candle | Candle pattern (single), extra pattern (Three White Soldiers, Morning/Evening Star, dst) | skor sendiri |
| Reversal/divergence | RSI divergence (regular + hidden), momentum chain | skor sendiri |
| Posisi harga | Fibonacci retracement | skor sendiri |
| Smart Money Concept (SMC) | FVG, Order Block, BOS, ChoCH, Liquidity sweep (digabung 1 skor `score_smc`) | skor sendiri |

**Filter keras** (bukan skor, wajib lolos semua atau langsung `WAIT` — lihat `_check_hard_filters`
dan `_check_htf_alignment` di `app/utils/signals/decision.py`):
- **ADX minimum** (`ADX_MIN=18.0`) — pastikan market memang trending, bukan sideways
- **ATR minimum %** (`ATR_MIN_PCT=0.03`) — hindari market terlalu sepi/spread-eating
- **H1 trend alignment** — arah sinyal M5 harus searah trend H1 (EMA50 vs EMA200 H1), kalau
  melawan langsung `WAIT`

**Dipakai di luar sinyal** (TP/SL & filter tambahan, bukan bagian `generate_signal_v12()`):
- **ATR (M5)** — dasar hitung SL/TP ATR-relatif (SL=2.0×ATR, TP=4.0×ATR)
- **Order Block M5 & H1** — pengecekan TERPISAH dari skor SMC di atas: kalau ada Order Block yang
  melawan arah sinyal, entry di-skip sama sekali (`has_opposing_order_block` di `usecase.py`)
- **Support/Resistance H1 & M15** — pengecekan TERPISAH lagi: kalau harga dekat level S/R
  (swing pivot) berlawanan arah sinyal, entry di-skip KECUALI skor sangat kuat atau ATR sudah
  "bertenaga" (indikasi breakout beneran) — lihat `check_sr_proximity` di `usecase.py` &
  [Filter Support/Resistance](#filter-supportresistance-h1--m15) di bawah
- **Momentum chain** (`bull_chain`/`bear_chain`) — kalau sudah mentok 8/8 (exhaustion), entry
  di-skip total (bukan lagi SL/TP diperkecil sejak 2026-09-01) — lihat riwayat versi di bawah

Indikator lain (Ichimoku cloud detail, semua kolom `h1_*` selain EMA50/200, dst) tercatat di
`trade_log_v13.csv` murni untuk bahan evaluasi/riset lanjutan — tidak mempengaruhi keputusan BUY/SELL/WAIT.

### Riwayat versi strategi (kenapa v13 yang aktif sekarang)

- **v04 → v06**: v04 (TP=12pt/SL=6pt fixed) dituning di harga XAUUSD ~$2600-2789 (2025). Live demo test
  7 Agustus 2026 (harga ~$4300+) hasilnya 67 LOSS/2 WIN dari 69 trade — SL fixed cuma ~0.6-1.5x ATR di
  rezim harga tinggi, gampang kena stop duluan. v06 ganti SL/TP fixed poin dengan kelipatan ATR.
- **v06 → v10-SKIP**: analisis trade log v06 menemukan 57.8% dari semua LOSS terjadi saat ada Order
  Block (SMC) M5/H1 melawan arah sinyal. Dua alternatif "balik arah" (reverse penuh & small-reverse)
  gagal validasi out-of-sample (overfitting) — **SKIP** terbukti satu-satunya opsi yang konsisten robust.
- **v10-SKIP → v12**: breakdown skor v06 menemukan skor tinggi krn SMC win rate 55.7%, tapi skor tinggi
  krn breadth/oscillator doang cuma win rate 41.4% — indikasi redundansi antar-oscillator bikin skor
  "palsu" tinggi. v12 gabung cluster berkorelasi tinggi (0.65-0.94) jadi skor komposit median, threshold
  optimal tetap 9.0 (dipilih via `profit_factor`, bukan `final_equity` yang bias ke volume trade).
- **v12 → v13**: analisis lanjutan nemuin momentum chain exhaustion (chain 8/8) → win rate anjlok ke
  52.1% (vs 76.7% di chain 7/8) kalau diperlakukan sama seperti chain normal. REVERSE gagal (win rate
  18-24%), SMALL-PROFIT (SL/TP diperkecil, tetap searah sinyal) yang jadi pilihan awal.
- **SMALL-PROFIT → SKIP (2026-09-01)**: investigasi loss beruntun live HFM (1 Sept 2026, 5 dari 6 SELL
  beruntun) menemukan pola konsisten — semuanya terjadi persis saat `bear_chain` sudah 7-8/8, BUKAN soal
  H1 sideways (H1 ADX 31-43, trending kuat) maupun S/R proximity (jarak 3-11x ATR, di luar radius
  filter). SL/TP yang diperkecil (SMALL-PROFIT) terbukti tidak cukup melindungi dari retrace saat tren
  exhaustion — validasi ulang (TRAIN/TEST walk-forward + full-period 2019-2026 + Monte Carlo + DSR)
  menunjukkan **SKIP total lebih baik di semua metrik**: PF TEST 1.68→1.88, net_pnl $4294.87→$4462.92,
  max_dd -18.91%→-15.27%, DSR=1.0000 (signifikan, N_TRIALS=2 krn keputusan biner bukan grid search
  besar). Detail di `notebooks/m5_scalping/v31_post_tp_chasing.ipynb` &
  `momentum_exhaustion_skip_analysis` di `models/m5_scalping/v13/params.json`.
- **v13 + v14 (analisis risiko, bukan versi strategi baru)**: v14 tidak mengubah sinyal/TP/SL v13
  sama sekali — cuma menguji seberapa dalam drawdown BISA terjadi lewat simulasi Monte Carlo (lihat
  [Risiko urutan (sequence risk)](#risiko-urutan-sequence-risk--analisis-monte-carlo) di atas).
- **v13 + v15 (audit statistik, bukan versi strategi baru)**: dari 10 versi yang dicoba (v02-v13),
  apakah v13 "menang" karena beneran bagus atau kebetulan cocok data historis? Dihitung Deflated
  Sharpe Ratio (Bailey & López de Prado 2014) — sempat menemukan v05 (ML, sudah ditolak dulu krn
  SELL-only bias) justru Sharpe/DSR tertinggi, terbukti MENYESATKAN (cacat model, bukan skill).
  Setelah v05 dikeluarkan dari kandidat valid, v13 Sharpe tertinggi di antara 9 versi dengan
  **DSR=1.00 (signifikan secara statistik, bukan cherry-picking)**. Detail di
  `notebooks/m5_scalping/v15_deflated_sharpe.ipynb`.
- **v13 + v16 (regime labeling, bukan versi strategi baru)**: apakah performa v13 konsisten di
  semua kondisi market, atau rata-rata agregat menyembunyikan regime yang rugi (analogi: rata-rata
  suhu 37°C bisa menyembunyikan separuh demam & separuh hipotermia)? Regime dipecah berdasar ADX
  (Trending/Ranging) x ATR% (High/Low Vol), diuji di 3 dataset — **TIDAK ADA regime yang rugi**,
  regime terlemah (Ranging/Low Vol) tetap win rate 57.7%/PF 1.95. High Vol konsisten unggul dari
  Low Vol; pola ADX ternyata non-monoton (ADX menengah-rendah justru terlemah, bukan ADX terendah)
  — mengonfirmasi filter `adx_min=18` saat ini sudah tepat, tidak perlu dinaikkan. Detail di
  `notebooks/m5_scalping/v16_regime_labeling.ipynb`.
- **v13 + v18 (realisme spread, bukan versi strategi baru)**: `SPREAD_POINTS=0.30` dipakai di
  SEMUA backtest sejak v02 ternyata tidak realistis — broker real user (**MIFX**, MT5) spread
  `XAUUSD.m`=**1.82** (6x lebih besar). Dengan spread real, strategi full period 2019-2026 jadi
  **rugi scr keseluruhan** (profit factor 3.58→0.82) karena SL/TP relatif-ATR "dimakan" spread
  saat ATR kecil (rezim volatilitas rendah). Filter adaptif `min_atr_over_spread>=3.0`
  memperbaiki metrik TEST, tapi perbandingan jujur (sama-sama spread real) menunjukkan trade-off
  nyata (Sharpe & total profit sedikit lebih rendah dengan filter) dan filter itu menghapus
  hampir seluruh era 2019-2024. Detail di `notebooks/m5_scalping/v18_spread_adaptive.ipynb`.
- **v13 + v19 (strategi rezim volatilitas rendah — hasil NEGATIF)**: lanjutan v18, mencari
  strategi terpisah yang genuinely cocok untuk rezim 2019-2024. Grid search 72 kombinasi
  parameter (mesin scoring v12, spread real 1.82) di TRAIN 2019-2023 — **tidak satu pun mencapai
  profit factor > 1.0** (terbaik PF=0.91, 436 trade, masih rugi). Kesimpulan jujur: rezim
  volatilitas rendah memang tidak menawarkan edge yang bisa ditemukan lewat re-tuning mesin
  scoring v12 — akar masalahnya struktural (ATR terlalu kecil vs spread broker), bukan salah
  pilih parameter. Robot sebaiknya tidak trading sama sekali kalau rezim ini terulang. Detail di
  `notebooks/m5_scalping/v19_low_volatility_regime.ipynb`.

> **Lima isu "pematangan v13" (Monte Carlo/v14, Deflated Sharpe Ratio/v15, Regime Labeling/v16,
> Spread Realism/v18, Strategi Rezim Rendah/v19) sudah selesai diriset** — v14-v17 memperkuat
> kepercayaan pada v13 tanpa mengubah `trade_params`/`signal_params`-nya; v18-v19 mengungkap
> keterbatasan nyata (strategi rugi dengan spread broker real di rezim volatilitas rendah) yang
> **belum ada solusinya** — robot saat ini tetap pakai parameter v13 asli di semua kondisi,
> dengan kesadaran eksplisit bahwa rezim volatilitas rendah adalah celah terbuka. Satu-satunya
> perubahan konkret ke kode/config dari seluruh riset ini: `MAX_DAILY_DRAWDOWN_PCT` direvisi
> 20%→40% di `.env` (dari temuan v14).

Model ML (v05, Random Forest) sempat dicoba tapi ternyata jadi SELL-only akibat *distribution shift*
ke rezim harga 2025-2026 — belum dipakai live, masih tersimpan sbg riset di `models/m5_scalping/v05/`.
Entry breakout/pending order (v07) dan trailing stop (v11) juga sempat dicoba tapi **ditolak** (terbukti
lebih buruk dari baseline di backtest). Detail lengkap tiap versi & angka di `notebooks/m5_scalping/README.md`.

### Kenapa spread mengalahkan strategi di rezim volatilitas rendah (penjelasan intuitif v18/v19)

Bagian ini menjelaskan **kenapa** temuan v18/v19 terjadi secara konsep, bukan cuma angka — supaya
kalau ada yang baca README ini nanti (termasuk diri sendiri beberapa bulan ke depan) tidak perlu
buka ulang notebook buat inget alasannya.

**Volatilitas ≠ arah harga.** Harga naik/turun itu soal *arah* (lebih banyak orang beli vs jual).
Volatilitas itu soal *seberapa liar/cepat* harga bergerak, terlepas dari arahnya — diukur pakai
**ATR (Average True Range)**, rata-rata seberapa jauh harga bergerak per candle. Harga bisa saja
naik terus tapi PELAN (volatilitas rendah, spt 2019-2024 — net naik $1300→$2400 tapi ATR% kecil),
atau naik CEPAT & liar (volatilitas tinggi, spt 2025-2026 — ATR% jauh lebih besar). Konsolidasi
(harga "diem" sideways) adalah kasus ekstrem volatilitas rendah, tapi volatilitas rendah tidak
harus berarti harga diem — bisa juga naik/turun stabil tanpa lonjakan liar.

**Apa yang mempengaruhi keliaran candle (ATR) di market real**: volume transaksi (makin banyak
buyer/seller aktif bersamaan, makin liar), berita/katalis besar (keputusan suku bunga The Fed,
data inflasi CPI, ketegangan geopolitik, data tenaga kerja AS — semua ini memicu lonjakan volume
mendadak), sesi trading (jam overlap London/New York lebih ramai dari sesi Asia), dan fase
psikologis pasar (setelah rally besar biasanya ada fase "istirahat" — yang sudah profit ambil
untung, yang baru ragu ikut karena harga sudah tinggi, transaksi mengecil sambil nunggu katalis
besar berikutnya — inilah kondisi yang persis terjadi di gold pasca all-time high $5,602 akhir
Januari 2026, sebelum historic reversal yang terjadi setelahnya). Robot tidak perlu membaca berita
ini secara langsung — efeknya sudah otomatis tercermin di ATR, karena ATR itu ujungnya cerminan
dari volume & kepastian arah pasar.

**Kenapa itu jadi masalah buat strategi v13**: SL/TP dihitung sbg kelipatan ATR (`SL=2×ATR`,
`TP=4×ATR`) — waktu ATR kecil (kondisi kalem), SL/TP dalam dolar absolut juga ikut menyempit.
Masalahnya, **spread broker (MIFX, 1.82 poin) itu KONSTAN, tidak ikut mengecil** cuma karena
market lagi kalem. Bandingkan:

- **2019** (ATR%=0.06%, harga~$1391): ATR≈$0.83 dolar. SL=2×ATR≈$1.66, TP=4×ATR≈$3.32. Spread
  $1.82 sendirian sudah **lebih besar dari SL**, dan memakan >50% dari target TP sebelum harga
  sempat bergerak sama sekali — margin untung nyaris tidak ada ruang.
- **2026** (ATR%=0.15%, harga~$4586): ATR≈$6.88 dolar. SL=2×ATR≈$13.76, TP=4×ATR≈$27.52. Spread
  $1.82 cuma ~6.6% dari target TP — porsi kecil, sisa margin untung jauh lebih lega.

Analoginya: kalau untung yang dikejar cuma $3 tapi ongkos kirim tetap $1.82, bisnisnya nyaris
tidak masuk akal — ongkos "memakan" nyaris semua margin. Kalau untung yang dikejar $27, ongkos
$1.82 itu jadi tidak berarti apa-apa. **Ini sebabnya v18 menemukan strategi jadi RUGI scr
keseluruhan dgn spread real (PF 0.82) begitu banyak sinyal terjadi di kondisi ATR kecil, dan
kenapa v19 gagal menemukan kombinasi parameter apa pun (dari 72 dicoba) yang bisa mengalahkan
biaya spread tetap itu scr konsisten di rezim 2019-2024** — bukan soal salah pilih parameter,
tapi batas matematis: pergerakan harga (dalam dolar) di rezim itu memang terlalu kecil dibanding
ongkos transaksi tetap broker, terlepas separapa canggih SL/TP diatur.

**Catatan konteks pasar terkini (Agustus 2026, belum divalidasi via data internal, sumber berita
eksternal)**: gold baru saja mencatat all-time high $5,602 (29 Januari 2026) setelah rally 40
bulan dari $1,619, lalu mengalami *historic reversal* — kerugian harian terbesar dalam sejarah
tercatat setelahnya. Pola historis gold menunjukkan fase konsolidasi/volatilitas rendah sering
terjadi SETELAH rally besar (bukan cuma di awal siklus harga rendah spt 2019). Kalau pola ini
berulang, kondisi "ATR mengecil di harga tinggi" bisa muncul dalam skenario yang BELUM pernah ada
di data historis manapun (2019-2026 seluruhnya net naik terus, tidak ada periode koreksi besar
tercatat) — celah ini juga sudah dicatat sbg keterbatasan eksplisit di v17.

**Arah riset ke depan (belum dikerjakan, dicatat sbg backlog)**:
1. **Monitoring dini berbasis ATR**: robot saat ini TIDAK punya kill-switch berbasis volatilitas
   (cuma berbasis drawdown equity) — kalau ATR M5 mulai mengecil signifikan dari baseline
   sekarang, itu sinyal awal utk waspada, tapi belum ada mekanisme otomatis yang memantau/alert
   ini. Kandidat: tambah metrik ATR rolling ke laporan bot Telegram (lihat [Bot
   Telegram](#bot-telegram)), supaya kelihatan dari laporan harian/mingguan tanpa perlu cek manual.
2. **Eksplorasi logika sinyal fundamental berbeda utk rezim rendah** (dari rekomendasi v19): v19
   cuma re-tuning mesin scoring v12 (trend-following) yang memang didesain utk rezim volatilitas
   tinggi — belum pernah dicoba logika BERBEDA scr fundamental spt mean-reversion/range-trading,
   yang secara teori lebih cocok utk kondisi harga sempit/sideways drpd trend-following. Riset
   terpisah & lebih besar, di luar cakupan v18/v19.
3. **Validasi ulang kalau harga XAUUSD suatu saat turun tajam dari level sekarang** ($4300+): itu
   skenario yang belum ada presedennya di data historis manapun. Kalau terjadi, v13 & filter
   v18/v19 perlu dievaluasi ulang scr eksplisit thd kondisi itu spesifik (bukan diasumsikan sama
   dgn pola 2019-2024, krn "turun dari tinggi" & "naik dari rendah" bisa punya karakteristik
   price action berbeda meski ATR-nya sama-sama kecil).

### Filter Support/Resistance (H1 & M15)

**Latar belakang**: pengamatan langsung dari chart live & trade log (Agustus 2026) menemukan
pola: robot entry BUY/SELL persis di dekat level S/R (swing high/low) berlawanan arah, lalu
harga mantul balik & kena SL — sinyal "benar" secara skor/trend, tapi timing entry buruk krn
mengabaikan bahwa harga sedang di zona rawan reversal.

**Deteksi level S/R**: `app/utils/indicators/support_resistance.py` — `add_swing_pivots()`
mendeteksi pivot high/low SEJATI (butuh konfirmasi candle SEBELUM & SESUDAH lebih rendah/tinggi,
beda dari rolling max/min biasa yang cuma lihat ke belakang), lalu `build_sr_levels()` ambil
level pivot TERDEKAT (dari 5 pivot terakhir yang sudah confirmed) di atas/bawah harga saat ini.
Dihitung dari H1 & M15 (bukan M5) supaya level yang dipakai signifikan, bukan noise —
`build_signal_row()` fetch candle M15 tambahan & merge kolom `m15_sr_resistance`/
`m15_sr_support` + `h1_sr_resistance`/`h1_sr_support` ke row sinyal, pola sama persis dgn
merge H1 EMA yang sudah ada (no-lookahead, divalidasi: level di candle manapun IDENTIK baik
dihitung dari data penuh maupun data yang dipotong setelah candle itu).

**Keputusan bertingkat** (`check_sr_proximity()` di `usecase.py`) — BUKAN skip biner semua yang
dekat S/R:
- Level S/R berlawanan arah (BUY vs resistance di atas, SELL vs support di bawah) diambil yang
  **paling ketat** dari H1 & M15 (`sr_source="both"`)
- "Dekat" = jarak ke level itu ≤ `near_atr_mult × ATR` (**3.0×ATR**, ATR-relatif bukan poin
  fixed — pelajaran dari kegagalan SL fixed v04)
- Kalau dekat, entry TETAP boleh jalan kalau salah satu syarat ini terpenuhi:
  - **Skor sangat kuat**: `|skor| >= MIN_SIGNAL_SCORE + strong_score_bonus` (**+4.0**, jadi ≥13.0)
  - **ATR sudah "bertenaga"**: `ATR >= min_atr_for_breakout` (**2.1**) — indikasi candle
    breakout beneran, bukan cuma menyentuh level pelan-pelan
- Kalau tidak ada satupun syarat itu terpenuhi → **skip** (bukan SL/TP dipangkas — lihat catatan
  di bawah kenapa "adjust" ditolak)

**Kenapa "SL/TP dipangkas" ditolak, "skip" yang dipilih**: investigasi mendalam (Max Favorable
Excursion — seberapa jauh harga sempat bergerak ke arah untung sebelum berbalik) menemukan
91.7% dari trade yang "mantul" (rugi) dekat S/R itu **harganya salah arah SEJAK AWAL** (77%
bahkan langsung mundur tanpa sempat maju sedikit pun) — TP dipangkas sekecil apapun TIDAK akan
menyelamatkan mayoritas kasus ini, krn masalahnya bukan "target kejauhan" tapi "seharusnya
tidak entry sama sekali di titik itu".

**Kenapa syarat ATR (bukan cuma jarak/skor)**: dari 733 trade v13 (data TRAIN 2019-2023) yang
entry dekat S/R H1 (≤2.0×ATR), 83.5% mantul (rugi) vs 16.5% tembus (untung) — S/R memang zona
berbahaya. Tapi uji statistik (Mann-Whitney U) atas 4 faktor pembeda (jarak S/R H1, jarak S/R
M15, kekuatan skor, ATR) menemukan **cuma ATR yang signifikan** (p=0.0000) — trade yang tembus
py ATR rata-rata jauh lebih tinggi (1.880) drpd yang mantul (1.149), sementara jarak & skor
TIDAK signifikan (p>0.5). Jadi filter yang lebih efektif bukan "makin dekat makin ketat", tapi
"kalau candle-nya bertenaga (ATR tinggi), izinkan meski dekat S/R".

**Validasi menyeluruh** (`notebooks/m5_scalping/v28_support_resistance_proximity.ipynb`, TRAIN
2019-2023/TEST 2024-2026 walk-forward, grid search 198 kombinasi, Monte Carlo, breakdown per
tahun): full-period 2019-2026 (fixed lot 0.03, modal $2000, tanpa kill-switch — basis drawdown
mentah) v13 murni PF=**0.87** (net **rugi** -$2434.69) vs v13+filter S/R PF=**1.25** (net
**untung** +$2967.73), win rate 25.5%→35.6%, max drawdown -386.97%→-116.84% (**3.3x lebih
ringan**), losing streak terpanjang **166→57 trade berturut-turut**, unggul di **6 dari 8
tahun** (2019-2026, robust lintas rezim bukan cuma menang di 1-2 tahun kebetulan).

> **Catatan kehati-hatian jujur**: Deflated Sharpe Ratio (basis TEST period, N_TRIALS=198
> kombinasi grid search yang dicoba) = **0.0000** — secara statistik ketat, belum bisa
> dipastikan kemenangan filter ini murni skill, bukan kebetulan cocok dari banyaknya kombinasi
> yang dicoba. Diterapkan ke live atas keputusan eksplisit user (2026-09-01) meski DSR rendah —
> **monitor performa live secara berkala** utk konfirmasi independen dari data live
> sesungguhnya, bukan cuma mengandalkan backtest historis.

Params tersimpan di `models/m5_scalping/v13/params.json` field `sr_proximity_filter`
(`enabled`, `min_signal_score_base`, `near_atr_mult`, `strong_score_bonus`,
`min_atr_for_breakout`) — filter tambahan di atas v13 yang sudah ada, BUKAN strategi/versi
terpisah (v13 tetap basisnya, cuma ditambah guard baru).

### Alur keputusan live (tiap polling)

`check_signal_and_trade()` di `app/features/m5_scalping/usecase.py` mengecek guard berikut secara
berurutan sebelum order dikirim — begitu satu guard gagal, langsung `WAIT` tanpa lanjut ke guard
berikutnya:

1. **Kill-switch drawdown** (`_check_drawdown_guard`) — equity sekarang vs peak/baseline
   harian/bulanan, dengan kemungkinan di-override manual lewat bot Telegram. Lihat
   [Kill-switch drawdown](#kill-switch-drawdown) di bawah.
2. **Weekend close window** (`_is_weekend_close_window`) — gak boleh buka posisi baru menjelang
   tutup market Jumat (lihat [Weekend close window](#weekend-close-window)). Posisi yang sudah OPEN
   dibiarkan jalan, cuma entry baru yang diblok.
3. **Posisi masih terbuka** (`list_open_tickets()`) — cuma boleh 1 posisi OPEN pada satu waktu.
4. **Skor sinyal** (`generate_signal_v12`) — harus lolos `MIN_SIGNAL_SCORE`, ADX, ATR%, H1 alignment.
5. **Order Block lawan arah** (`has_opposing_order_block`) — skip kalau ada OB M5/H1 melawan arah
   sinyal.
6. **Support/Resistance H1/M15** (`check_sr_proximity`) — skip kalau harga dekat level S/R
   berlawanan arah sinyal, kecuali skor sangat kuat atau ATR sudah "bertenaga" (indikasi
   breakout). Lihat [Filter Support/Resistance](#filter-supportresistance-h1--m15) di bawah.
7. **Momentum chain exhaustion** — skip total kalau `bull_chain`/`bear_chain` (dominan sesuai
   arah sinyal) sudah mentok `exhaustion_chain_threshold` (8/8). Sejak 2026-09-01 (sebelumnya
   entry tetap jalan dengan SL/TP diperkecil) — lihat riwayat versi di atas &
   `momentum_exhaustion_skip_analysis` di `models/m5_scalping/v13/params.json`.

Baru setelah semua lolos, SL/TP dihitung (SL=2.0×ATR, TP=4.0×ATR), order dikirim ke MT5, dan
dicatat ke `trade_log_v13.csv`.

### Kill-switch drawdown

Robot otomatis pause (skip entry baru) kalau equity turun dari baseline melebihi threshold di
`.env` (`MAX_DAILY_DRAWDOWN_PCT`, `MAX_MONTHLY_DRAWDOWN_PCT`, `MAX_TOTAL_DRAWDOWN_PCT`):

- **Daily/monthly**: reset otomatis begitu tanggal/bulan kalender (UTC) berganti — **tidak perlu
  campur tangan apapun**, robot otomatis boleh entry lagi di hari/bulan berikutnya. Bisa juga
  di-override manual lebih cepat lewat bot Telegram (lihat [Bot Telegram](#bot-telegram)) kalau kamu
  yakin kondisi market sudah kondusif sebelum reset otomatis terjadi.
- **Total**: dihitung dari peak equity tertinggi yang pernah tercatat, pause **PERMANEN** begitu
  ke-trigger sampai direset manual (hapus `dataset/live/m5_scalping/drawdown_state.json` —
  **JANGAN** hapus `trade_log_v13.csv`, itu file histori trade yang beda & tidak terkait). Total
  drawdown **tidak pernah** bisa di-override lewat Telegram atau command apapun — sengaja permanen
  karena breach ini dianggap sinyal akun rusak, bukan sekadar bad day/bulan.

Default (`.env.example`): **daily=40%, monthly=25%, total=40%** — nilai awal (20/25/40) divalidasi
via backtest (`notebooks/m5_scalping/v09_drawdown_killswitch.ipynb`): max drawdown historis strategi
v06 adalah -28.4%, jadi threshold yang lebih ketat (mis. 5/10/15% yang dicoba pertama kali) membuat
robot mati permanen di awal (trade ke-102 dari 1664, baru 6% perjalanan). 20/25/40% tervalidasi
tidak pernah ke-trigger di SATU urutan kronologis backtest historis — tapi v09 gak cek skenario
urutan lain yang mungkin terjadi.

`MAX_DAILY_DRAWDOWN_PCT` direvisi **20% → 40%** setelah analisis Monte Carlo (lihat
[Risiko urutan (sequence risk)](#risiko-urutan-sequence-risk--analisis-monte-carlo)) menemukan 20%
pada modal $100 + lot fixed 0.01 nyaris SELALU breach (100% dari 10.000 simulasi) — bukan karena
akumulasi kerugian harian seperti tujuannya, tapi karena satu trade tunggal (SL normal, bukan bug)
bisa mencapai ~37% dari modal $100 sendirian. 40% mengembalikan kill-switch daily jadi pengaman
akumulasi yang proporsional, bukan trigger tiap kali ada 1 trade rugi wajar. `monthly=25%` dan
`total=40%` tetap divalidasi proporsional, tidak direvisi.

### Weekend close window

Robot berhenti membuka posisi baru mulai **Jumat UTC 15:00 (WIB 22:00)** sampai market buka lagi
Minggu malam — posisi yang sudah terbuka sebelum jam ini dibiarkan berjalan sampai SL/TP-nya
sendiri, cuma entry baru yang diblokir. Alasan: histori live menunjukkan volatilitas/candle tidak
beraturan menjelang tutup weekend (banyak trader lain closing/ambil profit serentak). Titik UTC
15:00 dipilih berdasarkan data (bukan tebakan) — backtest v06 menunjukkan jam 13:00-14:59 UTC Jumat
justru net_pnl **positif** ($160.66 dari 112 trade), sementara UTC 15:00 adalah titik pertama di
mana trade yang ke-blok justru net_pnl **negatif** (-$21.21 dari 61 trade) — jadi window ini gak
membuang jam yang produktif.

**Catatan implementasi**: konstanta `WEEKEND_CLOSE_BLOCK_HOUR_UTC` di kode saat ini di-set ke `12`
(bukan `15`) sebagai kompensasi sementara untuk bug jam sistem laptop live yang drift ~3 jam — lihat
[Catatan bug & fix penting](#catatan-bug--fix-penting). Begitu jam laptop live disinkronkan ulang,
nilai ini **harus** dikembalikan ke `15`.

**Evaluasi mingguan**: tarik `dataset/live/m5_scalping/trade_log_v13.csv` (kolom OHLC + indikator
M5+H1 per trade, plus `is_exhausted` — sama cakupannya dgn hasil backtest), bandingkan dgn hasil
backtest, tuning ulang parameter kalau perlu (buat notebook versi baru, misal `v15_...ipynb`), lalu
update `models/m5_scalping/vXX/params.json` dan `PARAMS_PATH` di `app/features/m5_scalping/usecase.py`.

### Risiko urutan (sequence risk) — analisis Monte Carlo

Angka `max_drawdown_pct` di backtest cuma mencerminkan SATU urutan trade spesifik yang kebetulan
terjadi — kumpulan trade yang sama persis (menang/kalah & besarannya), kalau urutan kejadiannya
beda, bisa menghasilkan drawdown yang jauh lebih dalam meski win rate & profit factor keseluruhan
tidak berubah sama sekali. `notebooks/m5_scalping/v14_monte_carlo.ipynb` menguji ini dengan
mengacak (reshuffle, bukan resample dengan penggantian) urutan PnL trade v13 sebanyak 10.000 kali
per dataset, lalu menghitung ulang max drawdown tiap kali — di **3 dataset**: TEST (196 trade,
kondisi terkini), full 2025-2026 (721 trade), dan full 2019-2026 dengan lot fixed (3056 trade, 7.6
tahun, sample terbesar & paling stabil statistik — di-generate ulang khusus supaya PnL antar-trade
sebanding, tersimpan terpisah di `dataset/processed/m5_scalping/v14/trade_log_full_2019_2026_fixed_lot.csv`).

Semua angka di analisis ini pakai basis **modal $100** (`INITIAL_EQUITY = 100.0`) — representasi
langsung modal riil yang dipakai, bukan simulasi generik yang perlu dikonversi skala.

| Dataset | n trade | P95 worst-case (1-dari-20 kemungkinan) | % skenario tembus kill-switch total 40% |
|---|---|---|---|
| TEST (kondisi terkini) | 196 | -40.81% (~$41) | 5.39% |
| Full 2025-2026 | 721 | -52.84% (~$53) | 11.89% |
| **Full 2019-2026 (sample terbesar)** | **3056** | **-32.31% (~$32)** | **2.59%** |

**Kill-switch total (40%)**: masih dalam rentang wajar dilihat dari data 7.6 tahun (sample
terbesar & paling stabil, breach cuma 2.59%), tapi kalau dilihat murni dari kondisi pasar terkini
saja, risikonya sedikit lebih tinggi (breach 5.39%). Ini bukan kontradiksi — sample kecil punya
varians lebih tinggi, sample besar meredamnya lewat hukum bilangan besar.

**Kill-switch daily (20%) — temuan penting**: analisis lanjutan (metodologi beda — kelompokkan
trade per hari/bulan sintetis, baseline reset tiap kelompok, konsisten dgn cara
`_check_drawdown_guard` menghitung baseline harian) menemukan kill-switch **daily nyaris SELALU
breach (100% dari 10.000 simulasi)**. Penyebabnya BUKAN akumulasi banyak trade kecil, tapi **satu
trade tunggal** yang ukurannya sendiri sudah mendekati/melebihi 20% — trade terburuk di data TEST:
SL normal kena (bukan anomali/bug), ATR $18.72, SL=2×ATR=$37.44 poin, lot 0.01 → **rugi $37.44
(37.4% dari modal $100) dalam SATU trade**. Dengan cuma ~2 trade/hari, kill-switch daily 20% pada
modal $100 dengan lot fixed 0.01 efektifnya jadi "kill-switch per-trade", bukan "kill-switch
akumulasi harian" seperti tujuan aslinya. **Kill-switch monthly (25%, breach 38.63%) tidak
bermasalah** — breach-nya didorong akumulasi wajar beberapa trade jelek dalam 1 bulan, bukan 1
trade tunggal.

**Rekomendasi**: kill-switch daily 20% kemungkinan perlu dinaikkan (mis. ke 35-40%) supaya 1 trade
buruk tunggal tidak otomatis men-trigger pause harian, ATAU modal ditingkatkan dari $100 (kill-switch
% yang sama jadi lebih longgar dalam dolar). Trade-off antara proteksi ekstra konservatif (pause
tiap kali ada 1 trade SL besar) vs membiarkan strategi jalan (andalkan kill-switch monthly/total
saja) — preferensi user, bukan keharusan teknis. **v14 tidak mengubah `trade_params`/`signal_params`
v13 atau nilai apa pun di `.env`**, murni analisis risiko tambahan. Detail lengkap & angka persentil
lain (median, P75, P90, P99) di `models/m5_scalping/v13/params.json` (field `monte_carlo_analysis`)
dan `notebooks/m5_scalping/README.md`.

## Bot Telegram

Fitur di `app/features/bot_telegram/` — laporan trading otomatis, alert instan kill-switch drawdown,
dan kontrol manual (opsional) buat resume trading lebih cepat tanpa nunggu reset otomatis. Jalan
sebagai bagian dari proses `uvicorn app.main:app` yang sama (bukan proses terpisah), pakai mode
**polling** (`getUpdates`), bukan webhook — cocok untuk laptop lokal tanpa domain publik.

### Setup kredensial

Isi di `.env` (lihat `.env.example`):
- `TELEGRAM_TOKEN_XAUUSD` — token bot dari [@BotFather](https://t.me/BotFather)
- `TELEGRAM_CHAT_ID` — chat tujuan kirim laporan/alert (chat pribadi kamu dengan bot)
- `TELEGRAM_ALLOWED_USER_ID` — user ID yang boleh pakai command sensitif (`/start_tuning_*` & tombol
  override) — command/klik dari user lain otomatis ditolak
- `TELEGRAM_DAILY_REPORT_HOUR_UTC` / `TELEGRAM_WEEKLY_REPORT_HOUR_UTC` / `TELEGRAM_MONTHLY_REPORT_HOUR_UTC`
  — default semua jam 01:00 UTC (08:00 WIB)
- `TELEGRAM_REPORTS_ENABLED` — matikan laporan terjadwal kalau perlu (`false`), command on-demand & alert
  drawdown tetap jalan

Kalau `TELEGRAM_TOKEN_XAUUSD`/`TELEGRAM_CHAT_ID` kosong, bot otomatis skip start (`start_bot()` return
lebih awal dengan warning log) — trading tetap jalan normal tanpa Telegram.

### Laporan otomatis (terjadwal)

Tiga jenis, semua jam **08:00 WIB**:
- **Harian** — ringkas trade hari kalender UTC kemarin
- **Mingguan** — ringkas 7 hari kalender UTC terakhir (Senin-Minggu), dikirim tiap Senin
- **Bulanan** — ringkas bulan kalender UTC kemarin, dikirim tanggal 1

Isi laporan: total trade, menang/kalah, win rate, total PnL, rata-rata PnL/trade, trade terbaik/terburuk
— datanya dibaca langsung dari `trade_log_v13.csv` yang sama ditulis `m5_scalping`, bukan sumber terpisah.

**Format portofolio (gambar + teks)**: tiap laporan dikirim sbg **foto** (bukan cuma teks polos) —
gambar gabungan **equity curve** (kurva kumulatif PnL dalam periode itu, basis modal
`INITIAL_CAPITAL_USD`, area terisi hijau/merah tergantung untung/rugi) di atas, dan **bar chart PnL
harian** (breakdown per tanggal, warna hijau=untung/merah=rugi) di bawah — mirip laporan
portofolio saham/reksadana, dibuat pakai matplotlib (`render_report_chart()` di `usecase.py`),
di-generate on-the-fly ke buffer PNG in-memory (gak disimpan ke disk). Kalau tidak ada trade closed
sama sekali dalam periode (mis. weekend sepi), fallback ke pesan teks biasa (gak ada yang bisa
digambar).

Caption foto juga menambahkan (dibanding versi teks-saja sebelumnya):
- **Return %** — `total_pnl / INITIAL_CAPITAL_USD * 100`, basis modal riil tetap ($100), BUKAN
  saldo equity MT5 real-time — supaya return% antar-periode bisa dibandingkan apple-to-apple tanpa
  terpengaruh compounding lot/withdrawal.
- **Max drawdown periode ini** — penurunan terdalam dari puncak equity KUMULATIF selama periode
  laporan (bukan drawdown akun keseluruhan, cuma dalam window laporan itu).
- **Perbandingan vs periode sebelumnya** — total PnL periode SEBELUMNYA dengan durasi yang SAMA
  (mis. laporan mingguan bandingin ke 7 hari sebelum periode ini), dgn indikator naik/turun (🔼/🔽).

### Command di Telegram

Ketik langsung di chat dengan bot (muncul juga sebagai menu saran begitu ketik `/`, didaftarkan lewat
`set_my_commands()` saat bot start):

| Command | Fungsi |
|---|---|
| `/report_harian` | Laporan trading hari kemarin (on-demand, di luar jadwal) |
| `/report_mingguan` | Laporan trading 7 hari terakhir |
| `/report_bulanan` | Laporan trading bulan kemarin |
| `/start_tuning_harian` | Evaluasi kondisi market + tombol override kill-switch **harian** |
| `/start_tuning_bulanan` | Evaluasi kondisi market + tombol override kill-switch **bulanan** |

`/start_tuning_*` dan tombol override cuma direspon untuk user dengan ID yang cocok
`TELEGRAM_ALLOWED_USER_ID` — permintaan dari user lain dibalas "Tidak diizinkan."

### Alert drawdown & auto-resume

Begitu kill-switch daily/monthly/total ke-trigger, bot kirim alert **sekali** (dicek tiap 30 detik,
tapi cuma kirim di transisi False→True, bukan berulang selama masih breach):

- **Total**: alert informational-only, tanpa tombol — permanen sampai `drawdown_state.json` dihapus
  manual.
- **Daily/monthly**: alert dengan 2 tombol, "✅ Lanjutkan Trading" dan "⏸ Tetap Skip". **Klik tombol
  ini opsional** — kalau tidak diklik sama sekali, robot tetap otomatis resume sendiri begitu
  tanggal/bulan kalender (UTC) berganti, karena baseline daily/monthly & flag override-nya di-reset
  otomatis di rollover (lihat `_check_drawdown_guard` di `m5_scalping/usecase.py`). Tombol cuma buat
  mempercepat resume **sebelum** reset otomatis terjadi.

Alur override manual (via `/start_tuning_harian` atau `/start_tuning_bulanan`, atau langsung dari
tombol di alert): bot kirim laporan kondisi market TERKINI dulu (ADX M5/H1, trend H1, ATR%, sinyal
aktif kalau ada, status Order Block, status momentum chain — pakai pipeline sinyal yang **sama
persis** dengan robot live, `build_signal_row` + `generate_signal_v12`, bukan reimplementasi
terpisah) sebelum user memutuskan lewat tombol. Klik "Lanjutkan Trading" men-set
`daily_override_active`/`monthly_override_active` di `drawdown_state.json`, dicek di polling
berikutnya oleh `m5_scalping.usecase._check_drawdown_guard()`.

## Catatan bug & fix penting

Riwayat bug signifikan yang ditemukan & diperbaiki selama live trading — dicatat di sini supaya
gampang ditelusuri kalau ada gejala serupa muncul lagi:

- **`history_deals_get()` position filter bug** (ditemukan 2026-08-07): `mt5.history_deals_get(date_from,
  date_to, position=X)` diam-diam MENGABAIKAN filter `position` kalau `date_from`/`date_to` juga
  disertakan (undocumented MT5 API behavior) — menyebabkan 69 trade live pertama salah dicatat exit
  price/time/pnl-nya. Fix: tarik semua deal dalam rentang tanggal sekali, filter manual by `order`
  (dapat `position_id`), baru cari deal exit dgn `position_id` yang sama. Lihat `sync_closed_trades()`.
- **Overtrading / numpuk posisi** (ditemukan 2026-08-11): `check_signal_and_trade()` awalnya gak cek
  posisi OPEN sebelum order baru — kalau sinyal tetap valid di beberapa candle berturut-turut (mis.
  harga masih tren naik), robot numpuk banyak posisi BUY di titik harga makin tinggi tiap polling
  (~1 menit sekali), bukan 1 sinyal = 1 trade seperti asumsi backtest. 21 trade BUY beruntun kena SL
  nyaris bersamaan saat harga koreksi. Fix: guard `list_open_tickets()` — cuma boleh 1 posisi OPEN.
- **Order Block lookahead bug** (ditemukan 2026-08-15): `add_order_block()` pakai `.shift(-1/-2/-3)`
  (candle 3 KE DEPAN) untuk konfirmasi order block — valid di backtest (data historis lengkap), tapi
  di live, candle terakhir (yang dipakai untuk generate sinyal) SELALU `ob_bull=0, ob_bear=0` karena
  belum ada "3 candle ke depan"-nya. Akibatnya filter SKIP order block (v10) **tidak pernah aktif di
  live** sejak diterapkan sampai bug ini ditemukan — **belum diperbaiki**, dicatat sbg technical debt
  (perlu redesain indikator supaya gak lookahead, mis. deteksi dari N candle ke BELAKANG).
- **Jam sistem laptop live drift ~3 jam** (ditemukan 2026-08-15): `entry_time` yang dicatat robot
  (pakai `dt.datetime.now(dt.UTC)`) ternyata selisih persis 3 jam dari waktu order sesungguhnya di
  MT5 (`time_done`) — dicek di 10+ sampel trade, semua selisih 3 jam 0-1 detik. Root cause: jam
  sistem Windows di laptop yang menjalankan robot live salah/drift, bukan bug di kode Python.
  Dampak: `entry_time` historis salah, dan guard `_is_weekend_close_window` (yang pakai `now()` yang
  sama) jadi telat 3 jam dari yang seharusnya. Fix:
  - `entry_time` sekarang diambil dari `mt5.history_orders_get(ticket).time_done` (sumber kebenaran
    waktu dari server MT5, bukan jam laptop) via `_get_order_entry_time()` — trade baru otomatis
    benar. 201 baris data historis (7-14 Agustus, di `trade_log.csv` versi lama) juga sudah ditimpa
    dengan waktu MT5 yang benar (semua ticket dicocokkan ulang lewat `mt5.history_orders_get()`).
  - `WEEKEND_CLOSE_BLOCK_HOUR_UTC` dikompensasi sementara (lihat komentar di kode) sampai jam sistem
    laptop live disinkronkan ulang secara manual.
  - `_check_drawdown_guard()` (reset baseline daily/monthly) **belum** dikompensasi — masih pakai
    `now()` yang sama, jadi waktu reset harian/bulanan kemungkinan meleset beberapa jam dari UTC asli
    selama jam laptop belum disinkronkan. Dampaknya ringan (cuma soal kapan tepatnya reset terjadi).

## Catatan penting lain

- Package `MetaTrader5` hanya jalan di **Windows** dan environment tempat terminal MT5 ter-install,
  karena berkomunikasi langsung dengan aplikasi desktopnya.
- Tidak ada database — data disimpan/diproses lewat CSV (`dataset/`) dan Pandas. Log trade live juga CSV,
  bukan SQL. `trade_log.csv` (v04/v06, 201 baris) tersimpan sbg arsip histori, terpisah dari
  `trade_log_v13.csv` yang aktif dipakai sekarang — mekanismenya beda (kolom `is_exhausted`, dll) jadi
  sengaja tidak digabung/auto-migrate.
- Modal kecil ($100 awal, ~$1800+ setelah beberapa minggu live) dgn fixed lot dari `.env`
  (`XAUUSD_LOT_SIZE`) — bukan position sizing dinamis berbasis % risk seperti di backtest, supaya
  perilaku live predictable & gampang dievaluasi.
- `dataset/live/` **sengaja** ikut di-commit/push ke git (beda dari `dataset/processed/`,
  `dataset/exports/`, `dataset/raw/` yang di-gitignore) — supaya histori trading live gak hilang &
  bisa ditarik dari laptop lain untuk evaluasi.

## Testing

```powershell
pytest
```
