"""Builds the Void Cascade builds data (site/cascade.js) from the public Cascade Club builds guide (a Google Doc) and every build document it links to.
Text only: loadout screenshots stay in the original documents, which every entry links to.  Python 3, no packages:  python3 -I fetch_cascade.py"""
import html, json, os, re, sys, time, urllib.request
from urllib.parse import unquote

MAIN = '1m11trfxy8_DeRQn9FarkiW7Bki5PMdgCHvxkbJ9e5D8'
PAUSE = 0.7  # seconds between requests, to be kind to Google
EMOJI = {'🟩': 'g', '🟨': 'y', '🟧': 'o', '🟥': 'r'}

def get(id, fmt):
    r = urllib.request.urlopen(urllib.request.Request(f'https://docs.google.com/document/d/{id}/export?format={fmt}', headers={'User-Agent': 'Mozilla/5.0'}), timeout=30)
    time.sleep(PAUSE)
    return r.read().decode('utf8').lstrip('﻿')

def paragraphs(page):
    out = []
    for tag, p in re.findall(r'<(p|li|h\d)\b[^>]*>(.*?)</\1>', page[page.index('<body'):], re.S):
        text = html.unescape(re.sub('<[^>]+>', '', p)).replace('\xa0', ' ').strip()
        ids = []
        for u in re.findall(r'href="([^"]+)"', p):
            m = re.search(r'/document/d/([\w-]+)', unquote(re.sub(r'.*google\.com/url\?q=', '', u)))
            if m and m.group(1) != MAIN and m.group(1) not in ids: ids.append(m.group(1))
        if text: out.append((tag, text, ids))
    return out

def build_doc(txt):
    """-> list of builds {title, meta[], notes[[text, [sub...]]], by}"""
    lines = txt.split('\n')[1:]  # first line is the document title
    builds, head, notes = [], [], []
    def flush(by=''):
        nonlocal head, notes
        if head or notes or by: builds.append({'title': head[0] if head else '', 'meta': head[1:], 'notes': notes, 'by': by})
        head, notes = [], []
    for raw in lines:
        s = raw.replace('\t', '').rstrip()
        if not s.strip(): continue
        m = re.match(r'\s*Build provided by (.+)', s)
        if m: flush(m.group(1).strip()); continue
        if s.lstrip().startswith('*'):
            text = s.lstrip()[1:].strip()
            if raw.lstrip('\t').startswith(' ') and notes: notes[-1][1].append(text)
            else: notes.append([text, []])
        elif notes:  # wrapped continuation of the previous bullet
            (notes[-1][1][-1:] or notes[-1][:1])
            if notes[-1][1]: notes[-1][1][-1] += ' ' + s.strip()
            else: notes[-1][0] += ' ' + s.strip()
        else: head.append(s.strip())
    flush()
    return [b for b in builds if b['title'] or b['notes']]

def extra_doc(txt):
    """General tips: headings (short lines without a full stop), paragraphs and bullets -> [{h, items:[[kind, text]]}]"""
    secs = []
    for raw in txt.split('\n')[1:]:
        s = raw.strip()
        if not s: continue
        if s.startswith('*'):
            kind, t = ('sub', s[1:].strip()) if raw.startswith(' ') else ('li', s[1:].strip())
        elif len(s) <= 80 and not s.endswith(('.', ':')) and not secs and not s[0].islower() or (len(s) <= 80 and not s.endswith(('.', ':', ',')) and secs and not secs[-1]['items']):
            kind, t = 'h', s
        elif len(s) <= 70 and not s.endswith(('.', ':', ',', '!', '?', ')')) and not raw.startswith(' '):
            kind, t = 'h', s
        else: kind, t = 'p', s
        if kind == 'h' or not secs: secs.append({'h': t if kind == 'h' else '', 'items': []})
        else: secs[-1]['items'].append([kind, t])
    return secs

def main():
    page = get(MAIN, 'html')
    P = paragraphs(page)
    sections, cur, grp, legend, started = [], None, None, [], False
    extra = []
    for tag, text, ids in P:
        if re.fullmatch(r'_+', text): started = True; continue
        if not started:
            continue
        m = re.match(r'(\d)\. (.+)', text)
        if tag.startswith('h') and m:
            cur = {'id': re.sub(r'\W+', '-', m.group(2).lower()).strip('-'), 'title': m.group(2).title().replace('/', ' / '), 'desc': '', 'groups': []}; sections.append(cur); grp = None; continue
        if not cur: continue
        m = re.match(r'\d[a-z]\) (.+)', text)
        if m: grp = {'title': m.group(1), 'desc': '', 'items': []}; cur['groups'].append(grp); continue
        if text.startswith('If you want to add a build'): break
        if tag != 'p' and tag != 'li': continue
        if len(text) > 90 and not ids:
            if text[0] in EMOJI: legend.append([EMOJI[text[0]], text[1:].strip()])
            elif grp: grp['desc'] = text
            else: cur['desc'] = text
            continue
        if not grp: continue
        d = EMOJI.get(text[0], ''); text = text[1:].strip() if d else text
        m = re.fullmatch(r'(.*?)\s*\((.*)\)', text)
        n, t = (m.group(1), m.group(2)) if m else (text, '')
        if ' - ' in n: n, t = n.split(' - ', 1)
        grp['items'].append({'n': n, 'd': d, 't': t, 'doc': ids[0] if ids else ''})
    tips = [(t, i[0]) for tag, t, i in P if tag == 'li' and i and i[0] != MAIN and not any(t == x['n'] for s in sections for g in s['groups'] for x in g['items']) and t[0].isupper() and len(t) > 25]
    docs, ids = {}, {x['doc'] for s in sections for g in s['groups'] for x in g['items'] if x['doc']}
    for k, id in enumerate(sorted(ids)):
        docs[id] = build_doc(get(id, 'txt')); print(f'{k + 1}/{len(ids)}', file=sys.stderr)
    for title, id in tips: extra.append({'id': id, 'title': title, 'sections': extra_doc(get(id, 'txt'))})
    intro = [t for tag, t, i in P if tag == 'p' and len(t) > 90 and not t.startswith(('Measuring',))][:2]
    out = {'main': MAIN, 'intro': intro, 'legend': legend, 'sections': sections, 'docs': docs, 'extra': extra}
    open(os.path.join(os.path.dirname(os.path.abspath(__file__)), 'site', 'cascade.js'), 'w', encoding='utf8').write('const CASCADE=' + json.dumps(out, ensure_ascii=False, separators=(',', ':')) + ';')
    print('sections', [(s['title'], sum(len(g['items']) for g in s['groups'])) for s in sections], 'docs', len(docs), 'extra', [e['title'][:30] for e in extra], 'legend', len(legend))

if __name__ == '__main__': main()
