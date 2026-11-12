"""Siaga Banjir Nusantara - backend Flask + SQLite + data BMKG.
Jalankan:  python app.py   lalu buka http://127.0.0.1:5000
"""
import os, json, time, statistics, sqlite3, threading, datetime as dt
import xml.etree.ElementTree as ET
import requests
from collections import defaultdict
from flask import Flask, jsonify, request, render_template

BASE = os.path.dirname(os.path.abspath(__file__))
DB = os.path.join(BASE, "data", "banjir.db")
INTERVAL = int(os.environ.get("REFRESH_MENIT", "15")) * 60
BMKG_CUACA = "https://api.bmkg.go.id/publik/prakiraan-cuaca"
BMKG_NOWCAST = "https://www.bmkg.go.id/alerts/nowcast/id"
HEADERS = {"User-Agent": "SiagaBanjirNusantara/1.0 (proyek edukasi)"}
LEVELS = ["Aman", "Waspada", "Siaga", "Awas"]

app = Flask(__name__)
refresh_lock = threading.Lock()

# (provinsi, ibu kota, lat, lon, alias untuk mencocokkan peringatan BMKG)
PROVINSI = [
    ("Aceh", "Banda Aceh", 5.55, 95.32, ["aceh"]),
    ("Sumatera Utara", "Medan", 3.59, 98.67, ["sumatera utara", "sumut"]),
    ("Sumatera Barat", "Padang", -0.95, 100.35, ["sumatera barat", "sumbar"]),
    ("Riau", "Pekanbaru", 0.51, 101.45, ["riau"]),
    ("Kepulauan Riau", "Tanjungpinang", 0.92, 104.45, ["kepulauan riau", "kepri"]),
    ("Jambi", "Jambi", -1.61, 103.61, ["jambi"]),
    ("Sumatera Selatan", "Palembang", -2.98, 104.76, ["sumatera selatan", "sumsel"]),
    ("Bangka Belitung", "Pangkalpinang", -2.13, 106.11, ["bangka belitung", "babel"]),
    ("Bengkulu", "Bengkulu", -3.80, 102.26, ["bengkulu"]),
    ("Lampung", "Bandar Lampung", -5.43, 105.26, ["lampung"]),
    ("DKI Jakarta", "Jakarta", -6.18, 106.83, ["jakarta"]),
    ("Banten", "Serang", -6.12, 106.15, ["banten"]),
    ("Jawa Barat", "Bandung", -6.91, 107.61, ["jawa barat", "jabar"]),
    ("Jawa Tengah", "Semarang", -6.97, 110.42, ["jawa tengah", "jateng"]),
    ("DI Yogyakarta", "Yogyakarta", -7.80, 110.36, ["yogyakarta"]),
    ("Jawa Timur", "Surabaya", -7.25, 112.75, ["jawa timur", "jatim"]),
    ("Bali", "Denpasar", -8.65, 115.22, ["bali"]),
    ("Nusa Tenggara Barat", "Mataram", -8.58, 116.12, ["nusa tenggara barat", "ntb"]),
    ("Nusa Tenggara Timur", "Kupang", -10.18, 123.60, ["nusa tenggara timur", "ntt"]),
    ("Kalimantan Barat", "Pontianak", -0.03, 109.33, ["kalimantan barat", "kalbar"]),
    ("Kalimantan Tengah", "Palangka Raya", -2.21, 113.92, ["kalimantan tengah", "kalteng"]),
    ("Kalimantan Selatan", "Banjarmasin", -3.32, 114.59, ["kalimantan selatan", "kalsel"]),
    ("Kalimantan Timur", "Samarinda", -0.50, 117.15, ["kalimantan timur", "kaltim"]),
    ("Kalimantan Utara", "Tanjung Selor", 2.84, 117.37, ["kalimantan utara", "kaltara"]),
    ("Sulawesi Utara", "Manado", 1.47, 124.84, ["sulawesi utara", "sulut"]),
    ("Gorontalo", "Gorontalo", 0.54, 123.06, ["gorontalo"]),
    ("Sulawesi Tengah", "Palu", -0.90, 119.87, ["sulawesi tengah", "sulteng"]),
    ("Sulawesi Barat", "Mamuju", -2.68, 118.89, ["sulawesi barat", "sulbar"]),
    ("Sulawesi Selatan", "Makassar", -5.15, 119.43, ["sulawesi selatan", "sulsel"]),
    ("Sulawesi Tenggara", "Kendari", -3.97, 122.51, ["sulawesi tenggara", "sultra"]),
    ("Maluku", "Ambon", -3.70, 128.18, ["maluku"]),
    ("Maluku Utara", "Sofifi", 0.74, 127.57, ["maluku utara"]),
    ("Papua", "Jayapura", -2.53, 140.72, ["papua"]),
    ("Papua Barat", "Manokwari", -0.86, 134.06, ["papua barat"]),
    ("Papua Barat Daya", "Sorong", -0.88, 131.26, ["papua barat daya"]),
    ("Papua Selatan", "Merauke", -8.50, 140.40, ["papua selatan"]),
    ("Papua Tengah", "Nabire", -3.37, 135.48, ["papua tengah"]),
    ("Papua Pegunungan", "Wamena", -4.09, 138.95, ["papua pegunungan"]),
]
ALIAS = {p[0]: p[4] for p in PROVINSI}

