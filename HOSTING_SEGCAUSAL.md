# Hosting the segment + causal rating task on a VPS

Branch `segcausal`. Raters open a URL, log in with a username and password,
and for each story (Part 1) check the story's event segmentation and (Part 2) rate
causal links between the original events. Everything they produce is saved on the
server; there is nothing for them to install, download, upload or email.

This guide follows the same steps as `HOSTING.md` on the `dev` branch (the
recall-matching benchmark), and is written so that this task can run **on the same
server, next to** that deployment, without touching any of its files, accounts,
port, systemd unit or Caddy site. The commands are the same; only the names differ:

| | `dev` branch (matching) | this branch (segment + causal) |
|---|---|---|
| system user | `narraters` | `narraters-causal` |
| workspace | `/srv/narraters` | `/srv/narraters-causal` |
| install | `narraters[deploy]` | `narraters[deploy] @ git+…@segcausal` |
| systemd unit | `narraters.service` | `narraters-segcausal.service` |
| loopback port | 5000 | 5001 |
| Caddy | `Caddyfile` (replace or copy block) | `narraters-segcausal.caddy` (**append** block) |
| domain | e.g. `narraters.example.com` | e.g. `causal.example.com` |
| accounts | `~narraters/.narraters/users.json` | `~narraters-causal/.narraters-segcausal/users.json` |
| login cookie | `session` | `narraters_segcausal_session` |
| data exchange | `benchmark/{unrated,rated}` | `task_segcausal/{unrated,rated}` |
| sync group | `benchmark-sync` | `segcausal-sync` |

On this branch `narraters serve` and `narraters users` work on the rater task by
default, so no extra flags are needed (`narraters serve --pipeline` starts the plain
pipeline app instead). `narraters --version` prints `0.3.19+segcausal`.

---

## Prerequisites

- A VPS running a recent Linux (examples use Ubuntu/Debian with `apt`).
- A domain (or subdomain) for this task.
- SSH access with `sudo`.
- If the `dev` matching service already runs there, Caddy is already installed.

## 1. Point the domain at the server

Create a DNS **A record** for the task's domain (e.g. `causal.example.com`) pointing
at the VPS's public IP. Verify with `dig +short causal.example.com`.

## 2. Create a service user and workspace

```bash
sudo adduser --system --group --home /srv/narraters-causal narraters-causal
```

Its own user means the operating system itself keeps this service out of
`/srv/narraters` (and the matching service out of this one).

### Optional: access the workspace without `sudo`

```bash
sudo usermod -aG narraters-causal "$(id -un)"
sudo chmod 770 /srv/narraters-causal
sudo chmod g+s  /srv/narraters-causal
```

Run these as your normal login user, then **log out and back in**.

## 3. Install narRaters from this branch in a virtual environment

```bash
sudo apt update && sudo apt install -y python3 python3-venv python3-pip git
sudo -u narraters-causal python3 -m venv /srv/narraters-causal/.venv
sudo -u narraters-causal /srv/narraters-causal/.venv/bin/pip install --upgrade pip
sudo -u narraters-causal /srv/narraters-causal/.venv/bin/pip install \
    "narraters[deploy] @ git+https://github.com/xianNeuro/narRaters.git@segcausal"
sudo -u narraters-causal /srv/narraters-causal/.venv/bin/narraters --version   # narRaters 0.3.19+segcausal
```

Install from the branch, not from PyPI: the PyPI release is built from `main` and
has no rater task or login. (`git` is needed for the `git+https` install.)

## 4. Generate the systemd + Caddy config

```bash
sudo -u narraters-causal /srv/narraters-causal/.venv/bin/narraters init-service \
    --domain causal.example.com \
    --workdir /srv/narraters-causal \
    --user narraters-causal \
    --narraters-bin /srv/narraters-causal/.venv/bin/narraters
```

It writes `narraters-segcausal.service` and `narraters-segcausal.caddy` into the
workdir (never into system locations), and creates `task_segcausal/{unrated,rated}`
and the accounts folder `/srv/narraters-causal/.narraters-segcausal`. Defaults:
`--host 127.0.0.1`, `--port 5001`, `--service-name narraters-segcausal`; see
`narraters init-service --help`. Use another `--port` if 5001 is taken
(`ss -ltnp | grep 5001`).

