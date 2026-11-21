# Hosting the segment + causal rating task on a VPS

Branch `segcausal`. Deploy the segment + causal rating task on a Linux server so
raters can reach it from any machine at your own domain over HTTPS, with the
process supervised by **systemd** (auto-restart on crash or reboot) and TLS handled
by **Caddy**.

Raters open the URL, log in with a username and password, and for each story
(Part 1) check the story's event segmentation and (Part 2) rate causal links
between the original events. Everything they produce is saved on the server; there
is nothing for them to install, download, upload or email.

The names below (`.venv-segcausal`, port 5001, `narraters-segcausal.service`,
`.narraters-segcausal/`) and the service user `narraters_rcause` are chosen so this
task can later share a server with the recall-matching task from the `dev` branch
without touching it; see "Running next to the matching task" at the end.

On this branch `narraters serve` and `narraters users` work on the causal task by
default (`narraters serve --pipeline` starts the plain pipeline app instead).
`narraters --version` prints `0.3.19+segcausal`.

---

## Prerequisites

- A VPS running a recent Linux (examples use Ubuntu/Debian with `apt`).
- A domain name you control (e.g. `causal.example.com`).
- SSH access with `sudo`.

## 1. Point your domain at the server

Create a DNS **A record** for your domain (e.g. `causal.example.com`) pointing at
the VPS's public IP. Caddy needs this resolvable before it can obtain a
certificate. Verify with `dig +short causal.example.com`.

## 2. Create a service user and workspace

Run narRaters as a dedicated, unprivileged user. Its `--home` becomes the
workspace; `init-service` (step 4) creates the `benchmark/{unrated,rated}` folders
and the account folder `.narraters-segcausal/` inside it, so you only need to
create the user here.

```bash
sudo adduser --system --group --home /srv/narraters_rcause narraters_rcause
```

### Optional: access the narraters_rcause workspace without `sudo`

The workspace is owned by the `narraters_rcause` user (mode `750`), so your normal login
account can't `cd` into it without `sudo`. To get permanent, sudo-free access:

```bash
sudo usermod -aG narraters_rcause "$(id -un)"   # add yourself to the narraters_rcause group
sudo chmod 770 /srv/narraters_rcause            # group can read + write
sudo chmod g+s  /srv/narraters_rcause           # new files inherit the narraters_rcause group
```

Run these as your normal login user (not under `sudo -i`), so `id -un` resolves to
*you*. Then **log out and back in**. Note that the account can then read the
workspace's `.env` (API keys). For rsync access to the data folder only, see "Sync
data in and out" below instead.

## 3. Install this branch in a virtual environment

```bash
sudo apt update && sudo apt install -y python3 python3-venv python3-pip git
sudo -u narraters_rcause python3 -m venv /srv/narraters_rcause/.venv-segcausal
sudo -u narraters_rcause /srv/narraters_rcause/.venv-segcausal/bin/pip install --upgrade pip
# 'deploy' adds Waitress
sudo -u narraters_rcause /srv/narraters_rcause/.venv-segcausal/bin/pip install \
    "narraters[deploy] @ git+https://github.com/xianNeuro/narRaters.git@segcausal"
sudo -u narraters_rcause /srv/narraters_rcause/.venv-segcausal/bin/narraters --version   # narRaters 0.3.19+segcausal
```

Install from the branch, not from PyPI: the PyPI release is built from `main` and
has no causal task or login (`git` is needed for the `git+https` install). The
`narraters` command is now at `/srv/narraters_rcause/.venv-segcausal/bin/narraters`; every
command below uses that path.

## 4. Generate the systemd + Caddy config

Run `init-service`. It substitutes your values and writes
`narraters-segcausal.service` and `narraters-segcausal.caddy` into the `--workdir`
(it does not touch system locations; you install them in the next steps).

```bash
sudo -u narraters_rcause /srv/narraters_rcause/.venv-segcausal/bin/narraters init-service \
    --domain causal.example.com \
    --workdir /srv/narraters_rcause \
    --user narraters_rcause \
    --narraters-bin /srv/narraters_rcause/.venv-segcausal/bin/narraters
```

