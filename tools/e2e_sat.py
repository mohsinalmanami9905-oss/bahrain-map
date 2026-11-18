#!/usr/bin/env python3
"""E2E for the offline satellite layer (iPhone-sized emulation).
Usage: python3 tools/e2e_sat.py <base_url> [shots_dir]
Online: auto map download, then 'download satellite' with progress; switch to satellite; go offline + reload;
check imagery renders at many zooms (S2 everywhere, 1 m in the north/Hawar), labels toggle, Esri blocked offline."""
import io, json, os, sys, time
os.environ.pop('DISPLAY', None); os.environ.pop('WAYLAND_DISPLAY', None)
from playwright.sync_api import sync_playwright
from PIL import Image, ImageStat

BASE = sys.argv[1] if len(sys.argv) > 1 else 'http://localhost:8765/'
SHOTS = sys.argv[2] if len(sys.argv) > 2 else os.path.join(os.path.dirname(__file__), '..', 'shots_sat')
os.makedirs(SHOTS, exist_ok=True)
results = []
def check(name, ok, info=''):
    results.append((name, bool(ok), info)); print(('PASS' if ok else 'FAIL'), name, info, flush=True)
def wait_idle(page, timeout=60000):
    page.wait_for_function("() => window.__map && window.__map.loaded() && window.__map.areTilesLoaded()", timeout=timeout)
    page.wait_for_timeout(900)
def shot(page, name):
    path = f'{SHOTS}/{name}.png'; png = page.screenshot(path=path)
    im = Image.open(io.BytesIO(png)).convert('L').crop((60, 300, 720, 1300))  # map middle, away from UI
    return path, ImageStat.Stat(im).stddev[0]
def sat_tiles(page):
    # count raster tiles MapLibre holds for our offline imagery sources
    return page.evaluate("""() => { const m = window.__map; const out = {};
      for (const id of Object.keys(m.getStyle().sources)) if (id.startsWith('sat-')) {
        const sc = (m.style.tileManagers || m.style.sourceCaches || {})[id];
        const it = sc && (sc._inViewTiles || sc._tiles); let tiles = [];
        if (it) tiles = it._tiles ? Object.values(it._tiles) : (it instanceof Map ? [...it.values()] : (typeof it.getAllTiles === 'function' ? it.getAllTiles() : Object.values(it)));
        out[id] = tiles.filter(t => t.state === 'loaded' && (t.texture || t.image)).length; }
      return out; }""")

