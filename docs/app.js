// خريطة البحرين — offline Bahrain map (MIT). Data © OpenStreetMap contributors (ODbL).
import * as maplibregl from './vendor/maplibre-gl.mjs';

const BASE = new URL('./', location.href).href;
const PM_URL = BASE + 'data/bahrain.pmtiles';
const POI_URL = BASE + 'data/poi.json';
const META_URL = BASE + 'data/meta.json';
const DATA_CACHE = 'bm-data-v1';
const SHELL_CACHE_PREFIX = 'bm-shell-';
const BAHRAIN = { center: [50.555, 26.07], zoom: 9.4 };
const OSM_ATTR = '<a href="https://www.openstreetmap.org/copyright" target="_blank">© OpenStreetMap contributors (ODbL)</a> · <a href="https://protomaps.com" target="_blank">Protomaps</a>';
const SAT_ATTR = 'Imagery © <a href="https://www.esri.com" target="_blank">Esri</a>, Maxar, Earthstar Geographics';

const $ = (s) => document.querySelector(s);
const store = {
  get: (k, d) => { try { return localStorage.getItem('bm.' + k) ?? d; } catch { return d; } },
  set: (k, v) => { try { localStorage.setItem('bm.' + k, v); } catch {} },
};
let lang = store.get('lang', 'ar');
let theme = store.get('theme', matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light');
let base = 'map'; // satellite is never persisted: it needs internet
document.body.classList.toggle('dark', theme === 'dark');

// ---------- toast ----------
let toastT;
function toast(msg, ms = 2600) {
  const t = $('#toast'); t.textContent = msg; t.hidden = false;
  clearTimeout(toastT); toastT = setTimeout(() => (t.hidden = true), ms);
}

// ---------- PMTiles (network range requests until downloaded, then local Blob) ----------
class BlobSource {
  constructor(blob, key) { this.blob = blob; this.key = key; }
  getKey() { return this.key; }
  async getBytes(offset, length) { return { data: await this.blob.slice(offset, offset + length).arrayBuffer() }; }
}
const protocol = new pmtiles.Protocol();
maplibregl.addProtocol('pmtiles', protocol.tile);
let usingLocal = false;
async function cachedPmtiles() {
  if (!('caches' in window)) return null;
  try { const c = await caches.open(DATA_CACHE); const r = await c.match(PM_URL); return r ? await r.blob() : null; } catch { return null; }
}
async function useLocalBlob(blob) {
  protocol.add(new pmtiles.PMTiles(new BlobSource(blob, PM_URL)));
  usingLocal = true;
}

const bootBlob = await cachedPmtiles();
if (bootBlob) await useLocalBlob(bootBlob);

// ---------- style ----------
function firstSymbolIndex(layers) { const i = layers.findIndex((l) => l.type === 'symbol'); return i < 0 ? layers.length : i; }
function buildStyle() {
  const layers = basemaps.layers('protomaps', basemaps.namedFlavor(theme), { lang });
  const sat = { id: 'satellite', type: 'raster', source: 'esri', layout: { visibility: base === 'sat' ? 'visible' : 'none' } };
  layers.splice(firstSymbolIndex(layers), 0, sat);
  if (base === 'sat') for (const l of layers) if (l.type === 'symbol' && l.paint) { l.paint['text-halo-width'] = 1.6; }
  return {
    version: 8,
    glyphs: BASE + 'fonts/{fontstack}/{range}.pbf',
    sprite: BASE + 'sprites/' + theme,
    sources: {
      protomaps: { type: 'vector', url: 'pmtiles://' + PM_URL, attribution: OSM_ATTR },
      esri: { type: 'raster', tileSize: 256, maxzoom: 19, attribution: SAT_ATTR,
        tiles: ['https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}'] },
    },
    layers,
  };
}

// ---------- map ----------
let saved = null; try { saved = JSON.parse(store.get('view', 'null')); } catch {}
const map = new maplibregl.Map({
  container: 'map',
  style: buildStyle(),
  center: saved?.c || BAHRAIN.center,
  zoom: saved?.z ?? BAHRAIN.zoom,
  minZoom: 6,
  maxZoom: 19,
  maxBounds: [[49.4, 25.0], [51.7, 27.0]],
  attributionControl: false,
  dragRotate: true,
  pitchWithRotate: false,
  localIdeographFontFamily: 'sans-serif',
});
window.__map = map;
map.addControl(new maplibregl.AttributionControl({ compact: false }), 'bottom-right');
map.addControl(new maplibregl.ScaleControl({ unit: 'metric', maxWidth: 90 }), 'bottom-right');
map.touchZoomRotate.enableRotation();
map.on('moveend', () => { const c = map.getCenter(); store.set('view', JSON.stringify({ c: [c.lng, c.lat], z: map.getZoom() })); });
map.on('rotate', () => { const b = map.getBearing(); $('#northbtn').hidden = Math.abs(b) < 1; $('#northic').style.transform = `rotate(${-b}deg)`; });
$('#northbtn').onclick = () => { compassOn = false; map.easeTo({ bearing: 0, duration: 400 }); refreshGpsBtn(); };

function applyStyle() {
  document.body.classList.toggle('dark', theme === 'dark');
  map.setStyle(buildStyle());
  document.querySelector('meta[name=theme-color]').content = theme === 'dark' ? '#1f2227' : '#0e7490';
}

// ---------- GPS ----------
const geo = new maplibregl.GeolocateControl({
  positionOptions: { enableHighAccuracy: true, timeout: 15000, maximumAge: 5000 },
  trackUserLocation: true, showUserHeading: true, showAccuracyCircle: true,
  fitBoundsOptions: { maxZoom: 16.5 },
});
map.addControl(geo, 'bottom-right');
let gpsState = 'off'; // off | follow | background
let compassOn = false; let compassHeading = null;
window.__gps = () => ({ gpsState, compassOn });
function refreshGpsBtn() {
  const b = $('#gpsbtn');
  b.classList.toggle('on', gpsState !== 'off');
  b.classList.toggle('follow', gpsState === 'follow');
  b.setAttribute('aria-pressed', gpsState !== 'off');
}
geo.on('trackuserlocationstart', () => { gpsState = 'follow'; refreshGpsBtn(); });
geo.on('trackuserlocationend', () => { gpsState = 'background'; compassOn = false; refreshGpsBtn(); });
geo.on('geolocate', (p) => { if (gpsState === 'off') gpsState = 'follow'; window.__lastFix = [p.coords.longitude, p.coords.latitude]; refreshGpsBtn(); });
geo.on('error', (e) => {
  gpsState = 'off'; refreshGpsBtn();
  toast(e.code === 1 ? 'اسمح للتطبيق بالموقع: الإعدادات ← الخصوصية ← خدمات الموقع ← Safari' : 'تعذّر تحديد موقعك، حاول مرة ثانية');
});
function onOrientation(ev) {
  const h = ev.webkitCompassHeading ?? (ev.absolute && ev.alpha != null ? 360 - ev.alpha : null);
  if (h == null) return; compassHeading = h;
  if (compassOn && gpsState === 'follow') map.rotateTo(h, { duration: 150 });
}
let orientationAsked = false;
async function askOrientation() {
  if (orientationAsked) return; orientationAsked = true;
  try {
    if (typeof DeviceOrientationEvent !== 'undefined' && typeof DeviceOrientationEvent.requestPermission === 'function') {
      const r = await DeviceOrientationEvent.requestPermission(); if (r !== 'granted') return;
    }
    addEventListener('deviceorientation', onOrientation, true);
    addEventListener('deviceorientationabsolute', onOrientation, true);
  } catch {}
}
$('#gpsbtn').onclick = () => {
  askOrientation();
  if (gpsState === 'follow' && !compassOn && compassHeading != null) { compassOn = true; toast('وضع البوصلة: الخريطة تدور مع اتجاهك'); refreshGpsBtn(); return; }
  const prev = gpsState;
  if (prev === 'follow') { compassOn = false; map.easeTo({ bearing: 0 }); }
  geo.trigger();
  if (prev === 'follow') { /* trigger() turns tracking off */ setTimeout(() => { gpsState = 'off'; refreshGpsBtn(); }, 0); }
};

// ---------- pins, long-press ----------
let pin = null;
function pinEl() {
  const d = document.createElement('div');
  d.innerHTML = '<svg class="pin" viewBox="0 0 30 40"><path d="M15 39s13-13.2 13-23.5A13 13 0 0 0 2 15.5C2 25.8 15 39 15 39Z" fill="#e63946" stroke="#fff" stroke-width="2"/><circle cx="15" cy="15.5" r="5" fill="#fff"/></svg>';
  return d;
}
function dropPin(lngLat, title, sub) {
  if (pin) pin.remove();
  pin = new maplibregl.Marker({ element: pinEl(), anchor: 'bottom' }).setLngLat(lngLat).addTo(map);
  showPlaceSheet(lngLat, title, sub);
}
const fmt = (v) => v.toFixed(6);
function showPlaceSheet(ll, title, sub) {
  const lat = fmt(ll.lat), lng = fmt(ll.lng); const txt = `${lat}, ${lng}`;
  const g = `https://www.google.com/maps/search/?api=1&query=${lat},${lng}`;
  const a = `https://maps.apple.com/?ll=${lat},${lng}&q=${encodeURIComponent(title || 'نقطة')}`;
  const body = $('#sheetbody');
  body.innerHTML = '';
  const h = document.createElement('h3'); h.textContent = title || 'نقطة محددة'; body.append(h);
  if (sub) { const s = document.createElement('div'); s.className = 'note'; s.textContent = sub; body.append(s); }
  const c = document.createElement('div'); c.className = 'coords'; c.id = 'coordtext'; c.textContent = txt; body.append(c);
  const grid = document.createElement('div'); grid.className = 'btngrid';
  grid.innerHTML = `<button id="b-copy">نسخ الإحداثيات</button><button id="b-share">مشاركة</button>
  <a href="${g}" target="_blank" rel="noopener">Google Maps</a><a href="${a}" target="_blank" rel="noopener">Apple Maps</a>
  <button id="b-remove" class="wide">إزالة الدبوس</button>`;
  body.append(grid);
  $('#b-copy').onclick = () => copyText(txt);
  $('#b-share').onclick = async () => {
    const data = { title: title || 'موقع في البحرين', text: `${title ? title + '\n' : ''}${txt}\n${g}` };
    if (navigator.share) { try { await navigator.share(data); } catch {} } else copyText(data.text);
  };
  $('#b-remove').onclick = () => { if (pin) pin.remove(); pin = null; closeSheets(); };
  openSheet('#sheet');
}
async function copyText(t) {
  try { await navigator.clipboard.writeText(t); toast('تم النسخ ✓'); return; } catch {}
  const ta = document.createElement('textarea'); ta.value = t; ta.setAttribute('readonly', ''); ta.style.position = 'fixed'; ta.style.opacity = '0';
  document.body.append(ta); ta.select(); ta.setSelectionRange(0, 99999);
  try { document.execCommand('copy'); toast('تم النسخ ✓'); } catch { toast(t, 5000); }
  ta.remove();
}
let lpTimer = null, lpStart = null, lpAt = 0;
map.on('touchstart', (e) => {
  clearTimeout(lpTimer);
  if (e.points.length !== 1) return;
  lpStart = e.point; const ll = e.lngLat;
  lpTimer = setTimeout(() => { lpAt = Date.now(); navigator.vibrate?.(30); dropPin(ll, 'نقطة محددة', 'ضغطة مطوّلة'); }, 550);
});
map.on('touchmove', (e) => { if (lpStart && (Math.abs(e.point.x - lpStart.x) > 10 || Math.abs(e.point.y - lpStart.y) > 10)) clearTimeout(lpTimer); });
map.on('touchend', () => clearTimeout(lpTimer));
map.on('touchcancel', () => clearTimeout(lpTimer));
map.on('movestart', (e) => { if (e.originalEvent && e.originalEvent.touches?.length > 1) clearTimeout(lpTimer); });
map.on('contextmenu', (e) => dropPin(e.lngLat, 'نقطة محددة', null));
map.on('click', () => { if (Date.now() - lpAt < 1500) return; closeSheets(); hideResults(); $('#q').blur(); });

// ---------- sheets / menu ----------
function openSheet(sel) { closeSheets(); $(sel).hidden = false; }
function closeSheets() { $('#sheet').hidden = true; $('#menu').hidden = true; }
$('#menubtn').onclick = () => { hideResults(); syncSegs(); refreshOfflineStatus(); openSheet('#menu'); };
$('#layersbtn').onclick = () => { hideResults(); syncSegs(); refreshOfflineStatus(); openSheet('#menu'); };
$('#menuclose').onclick = closeSheets;
function syncSegs() {
  for (const [id, v] of [['#langseg', lang], ['#themeseg', theme], ['#baseseg', base]])
    for (const b of document.querySelectorAll(id + ' button')) b.classList.toggle('on', b.dataset.v === v);
}
$('#langseg').onclick = (e) => { const v = e.target.dataset?.v; if (!v || v === lang) return; lang = v; store.set('lang', v); syncSegs(); applyStyle(); };
$('#themeseg').onclick = (e) => { const v = e.target.dataset?.v; if (!v || v === theme) return; theme = v; store.set('theme', v); syncSegs(); applyStyle(); };
$('#baseseg').onclick = (e) => {
  const v = e.target.dataset?.v; if (!v || v === base) return;
  if (v === 'sat' && !navigator.onLine) { toast('القمر الصناعي يحتاج إنترنت — أنت الآن بدون اتصال'); return; }
  base = v; syncSegs(); applyStyle(); updateSatBadge();
};
function updateSatBadge() {
  let b = $('.satbadge');
  if (base === 'sat') { if (!b) { b = document.createElement('div'); b.className = 'satbadge'; document.body.append(b); } b.textContent = navigator.onLine ? 'قمر صناعي · يحتاج إنترنت' : 'قمر صناعي غير متاح بدون إنترنت'; }
  else b?.remove();
}
addEventListener('online', updateSatBadge); addEventListener('offline', updateSatBadge);

// ---------- search ----------
let POI = null, poiLoading = null;
const AR_KIND = { neighbourhood: 'حي / منطقة', macrohood: 'منطقة', locality: 'مدينة / قرية', region: 'محافظة', country: 'دولة', street: 'شارع',
  restaurant: 'مطعم', cafe: 'مقهى', fast_food: 'وجبات سريعة', hospital: 'مستشفى', clinic: 'عيادة', doctors: 'عيادة', dentist: 'طبيب أسنان', pharmacy: 'صيدلية',
  school: 'مدرسة', university: 'جامعة', college: 'كلية', kindergarten: 'روضة', place_of_worship: 'مسجد / دار عبادة', fuel: 'محطة وقود', mall: 'مجمع تجاري',
  supermarket: 'سوبرماركت', convenience: 'بقالة', hotel: 'فندق', bank: 'بنك', atm: 'صراف آلي', park: 'حديقة', beach: 'شاطئ', aerodrome: 'مطار',
  museum: 'متحف', stadium: 'ملعب', marina: 'مرسى', police: 'شرطة', fire_station: 'إطفاء', post_office: 'بريد', townhall: 'جهة حكومية', bakery: 'مخبز',
  clothes: 'ملابس', electronics: 'إلكترونيات', mobile_phone: 'هواتف', car_repair: 'تصليح سيارات', car: 'معرض سيارات', laundry: 'مغسلة', beauty: 'تجميل',
  hairdresser: 'حلاق / صالون', tailor: 'خياط', furniture: 'أثاث', attraction: 'معلم', bus_stop: 'موقف باص', ferry_terminal: 'مرسى عبّارات', island: 'جزيرة',
  golf_course: 'ملعب غولف', zoo: 'حديقة حيوانات', library: 'مكتبة', cinema: 'سينما', gym: 'نادي رياضي', sports_centre: 'مركز رياضي', embassy: 'سفارة', yes: 'مبنى' };
const RANK = { country: 0, region: 0, locality: 0, neighbourhood: 1, macrohood: 1, island: 1, street: 4 };
function norm(s) {
  return (s || '').toLowerCase()
    .replace(/[\u064B-\u065F\u0670\u0640]/g, '').replace(/[أإآٱ]/g, 'ا').replace(/ة/g, 'ه').replace(/ى/g, 'ي')
    .replace(/ؤ/g, 'و').replace(/ئ/g, 'ي').replace(/[٠-٩]/g, (d) => '٠١٢٣٤٥٦٧٨٩'.indexOf(d))
    .replace(/[^\p{L}\p{N}]+/gu, ' ').trim();
}
const stripAl = (s) => s.split(' ').map((w) => (w.length > 3 && w.startsWith('ال') ? w.slice(2) : w)).join(' ');
async function loadPoi() {
  if (POI) return POI;
  poiLoading ||= fetch(POI_URL).then((r) => r.json()).then((arr) => {
    POI = arr.map(([a, e, k, x, y]) => { const na = norm(a), ne = norm(e); return { a, e, k, x, y, h: `${na} ${stripAl(na)} ${ne}`, r: RANK[k] ?? 2 }; });
    return POI;
  });
  return poiLoading;
}
function search(q) {
  const nq = norm(q); if (!nq) return [];
  const nq2 = stripAl(nq); const words = nq2.split(' ');
  const out = [];
  for (const p of POI) {
    let s;
    const i = p.h.indexOf(nq), i2 = i < 0 ? p.h.indexOf(nq2) : i;
    if (i2 === 0) s = 0;
    else if (i2 > 0) s = p.h[i2 - 1] === ' ' ? 1 : 2;
    else if (words.length > 1 && words.every((w) => p.h.includes(w))) s = 3;
    else continue;
    out.push([s * 10 + p.r, (p.a || p.e).length, p]);
  }
  out.sort((x, y) => x[0] - y[0] || x[1] - y[1]);
  // drop duplicate names close to each other
  const seen = new Set(); const res = [];
  for (const [, , p] of out) { const key = (p.a || p.e) + '|' + p.k; if (seen.has(key)) continue; seen.add(key); res.push(p); if (res.length >= 40) break; }
  return res;
}
const nameOf = (p) => (lang === 'en' ? p.e || p.a : p.a || p.e);
const subOf = (p) => { const other = lang === 'en' ? p.a : p.e; const k = lang === 'en' ? p.k.replaceAll('_', ' ') : AR_KIND[p.k] || p.k.replaceAll('_', ' '); return other && other !== nameOf(p) ? `${k} · ${other}` : k; };
function hideResults() { $('#results').hidden = true; }
let qT;
$('#q').addEventListener('input', () => { $('#qclear').hidden = !$('#q').value; clearTimeout(qT); qT = setTimeout(runSearch, 120); });
$('#q').addEventListener('focus', () => { closeSheets(); loadPoi(); if ($('#q').value) runSearch(); });
$('#q').addEventListener('keydown', (e) => { if (e.key === 'Enter') { const f = $('#results li[data-i]'); if (f) f.click(); } });
$('#qclear').onclick = () => { $('#q').value = ''; $('#qclear').hidden = true; hideResults(); $('#q').focus(); };
async function runSearch() {
  const q = $('#q').value.trim(); const ul = $('#results');
  if (!q) { hideResults(); return; }
  await loadPoi();
  const res = search(q); ul.innerHTML = '';
  if (!res.length) { ul.innerHTML = '<li class="empty">ما في نتائج</li>'; ul.hidden = false; return; }
  res.forEach((p, i) => {
    const li = document.createElement('li'); li.dataset.i = i;
    const t = document.createElement('span'); t.className = 't'; t.textContent = nameOf(p);
    const s = document.createElement('span'); s.className = 's'; s.textContent = subOf(p);
    li.append(t, s);
    li.onclick = () => {
      hideResults(); $('#q').blur();
      const z = p.k === 'locality' ? 13 : p.k === 'neighbourhood' || p.k === 'macrohood' ? 14.5 : p.k === 'region' ? 11 : 16.5;
      map.flyTo({ center: [p.x, p.y], zoom: z, duration: 1200 });
      dropPin({ lng: p.x, lat: p.y }, nameOf(p), subOf(p));
    };
    ul.append(li);
  });
  ul.hidden = false;
}

// ---------- offline download ----------
const mb = (b) => (b / 1048576).toFixed(1) + ' ميغابايت';
let meta = null;
async function getMeta() {
  if (meta) return meta;
  try { meta = await (await fetch(META_URL, { cache: 'no-cache' })).json(); } catch {
    try { meta = await (await caches.match(META_URL)).json(); } catch { meta = null; }
  }
  return meta;
}
function setProgress(p, text) {
  for (const id of ['#offprog', '#offprog2']) $(id).style.width = Math.round(p * 100) + '%';
  if (text) { $('#offtext').textContent = text; }
}
let downloading = false;
async function downloadOffline(auto = false) {
  if (downloading) return; if (!('caches' in window)) { toast('المتصفح لا يدعم التخزين'); return; }
  if (!navigator.onLine) { toast('تحتاج إنترنت لأول تحميل'); return; }
  downloading = true; $('#dlbtn').disabled = true; $('#offlinebar').hidden = false;
  try {
    try { await navigator.storage?.persist?.(); } catch {}
    const m = await getMeta();
    const data = await caches.open(DATA_CACHE);
    // 1) app shell + fonts + sprites (the service worker also does this on install)
    setProgress(0.01, 'جاري تجهيز ملفات التطبيق…');
    const list = (self.PRECACHE || []).map((u) => new URL(u, BASE).href);
    const shellName = (await caches.keys()).find((k) => k.startsWith(SHELL_CACHE_PREFIX)) || DATA_CACHE;
    const shell = await caches.open(shellName);
    let done = 0;
    await Promise.all(list.map(async (u) => {
      if (!(await caches.match(u, { ignoreSearch: true }))) { const r = await fetch(u); if (r.ok) await shell.put(u, r); }
      done++; setProgress(0.01 + 0.09 * done / list.length);
    }));
    // 2) map data with progress
    const total = m?.pmtiles_size || 0;
    const res = await fetch(PM_URL, { cache: 'no-store' });
    if (!res.ok || !res.body) throw new Error('HTTP ' + res.status);
    const reader = res.body.getReader(); const chunks = []; let got = 0;
    for (;;) {
      const { done: d, value } = await reader.read(); if (d) break;
      chunks.push(value); got += value.length;
      setProgress(0.1 + 0.8 * (total ? Math.min(got / total, 1) : 0.5), `جاري تحميل خريطة البحرين… ${mb(got)}${total ? ' من ' + mb(total) : ''}`);
    }
    const blob = new Blob(chunks, { type: 'application/octet-stream' });
    if (total && blob.size !== total) throw new Error('size mismatch');
    await data.put(PM_URL, new Response(blob, { headers: { 'Content-Type': 'application/octet-stream', 'Content-Length': String(blob.size) } }));
    // 3) search index + meta
    setProgress(0.93, 'جاري تحميل فهرس البحث…');
    for (const u of [POI_URL, META_URL]) { const r = await fetch(u, { cache: 'no-store' }); if (r.ok) await data.put(u, r); }
    store.set('offlineVersion', m?.version || 'unknown');
    await useLocalBlob(blob);
    setProgress(1, 'جاهز ✓ الخريطة تعمل الآن بدون إنترنت');
    setTimeout(() => ($('#offlinebar').hidden = true), auto ? 2500 : 1500);
    if (!auto) toast('تم ✓ الخريطة محفوظة على جهازك');
  } catch (e) {
    console.error(e);
    $('#offtext').textContent = 'انقطع التحميل — اضغط «تحميل» من القائمة للمحاولة مرة ثانية';
    setTimeout(() => ($('#offlinebar').hidden = true), 5000);
  } finally {
    downloading = false; $('#dlbtn').disabled = false; refreshOfflineStatus();
  }
}
window.__downloadOffline = downloadOffline;
$('#dlbtn').onclick = () => downloadOffline(false);
async function refreshOfflineStatus() {
  const el = $('#offstatus'); const m = await getMeta();
  let stored = 0;
  try { const r = await (await caches.open(DATA_CACHE)).match(PM_URL); if (r) stored = (await r.blob()).size; } catch {}
  let usage = '';
  try { const est = await navigator.storage.estimate(); usage = ` · المساحة المستخدمة على الجهاز: ${mb(est.usage || 0)}`; } catch {}
  const date = m?.osm_date ? ` · بيانات بتاريخ ${m.osm_date}` : '';
  if (stored) {
    const outdated = m?.version && store.get('offlineVersion', '') !== m.version;
    el.textContent = `محفوظة على الجهاز ✓ (${mb(stored)})${date}${usage}` + (outdated ? ' — يوجد تحديث جديد' : '');
    $('#dlbtn').textContent = outdated ? 'تحديث الخريطة المحفوظة' : 'إعادة التحميل';
  } else {
    el.textContent = `غير محفوظة بعد. حجم التحميل: ${m ? mb(m.pmtiles_size + m.poi_size) : '~11 ميغابايت'}${date}`;
    $('#dlbtn').textContent = 'تحميل خريطة البحرين للاستخدام بدون إنترنت';
  }
  window.__offlineStored = stored;
}

// ---------- boot ----------
(async () => {
  const blob = bootBlob;
  if ('serviceWorker' in navigator) {
    try { await navigator.serviceWorker.register('sw.js'); } catch (e) { console.warn('SW', e); }
  }
  if (!blob && navigator.onLine) {
    await navigator.serviceWorker?.ready.catch(() => {});
    downloadOffline(true);
  } else if (blob && navigator.onLine) {
    const m = await getMeta(); if (m?.version && store.get('offlineVersion', '') !== m.version) toast('يوجد تحديث للخريطة — من القائمة اضغط «تحديث»', 4000);
  }
  window.__ready = true;
})();
