# Regenerates the data files in site/ (frames, weapons, companions, mods, arcanes, helminth, resources) from api.warframestat.us.
#   curl -s "https://api.warframestat.us/warframes?language=en" -o warframes.json
#   curl -s "https://api.warframestat.us/weapons?language=en" -o weapons.json
#   curl -s "https://api.warframestat.us/items?language=en" -o items.json      (about 78 MB)
#   python3 -I gen.py warframes.json weapons.json items.json
import json, re, sys
ITEMS = json.load(open(sys.argv[3])) if len(sys.argv) > 3 else []
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
def short(loc): return re.sub(r', Rotation [ABC]', '', loc)
def how(x):
    parts = []
    for c in x.get('components') or []:
        locs = []
        for r in c.get('drops', []):
            s = short(r['location'])
            if s not in locs: locs.append(s)
        if locs: parts.append(f"{c['name']}: {', '.join(locs[:2])}")
    out = '; '.join(parts) or 'See wiki'
    return out + (f" | Blueprint: market {x['marketCost']}p" if x.get('marketCost') else '')
out = []
for x in d:
    n = x['name']
    if n in ('Helminth', 'Sirius & Orion'): continue
    prime = bool(x.get('isPrime'))
    if prime and n == 'Excalibur Prime': tier, h, t = 6, None, 'Founders/Prime Access only - not obtainable (trade only)'
    elif prime and x.get('vaulted'): tier, h, t = 6, None, 'Vaulted: trade with players or wait for Prime Resurgence/Prime Vault'
    elif prime: tier, h, t = 4, 15, 'Void Relics (open via fissure missions). ' + how(x)
    else:
        h = EST.get(n, 8); tier = 1 if h <= 1 else 2 if h <= 3 else 3 if h <= 8 else 4 if h <= 20 else 5
        t = how(x)
    out.append(dict(name=n, prime=prime, tier=tier, hours=h, how=t, wiki=x.get('wikiaUrl'), img=x.get('imageName'), roles=R.get(n.removesuffix(' Prime'), [])))
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
            return ('Vaulted: trade parts with players or wait for Prime Resurgence/Vault. ' if 'Vaulted' in tags or x.get('vaulted') else 'Void Relics (fissure missions). ') + drops(x)
        d = drops(x)
        if d: return d + (f" | Blueprint: market {x['marketCost']}cr" if x.get('marketCost') else '')
        return f"Blueprint: market {x['marketCost']}cr" if x.get('marketCost') else 'Starter weapon, Market, Dojo research or quest reward - see wiki'
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
