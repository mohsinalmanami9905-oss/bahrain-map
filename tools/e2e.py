#!/usr/bin/env python3
"""End-to-end test in iPhone-sized emulation. Usage: python3 tools/e2e.py <base_url> [shots_dir]"""
import json, os, sys, time
os.environ.pop('DISPLAY', None); os.environ.pop('WAYLAND_DISPLAY', None)  # headless GL via SwiftShader
from playwright.sync_api import sync_playwright

BASE = sys.argv[1] if len(sys.argv) > 1 else 'http://localhost:8765/'
SHOTS = sys.argv[2] if len(sys.argv) > 2 else os.path.join(os.path.dirname(__file__), '..', 'shots')
os.makedirs(SHOTS, exist_ok=True)
MANAMA = {'latitude': 26.2235, 'longitude': 50.5876, 'accuracy': 15}
results = []
def check(name, ok, info=''):
    results.append((name, bool(ok), info)); print(('PASS' if ok else 'FAIL'), name, info, flush=True)

def wait_idle(page, timeout=30000):
    page.wait_for_function("() => window.__map && window.__map.loaded() && window.__map.areTilesLoaded()", timeout=timeout)
    page.wait_for_timeout(700)

def rendered(page):
    return page.evaluate("""() => { const m = window.__map; const f = m.queryRenderedFeatures().filter(x => x.source === 'protomaps');
      const labels = f.filter(x => x.layer.type === 'symbol').map(x => (x.properties['name:ar'] || x.properties.name || ''));
      return {n: f.length, layers: [...new Set(f.map(x => x.sourceLayer))], ar: labels.filter(t => /[\\u0600-\\u06FF]/.test(t)).slice(0, 8), z: m.getZoom()}; }""")