# Titik pantau dengan kode wilayah (adm4) -> dapat prakiraan per 3 jam dari BMKG.
# Tambah sendiri lewat tombol "Tambah titik pantau" di website.
TITIK_ADM4 = {
    "DKI Jakarta": "31.71.01.1001",  # Gambir
}
EXTRA = [
    ("Jakarta Selatan", "DKI Jakarta", -6.30, 106.82, "31.74.04.1006"),
    ("Ubud, Gianyar", "Bali", -8.50, 115.26, "51.04.05.1005"),
    ("Pandak, Banyumas", "Jawa Tengah", -7.43, 109.27, "33.02.07.2005"),
]

def db():
    c = sqlite3.connect(DB, timeout=20)
    c.row_factory = sqlite3.Row
    return c

def init_db():
    os.makedirs(os.path.dirname(DB), exist_ok=True)
    with db() as c:
        c.executescript("""
        CREATE TABLE IF NOT EXISTS lokasi(id INTEGER PRIMARY KEY AUTOINCREMENT, nama TEXT, provinsi TEXT,
            lat REAL, lon REAL, adm4 TEXT);
        CREATE TABLE IF NOT EXISTS risiko(lokasi_id INTEGER PRIMARY KEY, level INTEGER DEFAULT 0, skor INTEGER DEFAULT 0,
            ringkasan TEXT, slot_json TEXT, diperbarui TEXT);
        CREATE TABLE IF NOT EXISTS peringatan(id INTEGER PRIMARY KEY AUTOINCREMENT, judul TEXT, deskripsi TEXT,
            link TEXT, provinsi TEXT, waktu TEXT);
        CREATE TABLE IF NOT EXISTS curah(lokasi_id INTEGER, akhir TEXT, mm REAL, PRIMARY KEY(lokasi_id, akhir));
        CREATE TABLE IF NOT EXISTS curah_meta(lokasi_id INTEGER PRIMARY KEY, diambil TEXT);
        CREATE TABLE IF NOT EXISTS notifikasi(id INTEGER PRIMARY KEY AUTOINCREMENT, kunci TEXT UNIQUE, waktu TEXT,
            lokasi_id INTEGER, level INTEGER, pesan TEXT);
        """)
        if c.execute("SELECT COUNT(*) FROM lokasi").fetchone()[0] == 0:
            for nama, ibu, lat, lon, _ in PROVINSI:
                c.execute("INSERT INTO lokasi(nama,provinsi,lat,lon,adm4) VALUES(?,?,?,?,?)",
                          (ibu, nama, lat, lon, TITIK_ADM4.get(nama)))
            for nama, prov, lat, lon, adm4 in EXTRA:
                c.execute("INSERT INTO lokasi(nama,provinsi,lat,lon,adm4) VALUES(?,?,?,?,?)", (nama, prov, lat, lon, adm4))

