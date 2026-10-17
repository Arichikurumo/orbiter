# Regenerates the data files in site/ (frames, weapons, companions, mods, arcanes, helminth, resources) from api.warframestat.us.
#   curl -s "https://api.warframestat.us/warframes?language=en" -o warframes.json
#   curl -s "https://api.warframestat.us/weapons?language=en" -o weapons.json
#   curl -s "https://api.warframestat.us/items?language=en" -o items.json      (about 78 MB)
#   python3 -I gen.py warframes.json weapons.json items.json
import json, re, sys
ITEMS = json.load(open(sys.argv[3])) if len(sys.argv) > 3 else []
# Relics that can drop right now ("Unvaulted/Available" list on wiki.warframe.com/w/Void_Relic, read 2026-10-17). The API's own per-relic
# "vaulted" flag is stale: it marks Citrine Prime's new relics as vaulted and 20 relics that hold vaulted parts as available. Update this list
# when relics are vaulted or unvaulted (the wiki page lists them, Prime Vault announcements say which).
AVAILABLE_RELICS = set()
for blk in "Lith A13,C15,C7,G14,L8,S18,S19,V11;Meso A12,C11,D8,D9,K9,N11,V13,V17,Y2;Neo A16,C10,C11,C7,K10,V13,V9,Y2;Axi A21,A22,C12,D6,P10,S21,S8,V10,V14".split(';'):
    era, ids = blk.split(' ', 1)
    AVAILABLE_RELICS |= {f"{era} {i}" for i in ids.split(',')}
def prime_base(n): return (re.match(r'^(.*? Prime)\b', n) or [None, None])[1]
# Prime items with at least one part in an available relic (so Nyx Prime etc., permanently unvaulted since Update 29.10, count as obtainable)
AV_PRIMES = {prime_base(r['item']['name']) for x in ITEMS if x.get('category') == 'Relics' and x['name'].endswith(' Intact') and x['name'][:-7] in AVAILABLE_RELICS for r in x.get('rewards') or []} - {None}
d = [x for x in json.load(open(sys.argv[1])) if x['type'] == 'Warframe']
T1 = {'Excalibur': 0.5, 'Mag': 1, 'Volt': 1}
T2 = {n: 3 for n in 'Rhino Loki Frost Ash Ember Banshee Nova Nyx Trinity Oberon Vauban Saryn Zephyr Hydroid Mirage Limbo Atlas Valkyr Titania Equinox Nekros'.split()}
T3 = {n: 8 for n in 'Hildryn Chroma Nezha Ivara Gara Inaros Nidus Khora Garuda Harrow Wisp Gauss Grendel Protea Xaku Yareli Sevagoth Revenant Octavia Mesa Baruuk Wukong'.split()}
T4 = {n: 20 for n in 'Caliban Gyre Dagath Voruna Styanax Citrine Lavos Kullervo Qorvex Dante Nokko Jade Koumei Narin Cyte-09 Temple Follie Uriel'.split()}
T5 = {'Excalibur Umbra': 12}
EST = {**T1, **T2, **T3, **T4, **T5}
R = {}
for line in """Ash:stealth,damage|Atlas:tank,control|Banshee:damage,control|Baruuk:tank,control|Caliban:damage,control|Chroma:damage,tank|Citrine:support,control|Cyte-09:damage,stealth|Dagath:damage,control|Dante:support,damage|Ember:damage,control|Equinox:control,support|Excalibur:damage|Excalibur Umbra:damage|Frost:tank,control|Gara:tank,control|Garuda:damage,support|Gauss:speed,damage|Grendel:tank,damage|Gyre:damage,control|Harrow:support,damage|Hildryn:tank,support|Hydroid:control,farming|Inaros:tank,support|Ivara:stealth,farming|Jade:support,damage|Khora:damage,control|Koumei:support|Kullervo:damage,stealth|Lavos:damage,support|Limbo:control,support|Loki:stealth,control|Mag:control,damage|Mesa:damage|Mirage:damage,stealth|Nekros:farming,support|Nezha:tank,control|Nidus:tank,damage|Nova:damage,speed|Nyx:control,tank|Oberon:support,damage|Octavia:support,control|Protea:support,damage|Qorvex:tank,damage|Revenant:tank,control|Rhino:tank,support|Saryn:damage|Sevagoth:damage,support|Styanax:tank,support|Titania:damage,control|Trinity:support|Valkyr:tank,damage|Vauban:control,support|Volt:speed,damage|Voruna:damage,stealth|Wisp:support,control|Wukong:tank,damage|Xaku:damage,control|Yareli:control,speed|Zephyr:control,speed""".split('|'):
    k, v = line.split(':'); R[k] = v.split(',')  # shortcut: hand-picked, newest frames (Narin, Nokko, Temple...) untagged
