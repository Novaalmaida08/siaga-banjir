const NAMA = ["Aman", "Waspada", "Siaga", "Awas"];
const $ = (s) => document.querySelector(s);
const S = { data: [], filter: -1, q: "", sel: null, lastId: null, markers: {},
            subs: new Set(JSON.parse(localStorage.getItem("subs") || "[]")) };

const map = L.map("map", { center: [-2.5, 118], zoom: 5, minZoom: 4, zoomControl: false,
  maxBounds: [[-14, 91], [9, 145]] });
L.control.zoom({ position: "bottomright" }).addTo(map);
L.tileLayer("https://tile.openstreetmap.org/{z}/{x}/{y}.png",
  { attribution: "&copy; OpenStreetMap contributors | Data: BMKG", maxZoom: 18, className: "tile-gelap" }).addTo(map);

const j = (url, opt) => fetch(url, opt).then((r) => r.json());
const esc = (t) => String(t ?? "").replace(/[&<>"]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]));

function icon(l) {
  return L.divIcon({ className: "", iconSize: [18, 18],
    html: `<div class="pin lv${l.level} ${S.sel === l.id ? "pilih" : ""}"><b></b><i></i></div>` });
}

async function muat() {
  S.data = await j("/api/lokasi");
  const r = await j("/api/ringkasan");
  $("#update").textContent = r.diperbarui
    ? `Diperbarui ${r.diperbarui} | ${r.peringatan_aktif} peringatan hujan BMKG aktif`
    : "Menunggu data pertama dari BMKG...";
  gambarStat(r.jumlah);
  gambarPeta();
  gambarDaftar();
}

function gambarStat(j) {
  $("#stats").innerHTML = [3, 2, 1, 0].map((lv) =>
    `<button class="stat lv${lv} ${S.filter === lv ? "aktif" : ""}" data-lv="${lv}"><b>${j[lv]}</b><span>${NAMA[lv]}</span></button>`).join("");
  $("#stats").querySelectorAll(".stat").forEach((b) => b.onclick = () => {
    const lv = +b.dataset.lv; S.filter = S.filter === lv ? -1 : lv; render();
  });
}

function gambarPeta() {
  S.data.forEach((l) => {
    if (S.markers[l.id]) S.markers[l.id].setIcon(icon(l));
    else S.markers[l.id] = L.marker([l.lat, l.lon], { icon: icon(l), title: l.nama })
      .addTo(map).on("click", () => pilih(l.id));
    S.markers[l.id].bindTooltip(`${esc(l.nama)}: ${NAMA[l.level]}`, { direction: "top", offset: [0, -8] });
  });
}

function tersaring() {
  const q = S.q.toLowerCase();
  return S.data.filter((l) => (S.filter < 0 || l.level === S.filter) &&
    (!q || (l.nama + " " + l.provinsi).toLowerCase().includes(q)));
}

function gambarDaftar() {
  const rows = tersaring();
  $("#daftar").innerHTML = rows.length ? rows.map((l) => `
    <li tabindex="0" class="lv${l.level} ${S.sel === l.id ? "pilih" : ""}" data-id="${l.id}">
      <span class="dot"></span>
      <div><strong>${esc(l.nama)}</strong><span class="badge">${S.subs.has(l.id) ? "Dipantau | " : ""}${NAMA[l.level]}</span>
      <small>${esc(l.provinsi)}. ${esc(l.ringkasan)}</small></div></li>`).join("")
    : `<li class="kosong">Tidak ada lokasi yang cocok. Ubah kata kunci atau filter.</li>`;
  $("#daftar").querySelectorAll("li[data-id]").forEach((li) => {
    li.onclick = () => pilih(+li.dataset.id);
    li.onkeydown = (e) => e.key === "Enter" && pilih(+li.dataset.id);
  });
}

function render() { gambarStat(hitung()); gambarDaftar(); }
function hitung() { const c = [0, 0, 0, 0]; S.data.forEach((l) => c[l.level]++); return c; }

function pills() {
  $("#pills").innerHTML = [["Semua", -1], ["Awas", 3], ["Siaga", 2], ["Waspada", 1], ["Aman", 0]]
    .map(([t, v]) => `<button class="pill ${S.filter === v ? "aktif" : ""}" data-v="${v}">${t}</button>`).join("");
  $("#pills").querySelectorAll(".pill").forEach((b) => b.onclick = () => { S.filter = +b.dataset.v; render(); pills(); });
}

async function pilih(id) {
  S.sel = id;
  const d = await j("/api/lokasi/" + id);
  map.flyTo([d.lat, d.lon], Math.max(map.getZoom(), 8), { duration: 1.4 });
  gambarPeta(); gambarDaftar();
  const maks = Math.max(1, ...d.slot.map((s) => s.skor));
  const pantau = S.subs.has(id);
  $("#detail").innerHTML = `
    <button class="tutup ghost" id="x">Tutup</button>
    <h2>${esc(d.nama)}</h2><div class="sub">${esc(d.provinsi)}${d.adm4 ? " | adm4 " + esc(d.adm4) : ""}</div>
    <span class="status lv${d.level}">${NAMA[d.level]}</span>
    <p>${esc(d.ringkasan)}</p>
    ${d.slot.length ? `<div class="bars">${d.slot.map((s) =>
      `<div class="bar s${s.skor}" title="${esc(s.cuaca)}"><span style="--h:${Math.round(20 + 80 * s.skor / 3)}%"></span>${esc(s.jam.slice(6, 8))}:00</div>`).join("")}</div>
      <small style="color:var(--redup)">Prakiraan hujan per 3 jam (BMKG). Batang lebih tinggi berarti hujan lebih deras.</small>`
      : `<p style="color:var(--redup)">Titik ini belum punya kode adm4, jadi statusnya hanya mengikuti peringatan dini BMKG tingkat provinsi.</p>`}
    ${d.peringatan.map((a) => `<p>${a.link ? `<a href="${esc(a.link)}" target="_blank" rel="noopener">${esc(a.judul)}</a>` : esc(a.judul)}</p>`).join("")}
    <div class="row"><button id="pantau" class="${pantau ? "ghost" : ""}">${pantau ? "Berhenti memantau" : "Pantau lokasi ini"}</button>
    <button id="uji" class="ghost">Uji notifikasi</button></div>`;
  $("#detail").classList.add("buka");
  $("#x").onclick = () => { $("#detail").classList.remove("buka"); S.sel = null; gambarPeta(); gambarDaftar(); };
  $("#pantau").onclick = () => {
    pantau ? S.subs.delete(id) : S.subs.add(id);
    localStorage.setItem("subs", JSON.stringify([...S.subs]));
    if (!pantau) izinNotif();
    pilih(id);
  };
  $("#uji").onclick = () => { izinNotif(); fetch("/api/simulasi/" + id, { method: "POST" }).then(cekNotif); };
}

/* ---------- Notifikasi ---------- */
function izinNotif() {
  if ("Notification" in window && Notification.permission === "default") Notification.requestPermission().then(statusBel);
}
function statusBel() {
  const b = $("#btnBell");
  if (!("Notification" in window)) { b.textContent = "Notifikasi tidak didukung"; b.disabled = true; return; }
  b.textContent = Notification.permission === "granted" ? "Notifikasi aktif" : "Aktifkan notifikasi";
}
function bunyi() {
  try {
    const a = new (window.AudioContext || window.webkitAudioContext)(), o = a.createOscillator(), g = a.createGain();
    o.connect(g); g.connect(a.destination); o.type = "sine"; o.frequency.value = 660; g.gain.value = .12;
    o.start(); o.frequency.setValueAtTime(880, a.currentTime + .18); o.stop(a.currentTime + .4);
  } catch (e) {}
}
function toast(n) {
  const t = document.createElement("div");
  t.className = `toast lv${n.level}`;
  t.innerHTML = `<strong>Peringatan banjir: ${NAMA[n.level]}</strong>${esc(n.pesan)}`;
  t.onclick = () => { pilih(n.lokasi_id); t.remove(); };
  $("#toasts").append(t); bunyi();
  setTimeout(() => { t.classList.add("pergi"); setTimeout(() => t.remove(), 400); }, 9000);
  if ("Notification" in window && Notification.permission === "granted")
    new Notification("Peringatan banjir: " + NAMA[n.level], { body: n.pesan });
}
async function cekNotif() {
  const r = await j("/api/notifikasi?sejak=" + (S.lastId ?? 0));
  if (S.lastId === null) { S.lastId = r.max_id; return; }  // buka pertama kali: jangan putar ulang riwayat
  S.lastId = r.max_id;
  r.items.filter((n) => S.subs.has(n.lokasi_id) ? n.level >= 2 : n.level === 3).forEach(toast);
  if (r.items.length) muat();
}

/* ---------- Kontrol ---------- */
$("#cari").oninput = (e) => { S.q = e.target.value; gambarDaftar(); };
$("#btnBell").onclick = izinNotif;
$("#btnRefresh").onclick = async (e) => {
  e.target.textContent = "Mengambil data..."; await fetch("/api/refresh", { method: "POST" });
  setTimeout(async () => { await muat(); e.target.textContent = "Perbarui"; }, 6000);
};
$("#btnTambah").onclick = () => $("#dlg").showModal();
$("#dlg").addEventListener("close", async () => {
  if ($("#dlg").returnValue !== "ok") return;
  const f = Object.fromEntries(new FormData($("#formTambah")));
  const r = await fetch("/api/lokasi", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(f) });
  if (r.ok) { $("#formTambah").reset(); setTimeout(muat, 3000); }
  else alert((await r.json()).error);
});

pills(); statusBel(); cekNotif();
muat().then(() => { const q = new URLSearchParams(location.search).get("lokasi"); if (q) pilih(+q); });
setInterval(cekNotif, 30000);
setInterval(muat, 5 * 60000);
