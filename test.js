// Run: node --test test.js   (uses a throwaway database)
process.env.FETCH_IMAGES = '0';
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
  assert.equal((await put('x'.repeat(70 * 1024))).status, 413);
  assert.equal((await req('POST', '/api/state')).status, 405);
  assert.equal((await req('DELETE', '/')).status, 405);
});