def price(x, thing):
    # marketCost is the PLATINUM price of the finished item; bpCost is the CREDIT price of its Market blueprint (parts still have to be farmed)
    bp = f"Blueprint: Market, {x['bpCost']:,} credits" if x.get('bpCost') else ''
    pl = f"{x['marketCost']:,} platinum" if x.get('marketCost') else ''
    if bp and pl: return f"{bp} (or buy the finished {thing} for {pl})"
    return bp or (f"Buy the finished {thing} for {pl} in the Market" if pl else '')
def short(loc): return re.sub(r', Rotation [ABC]', '', loc)
def how(x):
    parts = []
    for c in x.get('components') or []:
        locs = []
        for r in c.get('drops', []):
            s = short(r['location'])
            if s not in locs: locs.append(s)
        if locs: parts.append(f"{c['name']}: {', '.join(locs[:2])}")
    out = '; '.join(parts) or 'Parts: see wiki'
    pr = price(x, 'frame')
    return out + (f" | {pr}" if pr else '')
PART_NAMES = ('Blueprint', 'Neuroptics', 'Chassis', 'Systems', 'Day Aspect', 'Night Aspect')
def frame_parts(x, prime):
    # one entry per part: n = name, i = the game's own icon, s = where to get it (primes: filled in by the page from the relic data)
    out, seen = [], set()
    for c in x.get('components') or []:
        if c['name'] not in PART_NAMES or c['name'] in seen: continue
        seen.add(c['name'])
        src = []
        if not prime:
            by = {}
            for r in c.get('drops', []):
                by[short(r['location'])] = max(by.get(short(r['location']), 0), r.get('chance') or 0)
            src = [loc if ch >= 100 else f"{loc} ({ch:g}%)" for loc, ch in sorted(by.items(), key=lambda kv: -kv[1])[:3]]
            if c['name'] == 'Blueprint' and x.get('bpCost'): src.append(f"Market: {x['bpCost']:,} credits")
        out.append(dict(n=c['name'], i=c.get('imageName'), s='; '.join(src)))
    return sorted(out, key=lambda p: PART_NAMES.index(p['n']))
out = []
for x in d:
    n = x['name']
    if n in ('Helminth', 'Sirius & Orion'): continue
    prime = bool(x.get('isPrime'))
    if prime and n == 'Excalibur Prime': tier, h, t = 6, None, 'Founders/Prime Access only - not obtainable (trade only)'
    elif prime and n not in AV_PRIMES: tier, h, t = 6, None, 'Vaulted: trade with players or wait for Prime Resurgence/Prime Vault'
    elif prime: tier, h, t = 4, 15, 'Void Relics (open via fissure missions). ' + how(x)
    else:
        h = EST.get(n, 8); tier = 1 if h <= 1 else 2 if h <= 3 else 3 if h <= 8 else 4 if h <= 20 else 5
        t = how(x)
    out.append(dict(name=n, prime=prime, tier=tier, hours=h, how=t, wiki=x.get('wikiaUrl'), img=x.get('imageName'), roles=R.get(n.removesuffix(' Prime'), []), parts=frame_parts(x, prime), plat=None if prime else x.get('marketCost')))