Defaults: `--host 127.0.0.1`, `--port 5001`, `--benchmark-dir <workdir>/benchmark`
(written into the unit as `NARRATERS_TASK_DIR`, see "Sync data in and out" below),
`--data-dir <user's home>/.narraters-segcausal` (accounts, written as
`NARRATERS_DATA_DIR`), `--service-name narraters-segcausal`, and `--output-dir`
defaults to the `--workdir`. Run `narraters init-service --help` for all options.
If 5001 is taken (`ss -ltnp | grep 5001`), pass another `--port`.

The generated `narraters-segcausal.service`:

```ini
[Unit]
Description=narRaters hosted task (narraters-segcausal)
After=network.target

[Service]
Type=simple
User=narraters_rcause
WorkingDirectory=/srv/narraters_rcause
Environment=NARRATERS_PROJECT_ROOT=/srv/narraters_rcause
Environment=NARRATERS_HOST=127.0.0.1
Environment=NARRATERS_PORT=5001
Environment=NARRATERS_DATA_DIR=/srv/narraters_rcause/.narraters-segcausal
Environment=NARRATERS_TASK_DIR=/srv/narraters_rcause/benchmark
EnvironmentFile=-/srv/narraters_rcause/.env
ExecStart=/srv/narraters_rcause/.venv-segcausal/bin/narraters serve --production --task segment-causal --no-browser --host 127.0.0.1 --port 5001
Restart=on-failure
RestartSec=5

[Install]
WantedBy=multi-user.target
```

## 5. Install and start the systemd service

```bash
sudo cp /srv/narraters_rcause/narraters-segcausal.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now narraters-segcausal
systemctl status narraters-segcausal        # should be "active (running)"
journalctl -u narraters-segcausal -f        # follow logs
```

`enable` makes it start on boot; `Restart=on-failure` restarts it if it crashes.

## 6. Install Caddy and the reverse proxy

