# Records which picture belongs to each item in Baro Ki'Teer's current stock (site/baro_icons.js). The server downloads the pictures itself.
# Usage: python3 -I fetch_baro_icons.py [items.json]    (without the argument it downloads the 78 MB item list from api.warframestat.us once)
# Re-run it when a new visit has items the page shows without an icon; the list accumulates, then commit baro_icons.js.
import io, json, os, re, sys, tempfile, urllib.request
UA = {'User-Agent': 'orbiter'}
get = lambda u: urllib.request.urlopen(urllib.request.Request(u, headers=UA), timeout=120).read()
stock = json.loads(get('https://api.warframestat.us/pc/voidTrader?language=en'))['inventory']
if len(sys.argv) > 1: items = json.load(open(sys.argv[1]))
else: items = json.loads(get('https://api.warframestat.us/items?language=en'))
byu = {x['uniqueName']: x for x in items}
byn = {}
for x in items: byn.setdefault(x['name'], x)
path = 'site/baro_icons.js'
known = json.loads(open(path).read().split('=', 1)[1].rstrip(';')) if os.path.exists(path) else {}
miss = []
for i in stock:
    x = byu.get(i['uniqueName'].replace('/Lotus/StoreItems/', '/Lotus/')) or byu.get(i['uniqueName']) or byn.get(i['item'])
    img = x and x.get('imageName')
    if not img: miss.append(i['item']); continue
    known[i['item']] = img
open(path, 'w').write('const BARO_ICONS=' + json.dumps(known) + ';')
print(len(stock), 'items,', len(known), 'icons known; no icon for:', miss)