open('site/frames.js', 'w').write('const FRAMES=' + json.dumps(out) + ';')
print(len(out))

# ---- weapons + companions (python3 -I gen.py wf.json weapons.json comp.json) ----
if len(sys.argv) > 3:
    SYN = {'Vaykor': 'Steel Meridian', 'Telos': 'Arbiters of Hexis', 'Secura': 'Cephalon Suda', 'Synoid': 'The Perrin Sequence', 'Rakta': 'Red Veil', 'Sancti': 'New Loka'}
    def drops(x):
        by = {}  # components sharing the same drop sources are merged: "Barrel, Receiver: Zanuka Hunter"
        for c in x.get('components') or []:
            if c.get('category') != 'Components': continue  # skip raw resources
            locs = []
            for r in c.get('drops', []):
                s = short(r['location'])
                if s not in locs: locs.append(s)
            if locs: by.setdefault(', '.join(locs[:2]), []).append(c['name'])
        return '; '.join(f"{', '.join(v)}: {k}" for k, v in by.items())
    def wh(x):
        n, tags = x['name'], x.get('tags') or []
        p = n.split()[0]
        if p == 'Kuva' or p == 'Tenet' and False: return 'Kuva Lich: defeat your Lich and keep it (Requiem mods), or buy a Kuva weapon from a Lich'
        if p == 'Tenet': return 'Sister of Parvos: vanquish a Sister holding it, or buy from Ergo Glast (needs The Archwing, MR 14)'
        if p == 'Coda': return "Eleanor Nightingale's shop, Höllvania Central Mall (needs The Hex quest)"
        if p == 'Prisma': return "Baro Ki'Teer (Void Trader): Ducats + credits, only when he visits"
        if p in SYN: return f"{SYN[p]} syndicate offerings (standing; cheaper at higher rank)"
        if p == 'Dex': return 'Event/anniversary reward - rarely obtainable'
        if 'Prime' in tags or x.get('isPrime'):
            return ('Vaulted: trade parts with players or wait for Prime Resurgence/Vault. ' if (x['name'] not in AV_PRIMES) else 'Void Relics (fissure missions). ') + drops(x)
        d = drops(x)
        pr = price(x, 'weapon')
        if d: return d + (f" | {pr}" if pr else '')
        return pr or 'Starter weapon, Market, Dojo research or quest reward - see wiki'
    MELEE = json.load(open('meleeclass.json'))  # weapon -> class, parsed from wiki.warframe.com Module:Weapons/data/melee
    W = []
    for x in json.load(open(sys.argv[2])):
        if not x.get('masterable') or x['type'] == 'Zaw Component': continue
        c, t = x['category'], x['type']
        g = c if c in ('Arch-Gun', 'Arch-Melee') else f"Melee / {MELEE.get(x['name'], MELEE.get(x['name'] + ' (Dual Swords)', 'Other'))}" if c == 'Melee' else f"{c} / {t}"
        W.append(dict(name=x['name'], group=g, mr=x.get('masteryReq') or 0, how=wh(x), wiki=x.get('wikiaUrl'), img=x.get('imageName')))
    W = list({(w['name'], w['group']): w for w in reversed(W)}.values())  # drop same-name variants (e.g. Doppelganger Grimoire)
    ORDER = ['Primary', 'Secondary', 'Melee', 'Arch-Gun', 'Arch-Melee']
    W.sort(key=lambda w: (ORDER.index(w['group'].split(' / ')[0]), w['group'], w['mr'], w['name']))
    open('site/weapons.js', 'w').write('const WEAPONS=' + json.dumps(W) + ';')
    # Companions: API data is patchy for pets, so most "how" text is from wiki.warframe.com pages (Carrier/Taxon/Djinn/Helios/Kubrow/Kavat/Vulpaphyla/Hound)
    HOW = {
     'Carrier': 'Blueprint: Market, 100,000 credits. Build 24h', 'Taxon': 'Blueprint: Venus junction reward on Earth, or Market 5,000 credits',
     'Djinn': 'Dojo Bio Lab research (needs Dual Ichor), blueprint 50,000 credits', 'Helios': 'Dojo Energy Lab research (needs Lanka), blueprint 15,000 credits',
     'Prisma Shade': "Baro Ki'Teer (Void Trader)", 'Venari': "Khora's companion - comes with Khora", 'Venari Prime': "Khora Prime's companion",
     'Helminth Charger': 'Drain a fully matured Helminth Cyst (guaranteed)',
     'Vasca Kavat': 'Let a wild Vasca (Plains of Eidolon, night) infect your Kavat, then cure it in the incubator with a Genetic Code Template; two Vasca Imprints guarantee a Vasca',
    }
    GROUP = {'Charger': 'Kubrow', 'Venari': 'Kavat', 'Venari Prime': 'Kavat', 'Kubrow': 'Kubrow', 'Kavat': 'Kavat', 'Moa': 'MOA', 'Hound': 'Hound', 'Vulpaphyla': 'Vulpaphyla', 'Predasite': 'Predasite'}
    KUB = 'Incubator + Kubrow Egg + Incubator Power Core (Howl of the Kubrow quest). Breed is random'
    KAV = 'Incubator with Kavat Incubator Upgrade, 10 Kavat Genetic Codes + Incubator Power Core (Howl of the Kubrow quest). Breed is random'
    C = []
    for x in ITEMS:
        if x.get('category') not in ('Pets', 'Sentinels') or x.get('type') not in ('Sentinel', 'Pets', 'Warframe'): continue
        n = x['name']
        g = 'Sentinel' if x['type'] == 'Sentinel' else next((v for k, v in GROUP.items() if n.endswith(k)), 'Other')
        if n in HOW: h = HOW[n]
        elif g == 'Kubrow': h = KUB
        elif g == 'Kavat': h = KAV
        elif g == 'Hound': h = 'Vanquish a Sister of Parvos - the Hound comes with it (model is random)'
        elif g == 'MOA': h = 'Build from parts at the Legs shop in Fortuna (Solaris United); see wiki'
        elif g == 'Vulpaphyla': h = 'Cambion Drift: capture a weakened wild Vulpaphyla (Conservation), then revivify it with Son in the Necralisk'
        elif g == 'Predasite': h = 'Cambion Drift (Entrati): build via Son in the Necralisk; see wiki'
        elif g == 'Sentinel':
            h = drops(x) if n in ('Nautilus', 'Oxylus') or n.endswith('Prime') else ''
            h = h or 'Blueprint from the Market or Dojo research (see wiki), built in the Foundry'
            if x.get('isPrime') or n.endswith('Prime'): h = 'Void Relics (fissure missions). ' + h
        else: h = 'See wiki'
        C.append(dict(name=n, group=g, how=h, wiki=x.get('wikiaUrl'), img=x.get('imageName')))
    C.sort(key=lambda c: (c['group'], c['name']))
    open('site/companions.js', 'w').write('const COMPANIONS=' + json.dumps(C) + ';')
    print(len(W), len(C))

