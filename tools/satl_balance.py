#!/usr/bin/env python3
"""Colour-balance Satellogic patches against the Sentinel-2 composite (removes the checkerboard of different passes).
For each 384 m patch: box-downsample to ~S2 resolution, compare to the S2 composite over the same footprint, fit per-band
gain/offset (mean + std matching, gain clamped), then write a VRT whose ComplexSources carry ScaleRatio/ScaleOffset.
Usage: python3 tools/satl_balance.py raw_satl raw_s2/plan3.json raw_s2/s2_composite.png"""
import json, math, os, re, subprocess, sys
import numpy as np
from PIL import Image
Image.MAX_IMAGE_PIXELS = None
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from tilekit import utm_inv
G = os.environ.get('GDAL_BIN', '/opt/data/cache/scratch/kafu_audit/pgenv/bin')
env = dict(os.environ, PROJ_DATA=G + '/../share/proj', GTIFF_SRS_SOURCE='EPSG')
raw, plan, comp = sys.argv[1:4]
g = json.load(open(plan))['grid']; te, res = g['te'], g['res']
s2 = np.asarray(Image.open(comp))  # H x W x 4 uint8 (~280 MB)
R = 6378137.0
def merc(lon, lat): return math.radians(lon) * R, math.log(math.tan(math.pi / 4 + math.radians(lat) / 2)) * R
idx = json.load(open(raw + '/index.json'))
landfrac = {}
samples = {}   # per patch: (patch 24x24x3, s2 24x24x3, land mask)
for i, r in enumerate(idx):
    E, N = map(int, r['region'].rstrip('/').split('region=')[1].split('_'))
    x0, y0 = merc(*utm_inv(E, N)); x1, y1 = merc(*utm_inv(E + 384, N - 384))
    px0, py0 = int(round((x0 - te[0]) / res)), int(round((te[3] - y0) / res))
    px1, py1 = int(round((x1 - te[0]) / res)), int(round((te[3] - y1) / res))
    if px0 < 0 or py0 < 0 or px1 > s2.shape[1] or py1 > s2.shape[0] or px1 - px0 < 8: continue
    ra = np.asarray(Image.fromarray(np.ascontiguousarray(s2[py0:py1, px0:px1])).resize((24, 24), Image.BOX)).astype(np.float32)
    pat = Image.open(r['file']).convert('RGB')
    pa = np.asarray(pat.resize((24, 24), Image.BOX)).astype(np.float32)
    ok = (ra[..., 3] > 250) & (pa.min(axis=2) > 3)
    s2land = (ra[..., 0] > 80) & (ra[..., 0] >= 0.95 * ra[..., 2])   # sand/urban: red >= blue; Gulf water is blue/teal
    land = ok & s2land & (pa.mean(axis=2) > 35)  # skip water (glint/haze differs per pass)
    samples[os.path.basename(r['file'])] = (r['capture'], pa[land], ra[..., :3][land])
    landfrac[os.path.basename(r['file'])] = float((s2land & (ra[..., 3] > 250)).mean())
    if i % 2000 == 0: print('sampled', i, flush=True)
del s2
def ratio(p, q):  # per band ratio of means S2 / Satellogic over the same land pixels
    return np.array([q[:, b].mean() / max(p[:, b].mean(), 1.0) for b in range(3)])
# Sentinel-2 is only the common yardstick: every pass is scaled to look like the biggest pass (native Satellogic look),
# i.e. gain = ratio(pass) / ratio(reference pass). Fixes brightness / colour-cast jumps between passes, keeps contrast.
pool = {}
for f, (c, p, q) in samples.items():
    if len(p): pool.setdefault(c, []).append((p, q))
cap_ratio = {}
for c, L in pool.items():
    p = np.concatenate([x[0] for x in L]); q = np.concatenate([x[1] for x in L])
    if len(p) >= 300: cap_ratio[c] = ratio(p, q)
ref = max(cap_ratio, key=lambda c: sum(len(x[0]) for x in pool[c]))
LOOK = np.array([1.12, 1.10, 1.06])   # gentle global brighten/warm of the (rather dark) VISUAL product
cap_fit = {c: (list(np.clip(r / cap_ratio[ref], 0.7, 1.45) * LOOK), [0.0, 0.0, 0.0]) for c, r in cap_ratio.items()}
gain_all = np.median([v[0] for v in cap_fit.values()], axis=0); off_all = [0.0, 0.0, 0.0]
print('reference pass', ref)
for c, v in sorted(cap_fit.items(), key=lambda kv: -len(pool[kv[0]]))[:10]: print('pass', c, [round(x, 2) for x in v[0]])
# per-patch: small extra gain (haze differences inside a pass), land-rich patches only, clamped +-12 %
fits = {}
for f, (c, p, q) in samples.items():
    g_ = cap_fit[c][0] if c in cap_fit else list(gain_all)
    g2 = list(g_)
    if len(p) >= 150 and c in cap_ratio:
        r = ratio(p, q)
        for b in range(3): g2[b] *= float(np.clip(r[b] / cap_ratio[c][b], 0.88, 1.12))
    fits[f] = (g2, [0.0, 0.0, 0.0])
cap_med = {c: v for c, v in cap_fit.items()}
# sea-only patches are dropped: the Sentinel-2 layer underneath shows the sea seamlessly, while 1 m sea patches from
# different passes (glint, haze) form a checkerboard. Keep patches with >= 8 % land (coast, islands, piers).
files = [r['file'] for r in idx if landfrac.get(os.path.basename(r['file']), 1.0) >= 0.08]
print('kept', len(files), 'of', len(idx), 'patches (sea-only dropped)', flush=True)
open(raw + '/files.txt', 'w').write('\n'.join(files))
json.dump([r for r in idx if r['file'] in set(files)], open(raw + '/index_kept.json', 'w'))
vrt = raw + '/mosaic.vrt'
subprocess.run([G + '/gdalbuildvrt', '-q', '-overwrite', '-b', '1', '-b', '2', '-b', '3', '-srcnodata', '0', '-vrtnodata', '0',
                '-input_file_list', raw + '/files.txt', vrt], env=env, check=True)
capof = {os.path.basename(r['file']): r['capture'] for r in idx}
x = open(vrt).read()
def sub(m):
    blk = m.group(0); f = os.path.basename(re.search(r'<SourceFilename[^>]*>([^<]+)<', blk).group(1))
    b = int(re.search(r'<SourceBand>(\d+)<', blk).group(1)) - 1
    fit = fits.get(f) or cap_med.get(capof.get(f))
    if not fit: return blk
    return blk.replace('</ComplexSource>', f'  <ScaleOffset>{fit[1][b]:.3f}</ScaleOffset>\n      <ScaleRatio>{fit[0][b]:.4f}</ScaleRatio>\n    </ComplexSource>')
x = re.sub(r'<ComplexSource>.*?</ComplexSource>', sub, x, flags=re.S)
open(vrt, 'w').write(x)
print('balanced', len(fits), 'of', len(idx), 'patches;', len(cap_fit), 'passes fitted')
