// On-demand price crawl for the mods that Arbiters of Hexis, Cephalon Suda and Cephalon Simaris sell for standing (site/syndicates.js, see fetch_syndicates.py).
// A crawl is started by a button on the page, looks each tradable mod up on warframe.market (one request, then a 2 second pause) and keeps the lowest price.
const fs = require('fs'), path = require('path'), vm = require('vm');
const { fetchOrders, sleep } = require('./prices');
const SLEEP_MS = 2_000;
const status = { running: false, total: 0, done: 0, started: null };
const norm = s => s.toLowerCase().replace(/[^a-z0-9]/g, '');
const strip = n => n.replace(/\s*\([^)]*\)$/, ''); // "Entropy Spike (Bolto)" is sold on the market as "Entropy Spike"

function init(db) {
  db.exec('CREATE TABLE IF NOT EXISTS synd_prices (key TEXT PRIMARY KEY, slug TEXT NOT NULL, name TEXT NOT NULL, min INTEGER, offers INTEGER, updated TEXT, error TEXT)');
}

// Lowest sell price of an unranked mod from a trader who is online or in game. Offers under half the median of the cheapest five are ignored as bait.
function lowest(orders) {
  const all = orders.filter(o => o.type === 'sell' && o.visible !== false && o.user && o.user.status !== 'offline' && !o.rank).map(o => o.platinum).sort((a, b) => a - b);
  const five = all.slice(0, 5), median = five.length ? five[Math.floor(five.length / 2)] : 0;
  const ok = all.filter(x => x >= median / 2);
  return { min: ok.length ? ok[0] : null, offers: ok.length };
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
      const up = db.prepare('INSERT INTO synd_prices (key, slug, name, min, offers, updated, error) VALUES (?, ?, ?, ?, ?, ?, NULL) ON CONFLICT(key) DO UPDATE SET slug=excluded.slug, name=excluded.name, min=excluded.min, offers=excluded.offers, updated=excluded.updated, error=NULL');
      const fail = db.prepare('INSERT INTO synd_prices (key, slug, name, error) VALUES (?, ?, ?, ?) ON CONFLICT(key) DO UPDATE SET error=excluded.error');
      for (const [key, { slug, name }] of list) {
        try { const x = lowest(await fetchOrders(slug, log)); up.run(key, slug, name, x.min, x.offers, new Date().toISOString()); }
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

const list = db => db.prepare('SELECT key, slug, name, min, offers, updated, error FROM synd_prices').all();
module.exports = { init, crawl, status, list, lowest, norm, strip };