# ---- mods + arcanes (needs the full items.json as argv[4]) ----
if len(sys.argv) > 3:
    items = ITEMS
    def best(x):
        d = sorted(x.get('drops') or [], key=lambda r: -(r['chance'] or 0))
        seen, out = [], []
        for r in d:
            s = f"{short(r['location'])} ({r['chance'] or 0:g}%)"
            if short(r['location']) not in seen: seen.append(short(r['location'])); out.append(s)
            if len(out) == 3: break
        if out: return 'Drops: ' + '; '.join(out)
        if x.get('transmutable') or x.get('type') == 'Transmutation Mod': return 'Transmutation or vendor - see wiki'
        return 'Vendor, quest, trade or event reward - see wiki'
    def eff(x):
        ls = x.get('levelStats') or []
        t = ' / '.join(ls[-1].get('stats', [])) if ls else (x.get('description') or '')
        return re.sub(r'<[^>]+>', '', t.replace('\\n', ' ').replace('\n', ' '))[:200]
    def build(cat, drop_types=()):
        r = {}
        for x in items:
            if x.get('category') != cat or x.get('type') in drop_types: continue
            tag = ' · '.join(t for t in (x.get('rarity'), (x.get('polarity') or '').title() or None) if t)
            k = (x['name'], x.get('type'))  # Flawed/duplicate entries share a name: keep the real one
            if k in r and 'Flawed' in (x.get('wikiaUrl') or ''): continue
            r[k] = dict(name=x['name'], group=x.get('type') or 'Other', tag=tag, sub=eff(x), how=best(x), wiki=x.get('wikiaUrl'), img=x.get('imageName'))
        return sorted(r.values(), key=lambda m: (m['group'], m['name']))
    M, A = build('Mods', ('Focus Way',)), build('Arcanes')
    open('site/mods.js', 'w').write('const MODS=' + json.dumps(M) + ';')
    open('site/arcanes.js', 'w').write('const ARCANES=' + json.dumps(A) + ';')
    print(len(M), len(A))


