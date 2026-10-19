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
     'Coda Tysis': ('B', 'Situational', '135 damage per shot (part of it Corrosive damage over time) and 50% status, but low crit.'),
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
        scale = shot / x['totalDamage'] if x['totalDamage'] else 1
        types = sorted(((k, round(v * scale)) for k, v in (x.get('damage') or {}).items() if k != 'total' and v and round(v * scale) > 0), key=lambda kv: -kv[1])
        cw.append(dict(name=x['name'], slot=slot, types=types, batch=b, pick=pick, note=note, dmg=round(shot), crit=round(x['criticalChance'] * 100), cm=round(x['criticalMultiplier'], 1),
                       status=round(x['procChance'] * 100), rate=round(x['fireRate'] or 0, 2), mag=x.get('magazineSize'), reload=round(x['reloadTime'], 1) if x.get('reloadTime') else None, wiki=x.get('wikiaUrl')))
    order = {'Melee': 0, 'Primary rifle': 1, 'Primary shotgun': 2, 'Primary sniper': 3, 'Secondary pistol': 4}
    cw.sort(key=lambda c: (order.get(c['slot'], 9), -c['dmg']))
    open('site/coda.js', 'w').write('const CODA=' + json.dumps(cw) + ';')
    print('coda', len(cw), sorted(set(CODA) - {c['name'] for c in cw}))

# ---- Kuva weapons: stats from the API, my pick and note per weapon (notes are drawn from those numbers) ----
if len(sys.argv) > 3:
    KUVA = {  # name: (pick, note)
     'Kuva Bramma': ('Top pick', 'Highest damage per shot of any Kuva weapon (mostly Blast) with 35% crit. Slow fire rate.'),
     'Kuva Chakkhurr': ('Top pick', 'Highest crit of the Kuva primaries (50%, x2.3), mostly Impact damage.'),
     'Kuva Nukor': ('Top pick', 'Radiation-only damage with a x5 crit multiplier (7% crit), 50% status and 77 rounds at 10 a second.'),
     'Kuva Zarr': ('Top pick', 'Five-round launcher with big Blast hits and a x2.5 crit multiplier.'),
     'Kuva Tonkor': ('Good', 'Big hits with 30% crit and x2.5, fires 3 a second but holds a single round.'),
     'Kuva Ogris': ('Good', 'Status launcher: 47% status but only 9% crit, so build it for status.'),
     'Kuva Ayanga': ('Good', 'Arch-gun with 35% crit and 33 rounds, mostly Blast.'),
     'Kuva Grattler': ('Good', 'Fast arch-gun with a 60-round magazine, mostly Blast.'),
     'Kuva Shildeg': ('Good', 'Best crit of the Kuva melee weapons (31%, x2.7), mostly Puncture.'),
     'Kuva Ghoulsaw': ('Good', 'Slash-heavy melee with 32% status.'),
     'Kuva Seer': ('Good', '200 damage per shot including 69 Corrosive, with 33% status.'),
     'Kuva Kraken': ('Good', 'Fast pistol (6.8 a second), mostly Impact.'),
     'Kuva Karak': ('Good', 'Fast rifle (11.7 a second) with 70 rounds and 31% status.'),
     'Kuva Hind': ('Good', 'Fast rifle (9 a second) with a 90-round magazine and 33% status.'),
     'Kuva Quartakk': ('Good', '88 rounds and 33% status; the highest damage per hit of the Kuva rifles.'),
     'Kuva Hek': ('Good', 'Puncture-heavy shotgun with 23% crit.'),
     'Kuva Sobek': ('Good', 'Shotgun with 20 rounds and 21% status, mostly Impact.'),
     'Kuva Drakgoon': ('Situational', 'Slash-heavy shotgun, but only 9% status.'),
     'Kuva Kohm': ('Situational', '209-round magazine, but low damage per pellet and 10% status.'),
     'Kuva Twin Stubbas': ('Situational', '10 shots a second with 114 rounds, but only 27 damage per shot.'),
     'Kuva Brakk': ('Skip', 'The weakest numbers of the Kuva weapons: 15 damage per shot and 11% status.'),
    }
    kw = []
    for x in json.load(open(sys.argv[2])):
        if x['name'] not in KUVA or not x.get('masterable'): continue
        pick, note = KUVA[x['name']]
        slot = {'Arch-Gun': 'Arch-gun', 'Melee': 'Melee'}.get(x['category']) or f"{x['category']} {x['type'].lower()}"
        mult = x.get('multishot') or 1
        scale = mult if x['type'] == 'Shotgun' and mult > 1 else 1  # the API lists shotgun damage per pellet
        shot = round(x['totalDamage'] * scale)
        types = sorted(((k, round(v * scale)) for k, v in (x.get('damage') or {}).items() if k != 'total' and v and round(v * scale) > 0), key=lambda kv: -kv[1])
        kw.append(dict(name=x['name'], slot=slot, pick=pick, note=note, types=types, dmg=shot, crit=round(x['criticalChance'] * 100), cm=round(x['criticalMultiplier'], 1),
                       status=round(x['procChance'] * 100), rate=round(x['fireRate'] or 0, 2), mag=x.get('magazineSize'), reload=round(x['reloadTime'], 1) if x.get('reloadTime') else None, wiki=x.get('wikiaUrl')))
    order = ['Primary rifle', 'Primary shotgun', 'Primary launcher', 'Primary bow', 'Secondary pistol', 'Secondary dual pistols', 'Melee', 'Arch-gun']
    kw.sort(key=lambda c: (order.index(c['slot']) if c['slot'] in order else 9, -c['dmg']))
    open('site/kuva.js', 'w').write('const KUVA=' + json.dumps(kw) + ';')
    print('kuva', len(kw), sorted(set(KUVA) - {c['name'] for c in kw}))

