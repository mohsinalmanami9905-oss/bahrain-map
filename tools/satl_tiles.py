#!/usr/bin/env python3
"""Satellogic EarthView 1 m patches -> Web-Mercator WebP tiles z12..z17 -> MBTiles.
Usage: python3 tools/satl_tiles.py raw_satl out.mbtiles
Works per z12 block (4096 px at z17): gdalwarp the VRT mosaic for that block only, cut tiles, build lower zooms
from the same block. Peak RAM ~ 300 MB."""
import json, math, os, subprocess, sys
import numpy as np
from PIL import Image
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from tilekit import MBTiles, encode, tile_bounds_m, utm_inv
G = os.environ.get('GDAL_BIN', '/opt/data/cache/scratch/kafu_audit/pgenv/bin')
env = dict(os.environ, PROJ_DATA=G + '/../share/proj', GTIFF_SRS_SOURCE='EPSG', GDAL_CACHEMAX='200')
raw, out = sys.argv[1], sys.argv[2]
idx = json.load(open(raw + '/index_kept.json'))  # written by satl_balance.py (sea-only patches dropped)
files = [r['file'] for r in idx if os.path.exists(r['file'])]
vrt = raw + '/mosaic.vrt'  # built (and colour-balanced) by tools/satl_balance.py
# patch footprints -> z12 blocks to process (UTM 39N upper-left corners, 384 m)
def tile_of(lon, lat, z):
    n = 2 ** z; return int((lon + 180) / 360 * n), int((1 - math.asinh(math.tan(math.radians(lat))) / math.pi) / 2 * n)
blocks = set()
for r in idx:
    E, N = map(int, r['region'].rstrip('/').split('region=')[1].split('_'))
    for dx in (0, 384):
        for dy in (0, -384):
            blocks.add(tile_of(*utm_inv(E + dx, N + dy), 12))
blocks = sorted(blocks)
print('patches', len(files), 'z12 blocks', len(blocks), flush=True)
lo, la = zip(*[utm_inv(*map(int, r['region'].rstrip('/').split('region=')[1].split('_'))) for r in idx])
mb = MBTiles(out, {'name': 'Bahrain 1 m (Satellogic EarthView)', 'format': 'webp', 'type': 'overlay', 'minzoom': 12, 'maxzoom': 17,
                   'bounds': '%.5f,%.5f,%.5f,%.5f' % (min(lo), min(la) - 0.004, max(lo) + 0.004, max(la)),
                   'attribution': 'Satellogic EarthView, CC BY 4.0', 'description': '1 m Satellogic Mark IV imagery, 2022'})
S = 4096; tmp = raw + '/block.tif'
for bi, (bx, by) in enumerate(blocks):
    z13img = {}
    for qy in range(2):
        for qx in range(2):  # each z13 quadrant = 4096 px at true z17 resolution (1.19 m/px)
            X13, Y13 = bx * 2 + qx, by * 2 + qy
            xmin, ymin, xmax, ymax = tile_bounds_m(13, X13, Y13)
            subprocess.run([G + '/gdalwarp', '-q', '-overwrite', '-of', 'GTiff', '-co', 'COMPRESS=NONE', '-t_srs', 'EPSG:3857',
                            '-te', str(xmin), str(ymin), str(xmax), str(ymax), '-ts', str(S), str(S), '-r', 'cubic', '-dstalpha',
                            '-wm', '200', vrt, tmp], env=env, check=True)
            img = Image.open(tmp); img.load()
            if img.getchannel('A').getextrema()[1] == 0: continue
            for z in range(17, 12, -1):
                k = 2 ** (z - 13)
                for ty in range(k):
                    for tx in range(k):
                        d = encode(img.crop((tx * 256, ty * 256, tx * 256 + 256, ty * 256 + 256)), 72)
                        if d: mb.put(z, X13 * k + tx, Y13 * k + ty, d)
                img = img.convert('RGBa').reduce(2).convert('RGBA')  # premultiplied: no dark fringes
            z13img[qx, qy] = img  # 128 px (the z13 tile halved) -> goes into the z12 tile
    if z13img:
        t12 = Image.new('RGBA', (256, 256), (0, 0, 0, 0))
        for (qx, qy), im in z13img.items(): t12.paste(im, (qx * 128, qy * 128))
        d = encode(t12, 72)
        if d: mb.put(12, bx, by, d)
    print('block', bi + 1, '/', len(blocks), 'tiles', mb.n, 'MB', round(mb.bytes / 1e6, 1), flush=True)
mb.close()
for f in (tmp, tmp + '.aux.xml'):
    if os.path.exists(f): os.remove(f)
print('done', mb.n, 'tiles', round(mb.bytes / 1e6, 1), 'MB')
