#!/usr/bin/env python3
"""Split an MBTiles (z>=12) into parts < LIMIT bytes, by z12 block (every tile z>=12 belongs to one z12 block),
so each part has tight bounds and fits GitHub's 100 MB file limit. Then convert each part to PMTiles.
Usage: python3 tools/split_mbtiles.py in.mbtiles out_dir prefix [limit_mb]"""
import math, os, sqlite3, subprocess, sys
src, out_dir, prefix = sys.argv[1:4]; LIMIT = float(sys.argv[4] if len(sys.argv) > 4 else 90) * 1e6
os.makedirs(out_dir, exist_ok=True)
db = sqlite3.connect(src)
meta = dict(db.execute('SELECT name, value FROM metadata'))
blocks = {}
for z, x, row, n in db.execute('SELECT zoom_level, tile_column, tile_row, length(tile_data) FROM tiles'):
    y = (2 ** z - 1) - row; k = (x >> (z - 12), y >> (z - 12)); blocks[k] = blocks.get(k, 0) + n
order = sorted(blocks)  # west->east, north->south columns: compact strips
parts, cur, size = [], [], 0
for k in order:
    if cur and size + blocks[k] > LIMIT: parts.append(cur); cur, size = [], 0
    cur.append(k); size += blocks[k]
if cur: parts.append(cur)
def lon(x, z): return x / 2 ** z * 360 - 180
def lat(y, z): return math.degrees(math.atan(math.sinh(math.pi * (1 - 2 * y / 2 ** z))))
root = os.path.dirname(os.path.abspath(__file__))
for i, bl in enumerate(parts):
    name = f'{prefix}-{i + 1}'; mbp = os.path.join(out_dir, name + '.mbtiles')
    if os.path.exists(mbp): os.remove(mbp)
    o = sqlite3.connect(mbp)
    o.executescript('CREATE TABLE metadata (name text, value text); CREATE TABLE tiles (zoom_level integer, tile_column integer, tile_row integer, tile_data blob);'
                    'CREATE UNIQUE INDEX tile_index on tiles (zoom_level, tile_column, tile_row);')
    xs = [b[0] for b in bl]; ys = [b[1] for b in bl]
    m = dict(meta, bounds='%.5f,%.5f,%.5f,%.5f' % (lon(min(xs), 12), lat(max(ys) + 1, 12), lon(max(xs) + 1, 12), lat(min(ys), 12)))
    o.executemany('INSERT INTO metadata VALUES (?,?)', m.items())
    sel = set(bl)
    for z in range(12, 18):
        rows = []
        for x, row, d in db.execute('SELECT tile_column, tile_row, tile_data FROM tiles WHERE zoom_level=?', (z,)):
            y = (2 ** z - 1) - row
            if (x >> (z - 12), y >> (z - 12)) in sel: rows.append((z, x, row, d))
        o.executemany('INSERT INTO tiles VALUES (?,?,?,?)', rows); o.commit(); del rows
    o.close()
    pm = os.path.join(out_dir, name + '.pmtiles')
    subprocess.run([os.path.join(root, '..', 'bin', 'pmtiles'), 'convert', mbp, pm], check=True, capture_output=True)
    os.remove(mbp)
    print(name, len(bl), 'blocks', round(os.path.getsize(pm) / 1e6, 1), 'MB', m['bounds'], flush=True)