# ---- Incarnon Genesis weapons (Duviri Circuit pool, names from wiki.warframe.com/w/Incarnon): base stats from the API, verdicts only where I wrote one ----
if len(sys.argv) > 3:
    GENESIS = {
     'Primary': 'Torid Boar Boltor Braton Burston Dera Dread Gorgon Latron Miter Paris Soma Strun Sybaris Vectis'.split(),
     'Secondary': ['Angstrum', 'Atomos', 'Ballistica', 'Bronco', 'Cestra', 'Despair', 'Dual Toxocyst', 'Furis', 'Gammacor', 'Kunai', 'Lato', 'Lex', 'Sicarus', 'Stug', 'Vasto', 'Zylok'],
     'Melee': 'Ack & Brunt|Anku|Bo|Ceramic Dagger|Destreza|Dual Ichor|Furax|Hate|Magistar|Nami Solo|Obex|Okina|Sibear|Skana'.split('|'),
    }
    VERDICT = {  # every Genesis weapon; verdicts are my judgement from base stats and the wiki's Incarnon notes
     'Sybaris': ('Top pick', 'Burst rifle with the best crit of this week\'s five (25%) and balanced physical damage. A solid take for the Tier 5 slot.'),
     'Okina': ('Top pick', 'The only melee on offer: sai with 140 base damage, mostly Slash and Puncture. In Incarnon form it adds +30% movement speed (wiki).'),
     'Sicarus': ('Good', 'Burst pistol with 16% crit and mostly Impact damage, but only 6% status.'),
     'Dera': ('Good', 'Fast auto rifle (11 shots a second, 45 rounds), mostly Puncture. Only 8% crit, so build it for status or puncture.'),
     'Cestra': ('Situational', 'Fast auto pistol with a 60-round magazine, but only 26 damage and 6% crit per shot.'),
     'Soma': ('Top pick', 'Crit 30% with a x3 multiplier and 15 shots a second from a 100-round magazine. Best crit stats of any rifle here.'),
     'Dread': ('Top pick', 'Bow with 50% crit and 336 damage per arrow. Slow to draw, but each hit is large.'),
     'Hate': ('Top pick', '230 damage, 30% crit and x2.5. Strongest raw melee numbers in the pool.'),
     'Dual Ichor': ('Top pick', '25% crit and a x3 multiplier, a very high crit ceiling.'),
     'Destreza': ('Good', '28% crit and 158 damage. Fast and crit-based.'),
     'Furax': ('Good', '25% crit and x2.3. Low status, so build for crit.'),
     'Obex': ('Good', '25% crit, but only 120 damage and 10% status.'),
     'Sibear': ('Good', '270 damage and 30% status. Only 15% crit, so a status build suits it.'),
     'Nami Solo': ('Good', '172 damage with 25% status. Balanced, leans on status over crit.'),
     'Anku': ('Good', '170 damage, 20% crit, x2. Solid all-round numbers.'),
     'Magistar': ('Situational', 'Slow swings: 210 damage but 20% crit and 10% status. Strong hits, little else.'),
     'Ack & Brunt': ('Situational', 'Slow swings: 149 damage, 20% crit, 10% status. Nothing stands out.'),
     'Bo': ('Situational', '140 damage, 12% crit and 20% status. Fine for status builds, weak on crit.'),
     'Ceramic Dagger': ('Skip', 'Only 10% crit and a x1.5 multiplier, with 140 damage. Low across the board.'),
     'Skana': ('Skip', 'Only 5% crit, x1.5 and 120 damage. Outclassed by the other melee here.'),
     'Gorgon': ('Good', 'Auto rifle with 90 rounds and 12.5 shots a second. Crit is only 17%, but it is dependable.'),
     'Paris': ('Good', 'Bow with 320 damage and 30% crit per arrow. Slow, but heavy hits.'),
     'Vectis': ('Good', 'Sniper with 225 damage, 25% crit and 30% status. One shot at a time.'),
     'Miter': ('Good', 'Burst weapon with 250 damage and 50% status, but 5% crit. Build it for status.'),
     'Boltor': ('Situational', 'Reliable auto rifle: 25 damage, 8.75 shots a second and 14% status. Average.'),
     'Torid': ('Situational', 'Launcher with 140 damage and 23% status, but a 5-round magazine and 15% crit.'),
     'Latron': ('Situational', 'Burst rifle with 55 damage and x2 crit, but a 12% crit chance and 15-round magazine.'),
     'Braton': ('Situational', 'Basic rifle: 24 damage, 12% crit and 6% status. Needs mods to keep up.'),
     'Burston': ('Situational', '30 damage, 18% status but only 6% crit. A status build is the only way to use it well.'),
     'Boar': ('Skip', 'Shotgun with 22 damage, 10% crit and 7% status per pellet. Weak on every stat.'),
     'Strun': ('Skip', 'Shotgun with 25 damage, 8% crit and 5% status per pellet and a 6-round magazine.'),
     'Lex': ('Good', 'Heavy revolver with 130 damage, 20% crit and x2. Only 6 rounds, but each shot hits hard.'),
     'Vasto': ('Good', 'Revolver with 90 damage and 20% crit. Slow to reload but hits well.'),
     'Zylok': ('Good', 'Pistol with 140 damage and 26% status. Leans on status, 8% crit.'),
     'Despair': ('Situational', 'Throwing weapon with 58 damage and 16% crit. Average numbers.'),
     'Dual Toxocyst': ('Situational', 'High 37% status but only 75 damage and 5% crit. A status specialist.'),
     'Angstrum': ('Situational', 'One rocket at a time: 450 damage and 22% status. Crit is 16%, and it only holds 1 round.'),
     'Atomos': ('Situational', '70-round beam with 29 damage and 15% crit. Needs support from mods.'),
     'Gammacor': ('Skip', 'Only 16 damage per hit, 8% crit and 20% status. Low damage even at 12 hits a second.'),
     'Ballistica': ('Skip', 'Only 2% crit and 10% status with 100 damage. Not much to build on.'),
     'Stug': ('Skip', '79 damage but 5% crit and no status chance at all.'),
     'Furis': ('Skip', 'Dual pistols with 20 damage, 5% crit and 12% status. Weak across the board.'),
     'Bronco': ('Skip', 'Shotgun-style pistol with 42 damage, 6% crit and only 2 rounds.'),
     'Lato': ('Skip', 'Starter pistol: 40 damage, 10% crit, 6% status.'),
     'Kunai': ('Skip', 'Thrown daggers with 46 damage, 8% crit and 8% status.'),
    }
    inc = {}
    for x in json.load(open(sys.argv[2])):
        for slot, names in GENESIS.items():
            if x['name'] in names and x.get('masterable') and x['category'] == ('Melee' if slot == 'Melee' else slot):
                pick, note = VERDICT.get(x['name'], (None, None))
                inc[x['name']] = dict(name=x['name'], slot=slot, type=x['type'], pick=pick, note=note,
                    types=sorted(((k, round(v)) for k, v in (x.get('damage') or {}).items() if k != 'total' and v and round(v) > 0), key=lambda kv: -kv[1]),
                    dmg=round(x['totalDamage']), crit=round(x['criticalChance'] * 100), cm=round(x['criticalMultiplier'], 1), status=round(x['procChance'] * 100),
                    rate=round(x['fireRate'] or 0, 2), mag=x.get('magazineSize'), reload=round(x['reloadTime'], 1) if x.get('reloadTime') else None, wiki=x.get('wikiaUrl'))
    open('site/incarnon.js', 'w').write('const INCARNON=' + json.dumps(inc) + ';')
    print('incarnon', len(inc), 'of', sum(len(v) for v in GENESIS.values()), 'missing:', sorted(set(sum(GENESIS.values(), [])) - set(inc)))
