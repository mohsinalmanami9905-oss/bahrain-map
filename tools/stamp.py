#!/usr/bin/env python3
"""Stamp a build: write app/data/meta.json and set the service-worker cache version."""
import hashlib, json, os, re, subprocess, sys, datetime
root = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'docs')
os.chdir(root)
exec(open('precache-list.js').read().replace('self.PRECACHE =', 'PRECACHE =').replace('//', '#', 1))
h = hashlib.sha256()
for f in ['sw.js'] + [p.replace('%20', ' ') for p in PRECACHE if p != './'] + ['data/bahrain.pmtiles', 'data/poi.json']:
    if f == 'sw.js':
        h.update(re.sub(r"const VERSION = '[^']*'", '', open(f).read()).encode())
    else:
        h.update(open(f, 'rb').read())
ver = h.hexdigest()[:10]
sw = open('sw.js').read()
sw = re.sub(r"const VERSION = '[^']*'", f"const VERSION = '{ver}'", sw)
open('sw.js', 'w').write(sw)
show = subprocess.run([os.path.join(root, '..', 'bin', 'pmtiles'), 'show', 'data/bahrain.pmtiles'], capture_output=True, text=True).stdout
m = re.search(r'osmosisreplicationtime (\d{4}-\d\d-\d\d)', show)
meta = {
    'version': hashlib.sha256(open('data/bahrain.pmtiles', 'rb').read()).hexdigest()[:10],
    'build': ver,
    'pmtiles_size': os.path.getsize('data/bahrain.pmtiles'),
    'poi_size': os.path.getsize('data/poi.json'),
    'osm_date': m.group(1) if m else datetime.date.today().isoformat(),
    'bbox': [50.20, 25.50, 50.90, 26.40], 'maxzoom': 15,
}
# offline satellite packs: s2.pmtiles (Sentinel-2 base) first, then hr-*.pmtiles (1 m Satellogic) on top
sat = sorted(f for f in os.listdir('data/sat') if f.endswith('.pmtiles')) if os.path.isdir('data/sat') else []
sat.sort(key=lambda f: (f != 's2.pmtiles', f))
if sat:
    files = [{'name': f, 'kind': 's2' if f == 's2.pmtiles' else 'hr', 'size': os.path.getsize('data/sat/' + f)} for f in sat]
    meta['sat'] = {'files': files, 'version': hashlib.sha256(json.dumps(files).encode()).hexdigest()[:10],
                   's2_date': '2026-09/11', 'hr_date': '2022'}
json.dump(meta, open('data/meta.json', 'w'))
print(json.dumps(meta))
