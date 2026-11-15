# Hosting the segment + causal rating task (next to the matching task)

Branch `segcausal`. Raters open a URL, log in with a username and password, and for
each story (Part 1) check the story's event segmentation and (Part 2) rate causal
links between the original events. Everything they produce is saved on the server;
there is nothing for them to install, download, upload or email.

This guide assumes the recall-matching task from the `dev` branch is already hosted
by following its `HOSTING.md`. The causal task is added **to that same setup**:
same server, same `narraters` system user, same `/srv/narraters` workspace, same
`benchmark/` folder with `unrated/` in and `rated/<username>/` out, same
`benchmark-sync` group and the same rsync commands. It gets its own program files,
service, port, website address and account list, so it never changes anything the
matching task uses.

| | matching task (`dev` branch) | causal task (this branch) |
|---|---|---|
| system user | `narraters` | `narraters` (same) |
| workspace | `/srv/narraters` | `/srv/narraters` (same) |
| data folder | `/srv/narraters/benchmark` | `/srv/narraters/benchmark` (same) |
| sync | `benchmark-sync` group, rsync of `unrated/` and `rated/` | same group, same rsync |
| stories in | `unrated/narraters-<datasource>-matching/<story>/matches/…csv` | `unrated/narraters-<datasource>-segcausal/<story>/…` |
| results out | `rated/<user>/<user>-<datasource>-matching/<story>/matches/…csv` | `rated/<user>/<user>-<datasource>-segcausal/<story>/…` |
| program (virtual environment) | `/srv/narraters/.venv` | `/srv/narraters/.venv-segcausal` |
| systemd unit | `narraters.service` | `narraters-segcausal.service` |
| loopback port | 5000 | 5001 |
| domain | e.g. `narraters.example.com` | e.g. `causal.example.com` |
| Caddy | site block in `/etc/caddy/Caddyfile` | second site block **appended** to the same file |
| accounts | `/srv/narraters/.narraters/users.json` | `/srv/narraters/.narraters-segcausal/users.json` (separate) |
| login cookie | `session` | `narraters_segcausal_session` |

Each app only reads its own kind of folder: the matching app only picks up story
folders that contain `matches/`, and the causal app only reads datasource folders
named `*-segcausal`, so the two can share `unrated/` and `rated/`.

On this branch `narraters serve` and `narraters users` work on the causal task by
default (`narraters serve --pipeline` starts the plain pipeline app instead).
`narraters --version` prints `0.3.19+segcausal`.

---

## Prerequisites

- The matching task is running as described in the `dev` branch's `HOSTING.md`
  (user `narraters`, workspace `/srv/narraters`, Caddy installed, and, for rsync,
  the `benchmark-sync` group set up on `/srv/narraters/benchmark`).
- A second domain or subdomain for the causal task.
- SSH access with `sudo`.

## 1. Point the new domain at the server

Create a DNS **A record** for the causal task's domain (e.g. `causal.example.com`)
pointing at the same server. Verify with `dig +short causal.example.com`.

## 2. Service user and workspace

Nothing to do: the causal task runs as the existing `narraters` user in
`/srv/narraters`.

## 3. Install this branch in its own virtual environment

Use a **second** virtual environment so the matching task's `/srv/narraters/.venv`
is not touched:

```bash
sudo apt install -y git      # needed for the git+https install
sudo -u narraters python3 -m venv /srv/narraters/.venv-segcausal
sudo -u narraters /srv/narraters/.venv-segcausal/bin/pip install --upgrade pip
sudo -u narraters /srv/narraters/.venv-segcausal/bin/pip install \
    "narraters[deploy] @ git+https://github.com/xianNeuro/narRaters.git@segcausal"
sudo -u narraters /srv/narraters/.venv-segcausal/bin/narraters --version   # narRaters 0.3.19+segcausal
```

Install from the branch, not from PyPI: the PyPI release is built from `main` and
has no causal task or login. Every command below uses
`/srv/narraters/.venv-segcausal/bin/narraters`; the matching task's
`/srv/narraters/.venv/bin/narraters` is a different program.

## 4. Generate the systemd + Caddy config

```bash
sudo -u narraters /srv/narraters/.venv-segcausal/bin/narraters init-service \
    --domain causal.example.com \
    --workdir /srv/narraters \
    --user narraters \
    --narraters-bin /srv/narraters/.venv-segcausal/bin/narraters
```

It writes `narraters-segcausal.service` and `narraters-segcausal.caddy` into
`/srv/narraters`, next to the matching task's `narraters.service` and `Caddyfile`
(which it does not touch), and creates the causal account folder
`/srv/narraters/.narraters-segcausal`. Defaults: `--host 127.0.0.1`, `--port 5001`,
`--benchmark-dir <workdir>/benchmark`, `--service-name narraters-segcausal`; see
`narraters init-service --help`. If 5001 is taken (`ss -ltnp | grep 5001`), pass
another `--port`.