Install Caddy ([official instructions](https://caddyserver.com/docs/install)).

The generated `narraters-segcausal.caddy` is a single site block:

```caddy
# narRaters hosted task: narraters-segcausal  (append to /etc/caddy/Caddyfile)
causal.example.com {
    reverse_proxy 127.0.0.1:5001
}
```

On a fresh Caddy install, the simplest path replaces the default Caddyfile with it:

```bash
sudo cp /srv/narraters_rcause/narraters-segcausal.caddy /etc/caddy/Caddyfile
sudo caddy validate --config /etc/caddy/Caddyfile && sudo systemctl reload caddy
```

> If Caddy already serves other sites (e.g. the matching task), **append** the
> block instead of overwriting the file:
>
> ```bash
> sudo cp /etc/caddy/Caddyfile /etc/caddy/Caddyfile.bak-$(date +%Y%m%d)
> sudo sh -c 'cat /srv/narraters_rcause/narraters-segcausal.caddy >> /etc/caddy/Caddyfile'
> sudo caddy validate --config /etc/caddy/Caddyfile && sudo systemctl reload caddy
> ```

Caddy automatically obtains and renews a Let's Encrypt certificate for the domain
on first request.

## 7. Create login accounts

`serve --production` requires users to log in. Create one account per rater, plus
`admin`:

```bash
sudo -u narraters_rcause /srv/narraters_rcause/.venv-segcausal/bin/narraters users add admin
sudo -u narraters_rcause /srv/narraters_rcause/.venv-segcausal/bin/narraters users add alice
# prompts for a password (stored as a scrypt hash in
# /srv/narraters_rcause/.narraters-segcausal/users.json, mode 600)
```

Manage accounts later with

```bash
sudo -u narraters_rcause /srv/narraters_rcause/.venv-segcausal/bin/narraters users list | passwd <name> | remove <name>
```

Usernames are letters, digits and `_`. The account named **`admin`** does not
rate: it gets a progress page at `/admin` (who has saved or submitted which part of
which story) and can also add raters and reset passwords there. Removing an account
keeps the files that rater saved. For scripted setup, `NARRATERS_NEW_PASSWORD=...`
skips the password prompt.

## 8. Put stories in

One datasource folder named `narraters-<datasource>-segcausal`, with one folder per
story holding the transcript and the events file (columns `event`, `story_texts`):

```
benchmark/unrated/narraters-dfrn-segcausal/angela/angela.txt
benchmark/unrated/narraters-dfrn-segcausal/angela/angela_events-api_model-claude-sonnet-4-5-20250929.xlsx
```

Copy them in with rsync (see "Sync data in and out" below). New folders show up for
raters on their next page load; no restart needed. Optional
`benchmark/segcausal_assignments.json` limits which stories a rater sees (raters
not listed see all stories), e.g. `{"alice": ["angela", "dfrn/spider"]}` (story
name, or `<datasource>/<story>`).

## 9. Verify

Browse to **`https://causal.example.com/`**: you should get a valid certificate
and the login page. A rater lands on "My tasks"; `admin` lands on the progress page.

---

## Sync data in and out

The task reads stories from `<benchmark-dir>/unrated/` and writes each rater's
results to `<benchmark-dir>/rated/<username>/`. `init-service` sets
`NARRATERS_TASK_DIR` (default `/srv/narraters_rcause/benchmark`) in the unit and creates
those two subdirs.

So that you can rsync without hassle, run:

```bash
# a dedicated shared group for the exchange dir only
sudo groupadd benchmark-sync
sudo usermod -aG benchmark-sync narraters_rcause   # the service
sudo usermod -aG benchmark-sync "$(id -un)"        # you, the admin; re-login after

# group-own the benchmark dir and set setgid so new files inherit the group;
# 2770 also gives the group write on the directories
sudo chgrp -R benchmark-sync /srv/narraters_rcause/benchmark
sudo chmod -R 2770 /srv/narraters_rcause/benchmark

# let your login traverse INTO the dir without reading /srv/narraters_rcause or its .env
sudo chmod o+x /srv/narraters_rcause              # 751: cd-through only, no listing
```

Now a **plain rsync works both directions, no `--chmod` flags needed** (replace
`HOST` with your server, and use your own login):

```bash
# push stories in
rsync -a ./unrated/  you@HOST:/srv/narraters_rcause/benchmark/unrated/
# pull rated results back out
rsync -a you@HOST:/srv/narraters_rcause/benchmark/rated/  ./rated/
```

Only `unrated/` (in) and `rated/` (out) need syncing. Each rater's output, in
`rated/<user>/<user>-<datasource>-segcausal/<story>/`:

| file                                          | contents                                                                               |
| --------------------------------------------- | -------------------------------------------------------------------------------------- |
| same filename as the unrated `*_events*.xlsx` | Part 1: the rater's segmentation (`event`, `story_texts`)                              |
| `<story>_causal-manual.xlsx`                  | Part 2: `event_A_number` (cause), `event_B_number` (effect), `rating` 1-3, `reasoning` |
| `status.json`                                 | save counts, last save, submit times                                                   |
| `userlogs/*_userlog.txt`                      | read-only operation log of each save/submit (time on page, clicks)                     |
| `history/`                                    | every earlier saved version (saves never destroy data)                                 |
| `source/`                                     | copy of the original events file that Part 2 was rated on                              |

The rated file keeps the unrated file's name; the folder path says whose it is.

---

## Updating

The version string does not change between commits on the branch, so force pip to
rebuild from the latest commit:

```bash
sudo -u narraters_rcause /srv/narraters_rcause/.venv-segcausal/bin/pip install --upgrade --force-reinstall --no-deps \
    "narraters @ git+https://github.com/xianNeuro/narRaters.git@segcausal"
sudo systemctl restart narraters-segcausal
```

Accounts, stories and saved ratings live in the workspace, not in the program, so
updating keeps them.

## Troubleshooting

| Symptom                                      | Check                                                                                                                                                                                                                                                                                                                                                    |
| -------------------------------------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Service won't start                          | `journalctl -u narraters-segcausal -e`: wrong `--narraters-bin` path (must be the `.venv-segcausal` one), missing `[deploy]` (Waitress), port already in use, or a workspace permission issue.                                                                                                                                                           |
| `--production needs waitress` in logs        | Install the deploy extra: the `narraters[deploy] @ git+…` line from step 3.                                                                                                                                                                                                                                                                              |
| `Address already in use`                     | Something else uses 5001. Re-run `init-service` with another `--port`, re-copy the unit, and fix the port in the Caddy block.                                                                                                                                                                                                                            |
| Nobody can log in                            | No accounts yet, or they were made with a different `narraters` program (e.g. the matching task's `/srv/narraters/.venv/bin/narraters`). `sudo -u narraters_rcause /srv/narraters_rcause/.venv-segcausal/bin/narraters users list` must show them.                                                                                                       |
| 502 from Caddy                               | App not listening: `systemctl status narraters-segcausal`, and the port in the Caddy block matches the unit.                                                                                                                                                                                                                                             |
| Another site broke after step 6              | The Caddyfile was overwritten instead of appended: restore `/etc/caddy/Caddyfile.bak-<date>` and append again.                                                                                                                                                                                                                                           |
| No certificate / TLS errors                  | DNS A record must resolve to this server, and ports 80/443 must be open in the firewall before Caddy can issue a cert.                                                                                                                                                                                                                                   |
| Login works but the page loops back to login | The site is being reached over plain `http://`. The login cookie is HTTPS-only; use the `https://` address through Caddy.                                                                                                                                                                                                                                |
| Rater sees no stories                        | Stories must be in `benchmark/unrated/<folder ending in -segcausal>/<story>/`, with a plain folder name (letters, digits, `_`, `-`, `.`) and a `*_events*.xlsx` (plus the transcript `*.txt`; with several, the first alphabetically is used). `journalctl -u narraters-segcausal` names skipped folders. Check `segcausal_assignments.json` if present. |
| `Permission denied` on rsync                 | You are not yet in `benchmark-sync` (log out and back in after `usermod`), or `/srv/narraters_rcause` lacks `o+x`.                                                                                                                                                                                                                                       |

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

- The app is bound to `127.0.0.1` only; all external traffic goes through Caddy.
- Run the service as the dedicated unprivileged `narraters_rcause` user, not root.
- `serve --production` enforces password login (Flask-Login session, scrypt-hashed
  passwords). Sessions are HTTPS-only cookies named `narraters_segcausal_session`;
  accounts and the session key live in `/srv/narraters_rcause/.narraters-segcausal`
  (`users.json`, mode `600`). Remove access by deleting the user.

---

## Running next to the matching task

The recall-matching task (`dev` branch, its own `HOSTING.md`) can run on the same
server. Each task has its own system user, workspace and data folder; they share
only the Caddy server (and, optionally, the `benchmark-sync` group):

|                               | matching task (`dev` branch)                                     | causal task (this branch)                               |
| ----------------------------- | ---------------------------------------------------------------- | ------------------------------------------------------- |
| system user and group         | `narraters`                                                      | `narraters_rcause`                                      |
| workspace                     | `/srv/narraters`                                                 | `/srv/narraters_rcause`                                 |
| data folder                   | `/srv/narraters/benchmark`                                       | `/srv/narraters_rcause/benchmark`                       |
| stories in                    | `unrated/narraters-<datasource>-matching/<story>/matches/…csv`   | `unrated/narraters-<datasource>-segcausal/<story>/…`    |
| results out                   | `rated/<user>/<user>-<datasource>-matching/<story>/matches/…csv` | `rated/<user>/<user>-<datasource>-segcausal/<story>/…`  |
| program (virtual environment) | `/srv/narraters/.venv`                                           | `/srv/narraters_rcause/.venv-segcausal`                 |
| systemd unit                  | `narraters.service`                                              | `narraters-segcausal.service`                           |
| loopback port                 | 5000                                                             | 5001                                                    |
| domain                        | e.g. `narraters.example.com`                                     | e.g. `causal.example.com`                               |
| Caddy                         | site block in `/etc/caddy/Caddyfile`                             | second site block in the same file                      |
| accounts                      | `/srv/narraters/.narraters/users.json`                           | `/srv/narraters_rcause/.narraters-segcausal/users.json` |
| login cookie                  | `session`                                                        | `narraters_segcausal_session`                           |

Accounts are separate, so a rater who does both tasks needs an account in each.
Stories and results are synced per task, with the rsync paths of each guide.

Whichever task is set up second skips the Caddy install, and its Caddy block is
**appended** to `/etc/caddy/Caddyfile` (step 6), never copied over it. If the
`benchmark-sync` group already exists, skip `groupadd` in "Sync data in and out"
and run the remaining commands; one group then gives you rsync access to both data
folders. Updating one task's virtual environment does not affect the other.

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
