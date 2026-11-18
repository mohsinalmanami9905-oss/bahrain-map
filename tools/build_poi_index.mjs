// Build a compact searchable POI/place/street index from the Bahrain PMTiles extract.
// Usage: node tools/build_poi_index.mjs data/bahrain.pmtiles docs/data/poi.json
import fs from 'node:fs';
import zlib from 'node:zlib';
import { PMTiles } from 'pmtiles';
import { VectorTile } from '@mapbox/vector-tile';
import { PbfReader as Protobuf } from 'pbf';

const [, , src, out] = process.argv;
class FileSource {
  constructor(p) { this.fd = fs.openSync(p, 'r'); this.p = p; }
  getKey() { return this.p; }
  async getBytes(offset, length) {
    const b = Buffer.alloc(length); fs.readSync(this.fd, b, 0, length, offset);
    return { data: b.buffer.slice(b.byteOffset, b.byteOffset + length) };
  }
}
const pm = new PMTiles(new FileSource(src));
const Z = 15;
const lon2x = (lon) => Math.floor((lon + 180) / 360 * 2 ** Z);
const lat2y = (lat) => Math.floor((1 - Math.log(Math.tan(lat * Math.PI / 180) + 1 / Math.cos(lat * Math.PI / 180)) / Math.PI) / 2 * 2 ** Z);
const [W, S, E, N] = [50.20, 25.50, 50.90, 26.40];
const x0 = lon2x(W), x1 = lon2x(E), y0 = lat2y(N), y1 = lat2y(S);
const items = new Map();
const r5 = (v) => Math.round(v * 1e5) / 1e5;
function add(key, rec) { if (!items.has(key)) items.set(key, rec); }
let tiles = 0;
for (let x = x0; x <= x1; x++) for (let y = y0; y <= y1; y++) {
  const t = await pm.getZxy(Z, x, y);
  if (!t || !t.data) continue;
  tiles++;
  let buf = Buffer.from(t.data);
  if (buf[0] === 0x1f && buf[1] === 0x8b) buf = zlib.gunzipSync(buf);
  const vt = new VectorTile(new Protobuf(buf));
  for (const ln of ['pois', 'places', 'roads', 'water', 'landuse', 'earth']) {
    const L = vt.layers[ln]; if (!L) continue;
    for (let i = 0; i < L.length; i++) {
      const f = L.feature(i); const p = f.properties;
      const ar = p['name:ar'] || (/[\u0600-\u06FF]/.test(p.name || '') ? p.name : '');
      const en = p['name:en'] || (!/[\u0600-\u06FF]/.test(p.name || '') ? (p.name || '') : '');
      if (!ar && !en) continue;
      const gj = f.toGeoJSON(x, y, Z).geometry;
      let c;
      if (gj.type === 'Point') c = gj.coordinates;
      else if (gj.type === 'LineString') c = gj.coordinates[Math.floor(gj.coordinates.length / 2)];
      else if (gj.type === 'MultiLineString') c = gj.coordinates[0][Math.floor(gj.coordinates[0].length / 2)];
      else if (gj.type === 'Polygon') c = gj.coordinates[0][0];
      else if (gj.type === 'MultiPolygon') c = gj.coordinates[0][0][0];
      else continue;
      if (ln !== 'pois' && ln !== 'places' && ln !== 'roads') { if (!['park','aerodrome','university','hospital','school','beach','stadium','golf_course','zoo','island'].includes(p.kind)) continue; }
      const kind = ln === 'roads' ? 'street' : (p.kind || ln);
      // streets: dedupe by name (one entry per name+approx area); pois: by name+kind+~100m cell
      const key = ln === 'roads' ? `r|${ar}|${en}|${Math.round(c[0]*50)}|${Math.round(c[1]*50)}` : `${kind}|${ar}|${en}|${Math.round(c[0]*1000)}|${Math.round(c[1]*1000)}`;
      add(key, { a: ar || undefined, e: en || undefined, k: kind, x: r5(c[0]), y: r5(c[1]), r: ln === 'places' ? 0 : ln === 'pois' ? 1 : ln === 'roads' ? 3 : 2 });
    }
  }
}
const arr = [...items.values()].sort((a, b) => a.r - b.r);
fs.writeFileSync(out, JSON.stringify(arr.map(o => [o.a || '', o.e || '', o.k, o.x, o.y])));
console.log('tiles', tiles, 'entries', arr.length, 'bytes', fs.statSync(out).size);
const kinds = {}; for (const o of arr) kinds[o.k] = (kinds[o.k] || 0) + 1;
console.log(Object.entries(kinds).sort((a, b) => b[1] - a[1]).slice(0, 25));
