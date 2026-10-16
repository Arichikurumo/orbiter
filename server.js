// Static file server + tiny state API backed by SQLite (node:sqlite, no dependencies).
const http = require('http'), fs = require('fs'), path = require('path');
const { DatabaseSync } = require('node:sqlite');
const ROOT = path.join(__dirname, 'site'), DB = process.env.DB || '/data/state.db', PORT = process.env.PORT || 8080;
const IMG_DIR = process.env.IMG_DIR || path.join(ROOT, 'img'), images = require('./fetch-images');
const MAX_BODY = 64 * 1024, MAX_KEYS = 5000;
fs.mkdirSync(path.dirname(DB), { recursive: true });
const db = new DatabaseSync(DB);
db.exec('CREATE TABLE IF NOT EXISTS state (id INTEGER PRIMARY KEY CHECK (id = 1), json TEXT NOT NULL, updated TEXT NOT NULL)');
const MIME = { '.html': 'text/html; charset=utf-8', '.js': 'text/javascript; charset=utf-8', '.css': 'text/css', '.png': 'image/png', '.jpg': 'image/jpeg', '.webp': 'image/webp', '.svg': 'image/svg+xml', '.ico': 'image/x-icon' };
// Inline script/styles are used by the page, so 'unsafe-inline' stays; everything else is locked to this origin plus the live-data API.
const SECURITY = {
  'content-security-policy': "default-src 'none'; script-src 'self' 'unsafe-inline'; style-src 'unsafe-inline'; img-src 'self' data:; connect-src 'self' https://api.warframestat.us; base-uri 'none'; form-action 'none'; frame-ancestors 'none'",
  'x-content-type-options': 'nosniff', 'referrer-policy': 'no-referrer', 'x-frame-options': 'DENY',
};

// Only plain {tasks:{id:true}, owned:{id:true}, reset:{d,w}} is stored; anything else is dropped.
const BAD_KEYS = new Set(['__proto__', 'constructor', 'prototype']);
function flags(o) {
  const out = {};
  if (o && typeof o === 'object' && !Array.isArray(o)) {
    for (const k of Object.keys(o).slice(0, MAX_KEYS)) if (o[k] && k.length <= 200 && !BAD_KEYS.has(k)) out[k] = true;
  }
  return out;
}
function sanitize(v) {
  if (!v || typeof v !== 'object' || Array.isArray(v)) return null;
  const n = x => (Number.isFinite(x) && x >= 0 ? x : 0);
  return { tasks: flags(v.tasks), owned: flags(v.owned), reset: { d: n(v.reset && v.reset.d), w: n(v.reset && v.reset.w) } };
}

function send(res, code, body, headers = {}) {
  res.writeHead(code, { ...SECURITY, ...headers });
  res.end(body);
}

// Cross-site pages can fire "simple" requests at a local server, so state changes need a JSON content type
// (which forces a CORS preflight we never allow) and an Origin that matches this host.
function sameOrigin(req) {
  const o = req.headers.origin;
  if (!o) return true;
  try { return new URL(o).host === req.headers.host; } catch { return false; }
}

function handle(req, res) {
  let url;
  try { url = new URL(req.url, 'http://x'); } catch { return send(res, 400, 'bad url'); }
  if (url.pathname === '/favicon.ico') { res.writeHead(302, { location: '/favicon-32.png' }); return res.end(); } // browsers ask for this by default
  if (url.pathname === '/healthz') return send(res, 200, 'ok');
  if (url.pathname === '/api/images') return send(res, 200, JSON.stringify(images.status), { 'content-type': 'application/json', 'cache-control': 'no-store' });
  if (url.pathname === '/api/state') {
    if (req.method === 'GET') {
      const row = db.prepare('SELECT json FROM state WHERE id = 1').get();
      return send(res, 200, row ? row.json : '{}', { 'content-type': 'application/json', 'cache-control': 'no-store' });
    }
    if (req.method === 'PUT') {
      if (!sameOrigin(req)) return send(res, 403, 'forbidden');
      if (!/^application\/json\b/i.test(req.headers['content-type'] || '')) return send(res, 415, 'content-type must be application/json');
      const chunks = []; let size = 0;
      req.on('data', c => {
        size += c.length;
        if (res.writableEnded) return; // already answered 413, discard the rest
        if (size > MAX_BODY) send(res, 413, 'too large', { connection: 'close' }); else chunks.push(c);
      });
      return req.on('end', () => {
        if (res.writableEnded) return;
        let v;
        try { v = sanitize(JSON.parse(Buffer.concat(chunks).toString('utf8'))); } catch { v = null; }
        if (!v) return send(res, 400, 'bad json');
        db.prepare('INSERT INTO state (id, json, updated) VALUES (1, ?, ?) ON CONFLICT(id) DO UPDATE SET json = excluded.json, updated = excluded.updated')
          .run(JSON.stringify(v), new Date().toISOString());
        send(res, 204);
      });
    }
    return send(res, 405, 'method not allowed', { allow: 'GET, PUT' });
  }
  if (req.method !== 'GET' && req.method !== 'HEAD') return send(res, 405, 'method not allowed', { allow: 'GET, HEAD' });
  let rel;
  try { rel = decodeURIComponent(url.pathname); } catch { return send(res, 400, 'bad path'); }
  if (rel.includes('\0')) return send(res, 400, 'bad path');
  // pictures live in IMG_DIR (downloaded on first start), everything else in site/
  const isImg = rel.startsWith('/img/'), base = isImg ? IMG_DIR : ROOT, sub = isImg ? rel.slice(4) : rel;
  const file = path.join(base, sub === '/' ? 'index.html' : sub);
  if (!file.startsWith(base + path.sep)) return send(res, 403, 'forbidden');
  fs.readFile(file, (err, data) => {
    if (err) return send(res, 404, 'not found');
    send(res, 200, req.method === 'HEAD' ? undefined : data, {
      'content-type': MIME[path.extname(file)] || 'application/octet-stream',
      'cache-control': rel.startsWith('/img/') ? 'public, max-age=86400' : 'no-cache',
    });
  });
}

const server = http.createServer((req, res) => {
  try { handle(req, res); } catch (e) { console.error(e); if (!res.headersSent) send(res, 500, 'server error'); else res.end(); }
});
if (require.main === module) {
  server.listen(PORT, () => console.log(`listening on :${PORT}, db ${DB}`));
  if (process.env.FETCH_IMAGES !== '0') images.run({ siteDir: ROOT, dir: IMG_DIR }).catch(e => console.error('images:', e));
  for (const s of ['SIGTERM', 'SIGINT']) process.on(s, () => process.exit(0)); // PID 1 ignores signals by default
}
module.exports = { server, sanitize };
