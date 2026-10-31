// On-demand price crawl for the mods that Arbiters of Hexis, Cephalon Suda and Cephalon Simaris sell for standing (site/syndicates.js, see fetch_syndicates.py).
// A crawl is started by a button on the page. For each tradable mod it asks warframe.market for the open sell offers and for the closed sales (two requests, each followed by a 2 second pause)
// and keeps the lowest ask, the recent sale price and how many were sold.
const fs = require('fs'), path = require('path'), vm = require('vm');
const { fetchOrders, sleep } = require('./prices');
const SLEEP_MS = 2_000;
const status = { running: false, total: 0, done: 0, started: null };
const norm = s => s.toLowerCase().replace(/[^a-z0-9]/g, '');
const strip = n => n.replace(/\s*\([^)]*\)$/, ''); // "Entropy Spike (Bolto)" is sold on the market as "Entropy Spike"

function init(db) {
  db.exec('CREATE TABLE IF NOT EXISTS synd_prices (key TEXT PRIMARY KEY, slug TEXT NOT NULL, name TEXT NOT NULL, min INTEGER, offers INTEGER, updated TEXT, error TEXT)');
  for (const col of ['sold48 INTEGER', 'sold90 INTEGER', 'sale INTEGER']) try { db.exec('ALTER TABLE synd_prices ADD COLUMN ' + col); } catch {} // tables made by older versions
}

// Lowest sell price of an unranked mod from a trader who is online or in game. Offers under half the median of the cheapest five are ignored as bait.
function lowest(orders) {
  const all = orders.filter(o => o.type === 'sell' && o.visible !== false && o.user && o.user.status !== 'offline' && !o.rank).map(o => o.platinum).sort((a, b) => a - b);
  const five = all.slice(0, 5), median = five.length ? five[Math.floor(five.length / 2)] : 0;
  const ok = all.filter(x => x >= median / 2);
  return { min: ok.length ? ok[0] : null, offers: ok.length };
}

// Closed sales of an unranked mod from the v1 statistics: sold in the last 48 h and 90 days, and the volume-weighted median price of the last 14 days (or all 90 if none).
function sales(stats, now = Date.now()) {
  const un = a => (a || []).filter(e => !e.mod_rank), s90 = un(stats['90days']), recent = s90.filter(e => Date.parse(e.datetime) >= now - 14 * 864e5), use = recent.length ? recent : s90;
  const vol = use.reduce((t, e) => t + e.volume, 0);
  return { sold48: un(stats['48hours']).reduce((t, e) => t + e.volume, 0), sold90: s90.reduce((t, e) => t + e.volume, 0), sale: vol ? Math.round(use.reduce((t, e) => t + e.median * e.volume, 0) / vol) : null };
}
const HEADERS = { accept: 'application/json', language: 'en', platform: 'pc', 'user-agent': 'Orbiter (self-hosted Warframe companion)' };
async function fetchStats(slug) {
  const r = await fetch(`https://api.warframe.market/v1/items/${slug}/statistics`, { headers: HEADERS, signal: AbortSignal.timeout(30_000) });
  if (!r.ok) throw new Error('statistics HTTP ' + r.status);
  return (await r.json()).payload.statistics_closed;
}

// Every syndicate offer that is a tradable mod on warframe.market -> Map(key -> {slug, name})
async function jobs(siteDir, log) {
  const r = await fetch('https://api.warframe.market/v2/items', { headers: { accept: 'application/json', language: 'en', platform: 'pc', 'user-agent': 'Orbiter (self-hosted Warframe companion)' }, signal: AbortSignal.timeout(60_000) });
  if (!r.ok) throw new Error('item list HTTP ' + r.status);
  const idx = new Map((await r.json()).data.map(x => [norm(x.i18n.en.name), x]));
  const syn = vm.runInNewContext(fs.readFileSync(path.join(siteDir, 'syndicates.js'), 'utf8') + ';SYNDICATES'), out = new Map();
  for (const s of syn) for (const it of s.items) for (const c of [it.n, strip(it.n)]) {
    const x = idx.get(norm(c));
    if (x) { if (x.tags.includes('mod')) out.set(norm(x.i18n.en.name), { slug: x.slug, name: x.i18n.en.name }); break; }
  }
  return out;
}

async function crawl({ db, siteDir, log = console.log }) {
  if (status.running) return false;
  Object.assign(status, { running: true, total: 0, done: 0, started: new Date().toISOString() });
  (async () => {
    try {
      const list = [...(await jobs(siteDir, log)).entries()];
      status.total = list.length;
      const up = db.prepare('INSERT INTO synd_prices (key, slug, name, min, offers, sold48, sold90, sale, updated, error) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, NULL) ON CONFLICT(key) DO UPDATE SET slug=excluded.slug, name=excluded.name, min=excluded.min, offers=excluded.offers, sold48=excluded.sold48, sold90=excluded.sold90, sale=excluded.sale, updated=excluded.updated, error=NULL');
      const fail = db.prepare('INSERT INTO synd_prices (key, slug, name, error) VALUES (?, ?, ?, ?) ON CONFLICT(key) DO UPDATE SET error=excluded.error');
      for (const [key, { slug, name }] of list) {
        try {
          const x = lowest(await fetchOrders(slug, log));
          await sleep(SLEEP_MS);
          const y = sales(await fetchStats(slug));
          up.run(key, slug, name, x.min, x.offers, y.sold48, y.sold90, y.sale, new Date().toISOString());
        }
        catch (e) { fail.run(key, slug, name, String(e.message || e)); log(`syndicate prices: ${name}: ${e.message || e}`); }
        status.done++;
        await sleep(SLEEP_MS);
      }
      log(`syndicate prices: crawled ${list.length} mods`);
    } catch (e) { log('syndicate prices: ' + e); }
    status.running = false;
  })();
  return true;
}

const list = db => db.prepare('SELECT key, slug, name, min, offers, sold48, sold90, sale, updated, error FROM synd_prices').all();
module.exports = { init, crawl, status, list, lowest, sales, norm, strip };