The generated `narraters-segcausal.service`:

```ini
[Unit]
Description=narRaters hosted task (narraters-segcausal)
After=network.target

[Service]
Type=simple
User=narraters
WorkingDirectory=/srv/narraters
Environment=NARRATERS_PROJECT_ROOT=/srv/narraters
Environment=NARRATERS_HOST=127.0.0.1
Environment=NARRATERS_PORT=5001
Environment=NARRATERS_DATA_DIR=/srv/narraters/.narraters-segcausal
Environment=NARRATERS_TASK_DIR=/srv/narraters/benchmark
EnvironmentFile=-/srv/narraters/.env
ExecStart=/srv/narraters/.venv-segcausal/bin/narraters serve --production --task segment-causal --no-browser --host 127.0.0.1 --port 5001
Restart=on-failure
RestartSec=5

[Install]
WantedBy=multi-user.target
```

## 5. Install and start the systemd service

```bash
sudo cp /srv/narraters/narraters-segcausal.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now narraters-segcausal
systemctl status narraters-segcausal        # should be "active (running)"
journalctl -u narraters-segcausal -f        # follow logs
systemctl status narraters                  # the matching service: still running, untouched
```

## 6. Add the Caddy site (append, never replace)

`/etc/caddy/Caddyfile` already holds the matching site, so **append** the causal
site's block instead of copying a file over it:

```bash
sudo cp /etc/caddy/Caddyfile /etc/caddy/Caddyfile.bak-$(date +%Y%m%d)
sudo sh -c 'cat /srv/narraters/narraters-segcausal.caddy >> /etc/caddy/Caddyfile'
sudo caddy validate --config /etc/caddy/Caddyfile && sudo systemctl reload caddy
```

The appended block:

```caddy
# narRaters hosted task: narraters-segcausal  (append to /etc/caddy/Caddyfile)
causal.example.com {
    reverse_proxy 127.0.0.1:5001
}
```

Caddy obtains a certificate for the new domain on first request.

## 7. Create login accounts

The causal task has its own account list, so a rater who does both tasks needs an
account in each (the same username keeps their `rated/<username>/` folder shared).
Create one account per rater, plus `admin`:

```bash
sudo -u narraters /srv/narraters/.venv-segcausal/bin/narraters users add admin
sudo -u narraters /srv/narraters/.venv-segcausal/bin/narraters users add alice
# prompts for a password (stored as a scrypt hash in
# /srv/narraters/.narraters-segcausal/users.json, mode 600)
```

Manage accounts later with

```bash
sudo -u narraters /srv/narraters/.venv-segcausal/bin/narraters users list | passwd <name> | remove <name>
```

Use the `.venv-segcausal` program here: `/srv/narraters/.venv/bin/narraters users …`
manages the matching task's accounts instead. Usernames are letters, digits and `_`.
The account named **`admin`** does not rate: it gets a progress page at `/admin`
(who has saved or submitted which part of which story) and can also add raters and
reset passwords there. Removing an account keeps the files that rater saved. For
scripted setup, `NARRATERS_NEW_PASSWORD=...` skips the password prompt.

## 8. Put stories in

