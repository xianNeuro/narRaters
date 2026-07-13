# Hosting narRaters on a VPS

Deploy narRaters on a Linux server so you can reach it from any
machine at your own domain over HTTPS, with the process supervised by **systemd**
(auto-restart on crash or reboot) and TLS handled by **Caddy**.

---

## Prerequisites

- A VPS running a recent Linux (examples use Ubuntu/Debian with `apt`).
- A domain name you control.
- SSH access with `sudo`.

## 1. Point your domain at the server

Create a DNS **A record** for your domain (e.g. `narraters.example.com`) pointing
at the VPS's public IP. Caddy needs this resolvable before it can obtain a
certificate. Verify with `dig +short narraters.example.com`.

## 2. Create a service user and workspace

Run narRaters as a dedicated, unprivileged user. Its `--home` becomes the
workspace; `init-service` (step 4) scaffolds the `data/`, `output/`, and
`benchmark/{unrated,rated}` folders inside it, so you only need to create the
user here.

```bash
sudo adduser --system --group --home /srv/narraters narraters
```

### Optional: access narraters workspace, without `sudo`

The workspace is owned by the `narraters` user (mode `750`), so your normal login
account can't `cd` into it without `sudo`. To get permanent, sudo-free access:

```bash
sudo usermod -aG narraters "$(id -un)"   # add yourself to the narraters group
sudo chmod 770 /srv/narraters            # group can read + write
sudo chmod g+s  /srv/narraters           # new files inherit the narraters group
```

Run these as your normal login user (not under `sudo -i`), so `id -un` resolves to *you*. Then **log out and back in**.
Just note that the account can read the workspace's `.env` (API keys).

## 3. Install narRaters in a virtual environment

```bash
sudo apt update && sudo apt install -y python3 python3-venv python3-pip
sudo -u narraters python3 -m venv /srv/narraters/.venv
sudo -u narraters /srv/narraters/.venv/bin/pip install --upgrade pip
# 'deploy' adds Waitress; add any extras you need, e.g. [deploy,api,audio]
sudo -u narraters /srv/narraters/.venv/bin/pip install "narraters[deploy]"
```

The `narraters` command is now at `/srv/narraters/.venv/bin/narraters`.


## 4. Generate the systemd + Caddy config

Run `init-service`. It substitutes your values and writes `narraters.service` and
`Caddyfile` into the `--workdir` (it does not touch system locations — you install
them in the next steps).

```bash
sudo -u narraters /srv/narraters/.venv/bin/narraters init-service \
    --domain narraters.example.com \
    --workdir /srv/narraters \
    --user narraters \
    --narraters-bin /srv/narraters/.venv/bin/narraters
```

Defaults: `--host 127.0.0.1`, `--port 5000`, and `--output-dir` defaults to the
`--workdir`. `--benchmark-dir` defaults to `<workdir>/benchmark` and is written
into the unit as `NARRATERS_BENCHMARK_DIR` (see "Sync benchmark data" below). Run
`narraters init-service --help` for all options.

The generated `narraters.service` looks like:

```ini
[Unit]
Description=narRaters web UI
After=network.target

[Service]
Type=simple
User=narraters
WorkingDirectory=/srv/narraters
Environment=NARRATERS_PROJECT_ROOT=/srv/narraters
Environment=NARRATERS_HOST=127.0.0.1
Environment=NARRATERS_PORT=5000
Environment=NARRATERS_BENCHMARK_DIR=/srv/narraters/benchmark
EnvironmentFile=-/srv/narraters/.env
ExecStart=/srv/narraters/.venv/bin/narraters serve --production --no-browser --host 127.0.0.1 --port 5000
Restart=on-failure
RestartSec=5

[Install]
WantedBy=multi-user.target
```

## 5. Install and start the systemd service

```bash
sudo cp /srv/narraters/narraters.service /etc/systemd/system/narraters.service
sudo systemctl daemon-reload
sudo systemctl enable --now narraters
systemctl status narraters          # should be "active (running)"
journalctl -u narraters -f          # follow logs
```

`enable` makes it start on boot; `Restart=on-failure` restarts it if it crashes.

## 7. Install Caddy and the reverse proxy

