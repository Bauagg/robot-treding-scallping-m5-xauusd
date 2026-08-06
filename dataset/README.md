# Dataset

- `raw/` — data mentah, apa adanya dari sumbernya (export MT5, broker, dll). **Jangan diedit langsung.**
- `processed/` — data hasil cleaning/transform, siap dipakai untuk analisis atau training.
- `exports/` — hasil akhir (laporan, backtest result, dll) yang mau dibagikan/disimpan.

Isi folder `raw/` dan `processed/` di-ignore oleh git (lihat `.gitignore`) supaya file dataset besar tidak masuk repo. Taruh data mentah kamu di `raw/` lalu proses lewat notebook di `notebooks/`.