# ---- Helminth: ability -> frame (pairs from wiki.warframe.com/w/Helminth); explanations come from the API's ability descriptions ----
PAIRS = "Ash:Shuriken|Atlas:Petrify|Banshee:Silence|Baruuk:Lull|Caliban:Sentient Wrath|Chroma:Elemental Ward|Citrine:Fractured Blast|Cyte-09:Evade|Dagath:Wyrd Scythes|Dante:Dark Verse|Ember:Fire Blast|Equinox:Rest & Rage|Excalibur:Radial Blind|Follie:Self Portrait|Frost:Ice Wave|Gara:Spectrorage|Garuda:Blood Altar|Gauss:Thermal Sunder|Grendel:Nourish|Gyre:Coil Horizon|Harrow:Condemn|Hildryn:Pillage|Hydroid:Tempest Barrage|Inaros:Desiccation|Ivara:Quiver|Jade:Ophanim Eyes|Khora:Ensnare|Koumei:Omamori|Kullervo:Wrathful Advance|Lavos:Vial Rush|Limbo:Banish|Loki:Decoy|Mag:Pull|Mesa:Shooting Gallery|Mirage:Eclipse|Narin:Neote|Nekros:Terrify|Nezha:Fire Walker|Nidus:Larva|Nokko:Brightbonnet|Nova:Null Star|Nyx:Mind Control|Oberon:Smite|Octavia:Resonator|Oraxia:Webbed Embrace|Protea:Dispensary|Qorvex:Chyrinka Pillar|Revenant:Reave|Rhino:Roar|Saryn:Molt|Sevagoth:Gloom|Sirius & Orion:Jade Stars / Astral Shell|Styanax:Tharros Strike|Temple:Pyrotechnics|Titania:Spellbind|Trinity:Well of Life|Uriel:Remedium|Valkyr:Warcry|Vauban:Tesla Nervos|Volt:Shock|Voruna:Lycath's Hunt|Wisp:Breach Surge|Wukong:Defy|Xaku:Xata's Whisper|Yareli:Aquablades|Zephyr:Airburst"
desc = {a['name'].lower(): a.get('description', '') for x in json.load(open(sys.argv[1])) for a in x.get('abilities') or []}
imgs = {f['name']: f['img'] for f in out}
wikis = {f['name']: f['wiki'] for f in out}
H = []
for p in PAIRS.split('|'):
    frame, ab = p.split(':')
    d = desc.get(ab.lower()) or next((v for k, v in desc.items() if k in [a.lower() for a in ab.split(' / ')]), '')
    H.append(dict(name=ab, group='Abilities', sub=re.sub(r'<[^>]+>', '', d), frame=frame, how='', img=imgs.get(frame), wiki=wikis.get(frame)))
