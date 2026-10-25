"""Builds site/spy.js: the Spy mission vault rewards of Pavlov and Pago (drop rates copied from their wiki.warframe.com pages) with the lowest sell price of each
item from online traders on warframe.market. One request per item with a pause, ~1 minute.  Python 3, no packages:  python3 -I fetch_spy.py"""
import json, os, time, urllib.request
from datetime import date

H = {'Accept': 'application/json', 'Language': 'en', 'Platform': 'pc', 'User-Agent': 'Orbiter (self-hosted Warframe companion)'}
def mods(names, p): return [(n, p) for n in names.split('|')]
MISSIONS = [
 ('pavlov', 'Pavlov', 'Lua', 'https://wiki.warframe.com/w/Pavlov', {
  'A': mods("Blood Rush|Fast Hands|Hydraulic Crosshairs|Piercing Hit|Pistol Gambit|Point Strike|Shrapnel Shot", 12.18) + [('Endo x100', 12.18), ('Astral Twilight', 1.29), ('Gnashing Payara', 1.29)],
  'B': mods("Catalyzer Link|Cryo Rounds|Deep Freeze|Focused Defense|Hell's Chamber|Hornet Strike|No Return|North Wind|Reflex Coil|Shocking Touch|Stormbringer|Streamline|Target Cracker", 7.49) + [('Crushing Ruin', 1.29), ('High Noon', 1.29)],
  'C': [('Coiling Viper', 37.94), ('Failsafe', 37.94), ('Rime Rounds', 11.06), ('Scattering Inferno', 11.06), ('Cleaving Whirlwind', 2.01)]}),
 ('pago', 'Pago', 'Kuva Fortress', 'https://wiki.warframe.com/w/Pago', {
  'A': [('Credit Cache x2500', 20), ('Harrow Neuroptics Blueprint', 16.67)] + mods("Power Throw|Stabilizer|Steady Hands|Stretch", 13.33) + [('Endo x200', 10)],
  'B': mods("Arrow Mutation|Covert Lethality|Frigid Blast|Frostbite|Runtime|Scorch|Shotgun Ammo Mutation|Sniper Ammo Mutation|Thermite Rounds|Untraceable", 10),
  'C': [(f'Meso {c} Relic', 9.68) for c in 'A12 D8 K8 L5 V13 V15 X1 Y2'.split()] + [(f'Neo {c} Relic', 3.22) for c in 'A16 C7 C8 C9 T11 V12 Y1'.split()]}),
]
def get(url): return json.load(urllib.request.urlopen(urllib.request.Request(url, headers=H), timeout=60))['data']

def main():
    slugs = {x['i18n']['en']['name']: x['slug'] for x in get('https://api.warframe.market/v2/items')}
    cache, out = {}, []
    for id, name, where, wiki, vaults in MISSIONS:
        v = {}
        for k, items in vaults.items():
            v[k] = []
            for n, p in items:
                row = {'n': n, 'p': p, 'price': None, 'note': ''}
                if n not in slugs: row['note'] = 'not tradable'
                else:
                    if n not in cache:
                        time.sleep(1.1)
                        online = sorted(o['platinum'] for o in get(f'https://api.warframe.market/v2/orders/item/{slugs[n]}') if o['type'] == 'sell' and o.get('visible', True) and o['user']['status'] != 'offline')
                        cache[n] = online[0] if online else None
                    row['price'] = cache[n]
                    if cache[n] is None: row['note'] = 'no online offer'
                v[k].append(row)
        out.append({'id': id, 'name': name, 'where': where, 'wiki': wiki, 'vaults': v})
    open(os.path.join(os.path.dirname(os.path.abspath(__file__)), 'site', 'spy.js'), 'w', encoding='utf8').write('const SPY=' + json.dumps({'date': date.today().isoformat(), 'missions': out}, ensure_ascii=False, separators=(',', ':')) + ';')
    print('priced', len(cache), 'items')

if __name__ == '__main__': main()