The generated `narraters-segcausal.service`:

```ini
[Unit]
Description=narRaters hosted task (narraters-segcausal)
After=network.target

[Service]
Type=simple
User=narraters-causal
WorkingDirectory=/srv/narraters-causal
Environment=NARRATERS_PROJECT_ROOT=/srv/narraters-causal
Environment=NARRATERS_HOST=127.0.0.1
Environment=NARRATERS_PORT=5001
Environment=NARRATERS_DATA_DIR=/srv/narraters-causal/.narraters-segcausal
Environment=NARRATERS_TASK_DIR=/srv/narraters-causal/task_segcausal
EnvironmentFile=-/srv/narraters-causal/.env
ExecStart=/srv/narraters-causal/.venv/bin/narraters serve --production --task segment-causal --no-browser --host 127.0.0.1 --port 5001
Restart=on-failure
RestartSec=5

[Install]
WantedBy=multi-user.target
```

## 5. Install and start the systemd service

```bash
sudo cp /srv/narraters-causal/narraters-segcausal.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now narraters-segcausal
systemctl status narraters-segcausal        # should be "active (running)"
journalctl -u narraters-segcausal -f        # follow logs
systemctl status narraters                  # the matching service: still untouched
```

## 6. Add the Caddy site (append, never replace)

The existing `/etc/caddy/Caddyfile` holds the matching site, so **append** this
task's block instead of copying a file over it:

```bash
sudo cp /etc/caddy/Caddyfile /etc/caddy/Caddyfile.bak-$(date +%Y%m%d)
sudo sh -c 'cat /srv/narraters-causal/narraters-segcausal.caddy >> /etc/caddy/Caddyfile'
sudo caddy validate --config /etc/caddy/Caddyfile && sudo systemctl reload caddy
```

The appended block:

```caddy
# narRaters hosted task: narraters-segcausal  (append to /etc/caddy/Caddyfile)
causal.example.com {
    reverse_proxy 127.0.0.1:5001
}
```

Caddy obtains a Let's Encrypt certificate for the new domain on first request.

## 7. Create login accounts

`serve --production` requires login. Create one account per rater, plus `admin`:

```bash
sudo -u narraters-causal /srv/narraters-causal/.venv/bin/narraters users add admin
sudo -u narraters-causal /srv/narraters-causal/.venv/bin/narraters users add alice
# prompts for a password (stored as a scrypt hash in
# /srv/narraters-causal/.narraters-segcausal/users.json, mode 600)
```

Manage accounts later with

```bash
sudo -u narraters-causal /srv/narraters-causal/.venv/bin/narraters users list | passwd <name> | remove <name>
```

Usernames are letters, digits and `_`. The account named **`admin`** does not rate:
it gets a progress page at `/admin` (who has saved or submitted which part of which
story) and can also add raters and reset passwords there. Removing an account keeps
the files that rater saved. For scripted setup, `NARRATERS_NEW_PASSWORD=...` skips
the password prompt.

## 8. Put stories in

One folder per story under `task_segcausal/unrated/`, holding the transcript and
the events file (columns `event`, `story_texts`):

```
task_segcausal/unrated/angela/angela.txt
task_segcausal/unrated/angela/angela_events-api_model-claude-sonnet-4-5-20250929.xlsx
```

New folders show up for raters on their next page load; no restart needed.
Optional `task_segcausal/assignments.json` limits which stories a rater sees
(raters not listed see all stories), e.g. `{"alice": ["angela", "spider"]}`.

## 9. Verify

Browse to **`https://causal.example.com/`**: valid certificate, then the login page.
A rater lands on "My tasks"; `admin` lands on the progress page. Check the matching
site still works at its own domain.

---

## Sync task data in and out

The task reads stories from `task_segcausal/unrated/` and writes each rater's work to
`task_segcausal/rated/<username>/<username>-segcausal/<story>/`:

