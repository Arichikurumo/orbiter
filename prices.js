// Prime Warframe set prices from warframe.market. Runs in the server so the browser never talks to it and the rate limit is respected:
// one request per Warframe, then a pause. Only sell orders from users who are online or in game count, cheapest 10 (the "first 10 offerings").
const fs = require('fs'), path = require('path'), vm = require('vm');
const SKIP = new Set(['Excalibur Prime']); // no longer obtainable, so there is no market set
const SLEEP_MS = 10_000, RESCAN_MS = 6 * 3600_000, OFFERS = 10;
const status = { total: 0, done: 0, running: false };
const sleep = ms => new Promise(r => setTimeout(r, ms));
const slug = name => name.toLowerCase().replace(/[^a-z0-9]+/g, '_').replace(/^_|_$/g, '') + '_set';

function primeFrames(siteDir) {
  const frames = vm.runInNewContext(fs.readFileSync(path.join(siteDir, 'frames.js'), 'utf8') + ';FRAMES');
  return frames.filter(f => f.prime && !SKIP.has(f.name)).map(f => f.name);
}

// Cheapest OFFERS sell orders of users who can trade right now -> {min, max, avg, offers}.
// Bait listings (a set for 2 p) would hide the real price, so offers under half the median of the cheapest OFFERS are ignored.
function summarize(orders) {
  const all = orders.filter(o => o.type === 'sell' && o.visible !== false && o.user && o.user.status !== 'offline').map(o => o.platinum).sort((a, b) => a - b);
  const first = all.slice(0, OFFERS), median = first.length ? first[Math.floor(first.length / 2)] : 0;
  const p = all.filter(x => x >= median / 2).slice(0, OFFERS);
  return p.length ? { min: p[0], max: p[p.length - 1], avg: Math.round(p.reduce((t, x) => t + x, 0) / p.length), offers: p.length } : { min: null, max: null, avg: null, offers: 0 };
}

async function fetchOrders(s, log) {
  for (let attempt = 0; attempt < 2; attempt++) {
    const r = await fetch(`https://api.warframe.market/v2/orders/item/${s}`, { headers: { accept: 'application/json', language: 'en', platform: 'pc', 'user-agent': 'Orbiter (self-hosted Warframe companion)' }, signal: AbortSignal.timeout(30_000) });
    if (r.status === 429 && attempt === 0) { log('prices: rate limited, waiting 60 s'); await sleep(60_000); continue; }
    if (!r.ok) throw new Error('HTTP ' + r.status);
    return (await r.json()).data || [];
  }
}

async function scan({ db, siteDir, log = console.log }) {
  const names = primeFrames(siteDir), up = db.prepare('INSERT INTO prices (slug, name, min, max, avg, offers, updated, error) VALUES (?, ?, ?, ?, ?, ?, ?, NULL) ON CONFLICT(slug) DO UPDATE SET min=excluded.min, max=excluded.max, avg=excluded.avg, offers=excluded.offers, updated=excluded.updated, error=NULL');
  const fail = db.prepare('INSERT INTO prices (slug, name, error) VALUES (?, ?, ?) ON CONFLICT(slug) DO UPDATE SET error=excluded.error');
  Object.assign(status, { total: names.length, done: 0, running: true });
  for (const name of names) {
    const s = slug(name);
    try { const x = summarize(await fetchOrders(s, log)); up.run(s, name, x.min, x.max, x.avg, x.offers, new Date().toISOString()); }
    catch (e) { fail.run(s, name, String(e.message || e)); log(`prices: ${name}: ${e.message || e}`); }
    status.done++;
    await sleep(SLEEP_MS);
  }
  status.running = false;
  log(`prices: scanned ${names.length} prime warframes`);
}

// Scan now if data is missing or old, then again every RESCAN_MS.
async function run(opts) {
  const { db } = opts;
  try { db.exec('ALTER TABLE prices ADD COLUMN avg INTEGER'); } catch {}
  const list_ = primeFrames(opts.siteDir), names = list_.length;
  db.exec('CREATE TABLE IF NOT EXISTS prices (slug TEXT PRIMARY KEY, name TEXT NOT NULL, min INTEGER, max INTEGER, avg INTEGER, offers INTEGER, updated TEXT, error TEXT)');
  db.prepare(`DELETE FROM prices WHERE slug NOT IN (${list_.map(() => '?').join(',')})`).run(...list_.map(slug)); // frames dropped from the list
  const row = db.prepare('SELECT COUNT(avg) n, MIN(updated) oldest FROM prices').get();
  let wait = row.n >= names && row.oldest ? Math.max(0, Date.parse(row.oldest) + RESCAN_MS - Date.now()) : 0;
  for (;;) { await sleep(wait); await scan(opts).catch(e => { status.running = false; opts.log ? opts.log('prices: ' + e) : console.error('prices:', e); }); wait = RESCAN_MS; }
}

const list = db => db.prepare('SELECT slug, name, min, max, avg, offers, updated, error FROM prices ORDER BY name').all();
module.exports = { run, status, list, summarize, slug };