# ---------- Ambil data BMKG ----------
def skor_slot(desc):
    d = (desc or "").lower()
    if "lebat" in d or "petir" in d: return 3
    if "sedang" in d: return 2
    if "hujan" in d: return 1
    return 0

def ambil_prakiraan(adm4):
    r = requests.get(BMKG_CUACA, params={"adm4": adm4}, headers=HEADERS, timeout=15)
    r.raise_for_status()
    hari = r.json()["data"][0]["cuaca"]
    slots = [s for h in hari for s in h]
    sekarang = dt.datetime.utcnow() - dt.timedelta(hours=3)
    hasil = []
    for s in slots:
        try:
            t = dt.datetime.strptime(s["utc_datetime"], "%Y-%m-%d %H:%M:%S")
        except Exception:
            continue
        if t >= sekarang:
            hasil.append({"jam": (s.get("local_datetime") or "")[5:16], "cuaca": s.get("weather_desc", "-"),
                          "suhu": s.get("t"), "lembab": s.get("hu"), "skor": skor_slot(s.get("weather_desc"))})
    return sorted(hasil, key=lambda x: x["jam"])[:8]

def ambil_peringatan():
    r = requests.get(BMKG_NOWCAST, headers=HEADERS, timeout=15)
    r.raise_for_status()
    out = []
    for it in ET.fromstring(r.content).iter("item"):
        judul = (it.findtext("title") or "").strip()
        desk = (it.findtext("description") or "").strip()
        teks = (judul + " " + desk).lower()
        if "hujan" not in teks and "banjir" not in teks:
            continue
        prov = [p for p, al in ALIAS.items() if any(a in teks for a in al)]
        # "papua" juga muncul di "papua barat": utamakan nama yang paling spesifik
        prov = [p for p in prov if not any(q != p and p.lower() in q.lower() and q.lower() in teks for q in prov)] or prov
        out.append({"judul": judul, "deskripsi": desk, "link": (it.findtext("link") or "").strip(),
                    "provinsi": ",".join(prov), "waktu": it.findtext("pubDate") or "",
                    "skor": 6 if ("lebat" in teks or "petir" in teks) else 3})
    return out

def level_dari_skor(s):
    return 3 if s >= 10 else 2 if s >= 6 else 1 if s >= 3 else 0

def refresh():
    if not refresh_lock.acquire(blocking=False):
        return
    try:
        try:
            alerts = ambil_peringatan()
        except Exception as e:
            print("[nowcast] gagal:", e); alerts = None
        now = dt.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        with db() as c:
            if alerts is not None:
                c.execute("DELETE FROM peringatan")
                for a in alerts:
                    c.execute("INSERT INTO peringatan(judul,deskripsi,link,provinsi,waktu) VALUES(?,?,?,?,?)",
                              (a["judul"], a["deskripsi"], a["link"], a["provinsi"], a["waktu"]))
            for l in c.execute("SELECT * FROM lokasi").fetchall():
                slots, ringkas = [], ""
                if l["adm4"]:
                    try:
                        slots = ambil_prakiraan(l["adm4"]); time.sleep(1.1)  # batas BMKG 60 req/menit
                    except Exception as e:
                        print("[prakiraan]", l["nama"], "gagal:", e)
                sf = sum(s["skor"] for s in slots)
                sa = max([a["skor"] for a in (alerts or []) if l["provinsi"] in a["provinsi"].split(",")] or [0])
                total = sf + sa
                lv = level_dari_skor(total)
                if slots:
                    n = sum(1 for s in slots if s["skor"] >= 2)
                    ringkas = f"{n} dari {len(slots)} periode 3 jam ke depan berpotensi hujan sedang-lebat."
                if sa:
                    ringkas = (ringkas + " " if ringkas else "") + "Peringatan dini hujan BMKG aktif di provinsi ini."
                if not ringkas:
                    ringkas = "Tidak ada peringatan hujan aktif." if not l["adm4"] else "Cuaca relatif aman 24 jam ke depan."
                lama = c.execute("SELECT level FROM risiko WHERE lokasi_id=?", (l["id"],)).fetchone()
                c.execute("INSERT OR REPLACE INTO risiko VALUES(?,?,?,?,?,?)",
                          (l["id"], lv, total, ringkas, json.dumps(slots), now))
                if lv >= 2 and (not lama or lama["level"] != lv):
                    kunci = f"{l['id']}:{lv}:{now[:13]}"
                    c.execute("INSERT OR IGNORE INTO notifikasi(kunci,waktu,lokasi_id,level,pesan) VALUES(?,?,?,?,?)",
                              (kunci, now, l["id"], lv, f"Status {LEVELS[lv]}: potensi banjir di {l['nama']}, {l['provinsi']}. {ringkas}"))
        print("[refresh] selesai", now)
    finally:
        refresh_lock.release()