One datasource folder named `narraters-<datasource>-segcausal` (like the matching
task's `narraters-<datasource>-matching`), with one folder per story holding the
transcript and the events file (columns `event`, `story_texts`):

```
benchmark/unrated/narraters-dfrn-segcausal/angela/angela.txt
benchmark/unrated/narraters-dfrn-segcausal/angela/angela_events-api_model-claude-sonnet-4-5-20250929.xlsx
```

New folders show up for raters on their next page load; no restart needed.
Optional `benchmark/segcausal_assignments.json` limits which stories a rater sees
(raters not listed see all stories), e.g.
`{"alice": ["angela", "dfrn/spider"]}` (story name, or `<datasource>/<story>`).

## 9. Verify

Browse to **`https://causal.example.com/`**: valid certificate, then the login page.
A rater lands on "My tasks"; `admin` lands on the progress page. Check that the
matching site still works at its own domain.

---

## Sync data in and out

Nothing new to set up: the causal task writes into the same
`/srv/narraters/benchmark` folder, so the `benchmark-sync` group from the matching
task's `HOSTING.md` already covers it (new folders inherit the group; files are
group-readable, as the matching task's are). The same rsync commands move both tasks:

```bash
rsync -a ./unrated/  you@HOST:/srv/narraters/benchmark/unrated/   # stories in (both tasks)
rsync -a you@HOST:/srv/narraters/benchmark/rated/  ./rated/       # results out (both tasks)
```

Each rater's causal-task output, in
`rated/<user>/<user>-<datasource>-segcausal/<story>/`:

| file | contents |
|---|---|
| same filename as the unrated `*_events*.xlsx` | Part 1: the rater's segmentation (`event`, `story_texts`) |
| `<story>_causal-manual.xlsx` | Part 2: `event_A_number` (cause), `event_B_number` (effect), `rating` 1-3, `reasoning` |
| `status.json` | save counts, last save, submit times |
| `userlogs/*_userlog.txt` | read-only operation log of each save/submit (time on page, clicks) |
| `history/` | every earlier saved version (saves never destroy data) |
| `source/` | copy of the original events file that Part 2 was rated on |

As in the matching task, the rated file keeps the unrated file's name; the folder
path says whose it is. The extra files (`status.json`, `userlogs/`, `history/`,
`source/`) have no counterpart in the matching task.

---

## Updating

The version string does not change between commits on the branch, so force pip to
rebuild from the latest commit:

```bash
sudo -u narraters /srv/narraters/.venv-segcausal/bin/pip install --upgrade --force-reinstall --no-deps \
    "narraters @ git+https://github.com/xianNeuro/narRaters.git@segcausal"
sudo systemctl restart narraters-segcausal
```

Accounts, stories and saved ratings live in the workspace, not in the program, so
updating keeps them. Updating the matching task (its own `.venv`) does not affect
the causal task, and the other way round.

## Troubleshooting

| Symptom | Check |
|---|---|
| Service won't start | `journalctl -u narraters-segcausal -e`: wrong `--narraters-bin` (must be the `.venv-segcausal` one), missing `[deploy]` (Waitress), port already in use. |
| `Address already in use` | Something else uses 5001. Re-run `init-service` with another `--port`, re-copy the unit, and fix the port in the appended Caddy block. |
| Nobody can log in | No causal accounts yet, or they were made with the matching task's program (`/srv/narraters/.venv/bin/narraters`). `sudo -u narraters /srv/narraters/.venv-segcausal/bin/narraters users list` must show them. |
| 502 from Caddy | App not listening: `systemctl status narraters-segcausal`, and the port in the Caddy block matches the unit. |
| Matching site broke after step 6 | The Caddyfile was overwritten instead of appended: restore `/etc/caddy/Caddyfile.bak-<date>` and append again. |
| No certificate / TLS errors | DNS A record for the new domain must resolve to this server. |
| Login works but the page loops back to login | The site is being reached over plain `http://`. The login cookie is HTTPS-only; use the `https://` address through Caddy. |
| Rater sees no stories | Stories must be in `benchmark/unrated/<folder ending in -segcausal>/<story>/`, with a plain folder name (letters, digits, `_`, `-`, `.`) and a `*_events*.xlsx` (plus the transcript `*.txt`; with several, the first alphabetically is used). `journalctl -u narraters-segcausal` names skipped folders. Check `segcausal_assignments.json` if present. |

## Rules the server enforces

* The rater identity comes from the login; every file path is chosen on the server.
* Part 2 opens only after Part 1 is submitted, and always shows the original
  segmentation, never the rater's edited one.
* Only the task routes exist; the pipeline builder, dashboards and script runners
  return 404.
* Autosave every 30 s plus a "Save progress" button; stale or out-of-order saves are
  dropped; writes are atomic; the previous version goes to `history/`.
* Ratings are validated (events must exist, rating 0-3) before anything is written.

## Security notes

- The app binds to `127.0.0.1` only; all external traffic goes through Caddy.
- It runs as the unprivileged `narraters` user, like the matching task.
- `serve --production` enforces password login (Flask-Login session, scrypt-hashed
  passwords). Sessions are HTTPS-only cookies under their own name; accounts and the
  session key live in `/srv/narraters/.narraters-segcausal`, apart from the matching
  task's `/srv/narraters/.narraters`.

---

## Local trial (on a Mac, next to other narRaters apps)

```bash
pip install -e ".[deploy]"                      # in this branch's own virtual environment
narraters users add admin                       # accounts go to ~/.narraters-segcausal
narraters serve                                 # causal task, no login (rater = local_rater), port 5001
narraters serve --production                    # with login; open http://localhost:5001 in Chrome
```

Stories go in `benchmark/unrated/narraters-<datasource>-segcausal/<story>/` under the
folder you start it from (or `NARRATERS_TASK_DIR`). The double-click launchers on this
branch (`narRater.app`, `server/START_HERE.command`, `install.sh`) start the causal
task without login on the first free port from 5001, and add the example story
`the_siren` (in `narraters-example-segcausal/`) if there are no causal stories yet.
