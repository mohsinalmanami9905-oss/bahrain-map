#!/usr/bin/env python3
"""Cloud-free Sentinel-2 true-colour composite (per-pixel median of the warped dates) -> WebP tiles z6..z14 -> MBTiles.
Usage: python3 tools/s2_tiles.py raw_s2/plan3.json raw_s2 out.mbtiles
Low-RAM: bands are converted to raw files and memory-mapped; the composite is built in row strips."""
import json, os, subprocess, sys
import numpy as np
from PIL import Image
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from tilekit import MBTiles, encode
G = os.environ.get('GDAL_BIN', '/opt/data/cache/scratch/kafu_audit/pgenv/bin')
env = dict(os.environ, PROJ_DATA=G + '/../share/proj', GTIFF_SRS_SOURCE='EPSG')
plan = json.load(open(sys.argv[1])); raw = sys.argv[2]; out = sys.argv[3]
g = plan['grid']; X0, Y0 = g['x0'], g['y0']; W, H = (g['x1'] - g['x0']) * 256, (g['y1'] - g['y0']) * 256
dates = sorted({k.split('_')[2] for k in plan['items']}, reverse=True)
mm = {}
for d in dates:
    for b in ['red', 'green', 'blue']:
        src, dst = f'{raw}/{d}.{b}.tif', f'{raw}/{d}.{b}.raw'
        if not os.path.exists(dst):
            subprocess.run([G + '/gdal_translate', '-q', '-of', 'ENVI', src, dst], env=env, check=True)
        mm[d, b] = np.memmap(dst, dtype='<u2', mode='r', shape=(H, W))
# --- composite: median of valid observations; reflectance = DN / 10000 (Earth Search already applied the BOA offset)
rgb = np.zeros((H, W, 4), np.uint8)
LO, HI, GAMMA = 0.0, 0.50, 1 / 1.9    # tuned for bright desert + dark Gulf water
STEP = 512
for y in range(0, H, STEP):
    sl = slice(y, min(H, y + STEP))
    for i, b in enumerate(['red', 'green', 'blue']):
        stack = np.stack([mm[d, b][sl].astype(np.float32) for d in dates])
        stack[stack == 0] = np.nan
        with np.errstate(all='ignore'):
            v = np.nanmedian(stack, axis=0) / 10000  # Earth Search COGs: boa_offset_applied=true
        valid = ~np.isnan(v)
        v = np.clip((np.nan_to_num(v) - LO) / (HI - LO), 0, 1) ** GAMMA
        rgb[sl, :, i] = (v * 255 + 0.5).astype(np.uint8)
        if i == 0: rgb[sl, :, 3] = np.where(valid, 255, 0)
    print('composite rows', y, flush=True)
img = Image.fromarray(rgb, 'RGBA'); del rgb
img.save(raw + '/s2_composite.png')  # for visual QA
bounds = [50.2, 25.5, 50.9, 26.4]
mb = MBTiles(out, {'name': 'Bahrain Sentinel-2 composite', 'format': 'webp', 'type': 'baselayer', 'minzoom': 6, 'maxzoom': 14,
                   'bounds': '%.4f,%.4f,%.4f,%.4f' % (49.95, 25.2, 51.1, 27.1),
                   'attribution': 'Contains modified Copernicus Sentinel data 2026 (ESA)', 'description': 'Median of Sentinel-2 L2A Sep-Nov 2026'})
# --- pyramid. ox, oy = pixel position of the image's top-left in the zoom-z global pixel grid
ox, oy = X0 * 256, Y0 * 256
for z in range(14, 5, -1):
    w, h = img.size
    tx0, ty0, tx1, ty1 = ox // 256, oy // 256, (ox + w - 1) // 256, (oy + h - 1) // 256
    n = 0
    for ty in range(ty0, ty1 + 1):
        for tx in range(tx0, tx1 + 1):
            tile = Image.new('RGBA', (256, 256), (0, 0, 0, 0))
            tile.paste(img.crop((tx * 256 - ox, ty * 256 - oy, tx * 256 - ox + 256, ty * 256 - oy + 256)), (0, 0))
            data = encode(tile, 80)
            if data: mb.put(z, tx, ty, data); n += 1
    print('z', z, 'tiles', n, 'MB', round(mb.bytes / 1e6, 1), flush=True)
    # next zoom: pad to even origin then halve
    px, py = ox % 2, oy % 2
    if px or py or w % 2 or h % 2:
        nw, nh = w + px + ((w + px) % 2), h + py + ((h + py) % 2)
        pad = Image.new('RGBA', (nw, nh), (0, 0, 0, 0)); pad.paste(img, (px, py)); img = pad
    img = img.reduce(2); ox, oy = (ox - px) // 2, (oy - py) // 2
mb.close()
print('done', mb.n, 'tiles', round(mb.bytes / 1e6, 1), 'MB')
