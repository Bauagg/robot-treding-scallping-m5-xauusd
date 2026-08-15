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
- SL/TP **ATR-relatif**: normal SL=2.0×ATR, TP=4.0×ATR (max hold 12 candle M5). Kalau momentum chain
  (`bull_chain`/`bear_chain`) sudah mentok 8/8 (exhaustion — momentum "matang", rawan melambat), pakai
  SL=1.25×ATR, TP=1.0×ATR yang lebih kecil (max hold 6 candle) — **bukan** membalik arah sinyal (opsi
  reverse terbukti gagal validasi, win rate cuma 18-24%).
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
- **ATR (M5)** — dasar hitung SL/TP ATR-relatif (normal 2.0×/4.0×, exhaustion 1.25×/1.0×)
- **Order Block M5 & H1** — pengecekan TERPISAH dari skor SMC di atas: kalau ada Order Block yang
  melawan arah sinyal, entry di-skip sama sekali (`has_opposing_order_block` di `usecase.py`)
- **Momentum chain** (`bull_chain`/`bear_chain`) — penentu mode SL/TP normal vs exhaustion

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
  18-24%), SMALL-PROFIT (SL/TP diperkecil, tetap searah sinyal) yang tervalidasi.

Model ML (v05, Random Forest) sempat dicoba tapi ternyata jadi SELL-only akibat *distribution shift*
ke rezim harga 2025-2026 — belum dipakai live, masih tersimpan sbg riset di `models/m5_scalping/v05/`.
Entry breakout/pending order (v07) dan trailing stop (v11) juga sempat dicoba tapi **ditolak** (terbukti
lebih buruk dari baseline di backtest). Detail lengkap tiap versi & angka di `notebooks/m5_scalping/README.md`.

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

Baru setelah semua lolos, SL/TP dihitung (normal atau exhaustion-mode tergantung momentum chain), order
dikirim ke MT5, dan dicatat ke `trade_log_v13.csv` (termasuk kolom `is_exhausted`).

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

Default (`.env.example`): **daily=20%, monthly=25%, total=40%** — divalidasi via backtest
(`notebooks/m5_scalping/v09_drawdown_killswitch.ipynb`): max drawdown historis strategi v06 adalah
-28.4%, jadi threshold yang lebih ketat (mis. 5/10/15% yang dicoba pertama kali) membuat robot mati
permanen di awal (trade ke-102 dari 1664, baru 6% perjalanan). 20/25/40% tervalidasi tidak pernah
ke-trigger di seluruh backtest historis, tapi tetap jadi jaring pengaman kalau kondisi live
menyimpang jauh dari backtest (mis. bug, akun benar-benar rusak).

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
backtest, tuning ulang parameter kalau perlu (buat notebook versi baru, misal `v14_...ipynb`), lalu
update `models/m5_scalping/vXX/params.json` dan `PARAMS_PATH` di `app/features/m5_scalping/usecase.py`.

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
