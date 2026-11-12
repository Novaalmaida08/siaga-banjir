const $ = (s) => document.querySelector(s);
const KAT = { "Sangat Ringan": 0, "Ringan": 0, "Sedang": 1, "Lebat": 2, "Sangat Lebat": 3 };
let model = "musiman", terakhir = null, DAFTAR = [];
const WARNA = ["#34d399", "#facc15", "#fb923c", "#f43f5e"], STATUS = ["Aman", "Waspada", "Siaga", "Awas"];
let mini = null, pin = null;

function petaMini() {
  const l = DAFTAR.find((x) => x.id == $("#kota").value); if (!l) return;
  const ikon = L.divIcon({ className: "", iconSize: [18, 18], html: `<div class="pinmini" style="--c:${WARNA[l.level]}"></div>` });
  if (!mini) {
    mini = L.map("miniPeta", { zoomControl: false, scrollWheelZoom: false, dragging: false, doubleClickZoom: false, touchZoom: false, keyboard: false })
      .setView([l.lat, l.lon], 8);
    L.tileLayer("https://tile.openstreetmap.org/{z}/{x}/{y}.png", { attribution: "&copy; OpenStreetMap", maxZoom: 18 }).addTo(mini);
    mini.on("click", () => { location.href = "/peta?lokasi=" + $("#kota").value; });
  }
  if (pin) pin.remove();
  pin = L.marker([l.lat, l.lon], { icon: ikon }).addTo(mini).bindTooltip(`${l.nama}: ${STATUS[l.level]}`, { permanent: true, direction: "top", offset: [0, -10] });
  mini.flyTo([l.lat, l.lon], 8, { duration: 1.2 });
  $("#bukaPeta").href = "/peta?lokasi=" + l.id;
}

/* animasi muncul saat di-scroll */
const io = new IntersectionObserver((es) => es.forEach((e) => {
  if (e.isIntersecting) { e.target.classList.add("tampil"); io.unobserve(e.target); }
}), { threshold: .12 });
document.querySelectorAll(".rev").forEach((el, i) => { el.style.transitionDelay = (i % 4) * 90 + "ms"; io.observe(el); });

const nice = (v) => { const p = 10 ** Math.floor(Math.log10(v)), f = v / p; return (f <= 1 ? 1 : f <= 2 ? 2 : f <= 5 ? 5 : 10) * p; };
const tgl = (s) => s;

function grafik(el, d, kecil) {
  const P = d.hasil, n = P.length, W = 700, H = kecil ? 230 : 330;
  const m = { l: 46, r: 16, t: 14, b: kecil ? 28 : 74 };
  const maks = Math.max(10, ...P.map((p) => p.atas)), st = nice(maks / 5), ym = Math.ceil(maks / st) * st;
  const x = (i) => m.l + (n === 1 ? (W - m.l - m.r) / 2 : i * (W - m.l - m.r) / (n - 1));
  const y = (v) => m.t + (H - m.t - m.b) * (1 - v / ym);
  let g = "";
  for (let v = 0; v <= ym; v += st) g += `<line class="gl" x1="${m.l}" x2="${W - m.r}" y1="${y(v)}" y2="${y(v)}"/><text class="tk" x="${m.l - 8}" y="${y(v) + 3}" text-anchor="end">${v} mm</text>`;
  const atas = P.map((p, i) => `${x(i)},${y(p.atas)}`).join(" ");
  const bawah = P.map((p, i) => `${x(i)},${y(p.bawah)}`).reverse().join(" ");
  const garis = P.map((p, i) => `${i ? "L" : "M"}${x(i)},${y(p.mm)}`).join(" ");
  const k = Math.ceil(n / (kecil ? 4 : 13));
  let lab = "";
  P.forEach((p, i) => {
    if (i % k) return;
    const t = kecil ? "W-" + String(i + 1).padStart(2, "0") : p.akhir;
    lab += kecil ? `<text class="tk" x="${x(i)}" y="${H - 8}" text-anchor="middle">${t}</text>`
      : `<text class="tk" transform="translate(${x(i)},${H - m.b + 14}) rotate(-50)" text-anchor="end">${t}</text>`;
  });
  const pts = P.map((p, i) => `<circle class="titik" cx="${x(i)}" cy="${y(p.mm)}" r="${n > 30 ? 2.5 : 4}"><title>${p.akhir}: ${p.mm} mm (${p.kategori})</title></circle>`).join("");
  el.innerHTML = `<svg viewBox="0 0 ${W} ${H}" role="img" aria-label="Grafik prediksi curah hujan">${g}<polygon class="pita" points="${atas} ${bawah}"/>
    <path class="garis" pathLength="1" d="${garis}"/>${pts}${lab}</svg>`;
}

