// Run: node --test test.js   (uses a throwaway database)
process.env.FETCH_IMAGES = '0';
process.env.FETCH_PRICES = '0';
process.env.IMG_DIR = require('path').join(require('os').tmpdir(), `orbiter-test-img-${process.pid}`);
process.env.DB = require('path').join(require('os').tmpdir(), `orbiter-test-${process.pid}.db`);
const test = require('node:test'), assert = require('node:assert'), http = require('http');
const { server } = require('./server.js');

let port;
test.before(() => new Promise(r => server.listen(0, () => { port = server.address().port; r(); })));
test.after(() => { server.close(); require('fs').rmSync(process.env.DB, { force: true }); });

// Raw request so odd paths (%E0%A4%A, %00, ..) reach the server unchanged.
const req = (method, path, { headers = {}, body } = {}) => new Promise((res, rej) => {
  const r = http.request({ port, method, path, headers }, m => { let d = ''; m.on('data', c => d += c); m.on('end', () => res({ status: m.statusCode, headers: m.headers, body: d })); });
  r.on('error', rej); r.end(body);
});
const put = (body, headers = { 'content-type': 'application/json' }) => req('PUT', '/api/state', { headers, body: typeof body === 'string' ? body : JSON.stringify(body) });

test('static pages and security headers', async () => {
  const r = await req('GET', '/');
  assert.equal(r.status, 200);
  assert.match(r.headers['content-security-policy'], /default-src 'none'/);
  assert.equal(r.headers['x-content-type-options'], 'nosniff');
  assert.equal((await req('GET', '/api/images')).status, 200);
  assert.equal((await req('GET', '/img/..%2fserver.js')).status, 403);
  assert.equal((await req('GET', '/healthz')).status, 200);
});

test('malformed or hostile paths never crash the server', async () => {
  for (const p of ['/%E0%A4%A', '/%00', '/..%2f..%2fserver.js', '/%2e%2e/server.js', '/../server.js', '/img', '/nope']) {
    const r = await req('GET', p);
    assert.ok([400, 403, 404].includes(r.status), `${p} -> ${r.status}`);
  }
  assert.equal((await req('GET', '/')).status, 200); // still alive
});

test('state API round trip and sanitising', async () => {
  assert.equal((await req('GET', '/api/state')).body, '{}');
  assert.equal((await put({ tasks: { login: true, off: false }, owned: { Rhino: true }, reset: { d: 5, w: 6 }, junk: 1 })).status, 204);
  assert.deepEqual(JSON.parse((await req('GET', '/api/state')).body), { tasks: { login: true }, owned: { Rhino: true }, reset: { d: 5, w: 6 } });
  await put('{"__proto__":{"x":1},"tasks":{"__proto__":true,"constructor":true,"ok":true},"owned":5,"reset":{"d":"x","w":-1}}');
  assert.deepEqual(JSON.parse((await req('GET', '/api/state')).body), { tasks: { ok: true }, owned: {}, reset: { d: 0, w: 0 } });
});

test('state API rejects bad input', async () => {
  assert.equal((await put('nope')).status, 400);
  assert.equal((await put('[1,2]')).status, 400);
  assert.equal((await put('null')).status, 400);
  assert.equal((await put({ tasks: {} }, { 'content-type': 'text/plain' })).status, 415); // cross-site "simple" request
  assert.equal((await put({ tasks: {} }, { 'content-type': 'application/json', origin: 'http://evil.example' })).status, 403);
  assert.equal((await put('x'.repeat(600 * 1024))).status, 413);
  assert.equal((await req('POST', '/api/state')).status, 405);
  assert.equal((await req('DELETE', '/')).status, 405);
});

test('a fully ticked collection (about 75 KB) is accepted and kept intact', async () => {
  const owned = {};
  for (let i = 0; i < 3200; i++) owned[`M|w:Some Long Weapon Name ${i}`] = true;
  assert.equal((await put({ tasks: { login: true }, owned, reset: { d: 1, w: 2 } })).status, 204);
  const back = JSON.parse((await req('GET', '/api/state')).body);
  assert.equal(Object.keys(back.owned).length, 3200);
  assert.equal(back.tasks.login, true);
});

