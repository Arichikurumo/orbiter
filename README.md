# Orbiter

A self-hosted companion for [Warframe](https://www.warframe.com/): a daily and weekly task checklist, collection trackers, and farming guides in one small web app. Your progress is stored in a SQLite file on your own machine.

> Orbiter is an unofficial fan project. It is not affiliated with, endorsed by or sponsored by Digital Extremes. Warframe and everything that belongs to it are the property of Digital Extremes Ltd.

## Features

- **Tasks:** the daily and weekly checklist (with sub-tasks, vendors and reset timers) that resets itself at 00:00 UTC and on Mondays.
- **Collection:** every Warframe, weapon and companion with *collected* and *mastered* ticks (frames and weapons), search, filters, how to get it, and an "easiest first" order for Warframes with role tags. Weapons are grouped by type, melee by weapon class.
- **Upgrades:** mods, arcanes and the Helminth (which ability comes from which frame).
- **Relics:** every Prime item you can farm from relics right now, the current Prime Resurgence rotation, and all relics with their rewards, plus drop rates per refinement stage, a relic finder (search all relics by name or reward) and a calculator for how many relics you need to open to be sure of a drop.
- **Resources:** an interactive star chart showing where to farm each resource.
- **Guides:** this season's Nightwave acts plus every recoverable act with tips, syndicate leveling, Kahl's Garrison missions, a Coda weapons comparison with buying advice, and Baro Ki'Teer.
- **Home:** the current game version, active events, what is coming up and the latest news.
- Runs as a single container and works on a phone. Progress is saved on the server (and in the browser), so it survives restarts and shows up on every device that opens it.

## Quick start

You need Docker (or Podman) with the compose plugin and an internet connection.

**Without cloning anything**, in an empty folder:

```bash
curl -fsSLO https://raw.githubusercontent.com/Arichikurumo/orbiter/main/compose.install.yaml
docker compose -f compose.install.yaml up -d
```

**From a clone:**

```bash
git clone https://github.com/Arichikurumo/orbiter.git
cd orbiter
docker compose up -d --build
```

Then open <http://localhost:8080>. To use another port, set `ORBITER_PORT`, for example `ORBITER_PORT=8090 docker compose up -d`.

With Podman use `podman compose` instead of `docker compose`.

### First start: pictures

No game artwork is stored in this repository. On the first start the server downloads the pictures it needs (about 2,300 small item, mod and weapon icons, the star chart, syndicate flags and a few mission images) from public sources, shrinks them to WebP and keeps them in the data volume. This takes a few minutes. A banner on every page shows the progress, and the pictures appear as they arrive. It only happens once, because the pictures are kept in the volume and any that failed are retried on the next start.

Sources: item pictures from [WFCD/warframe-items](https://github.com/WFCD/warframe-items), the star chart, flags and mission images from the [Warframe Wiki](https://wiki.warframe.com/).

### Your data

Everything you tick is stored in `/data/state.db` (SQLite) inside the container, on the `orbiter-data` volume, next to the downloaded pictures. Rebuilding or recreating the container keeps it. Removing the volume (`docker compose down -v`) deletes it, so back it up if it matters:

```bash
docker compose cp orbiter:/data/state.db ./state-backup.db
```

### Backup and restore

Open **Backup & restore** (link at the bottom of every page). *Download backup* saves your whole collection as one JSON file. To load it again, on this or another install, choose the file on the same page: Orbiter shows what is inside and lets you **replace** your progress or **merge** it with what you have. By default it downloads a backup of your current progress first.

The same file is available from the command line: `curl -o orbiter-backup.json http://localhost:8080/api/export`.

### Data model (stable between versions)

Progress is a small JSON document, stored in SQLite and used in backup files exactly as stored:

```json
{ "tasks": { "login": true }, "owned": { "Rhino": true, "M|Rhino": true, "w:Skana": true }, "reset": { "d": 0, "w": 0 } }
```

`owned` keys: a plain name is a collected Warframe, `M|<key>` marks an item as mastered, and the prefixes `w:` weapons, `c:` companions, `m:` mods, `a:` arcanes and `h:` Helminth abilities. `tasks` holds ticked task ids, and `reset` the last daily and weekly reset. **New versions only add keys; they never rename or remove them**, so updating never resets anyone's progress and old backups keep loading. Backup files carry a `version` number for future migrations.

### Updating

```bash
git pull && docker compose up -d --build        # from a clone
docker compose -f compose.install.yaml up -d --build   # one-file install
```

Your data and pictures stay in the volume.

## Security notes

Orbiter has **no login**. Anyone who can reach the port shares one save and can change it. Run it on your own computer or home network, or put it behind a reverse proxy with authentication before exposing it to the internet.

The server only accepts a small JSON document with ticks, validates and trims it, rejects cross-site writes, and sends a strict content-security policy.

## Live data and the internet

Home, Tasks (Baro timer) and the Nightwave and Baro pages read live data from the community API at [api.warframestat.us](https://docs.warframestat.us/) (events, news, Baro, Nightwave, game version). It is requested when a page opens and then at most once an hour. Without a connection those parts say they are unavailable and everything else keeps working.

## Development

Needs Node.js 24 or newer.

```bash
npm install
npm test                                              # server tests (node --test)
DB=./data/state.db IMG_DIR=./data/img node server.js  # http://localhost:8080
```

Environment variables: `PORT` (default 8080), `DB` (default `/data/state.db`, the SQLite file), `IMG_DIR` (default `/data/img`, where pictures are downloaded) and `FETCH_IMAGES=0` to skip the picture download.

### Regenerating the game data

The lists in `site/*.js` are generated from the warframestat.us API with `gen.py` (Python 3, no packages needed):

```bash
curl -s "https://api.warframestat.us/warframes?language=en" -o warframes.json
curl -s "https://api.warframestat.us/weapons?language=en"   -o weapons.json
curl -s "https://api.warframestat.us/items?language=en"     -o items.json   # about 78 MB
python3 -I gen.py warframes.json weapons.json items.json
```

Some content is written by hand and is not generated: the task list and guides in `site/index.html`, farming-time estimates and role tags in `gen.py`, `site/nightwave.js` (all Nightwave acts), and the melee classes in `meleeclass.json` (taken from the wiki's weapon data). New items from a new Baro visit show a Ducat icon until you run `python3 -I fetch_baro_icons.py` and commit the updated `site/baro_icons.js`.

Which relics can drop right now is the `AVAILABLE_RELICS` list in `gen.py`, taken from the wiki's "Unvaulted/Available" list on the Void Relic page, because the API's own vaulted flag per relic is out of date. Update that list when relics are vaulted or unvaulted, then rerun `gen.py`.

Descriptions of tasks, tips and "what to buy first" are general advice written from the wiki and game knowledge. Check them against the game before relying on them.

## Credits and licenses

- Code: [MIT](LICENSE).
- Item data and live world state: [warframestat.us](https://warframestat.us/) and [WFCD/warframe-items](https://github.com/WFCD/warframe-items).
- Drop locations, guides and class data summarised from the [Warframe Wiki](https://wiki.warframe.com/) (text there is CC BY-SA).
- Game names, text and artwork belong to Digital Extremes Ltd. Pictures are downloaded by your own instance and are not part of this repository.