async function ambil(kota, model, hz) {
  const r = await fetch(`/api/prediksi?kota=${kota}&model=${model}&horizon=${hz}`);
  const d = await r.json();
  if (!r.ok) throw new Error(d.error || "Gagal mengambil prediksi.");
  return d;
}

function tampil(d) {
  terakhir = d;
  $("#gJudul").textContent = `${d.kota} | ${d.horizon} minggu ke depan`;
  $("#gChip").textContent = d.model === "adaptif" ? "Adaptif" : "Musiman";
  grafik($("#grafik"), d, false);
  $("#sRata").textContent = d.rata2 + " mm"; $("#sTren").textContent = d.tren; $("#sLebat").textContent = d.minggu_lebat + " minggu";
  $("#tbody").innerHTML = d.hasil.map((p, i) => `<tr><td>${i + 1}</td><td>${p.akhir}</td><td>${p.mm.toFixed(2)} mm</td>
    <td><span class="bdg k${KAT[p.kategori]}">${p.kategori}</span>${p.mm >= 100 ? ' <span class="bdg k3">Potensi banjir</span>' : ""}</td></tr>`).join("");
  $("#catatan").textContent = `Berdasarkan ${d.minggu_data} minggu data (${d.rentang}). Rentang bawah-atas adalah perkiraan 80% dari variasi historis. Ini indikator, bukan prakiraan resmi.`;
}

async function jalankan() {
  const b = $("#jalan"); b.disabled = true; b.textContent = "Menghitung...";
  $("#grafik").innerHTML = `<p class="muat">Mengambil data historis 2010 sampai kini dari Open-Meteo. Pertama kali untuk satu kota bisa 5 sampai 20 detik.</p>`;
  try { tampil(await ambil($("#kota").value, model, $("#horizon").value)); }
  catch (e) { $("#grafik").innerHTML = `<p class="muat err">${e.message}</p>`; }
  b.disabled = false; b.textContent = "Jalankan Prediksi";
}

$("#kota").onchange = petaMini;
$("#horizon").oninput = (e) => $("#hz").textContent = e.target.value;
document.querySelectorAll(".seg button").forEach((b) => b.onclick = () => {
  document.querySelectorAll(".seg button").forEach((x) => x.classList.remove("aktif"));
  b.classList.add("aktif"); model = b.dataset.m;
});
$("#form").onsubmit = (e) => { e.preventDefault(); jalankan(); };
$("#salin").onclick = async (e) => {
  if (!terakhir) return;
  try { await navigator.clipboard.writeText(JSON.stringify(terakhir, null, 2)); e.target.textContent = "Tersalin"; }
  catch { e.target.textContent = "Gagal menyalin"; }
  setTimeout(() => e.target.textContent = "Salin JSON", 1800);
};

(async () => {
  const lok = await (await fetch("/api/lokasi")).json();
  lok.sort((a, b) => a.nama.localeCompare(b.nama));
  $("#kota").innerHTML = lok.map((l) => `<option value="${l.id}">${l.nama} (${l.provinsi})</option>`).join("");
  $("#jmlKota").textContent = lok.length + " lokasi";
  const jkt = lok.find((l) => l.nama === "Jakarta");
  if (jkt) $("#kota").value = jkt.id;
  DAFTAR = lok; petaMini();
  try {
    const d = await ambil($("#kota").value, "musiman", 4);
    $("#heroJudul").textContent = `${d.kota}, 4 minggu ke depan`;
    grafik($("#heroGrafik"), d, true);
    $("#heroRata").textContent = d.rata2 + " mm"; $("#heroTren").textContent = d.tren;
    tampil(await ambil($("#kota").value, "musiman", 12));
  } catch (e) {
    $("#heroGrafik").innerHTML = `<p class="muat err">${e.message}</p>`;
  }
})();
