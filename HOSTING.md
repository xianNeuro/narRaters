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

Run narRaters as a dedicated, unprivileged user with its own workspace holding
the `data/` and `output/` folders.

```bash
sudo adduser --system --group --home /srv/narraters narraters
sudo -u narraters mkdir -p /srv/narraters/data /srv/narraters/output
```

### Optional: access narraters workspace, without `sudo`

The workspace is owned by the `narraters` user (mode `750`), so your normal login
account can't `cd` into it without `sudo`. To get permanent, sudo-free access:

```bash
sudo usermod -aG narraters "$(id -un)"   # add yourself to the narraters group
sudo chmod 770 /srv/narraters            # group can read + write
sudo chmod g+s  /srv/narraters           # new files inherit the narraters group
```

Run these as your normal login user (not under `sudo -i`), so `id -un` resolves to
*you*. Then **log out and back in**.
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
`--workdir`. Run `narraters init-service --help` for all options.

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

    # --- Interim access control -------------------------------------------
    # narRaters has no built-in authentication yet, and its web UI can run
    # subprocesses and write files. Until app-level auth is added, do NOT leave
    # this publicly reachable unprotected. Generate a password hash with:
    #     caddy hash-password
    # then uncomment and fill in:
    # basic_auth {
    #     youruser <PASTE_HASH_HERE>
    # }
    # ----------------------------------------------------------------------
}
```

> If you already run other sites in Caddy, copy the `narraters.example.com { ... }`
> block into your existing `/etc/caddy/Caddyfile` (or `import` it) instead of
> overwriting the file.

Caddy automatically obtains and renews a Let's Encrypt certificate for the domain
on first request.

## 8. Verify

Browse to **`https://narraters.example.com/pipeline-config`** — you should get a
valid certificate and the narRaters UI.

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
