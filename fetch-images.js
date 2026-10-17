// Downloads every picture the site uses on first start, so no game art has to be shipped in the repository.
// Sources: github.com/WFCD/warframe-items (item pictures) and wiki.warframe.com (star chart, syndicate flags, Kahl scenes).
// Pictures are shrunk to WebP and cached in IMG_DIR (a volume), so this only downloads what is missing.
const fs = require('fs'), path = require('path'), vm = require('vm');
const SRC = 'https://raw.githubusercontent.com/WFCD/warframe-items/master/data/img/', WIKI = 'https://wiki.warframe.com/images/';
const SYND = { 'steel-meridian': 'SteelMeridianFlag', arbiters: 'ArbitersofHexisFlag', suda: 'CephalonSudaFlag', perrin: 'ThePerrinSequenceFlag', 'red-veil': 'RedVeilFlag', 'new-loka': 'NewLokaFlag', conclave: 'ConclaveFlag', simaris: 'CephalonSimarisFlag', ostron: 'OstronSyndicateFlag', quills: 'TheQuillsSyndicateFlag', solaris: 'SolarisUnitedSyndicateFlag', vox: 'VoxSolarisSyndicateFlag', ventkids: 'VentkidsSyndicateFlag', entrati: 'EntratiSyndicateFlag', necraloid: 'NecraloidSyndicateFlag', hex: 'TheHexSyndicateFlag', holdfasts: 'HoldfastsSyndicateFlag', cavia: 'CaviaSyndicateFlag', garrison: 'GarrisonSyndicateFlag' };
const KAHL = { forest: 'VeilbreakForestScene', murex: 'VeilbreakMurexScene', factory: 'VeilbreakFactoryScene', garrison: 'GarrisonIcon', stock: 'KahlStock' };

const load = (siteDir, file, name) => vm.runInNewContext(fs.readFileSync(path.join(siteDir, file), 'utf8') + ';' + name);

function jobs(siteDir, dir) {
  const names = new Set(['Ducat.png']);
  for (const [f, v] of [['frames', 'FRAMES'], ['weapons', 'WEAPONS'], ['companions', 'COMPANIONS'], ['helminth', 'HELMINTH'], ['resources', 'RESOURCES'], ['mods', 'MODS'], ['arcanes', 'ARCANES']]) {
    for (const x of load(siteDir, f + '.js', v)) { if (x.img) names.add(x.img); for (const p of x.parts || []) if (p.i) names.add(p.i); } // Warframe part icons
  }
  try { Object.values(load(siteDir, 'baro_icons.js', 'BARO_ICONS')).forEach(n => names.add(n)); } catch {}
  const out = [...names].map(n => ({ url: SRC + encodeURIComponent(n), out: path.join(dir, n + '.webp'), w: 128 }));
  out.push({ url: WIKI + 'StarChartLateGame.jpg', out: path.join(dir, 'starchart.webp'), w: 1920 });
  for (const [k, f] of Object.entries(KAHL)) out.push({ url: WIKI + f + '.png', out: path.join(dir, 'kahl', k + '.webp'), w: k === 'stock' ? 96 : 900 });
  for (const [k, f] of Object.entries(SYND)) out.push({ url: WIKI + f + '.png', out: path.join(dir, 'synd', k + '.webp'), w: 128 });
  return out;
}

const status = { total: 0, done: 0, failed: 0, running: false };

async function run({ siteDir, dir, concurrency = 12, log = console.log }) {
  if (status.running) return status;
  let sharp;
  try { sharp = require('sharp'); } catch { log('images: "sharp" is not installed, skipping picture download'); return status; }
  const all = jobs(siteDir, dir).filter(j => !fs.existsSync(j.out));
  Object.assign(status, { total: all.length, done: 0, failed: 0, running: all.length > 0 });
  if (all.length) log(`images: downloading ${all.length} pictures into ${dir}`);
  let i = 0;
  const worker = async () => {
    while (i < all.length) {
      const j = all[i++];
      let ok = false;
      for (let t = 0; t < 3 && !ok; t++) {
        try {
          const r = await fetch(j.url, { headers: { 'user-agent': 'orbiter' }, signal: AbortSignal.timeout(60000) });
          if (!r.ok) throw new Error(r.status);
          fs.mkdirSync(path.dirname(j.out), { recursive: true });
          const tmp = j.out + '.part';
          await sharp(Buffer.from(await r.arrayBuffer())).resize(j.w, j.w, { fit: 'inside', withoutEnlargement: true }).webp({ quality: 80 }).toFile(tmp);
          fs.renameSync(tmp, j.out);
          ok = true;
        } catch { await new Promise(r => setTimeout(r, 1000 * (t + 1))); }
      }
      ok ? status.done++ : status.failed++;
    }
  };
  await Promise.all(Array.from({ length: concurrency }, worker));
  status.running = false;
  log(`images: finished, ${status.done} downloaded, ${status.failed} failed${status.failed ? ' (they are retried on the next start)' : ''}`);
  return status;
}

module.exports = { run, status, jobs };
if (require.main === module) run({ siteDir: path.join(__dirname, 'site'), dir: process.env.IMG_DIR || path.join(__dirname, 'site', 'img') });