H.sort(key=lambda h: h['name'])
open('site/helminth.js', 'w').write('const HELMINTH=' + json.dumps(H) + ';')
print('helminth', len(H), [h['name'] for h in H if not h['sub']])

# ---- resources: farming spots from wiki.warframe.com/w/Resources ("Recommended Farming Locations") ----
if len(sys.argv) > 3:
    SPOTS = {
     'Alloy Plate': 'Ceres/Gabii, Ceres/Draco, Venus/Malva', 'Argon Crystal': 'Void/Any Survival or Exterminate',
     'Circuits': 'Ceres/Draco, Venus/Malva', 'Control Module': 'Void/Any Survival or Defense, Neptune/Hyena Pack, Neptune/Psamathe, Europa/Naamah (Raptors)',
     'Cryotic': '*/Any Excavation mission', 'Ferrite': 'Void/Any Survival or Defense, Earth/Tikal, Mercury/Apollodorus',
     'Gallium': 'Uranus/Assur, Mars/War (Lieutenant Lech Kril)', 'Hexenon': 'Jupiter/Ganymede, Jupiter/Cameria',
     'Morphics': 'Mars/Wahiba, Mercury/Tolstoj (Captain Vor), Mercury/Apollodorus', 'Nano Spores': 'Deimos/Hyf, Deimos/Terrorem, Deimos/Cambion Drift, Eris/Akkad, Saturn/Piscinas',
     'Neural Sensors': 'Jupiter/Cameria, Jupiter/Themisto (Alad V), Europa/Naamah (Raptors)',
     'Neurodes': 'Lua/Tycho, Deimos/Hyf, Deimos/Terrorem, Deimos/Lephantis, Earth/Tikal, Eris/Zabala', 'Orokin Cell': 'Deimos/Terrorem, Ceres/Draco, Saturn/Piscinas',
     'Oxium': 'Jupiter/Elara, Jupiter/Io, Neptune/Galatea, Neptune/Despina, Lua/Apollo', 'Plastids': 'Phobos/Zeugma, Uranus/Ophelia, Eris/Zabala',
     'Polymer Bundle': 'Uranus/Assur, Uranus/Ophelia, Mercury/Apollodorus', 'Rubedo': 'Void/Any Survival or Defense, Phobos/Zeugma',
     'Salvage': 'Jupiter/Cameria, Mars/Wahiba', 'Tellurium': 'Uranus/Ophelia, Uranus/Caelus, Neptune/Salacia',
    }
    imgn = {}
    for x in ITEMS:
        if x['name'] in SPOTS and x.get('category') in ('Misc', 'Resources') and x.get('imageName'): imgn.setdefault(x['name'], x['imageName'])
    RES = [dict(name=n, img=imgn.get(n), spots=[dict(planet=s.split('/')[0], node=s.split('/', 1)[1]) for s in v.split(', ')]) for n, v in sorted(SPOTS.items())]
    open('site/resources.js', 'w').write('const RESOURCES=' + json.dumps(RES) + ';')
    print('resources', len(RES), [r['name'] for r in RES if not r['img']])

# ---- relics: one entry per relic (Intact refinement), with rewards by rarity ----
if len(sys.argv) > 3:
    R = {}
    for x in ITEMS:
        if x.get('category') != 'Relics' or not x['name'].endswith(' Intact'): continue
        n = x['name'][:-len(' Intact')]
        R[n] = dict(n=n, t=n.split()[0], v=n not in AVAILABLE_RELICS,
                    r=[[r['item']['name'], 'C' if r['chance'] > 20 else 'U' if r['chance'] > 5 else 'R'] for r in x.get('rewards') or []])  # the API's rarity field is wrong; Intact odds are 25.33 / 11 / 2 percent
    TIER = {'Lith': 0, 'Meso': 1, 'Neo': 2, 'Axi': 3, 'Requiem': 4}
    RL = sorted(R.values(), key=lambda r: (TIER.get(r['t'], 9), int(re.sub(r'\D', '', r['n'].split()[1]) or 0), r['n']))
    open('site/relics.js', 'w').write('const RELICS=' + json.dumps(RL, separators=(',', ':')) + ';')
    print('relics', len(RL), 'unvaulted', sum(1 for r in RL if not r['v']))

