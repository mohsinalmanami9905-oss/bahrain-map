// Tiny static server with HTTP Range support (for local testing). node tools/serve.mjs docs 8765
import http from 'node:http'; import fs from 'node:fs'; import path from 'node:path';
const [, , dir = 'docs', port = 8765] = process.argv;
const T = { '.html': 'text/html; charset=utf-8', '.js': 'text/javascript', '.mjs': 'text/javascript', '.css': 'text/css', '.json': 'application/json', '.webmanifest': 'application/manifest+json', '.png': 'image/png', '.pbf': 'application/x-protobuf', '.pmtiles': 'application/octet-stream' };
http.createServer((req, res) => {
  let p = decodeURIComponent(new URL(req.url, 'http://x').pathname); if (p.endsWith('/')) p += 'index.html';
  const f = path.join(dir, path.normalize(p));
  if (!f.startsWith(path.resolve(dir)) && !f.startsWith(dir)) { res.writeHead(403); return res.end(); }
  fs.stat(f, (err, st) => {
    if (err || !st.isFile()) { res.writeHead(404); return res.end('nf'); }
    const h = { 'Content-Type': T[path.extname(f)] || 'application/octet-stream', 'Accept-Ranges': 'bytes' };
    const m = process.env.NORANGE ? null : /bytes=(\d+)-(\d*)/.exec(req.headers.range || '');
    if (m) { const s = +m[1], e = m[2] ? Math.min(+m[2], st.size - 1) : st.size - 1;
      res.writeHead(206, { ...h, 'Content-Range': `bytes ${s}-${e}/${st.size}`, 'Content-Length': e - s + 1 }); fs.createReadStream(f, { start: s, end: e }).pipe(res); }
    else { res.writeHead(200, { ...h, 'Content-Length': st.size }); fs.createReadStream(f).pipe(res); }
  });
}).listen(port, () => console.log('serving', dir, port));