def loop():
    while True:
        try: refresh()
        except Exception as e: print("[loop]", e)
        time.sleep(INTERVAL)

# ---------- Halaman & API ----------
@app.route("/")
def beranda():
    return render_template("beranda.html")

@app.route("/peta")
def peta():
    return render_template("peta.html")

def baris_lokasi(r):
    return {"id": r["id"], "nama": r["nama"], "provinsi": r["provinsi"], "lat": r["lat"], "lon": r["lon"],
            "adm4": r["adm4"], "level": r["level"] or 0, "skor": r["skor"] or 0,
            "ringkasan": r["ringkasan"] or "Menunggu data BMKG...", "diperbarui": r["diperbarui"]}

SQL_LOKASI = "SELECT l.*, r.level, r.skor, r.ringkasan, r.diperbarui FROM lokasi l LEFT JOIN risiko r ON r.lokasi_id=l.id"

@app.get("/api/lokasi")
def api_lokasi():
    with db() as c:
        return jsonify([baris_lokasi(r) for r in c.execute(SQL_LOKASI + " ORDER BY r.level DESC, l.nama")])

@app.get("/api/lokasi/<int:i>")
def api_detail(i):
    with db() as c:
        r = c.execute(SQL_LOKASI + " WHERE l.id=?", (i,)).fetchone()
        if not r: return jsonify({"error": "tidak ditemukan"}), 404
        s = c.execute("SELECT slot_json FROM risiko WHERE lokasi_id=?", (i,)).fetchone()
        a = c.execute("SELECT judul,link FROM peringatan WHERE ','||provinsi||',' LIKE ?", (f"%,{r['provinsi']},%",)).fetchall()
        d = baris_lokasi(r)
        d["slot"] = json.loads(s["slot_json"]) if s and s["slot_json"] else []
        d["peringatan"] = [dict(x) for x in a]
        return jsonify(d)

@app.post("/api/lokasi")
def api_tambah():
    j = request.get_json(force=True)
    try:
        nama, prov = j["nama"].strip(), j["provinsi"].strip()
        lat, lon = float(j["lat"]), float(j["lon"])
        assert nama and -11.5 <= lat <= 6.5 and 94 <= lon <= 142
    except Exception:
        return jsonify({"error": "Isi nama, provinsi, lat, dan lon yang berada di wilayah Indonesia."}), 400
    with db() as c:
        c.execute("INSERT INTO lokasi(nama,provinsi,lat,lon,adm4) VALUES(?,?,?,?,?)",
                  (nama, prov, lat, lon, (j.get("adm4") or "").strip() or None))
    threading.Thread(target=refresh, daemon=True).start()
    return jsonify({"ok": True})