| file | contents |
|---|---|
| `<events file stem>_<user>-edit.xlsx` | Part 1: the rater's segmentation (`event`, `story_texts`) |
| `<story>_causal-manual_<user>-edit.xlsx` | Part 2: `event_A_number` (cause), `event_B_number` (effect), `rating` 1-3, `reasoning` |
| `status.json` | save counts, last save, submit times |
| `userlogs/*_userlog.txt` | read-only operation log of each save/submit (time on page, clicks) |
| `history/` | every earlier saved version (saves never destroy data) |
| `source/` | copy of the original events file that Part 2 was rated on |

Same setup as the matching service's `benchmark-sync`, with its own group:

```bash
sudo groupadd segcausal-sync
sudo usermod -aG segcausal-sync narraters-causal
sudo usermod -aG segcausal-sync "$(id -un)"          # you, the admin; re-login after
sudo chgrp -R segcausal-sync /srv/narraters-causal/task_segcausal
sudo chmod -R 2770 /srv/narraters-causal/task_segcausal
sudo chmod o+x /srv/narraters-causal                 # cd-through only, no listing
```

Then plain rsync works both ways:

```bash
rsync -a ./unrated/  you@HOST:/srv/narraters-causal/task_segcausal/unrated/   # stories in
rsync -a you@HOST:/srv/narraters-causal/task_segcausal/rated/  ./rated/       # results out
```

---

## Updating

The version string does not change between commits on the branch, so force pip to
rebuild from the latest commit:

```bash
sudo -u narraters-causal /srv/narraters-causal/.venv/bin/pip install --upgrade --force-reinstall --no-deps \
    "narraters @ git+https://github.com/xianNeuro/narRaters.git@segcausal"
sudo systemctl restart narraters-segcausal
```

Accounts, stories and saved ratings live in the workspace, not in the package, so
updating keeps them.

## Troubleshooting

| Symptom | Check |
|---|---|
| Service won't start | `journalctl -u narraters-segcausal -e`: wrong `--narraters-bin`, missing `[deploy]` (Waitress), port already in use, or a workspace permission issue. |
| `Address already in use` | Something else uses 5001. Re-run `init-service` with another `--port`, re-copy the unit, and fix the port in the appended Caddy block. |
| Nobody can log in | No accounts yet, or they were made without `sudo -u narraters-causal` (then they land in another user's home). `sudo -u narraters-causal …/narraters users list` must show them. |
| 502 from Caddy | App not listening: `systemctl status narraters-segcausal`, and the port in the Caddy block matches the unit. |
| Matching site broke after step 6 | The Caddyfile was overwritten instead of appended: restore `/etc/caddy/Caddyfile.bak-<date>` and append again. |
| No certificate / TLS errors | DNS A record for the new domain must resolve to this server; ports 80/443 open. |
| Login works but the page loops back to login | The site is being reached over plain `http://`. The login cookie is HTTPS-only; use the `https://` address through Caddy. |
| Rater sees no stories | Story folders must be directly under `task_segcausal/unrated/`, have a plain name (letters, digits, `_`, `-`, `.`), and contain a `*_events*.xlsx` (plus the transcript `*.txt`; with several, the first alphabetically is used). `journalctl -u narraters-segcausal` names skipped folders. Check `assignments.json` if present. |

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
- It runs as the unprivileged `narraters-causal` user, not root, and cannot write
  into `/srv/narraters`.
- `serve --production` enforces password login (Flask-Login session, scrypt-hashed
  passwords). Sessions are HTTPS-only cookies with their own name, so a browser
  logged into both sites keeps both sessions.

---

## Local trial (on a Mac, next to other narRaters apps)

```bash
pip install -e ".[deploy]"                      # in this branch's own virtual environment
narraters users add admin                       # accounts go to ~/.narraters-segcausal
narraters serve                                 # rater task, no login (rater = local_rater), port 5001
narraters serve --production                    # with login; open http://localhost:5001 in Chrome
```

The double-click launchers on this branch (`narRater.app`, `server/START_HERE.command`,
`install.sh`) start the rater task without login on the first free port from 5001,
and add the example story `the_siren` if `task_segcausal/unrated/` is empty. The main
app and the `dev` matching app use port 5000, `~/.narraters` and `benchmark/`, so
none of them share anything.