# ---- Coda weapons: stats from the API plus batch, unique effect and my pick (batches and effects from wiki.warframe.com/w/Coda_Weapons) ----
if len(sys.argv) > 3:
    CODA = {  # name: (shop batch, pick, note)
     'Coda Bassocyst': ('B', 'Top pick', 'Highest damage per shot of any Coda and 40% status. Alt fire mites and the teleport to enemies open to a Mercy finisher add utility.'),
     'Dual Coda Torxica': ('A', 'Top pick', 'Huge 160-round magazine and 25% crit. Spore tagging adds Cold and damage vulnerability, which makes it an easy all-rounder.'),
     'Coda Caustacyst': ('B', 'Top pick', 'Highest damage per hit of the melee Codas with 41% status, and larger corrosive pools from heavy attacks.'),
     'Coda Hirudo': ('B', 'Good', 'Best crit melee: 34% chance and x3.1. Pick it for a crit build.'),
     'Coda Catabolyst': ('A', 'Good', 'Fastest fire rate of the pistols (12 a second) and 50% status. Reloading tosses three grenades.'),
     'Coda Synapse': ('B', 'Good', 'Highest crit of the rifles (40%, x2.7) with 76 rounds at 12 a second.'),
     'Coda Mire': ('A', 'Good', 'Solid status melee (40%), a close second to the Caustacyst.'),
     'Coda Motovore': ('A', 'Good', 'Gains a bonus from your highest physical stat, so it suits impact, puncture or slash builds.'),
     'Coda Sporothrix': ('A', 'Situational', 'Heavy hits and 55% status, but only 5% crit, so it needs a status or crit-boosting build. Larger explosion and faster reload.'),
     'Coda Tysis': ('B', 'Situational', '135 damage per shot and 50% status, but low crit.'),
     'Coda Hema': ('A', 'Situational', 'Burst rifle with a 72-round magazine. Solid numbers, nothing unique.'),
     'Coda Bubonico': ('B', 'Situational', 'Shotgun-style spread with 27% crit. Solid, nothing unique.'),
     'Coda Pathocyst': ('B', 'Skip', 'Slowest attack speed (0.67), so the lowest damage output of the melee Codas. Throws spawn stronger maggots.'),
     'Coda Pox': ('A', 'Skip', 'Smallest magazine (8) and only 10% crit, the weakest numbers of the pistols.'),
    }
    cw = []
    for x in json.load(open(sys.argv[2])):
        if x['name'] not in CODA: continue
        b, pick, note = CODA[x['name']]
        slot = 'Melee' if x['category'] == 'Melee' else f"{x['category']} {x['type'].lower()}"
        shot = x['totalDamage'] * (x.get('multishot') or 1) if x['name'] == 'Coda Bubonico' else x['totalDamage']  # the API lists Bubonico per pellet
        cw.append(dict(name=x['name'], slot=slot, batch=b, pick=pick, note=note, dmg=round(shot), crit=round(x['criticalChance'] * 100), cm=round(x['criticalMultiplier'], 1),
                       status=round(x['procChance'] * 100), rate=round(x['fireRate'] or 0, 2), mag=x.get('magazineSize'), reload=round(x['reloadTime'], 1) if x.get('reloadTime') else None, wiki=x.get('wikiaUrl')))
    order = {'Melee': 0, 'Primary rifle': 1, 'Primary shotgun': 2, 'Primary sniper': 3, 'Secondary pistol': 4}
    cw.sort(key=lambda c: (order.get(c['slot'], 9), -c['dmg']))
    open('site/coda.js', 'w').write('const CODA=' + json.dumps(cw) + ';')
    print('coda', len(cw), sorted(set(CODA) - {c['name'] for c in cw}))
