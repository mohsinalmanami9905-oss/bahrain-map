"""Small helpers: Web-Mercator tile math and an MBTiles writer (converted to PMTiles with `bin/pmtiles convert`)."""
import io, math, os, sqlite3
R = 6378137.0
ORIGIN = math.pi * R
def tile_res(z): return 2 * ORIGIN / (256 * 2 ** z)
def tile_bounds_m(z, x, y):
    s = 2 * ORIGIN / 2 ** z
    return (-ORIGIN + x * s, ORIGIN - (y + 1) * s, -ORIGIN + (x + 1) * s, ORIGIN - y * s)
def lonlat_to_tile(lon, lat, z):
    n = 2 ** z; x = (lon + 180) / 360 * n
    y = (1 - math.asinh(math.tan(math.radians(lat))) / math.pi) / 2 * n
    return int(x), int(y)

class MBTiles:
    def __init__(self, path, meta):
        if os.path.exists(path): os.remove(path)
        self.db = sqlite3.connect(path)
        self.db.executescript('CREATE TABLE metadata (name text, value text);'
                              'CREATE TABLE tiles (zoom_level integer, tile_column integer, tile_row integer, tile_data blob);'
                              'CREATE UNIQUE INDEX tile_index on tiles (zoom_level, tile_column, tile_row);')
        self.db.executemany('INSERT INTO metadata VALUES (?,?)', [(k, str(v)) for k, v in meta.items()])
        self.n = 0; self.bytes = 0
    def put(self, z, x, y, data):
        self.db.execute('INSERT OR REPLACE INTO tiles VALUES (?,?,?,?)', (z, x, (2 ** z - 1) - y, data))
        self.n += 1; self.bytes += len(data)
        if self.n % 500 == 0: self.db.commit()
    def close(self): self.db.commit(); self.db.close()

def encode(img, q=78):
    """img: PIL RGBA. Returns WebP bytes, or None if fully transparent."""
    a = img.getchannel('A')
    lo, hi = a.getextrema()
    if hi == 0: return None
    if lo == 255: img = img.convert('RGB')
    b = io.BytesIO(); img.save(b, 'WEBP', quality=q, method=4); return b.getvalue()

def utm_inv(E, N, zone=39):
    a = 6378137.0; f = 1 / 298.257223563; k0 = 0.9996; e2 = f * (2 - f); ep2 = e2 / (1 - e2)
    x = E - 500000; lon0 = math.radians(zone * 6 - 183)
    mu = N / k0 / (a * (1 - e2 / 4 - 3 * e2 ** 2 / 64 - 5 * e2 ** 3 / 256)); e1 = (1 - math.sqrt(1 - e2)) / (1 + math.sqrt(1 - e2))
    p1 = mu + (3 * e1 / 2 - 27 * e1 ** 3 / 32) * math.sin(2 * mu) + (21 * e1 ** 2 / 16 - 55 * e1 ** 4 / 32) * math.sin(4 * mu) + (151 * e1 ** 3 / 96) * math.sin(6 * mu)
    C1 = ep2 * math.cos(p1) ** 2; T1 = math.tan(p1) ** 2; N1 = a / math.sqrt(1 - e2 * math.sin(p1) ** 2); R1 = a * (1 - e2) / (1 - e2 * math.sin(p1) ** 2) ** 1.5
    D = x / (N1 * k0)
    lat = p1 - (N1 * math.tan(p1) / R1) * (D ** 2 / 2 - (5 + 3 * T1 + 10 * C1 - 4 * C1 ** 2 - 9 * ep2) * D ** 4 / 24)
    lon = lon0 + (D - (1 + 2 * T1 + C1) * D ** 3 / 6) / math.cos(p1)
    return math.degrees(lon), math.degrees(lat)