with sync_playwright() as p:
    b = p.chromium.launch(executable_path=os.environ.get('CHROME', '/opt/hermes/tools/chromium-1208/chrome-linux64/chrome'), args=['--ozone-platform=headless', '--use-angle=swiftshader', '--enable-unsafe-swiftshader', '--ignore-gpu-blocklist'])
    ctx = b.new_context(viewport={'width': 390, 'height': 844}, device_scale_factor=2, is_mobile=True, has_touch=True, locale='ar-BH',
                        user_agent='Mozilla/5.0 (iPhone; CPU iPhone OS 18_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/18.0 Mobile/15E148 Safari/604.1')
    page = ctx.new_page(); errors = []
    page.on('pageerror', lambda e: errors.append(str(e)))
    page.on('console', lambda m: m.type == 'error' and errors.append('console: ' + m.text))
    page.goto(BASE, wait_until='load'); wait_idle(page)
    page.wait_for_function("() => window.__offlineStored > 0", timeout=180000)
    check('vector map stored offline', True)
    page.click('#menubtn'); page.wait_for_timeout(1500)
    st = page.inner_text('#satstatus'); bt = page.inner_text('#satdlbtn')
    check('satellite pack status + size shown', 'Sentinel-2' in st and 'ميغابايت' in bt, st + ' | ' + bt)
    page.screenshot(path=f'{SHOTS}/01_menu_before_sat_download.png')
    t0 = time.time()
    page.click('#satdlbtn')
    page.wait_for_function("() => parseFloat(document.querySelector('#satprog').style.width) > 5", timeout=120000)
    page.screenshot(path=f'{SHOTS}/02_sat_download_progress.png')
    page.wait_for_function("() => document.querySelector('#satstatus').textContent.includes('محفوظة على الجهاز')", timeout=1500000)
    check('satellite pack downloaded', True, f'{time.time()-t0:.0f}s · ' + page.inner_text('#satstatus'))
    page.screenshot(path=f'{SHOTS}/03_menu_sat_saved.png')
    page.click('#baseseg button[data-v=sat]'); page.click('#menuclose')
    # ---- OFFLINE ----
    errors.clear(); ctx.set_offline(True)
    page.reload(wait_until='load'); wait_idle(page)
    check('satellite base persisted after reload', page.evaluate("() => window.__map.getLayoutProperty('sat-0','visibility')") == 'visible')
    views = [('north_manama_z12', [50.58, 26.21], 12), ('manama_z15_1m', [50.5866, 26.2285], 15), ('manama_z17_1m', [50.5795, 26.2302], 17),
             ('muharraq_z16_1m', [50.615, 26.258], 16), ('seef_z18_overzoom', [50.532, 26.236], 18), ('south_desert_z13_s2', [50.55, 25.9], 13),
             ('south_z15_s2_overzoom', [50.6, 25.85], 15), ('hawar_z15', [50.77, 25.65], 15), ('bahrain_z9', [50.55, 26.05], 9)]
    for name, c, z in views:
        page.evaluate(f"() => window.__map.jumpTo({{center:{c}, zoom:{z}, bearing:0}})"); wait_idle(page)
        path, sd = shot(page, 'offline_' + name); t = sat_tiles(page)
        check(f'offline imagery {name}', sum(t.values()) > 0 and sd > 12, f'tiles={t} texture_sd={sd:.1f}')
    page.click('#menubtn'); page.click('#labelseg button[data-v="0"]'); page.click('#menuclose')
    page.evaluate("() => window.__map.jumpTo({center:[50.5866,26.2285], zoom:15})"); wait_idle(page)
    nsym = page.evaluate("() => window.__map.getStyle().layers.filter(l => l.type === 'symbol').length")
    shot(page, 'offline_labels_hidden'); check('labels toggle off', nsym == 0, f'symbol layers={nsym}')
    page.click('#menubtn'); page.click('#labelseg button[data-v="1"]'); page.click('#menuclose'); wait_idle(page)
    nsym = page.evaluate("() => window.__map.getStyle().layers.filter(l => l.type === 'symbol').length")
    shot(page, 'offline_labels_shown'); check('labels toggle on', nsym > 0, f'symbol layers={nsym}')
    page.click('#menubtn'); page.click('#baseseg button[data-v=esri]'); page.wait_for_timeout(400)
    check('Esri refused offline with message', 'Esri' in page.inner_text('#toast'), page.inner_text('#toast'))
    page.click('#menuclose')
    check('no page errors (offline)', not errors, '; '.join(errors[:3]))
    # ---- back online: Esri option still works ----
    ctx.set_offline(False); page.wait_for_timeout(500)
    page.click('#menubtn'); page.click('#baseseg button[data-v=esri]'); page.click('#menuclose')
    page.evaluate("() => window.__map.jumpTo({center:[50.5866,26.2285], zoom:16})"); page.wait_for_timeout(5000)
    shot(page, 'online_esri_option'); check('Esri online option visible', page.evaluate("() => window.__map.getLayoutProperty('satellite','visibility')") == 'visible')
    b.close()
fails = [r for r in results if not r[1]]
print(f'\n{len(results)-len(fails)}/{len(results)} passed')
json.dump([{'test': n, 'pass': ok, 'info': i} for n, ok, i in results], open(os.path.join(SHOTS, 'e2e_sat_results.json'), 'w'), ensure_ascii=False, indent=1)
sys.exit(1 if fails else 0)