with sync_playwright() as p:
    b = p.chromium.launch(executable_path=os.environ.get('CHROME', '/opt/hermes/tools/chromium-1208/chrome-linux64/chrome'), args=['--ozone-platform=headless', '--use-angle=swiftshader', '--enable-unsafe-swiftshader', '--ignore-gpu-blocklist'])
    ctx = b.new_context(viewport={'width': 390, 'height': 844}, device_scale_factor=2, is_mobile=True, has_touch=True,
                        locale='ar-BH', geolocation=MANAMA, permissions=['geolocation'],
                        user_agent='Mozilla/5.0 (iPhone; CPU iPhone OS 18_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/18.0 Mobile/15E148 Safari/604.1')
    page = ctx.new_page()
    errors = []
    page.on('pageerror', lambda e: errors.append(str(e)))
    page.on('console', lambda m: m.type == 'error' and errors.append('console: ' + m.text))
    t0 = time.time()
    page.goto(BASE, wait_until='load')
    wait_idle(page, 60000)
    check('map loads', True, f'{time.time()-t0:.1f}s')
    page.screenshot(path=f'{SHOTS}/01_open_bahrain.png')
    # offline download auto-starts on first open
    page.wait_for_function("() => window.__offlineStored > 0 || (document.querySelector('#offtext')?.textContent || '').includes('جاهز')", timeout=120000)
    page.screenshot(path=f'{SHOTS}/02_offline_ready.png')
    page.evaluate("() => { document.querySelector('#menubtn').click(); }"); page.wait_for_timeout(1200)
    st = page.inner_text('#offstatus')
    check('offline data stored', 'محفوظة' in st, st)
    page.screenshot(path=f'{SHOTS}/03_menu_offline_status.png')
    page.click('#menuclose')
    # Arabic labels in Manama
    page.evaluate("() => window.__map.jumpTo({center:[50.5800,26.2200], zoom:14})"); wait_idle(page)
    r = rendered(page)
    check('arabic labels rendered z14', len(r['ar']) > 0, json.dumps(r['ar'][:5], ensure_ascii=False))
    page.screenshot(path=f'{SHOTS}/04_manama_z14_arabic.png')
    # search Arabic
    page.click('#q'); page.fill('#q', 'السلمانيه'); page.wait_for_timeout(800); page.wait_for_selector('#results li[data-i]', timeout=10000)
    items = page.eval_on_selector_all('#results li[data-i] .t', 'els => els.slice(0,6).map(e => e.textContent)')
    check('search arabic (normalised ة/ه)', any('السلمانية' in i for i in items), json.dumps(items, ensure_ascii=False))
    page.screenshot(path=f'{SHOTS}/05_search_arabic.png')
    page.click('#results li[data-i]'); page.wait_for_timeout(1800); wait_idle(page)
    check('result opens place sheet', page.is_visible('#sheet') and page.is_visible('#coordtext'), page.inner_text('#coordtext'))
    page.screenshot(path=f'{SHOTS}/06_search_result_pin.png')
    # search English
    page.click('#q'); page.fill('#q', 'city centre'); page.wait_for_timeout(800); page.wait_for_selector('#results li[data-i]', timeout=10000)
    items = page.eval_on_selector_all('#results li[data-i] .t', 'els => els.slice(0,6).map(e => e.textContent)')
    check('search english', len(items) > 0, json.dumps(items, ensure_ascii=False))
    page.screenshot(path=f'{SHOTS}/07_search_english.png')
    page.click('#qclear'); page.keyboard.press('Escape'); page.evaluate("() => document.activeElement.blur()")
    page.evaluate("() => window.__map.jumpTo({center:[50.45,26.05], zoom:11})"); wait_idle(page)
    # GPS
    page.click('#gpsbtn')
    page.wait_for_function("() => window.__lastFix", timeout=20000); page.wait_for_timeout(2500); wait_idle(page)
    c = page.evaluate("() => { const c = window.__map.getCenter(); return [c.lng, c.lat, window.__map.getZoom(), window.__gps().gpsState]; }")
    check('GPS centres on mocked Manama fix', abs(c[0]-50.5876) < 0.01 and abs(c[1]-26.2235) < 0.01, str(c))
    check('GPS follow mode on', c[3] == 'follow', c[3])
    page.screenshot(path=f'{SHOTS}/08_gps_my_location.png')
    # long press -> pin with coordinates (real touch long-press via CDP)
    cdp = ctx.new_cdp_session(page)
    cdp.send('Input.dispatchTouchEvent', {'type': 'touchStart', 'touchPoints': [{'x': 200, 'y': 520}]})
    page.wait_for_timeout(900)
    cdp.send('Input.dispatchTouchEvent', {'type': 'touchEnd', 'touchPoints': []})
    page.wait_for_timeout(500)
    ok = page.is_visible('#sheet') and page.is_visible('#coordtext')
    check('long-press drops pin + coordinates', ok, page.inner_text('#coordtext') if ok else '')
    hrefs = page.eval_on_selector_all('#sheet:not([hidden]) a', 'els => els.map(e => e.href)')
    check('Google/Apple Maps links', any('google.com/maps' in h for h in hrefs) and any('maps.apple.com' in h for h in hrefs), hrefs[0][:70] if hrefs else '')
    page.screenshot(path=f'{SHOTS}/09_longpress_pin.png')
    page.click('#b-remove')
    # English labels toggle
    page.click('#gpsbtn'); page.wait_for_timeout(300)
    page.click('#menubtn'); page.click('#langseg button[data-v=en]'); page.click('#menuclose')
    page.evaluate("() => window.__map.jumpTo({center:[50.5800,26.2200], zoom:14, bearing:0})"); wait_idle(page)
    page.screenshot(path=f'{SHOTS}/10_english_labels.png')
    page.click('#menubtn'); page.click('#langseg button[data-v=ar]'); page.click('#themeseg button[data-v=dark]'); page.click('#menuclose')
    wait_idle(page); page.screenshot(path=f'{SHOTS}/11_dark_arabic.png')
    page.click('#menubtn'); page.click('#themeseg button[data-v=light]'); page.click('#baseseg button[data-v=esri]'); page.click('#menuclose')
    page.wait_for_timeout(4000)
    page.screenshot(path=f'{SHOTS}/12_esri_online.png')
    page.click('#menubtn'); page.click('#baseseg button[data-v=map]'); page.click('#menuclose')
    check('no page errors (online)', not [e for e in errors if 'arcgisonline' not in e], '; '.join(errors[:3]))
    # ---- OFFLINE ----
    errors.clear()
    ctx.set_offline(True)
    page.reload(wait_until='load')
    wait_idle(page, 60000)
    check('app shell loads offline', page.title() == 'خريطة البحرين', page.title())
    zooms = {}
    for z, ctr in [(8, [50.55, 26.05]), (10, [50.55, 26.1]), (12, [50.58, 26.21]), (14, [50.58, 26.22]), (16, [50.5866, 26.2285])]:
        page.evaluate(f"() => window.__map.jumpTo({{center:{ctr}, zoom:{z}}})"); wait_idle(page)
        r = rendered(page); zooms[z] = r['n']
        page.screenshot(path=f'{SHOTS}/13_offline_z{z:02d}.png')
        check(f'offline render z{z}', r['n'] > 0, f"features={r['n']} layers={r['layers']} ar={r['ar'][:3]}")
    page.click('#q'); page.fill('#q', 'مطار البحرين'); page.wait_for_timeout(800); page.wait_for_selector('#results li[data-i]', timeout=10000)
    items = page.eval_on_selector_all('#results li[data-i] .t', 'els => els.slice(0,4).map(e => e.textContent)')
    check('search works offline', len(items) > 0, json.dumps(items, ensure_ascii=False))
    page.screenshot(path=f'{SHOTS}/14_offline_search.png')
    page.click('#qclear'); page.evaluate("() => document.activeElement.blur()")
    page.click('#gpsbtn'); page.wait_for_timeout(2500)
    check('GPS works offline', page.evaluate("() => window.__gps().gpsState") == 'follow')
    page.screenshot(path=f'{SHOTS}/15_offline_gps.png')
    check('no page errors (offline)', not errors, '; '.join(errors[:3]))
    b.close()

fails = [r for r in results if not r[1]]
print(f'\n{len(results)-len(fails)}/{len(results)} passed')
json.dump([{'test': n, 'pass': ok, 'info': i} for n, ok, i in results], open(os.path.join(SHOTS, 'e2e_results.json'), 'w'), ensure_ascii=False, indent=1)
sys.exit(1 if fails else 0)