@app.get("/api/ringkasan")
def api_ringkasan():
    with db() as c:
        cnt = [0, 0, 0, 0]
        for r in c.execute("SELECT COALESCE(level,0) lv, COUNT(*) n FROM lokasi l LEFT JOIN risiko r ON r.lokasi_id=l.id GROUP BY lv"):
            cnt[r["lv"]] = r["n"]
        up = c.execute("SELECT MAX(diperbarui) m FROM risiko").fetchone()["m"]
        na = c.execute("SELECT COUNT(*) FROM peringatan").fetchone()[0]
    return jsonify({"jumlah": cnt, "diperbarui": up, "peringatan_aktif": na})

@app.get("/api/notifikasi")
def api_notif():
    sejak = int(request.args.get("sejak", 0))
    with db() as c:
        mx = c.execute("SELECT COALESCE(MAX(id),0) m FROM notifikasi").fetchone()["m"]
        rows = c.execute("SELECT n.*, l.nama, l.provinsi FROM notifikasi n JOIN lokasi l ON l.id=n.lokasi_id "
                         "WHERE n.id>? ORDER BY n.id", (sejak,)).fetchall()
    return jsonify({"max_id": mx, "items": [dict(r) for r in rows]})

@app.post("/api/refresh")
def api_refresh():
    threading.Thread(target=refresh, daemon=True).start()
    return jsonify({"ok": True})

@app.post("/api/simulasi/<int:i>")
def api_simulasi(i):
    """Untuk menguji notifikasi tanpa menunggu banjir sungguhan."""
    with db() as c:
        l = c.execute("SELECT * FROM lokasi WHERE id=?", (i,)).fetchone()
        if not l: return jsonify({"error": "tidak ditemukan"}), 404
        now = dt.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        c.execute("INSERT INTO notifikasi(kunci,waktu,lokasi_id,level,pesan) VALUES(?,?,?,?,?)",
                  (f"uji:{i}:{time.time()}", now, i, 3, f"[UJI COBA] Status Awas: potensi banjir di {l['nama']}, {l['provinsi']}."))
    return jsonify({"ok": True})

# ---------- Prediksi curah hujan mingguan ----------
ARSIP = "https://archive-api.open-meteo.com/v1/archive"

def kategori(mm):
    return ("Sangat Ringan" if mm < 20 else "Ringan" if mm < 50 else "Sedang" if mm < 100
            else "Lebat" if mm < 150 else "Sangat Lebat")

def muat_curah(l):
    """Ambil curah hujan harian Open-Meteo (reanalisis ERA5) sejak 2010, simpan sebagai total mingguan."""
    with db() as c:
        m = c.execute("SELECT diambil FROM curah_meta WHERE lokasi_id=?", (l["id"],)).fetchone()
    if m and (dt.date.today() - dt.date.fromisoformat(m["diambil"])).days < 7:
        return
    akhir = dt.date.today() - dt.timedelta(days=7)
    r = requests.get(ARSIP, params={"latitude": l["lat"], "longitude": l["lon"], "start_date": "2010-01-04",
                                    "end_date": akhir.isoformat(), "daily": "precipitation_sum",
                                    "timezone": "Asia/Jakarta"}, headers=HEADERS, timeout=90)
    r.raise_for_status()
    d = r.json()["daily"]
    total, jml = defaultdict(float), defaultdict(int)
    for tgl, v in zip(d["time"], d["precipitation_sum"]):
        if v is None: continue
        t = dt.date.fromisoformat(tgl)
        k = (t + dt.timedelta(days=6 - t.weekday())).isoformat()  # minggu berakhir hari Minggu
        total[k] += v; jml[k] += 1
    rows = [(l["id"], k, round(v, 2)) for k, v in total.items() if jml[k] == 7]
    with db() as c:
        c.executemany("INSERT OR REPLACE INTO curah VALUES(?,?,?)", rows)
        c.execute("INSERT OR REPLACE INTO curah_meta VALUES(?,?)", (l["id"], dt.date.today().isoformat()))

