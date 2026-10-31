"""Builds site/syndicates.js: what Arbiters of Hexis, Cephalon Suda and Cephalon Simaris sell for standing, read from the {{SynOfferBox}} rows in the wiki.warframe.com page sources.
Prices are not stored here: the server looks them up on demand (see syndprices.js).  Python 3, no packages:  python3 -I fetch_syndicates.py"""
import json, os, re, urllib.request

PAGES = [('hexis', 'Arbiters of Hexis', 'Arbiters_of_Hexis'), ('suda', 'Cephalon Suda', 'Cephalon_Suda'), ('simaris', 'Cephalon Simaris', 'Cephalon_Simaris')]

def offers(page):
    raw = urllib.request.urlopen(urllib.request.Request(f'https://wiki.warframe.com/w/{page}?action=raw', headers={'User-Agent': 'Orbiter-dev'}), timeout=30).read().decode('utf8')
    out = []
    for row in re.findall(r'\{\{SynOfferBox\|([^}]*)\}\}', raw):
        f = [x.strip() for x in row.split('|')]
        if len(f) < 4: continue
        cost = int(re.sub(r'\D', '', f[3]) or 0)
        rank = next((x for x in f[4:] if x and '=' not in x), '')
        out.append({'n': f[2], 'cat': f[1].replace('_', ' ').split('#')[0], 'cost': cost, 'rank': rank, 'bp': any(x.startswith('blueprint=') for x in f[4:])})
    return out

def main():
    data = [{'id': i, 'name': n, 'wiki': f'https://wiki.warframe.com/w/{p}', 'items': offers(p)} for i, n, p in PAGES]
    open(os.path.join(os.path.dirname(os.path.abspath(__file__)), 'site', 'syndicates.js'), 'w', encoding='utf8').write('const SYNDICATES=' + json.dumps(data, ensure_ascii=False, separators=(',', ':')) + ';')
    print({s['name']: len(s['items']) for s in data})

if __name__ == '__main__': main()
