"""Deployment config generation for hosting narRaters on a VPS.

`narraters init-service` uses this module to render a systemd unit file and a
Caddyfile (reverse proxy + automatic TLS) from a few parameters. The generated
files are written to a directory the user chooses; this module never touches
system locations — installing the files is a manual, documented step (HOSTING.md)
so the user stays in control of anything requiring sudo.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

# systemd unit. `Restart=on-failure` + `enable` give crash/reboot auto-restart.
# `EnvironmentFile=-...` makes a project .env (API keys) optional, not required.
SERVICE_TEMPLATE = """\
[Unit]
Description=narRaters web UI
After=network.target

[Service]
Type=simple
User={user}
WorkingDirectory={workdir}
Environment=NARRATERS_PROJECT_ROOT={workdir}
Environment=NARRATERS_HOST={host}
Environment=NARRATERS_PORT={port}
EnvironmentFile=-{workdir}/.env
ExecStart={narraters_bin} serve --production --no-browser --host {host} --port {port}
Restart=on-failure
RestartSec=5

[Install]
WantedBy=multi-user.target
"""

# Caddy auto-provisions and renews TLS certificates for the domain and reverse
# proxies to the loopback app. narRaters now has its own password login (enforced
# by `serve --production`), so no Caddy-level basic_auth is needed.
CADDYFILE_TEMPLATE = """\
{domain} {{
    reverse_proxy {host}:{port}
}}
"""


@dataclass
class DeployConfig:
    domain: str
    workdir: str
    user: str
    host: str
    port: int
    narraters_bin: str

    def service_text(self) -> str:
        return SERVICE_TEMPLATE.format(
            user=self.user,
            workdir=self.workdir,
            host=self.host,
            port=self.port,
            narraters_bin=self.narraters_bin,
        )

    def caddyfile_text(self) -> str:
        return CADDYFILE_TEMPLATE.format(
            domain=self.domain,
            host=self.host,
            port=self.port,
        )


def write_configs(config: DeployConfig, output_dir: Path) -> tuple[Path, Path]:
    """Write narraters.service and Caddyfile into ``output_dir``.

    Returns the (service_path, caddyfile_path) tuple.
    """
    output_dir.mkdir(parents=True, exist_ok=True)
    service_path = output_dir / "narraters.service"
    caddyfile_path = output_dir / "Caddyfile"
    service_path.write_text(config.service_text(), encoding="utf-8")
    caddyfile_path.write_text(config.caddyfile_text(), encoding="utf-8")
    return service_path, caddyfile_path