def prakiraan(rows, model, horizon):
    seri = [(dt.date.fromisoformat(a), mm) for a, mm in rows]
    mingguke = lambda t: min(t.isocalendar()[1], 52)
    per = defaultdict(list)
    for t, mm in seri: per[mingguke(t)].append(mm)

    def klim(t):
        w = mingguke(t); v = []
        for k in (-1, 0, 1): v += per[((w - 1 + k) % 52) + 1]
        return statistics.mean(v), (statistics.pstdev(v) if len(v) > 1 else 0.0)

    terakhir = seri[-1][0]
    rasio = 1.0
    if model == "adaptif":  # koreksi musiman dengan kondisi 8 minggu terakhir, memudar tiap minggu
        a = sum(mm for _, mm in seri[-8:]); b = sum(klim(t)[0] for t, _ in seri[-8:])
        rasio = min(2.0, max(0.5, a / b)) if b > 0 else 1.0
    t = dt.date.today() + dt.timedelta(days=6 - dt.date.today().weekday())  # Minggu terdekat
    out = []
    for _ in range(horizon):
        mean, sd = klim(t)
        jarak = max(1, (t - terakhir).days // 7)
        mean *= 1 + (rasio - 1) * (0.85 ** jarak)
        mm = round(mean, 2)
        out.append({"akhir": t.isoformat(), "mm": mm, "bawah": round(max(0, mean - 1.28 * sd), 2),
                    "atas": round(mean + 1.28 * sd, 2), "kategori": kategori(mm)})
        t += dt.timedelta(days=7)
    return out

@app.get("/api/prediksi")
def api_prediksi():
    try:
        i = int(request.args.get("kota", 0)); h = max(1, min(52, int(request.args.get("horizon", 12))))
    except ValueError:
        return jsonify({"error": "Parameter tidak valid."}), 400
    model = "adaptif" if request.args.get("model") == "adaptif" else "musiman"
    with db() as c:
        l = c.execute("SELECT * FROM lokasi WHERE id=?", (i,)).fetchone()
    if not l: return jsonify({"error": "Kota tidak ditemukan."}), 404
    try:
        muat_curah(l)
    except Exception as e:
        print("[curah] gagal:", e)
    with db() as c:
        rows = c.execute("SELECT akhir, mm FROM curah WHERE lokasi_id=? ORDER BY akhir", (i,)).fetchall()
    if len(rows) < 104:
        return jsonify({"error": "Data historis belum bisa diambil dari Open-Meteo. Pastikan internet aktif, lalu coba lagi."}), 503
    hasil = prakiraan([(r["akhir"], r["mm"]) for r in rows], model, h)
    rata = round(sum(x["mm"] for x in hasil) / len(hasil), 1)
    ref = sum(r["mm"] for r in rows[-8:]) / 8
    return jsonify({"kota": l["nama"], "provinsi": l["provinsi"], "model": model, "horizon": h,
                    "rentang": f"{rows[0]['akhir'][:4]} - {rows[-1]['akhir'][:4]}", "minggu_data": len(rows),
                    "rata2": rata, "tren": "Naik" if rata > ref * 1.05 else "Turun" if rata < ref * 0.95 else "Stabil",
                    "minggu_lebat": sum(1 for x in hasil if x["mm"] >= 100), "hasil": hasil})

init_db()
_mulai = False

def mulai_latar():
    """Jalankan pembaruan data BMKG di latar belakang (sekali saja)."""
    global _mulai
    if not _mulai:
        _mulai = True
        threading.Thread(target=loop, daemon=True).start()

# Saat dijalankan oleh server hosting (gunicorn), pembaruan otomatis ikut menyala.
if os.environ.get("PORT") and __name__ != "__main__":
    mulai_latar()

if __name__ == "__main__":
    mulai_latar()
    port = int(os.environ.get("PORT", 5000))
    host = "0.0.0.0" if os.environ.get("PORT") else "127.0.0.1"
    app.run(host=host, port=port, debug=False)
