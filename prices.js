// Prime Warframe set prices from warframe.market. Runs in the server so the browser never talks to it and the rate limit is respected:
// one request per Warframe, then a 2 second pause; every scan is also kept as a history row. Only sell orders from users who are online or in game count, cheapest 10 (the "first 10 offerings").
const fs = require('fs'), path = require('path'), vm = require('vm');
const SKIP = new Set(['Excalibur Prime']); // no longer obtainable, so there is no market set
const SLEEP_MS = 2_000, RESCAN_MS = 6 * 3600_000, OFFERS = 10;
const status = { total: 0, done: 0, running: false };
const sleep = ms => new Promise(r => setTimeout(r, ms));
const slug = name => name.toLowerCase().replace(/[^a-z0-9]+/g, '_').replace(/^_|_$/g, '') + '_set';

function primeFrames(siteDir) {
  const frames = vm.runInNewContext(fs.readFileSync(path.join(siteDir, 'frames.js'), 'utf8') + ';FRAMES');
  return frames.filter(f => f.prime && !SKIP.has(f.name)).map(f => f.name);
}

// Cheapest OFFERS sell orders of users who can trade right now -> {min, max, avg, offers, prices}.
// Bait listings (a set for 2 p) would hide the real price, so offers under half the median of the cheapest OFFERS are ignored.
function summarize(orders) {
  const all = orders.filter(o => o.type === 'sell' && o.visible !== false && o.user && o.user.status !== 'offline').map(o => o.platinum).sort((a, b) => a - b);
  const first = all.slice(0, OFFERS), median = first.length ? first[Math.floor(first.length / 2)] : 0;
  const p = all.filter(x => x >= median / 2).slice(0, OFFERS);
  return p.length ? { min: p[0], max: p[p.length - 1], avg: Math.round(p.reduce((t, x) => t + x, 0) / p.length), offers: p.length, prices: p } : { min: null, max: null, avg: null, offers: 0, prices: [] };
}

async function fetchOrders(s, log) {
  for (let attempt = 0; attempt < 2; attempt++) {
    const r = await fetch(`https://api.warframe.market/v2/orders/item/${s}`, { headers: { accept: 'application/json', language: 'en', platform: 'pc', 'user-agent': 'Orbiter (self-hosted Warframe companion)' }, signal: AbortSignal.timeout(30_000) });
    if (r.status === 429 && attempt === 0) { log('prices: rate limited, waiting 60 s'); await sleep(60_000); continue; }
    if (!r.ok) throw new Error('HTTP ' + r.status);
    return (await r.json()).data || [];
  }
}

// Tables: prices = latest result per Warframe (with its cheapest offers as JSON), price_history = one row per Warframe per scan (scan = when the scan started).
function init(db) {
  db.exec('CREATE TABLE IF NOT EXISTS prices (slug TEXT PRIMARY KEY, name TEXT NOT NULL, min INTEGER, max INTEGER, avg INTEGER, offers INTEGER, updated TEXT, error TEXT)');
  for (const col of ['avg INTEGER', 'lowest TEXT']) try { db.exec('ALTER TABLE prices ADD COLUMN ' + col); } catch {} // tables made by older versions
  db.exec('CREATE TABLE IF NOT EXISTS price_history (scan TEXT NOT NULL, slug TEXT NOT NULL, min INTEGER, avg INTEGER, max INTEGER, offers INTEGER, PRIMARY KEY (scan, slug))');
  db.exec('INSERT OR IGNORE INTO price_history SELECT updated, slug, min, avg, max, offers FROM prices WHERE avg IS NOT NULL'); // the latest earlier result becomes the first point
}

async function scan({ db, siteDir, log = console.log }) {
  const names = primeFrames(siteDir), scanId = new Date().toISOString();
  const up = db.prepare('INSERT INTO prices (slug, name, min, max, avg, offers, lowest, updated, error) VALUES (?, ?, ?, ?, ?, ?, ?, ?, NULL) ON CONFLICT(slug) DO UPDATE SET min=excluded.min, max=excluded.max, avg=excluded.avg, offers=excluded.offers, lowest=excluded.lowest, updated=excluded.updated, error=NULL');
  const hist = db.prepare('INSERT OR REPLACE INTO price_history (scan, slug, min, avg, max, offers) VALUES (?, ?, ?, ?, ?, ?)');
  const fail = db.prepare('INSERT INTO prices (slug, name, error) VALUES (?, ?, ?) ON CONFLICT(slug) DO UPDATE SET error=excluded.error');
  Object.assign(status, { total: names.length, done: 0, running: true });
  for (const name of names) {
    const s = slug(name);
    try {
      const x = summarize(await fetchOrders(s, log));
      up.run(s, name, x.min, x.max, x.avg, x.offers, JSON.stringify(x.prices), new Date().toISOString());
      if (x.min != null) hist.run(scanId, s, x.min, x.avg, x.max, x.offers);
    } catch (e) { fail.run(s, name, String(e.message || e)); log(`prices: ${name}: ${e.message || e}`); }
    status.done++;
    await sleep(SLEEP_MS);
  }
  status.running = false;
  log(`prices: scanned ${names.length} prime warframes`);
}

// Scan now if data is missing or old, then again every RESCAN_MS.
async function run(opts) {
  const { db } = opts;
  init(db);
  const list_ = primeFrames(opts.siteDir), names = list_.length;
  db.prepare(`DELETE FROM prices WHERE slug NOT IN (${list_.map(() => '?').join(',')})`).run(...list_.map(slug)); // frames dropped from the list
  const row = db.prepare('SELECT COUNT(lowest) n, MIN(updated) oldest FROM prices').get();
  let wait = row.n >= names && row.oldest ? Math.max(0, Date.parse(row.oldest) + RESCAN_MS - Date.now()) : 0;
  for (;;) { await sleep(wait); await scan(opts).catch(e => { status.running = false; opts.log ? opts.log('prices: ' + e) : console.error('prices:', e); }); wait = RESCAN_MS; }
}

const list = db => db.prepare('SELECT slug, name, min, max, avg, offers, lowest, updated, error FROM prices ORDER BY name').all().map(r => ({ ...r, lowest: r.lowest ? JSON.parse(r.lowest) : [] }));
// 'all' = every Prime set added together per scan (scans that missed many Warframes are left out); otherwise one Warframe.
const history = (db, slug) => slug === 'all'
  ? db.prepare('SELECT scan ts, SUM(min) min, SUM(avg) avg, SUM(max) max FROM price_history GROUP BY scan HAVING COUNT(*) >= 0.9 * (SELECT COUNT(DISTINCT slug) FROM price_history) ORDER BY scan').all()
  : db.prepare('SELECT scan ts, min, avg, max FROM price_history WHERE slug = ? ORDER BY scan').all(slug);
module.exports = { run, init, status, list, history, summarize, slug, fetchOrders, sleep };
