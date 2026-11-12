# Siaga Banjir Nusantara

Website pemantau potensi banjir seluruh Indonesia: peta interaktif, database SQLite, backend Flask, data BMKG, dan notifikasi peringatan.

## Cara menjalankan di VS Code
1. Pasang Python 3.9+ dan buka folder ini di VS Code.
2. Terminal (Ctrl+`):
   ```
   python -m venv .venv
   .venv\Scripts\activate        (Windows)   atau   source .venv/bin/activate   (Mac/Linux)
   pip install -r requirements.txt
   python app.py
   ```
3. Buka http://127.0.0.1:5000 (perlu internet untuk peta dan data BMKG).

## Cara kerja
- `app.py`: backend. Tiap 15 menit mengambil (a) peringatan dini hujan BMKG (nowcast) dan (b) prakiraan cuaca 3 jam-an BMKG untuk titik yang punya kode wilayah `adm4`. Hasilnya dihitung menjadi level Aman / Waspada / Siaga / Awas dan disimpan di `data/banjir.db`.
- Notifikasi dibuat saat level naik ke Siaga atau Awas. Browser mengeceknya tiap 30 detik: muncul toast, bunyi, dan notifikasi browser (klik "Aktifkan notifikasi").
- Klik lokasi lalu "Pantau lokasi ini" supaya notifikasi Siaga untuk lokasi itu ikut muncul. Tanpa dipantau, hanya level Awas yang muncul.
- "Uji notifikasi" di panel detail memicu notifikasi contoh.

## Menambah titik pantau
Seluruh 38 ibu kota provinsi sudah ada dan dipantau lewat peringatan dini BMKG tingkat provinsi. Untuk prakiraan hujan per 3 jam, titik butuh kode adm4 (kelurahan/desa). Tambahkan lewat tombol "Tambah titik pantau". Daftar kode wilayah: https://github.com/cahyadsn/wilayah

## Catatan penting
- Level risiko adalah indikator sederhana dari prakiraan hujan, bukan prakiraan banjir resmi. Untuk keputusan keselamatan, ikuti info resmi BMKG, BNPB, dan BPBD.
- BMKG mewajibkan pencantuman BMKG sebagai sumber data (sudah ada di website) dan membatasi 60 permintaan/menit per IP.
- Alamat RSS peringatan dini ada di `BMKG_NOWCAST` di `app.py`. Jika BMKG mengubahnya, cukup perbarui konstanta itu.

## Menaruh di internet (agar bisa dibuka siapa saja dan di HP)
Lihat langkah Render di chat, atau:
1. Unggah folder ini ke GitHub (repository baru).
2. Di render.com: New > Web Service > pilih repository tadi.
3. Build Command: `pip install -r requirements.txt`  |  Start Command: `gunicorn app:app --workers 1 --threads 4 --timeout 120`
4. Environment: tambahkan `PORT` = `10000`. Pilih paket Free, lalu Deploy.