test('export returns a downloadable backup with the stored data', async () => {
  await put({ tasks: { login: true }, owned: { Rhino: true }, reset: { d: 3, w: 4 } });
  const r = await req('GET', '/api/export');
  assert.equal(r.status, 200);
  assert.match(r.headers['content-disposition'], /attachment; filename="orbiter-backup-\d{4}-\d{2}-\d{2}\.json"/);
  const b = JSON.parse(r.body);
  assert.equal(b.app, 'orbiter');
  assert.equal(b.version, 1);
  assert.deepEqual(b.data, { tasks: { login: true }, owned: { Rhino: true }, reset: { d: 3, w: 4 } });
});

test('price summary uses the 10 cheapest sell offers of online traders', () => {
  const { summarize, slug } = require('./prices.js');
  const o = (platinum, status = 'ingame', type = 'sell') => ({ type, platinum, visible: true, user: { status } });
  const orders = [...Array.from({ length: 12 }, (_, i) => o(100 + i * 10)), o(1, 'offline'), o(2, 'online', 'buy')];
  assert.deepEqual(summarize(orders), { min: 100, max: 190, avg: 145, offers: 10, prices: Array.from({ length: 10 }, (_, i) => 100 + i * 10) });
  assert.deepEqual(summarize([o(2), ...Array.from({ length: 11 }, (_, i) => o(47 + i))]), { min: 47, max: 56, avg: 52, offers: 10, prices: Array.from({ length: 10 }, (_, i) => 47 + i) }); // the 2 p bait offer is ignored
  assert.deepEqual(summarize([o(5, 'offline')]), { min: null, max: null, avg: null, offers: 0, prices: [] });
  assert.equal(slug('Rhino Prime'), 'rhino_prime_set');
});

test('prices API returns the stored scan', async () => {
  const r = JSON.parse((await req('GET', '/api/prices')).body);
  assert.deepEqual(r.items, []);
  assert.equal(r.scan.running, false);
});

test('price history: one frame, all frames added up, bad slugs rejected', async () => {
  const { DatabaseSync } = require('node:sqlite'), db = new DatabaseSync(process.env.DB);
  const ins = db.prepare('INSERT INTO price_history (scan, slug, min, avg, max, offers) VALUES (?, ?, ?, ?, ?, ?)');
  for (const scan of ['2026-01-01T00:00:00Z', '2026-01-01T06:00:00Z']) { ins.run(scan, 'a_prime_set', 10, 12, 15, 10); ins.run(scan, 'b_prime_set', 20, 22, 25, 10); }
  ins.run('2026-01-01T12:00:00Z', 'a_prime_set', 1, 1, 1, 1); // a scan that only reached one of two frames is skipped in the total
  db.close();
  const one = JSON.parse((await req('GET', '/api/price-history?slug=a_prime_set')).body);
  assert.deepEqual(one.map(x => x.avg), [12, 12, 1]);
  const all = JSON.parse((await req('GET', '/api/price-history?slug=all')).body);
  assert.deepEqual(all.map(x => x.avg), [34, 34]);
  assert.equal((await req('GET', '/api/price-history?slug=a%27%3B--')).status, 400);
});

test('syndicate price: lowest unranked online offer, bait ignored; crawl endpoint is protected', async () => {
  const { lowest, norm, strip } = require('./syndprices.js');
  const o = (platinum, rank, status = 'ingame') => ({ type: 'sell', platinum, rank, visible: true, user: { status } });
  assert.deepEqual(lowest([o(1), o(40), o(42), o(45), o(50), o(55), o(3, 10), o(2, 0, 'offline')]), { min: 40, offers: 5 }); // 1 p is bait, the ranked 3 p and the offline 2 p do not count
  assert.deepEqual(lowest([]), { min: null, offers: 0 });
  assert.equal(norm(strip('Entropy Spike (Bolto)')), 'entropyspike');
  assert.equal((await req('POST', '/api/syndicate-prices', { headers: { 'content-type': 'text/plain' } })).status, 415);
  assert.equal((await req('POST', '/api/syndicate-prices', { headers: { 'content-type': 'application/json', origin: 'http://evil.example' } })).status, 403);
  assert.equal((await req('POST', '/api/syndicate-prices', { headers: { 'content-type': 'application/json' } })).status, 503); // tests run with FETCH_PRICES=0
  assert.deepEqual(JSON.parse((await req('GET', '/api/syndicate-prices')).body).items, []);
});