Install Caddy: ([official instructions](https://caddyserver.com/docs/install)):

Use the generated Caddyfile. The simplest path replaces the default one:

```bash
sudo cp /srv/narraters/Caddyfile /etc/caddy/Caddyfile
sudo systemctl reload caddy
```

The generated `Caddyfile`:

```caddy
narraters.example.com {
    reverse_proxy 127.0.0.1:5000
}
```

> If you already run other sites in Caddy, copy the `narraters.example.com { ... }`
> block into your existing `/etc/caddy/Caddyfile` (or `import` it) instead of
> overwriting the file.

Caddy automatically obtains and renews a Let's Encrypt certificate for the domain
on first request.

## 8. Create a login account

`narraters serve --production` requires users to log in, so create at least one account.

```bash
sudo -u narraters /srv/narraters/.venv/bin/narraters users add alice
# prompts for a password (stored as a scrypt hash in ~/.narraters/users.json, mode 600)
```

Manage accounts later with
```bash
sudo -u /srv/narraters/.venv/bin/narraters users list | passwd <name> | remove <name>
```

In `--benchmark` mode every rater starts locked to the first (matching) pass.
Unlock a rater's second (rating) pass — after which they work only in the
second pass — or switch them back with:
```bash
sudo -u narraters /srv/narraters/.venv/bin/narraters users second-pass alice
sudo -u narraters /srv/narraters/.venv/bin/narraters users first-pass alice
```
The second pass is kept in a separate rated file (`…-matched_second-pass.csv`
next to the first-pass file), pre-populated from the rater's first pass the
first time they save in the second pass.

## 9. Verify

Browse to **`https://narraters.example.com/`** — you should get a valid certificate
and the narRaters login page. Sign in with the account from step 8 to reach the UI.

---

## Sync benchmark data in and out

The benchmark text-matching workflow reads recall files from `<benchmark-dir>/unrated/` and writes rated results to
`<benchmark-dir>/rated/<username>/`.

`init-service` sets `NARRATERS_BENCHMARK_DIR`
(default `/srv/narraters/benchmark`) in the unit and creates those two subdirs.

Such that you can rsync without hassle, run the following commands:
```bash
# a dedicated shared group for the exchange dir only
sudo groupadd benchmark-sync
sudo usermod -aG benchmark-sync narraters       # the service
sudo usermod -aG benchmark-sync "$(id -un)"     # you, the admin — re-login after

# group-own the benchmark dir and set setgid so new files inherit the group;
# 2770 also gives the group write on the directories
sudo chgrp -R benchmark-sync /srv/narraters/benchmark
sudo chmod -R 2770 /srv/narraters/benchmark

# let your login traverse INTO the dir without reading /srv/narraters or its .env
sudo chmod o+x /srv/narraters                   # 751: cd-through only, no listing
```

Now a **plain rsync works both directions — no `--chmod` flags needed** (replace
`HOST` with your server, and use your own login — there is no assumed `ubuntu`):

```bash
# push recall inputs in
rsync -a ./unrated/  you@HOST:/srv/narraters/benchmark/unrated/
# pull rated results back out
rsync -a you@HOST:/srv/narraters/benchmark/rated/  ./rated/
```

---

## Updating

```bash
sudo -u narraters /srv/narraters/.venv/bin/pip install --upgrade "narraters[deploy]"
sudo systemctl restart narraters
```

## Troubleshooting

| Symptom                                                                   | Check                                                                                                                                                                                                              |
| ------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| Service won't start                                                       | `journalctl -u narraters -e` — common causes: wrong `--narraters-bin` path, missing `[deploy]` (Waitress), or a workspace permission issue.                                                                        |
| `--production needs waitress` in logs                                     | Install the deploy extra: `pip install "narraters[deploy]"`.                                                                                                                                                       |
| 502 from Caddy                                                            | App not listening — confirm `systemctl status narraters` is active and the port matches the Caddyfile.                                                                                                             |
| No certificate / TLS errors                                               | DNS A record must resolve to this server, and ports 80/443 must be open in the firewall before Caddy can issue a cert.                                                                                             |
| 404 / blank page                                                          | Open the `/pipeline-config` path explicitly.                                                                                                                                                                       |
| `PermissionError` writing `…/narraters.service` from `init-service`       | You passed `--output-dir` (or an old narRaters version wrote to the cwd) pointing at a directory the service user can't write to. Omit `--output-dir` so it writes to `--workdir`, or point it at a writable path. |
| `Permission denied` installing from a local dir (e.g. `/home/ubuntu/...`) | The `narraters` user can't read another user's home. Install from PyPI, or copy the source into a path it owns (e.g. `/srv/narraters/src`) before `pip install`.                                                   |

## Security notes

- The app is bound to `127.0.0.1` only; all external traffic goes through Caddy.
- Run the service as the dedicated unprivileged `narraters` user, not root.
- `serve --production` enforces password login (Flask-Login session + scrypt-hashed
  passwords). Sessions are HTTPS-only cookies; accounts live in `~/.narraters/users.json`
  (mode `600`). Manage them with `narraters users …` and remove access by deleting the user.
