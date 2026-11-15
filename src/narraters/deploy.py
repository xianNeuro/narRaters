"""Deployment config generation for hosting a narRaters task on a VPS.

Adapted from the ``dev`` branch (hosted recall-matching benchmark). This version
is built to run *next to* other narRaters deployments on the same server, so
every name that the ``dev`` version hard-coded is a parameter:

* the systemd unit name (``narraters-segcausal.service`` by default, not
  ``narraters.service``),
* the loopback port (5001 by default, not 5000),
* the account/state directory (``NARRATERS_DATA_DIR``), and
* the Caddy config, which is written as a *site block to append* to the
  existing Caddyfile, never as a replacement for it.

`narraters init-service` renders the files into a directory you choose; this
module never touches system locations.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

SERVICE_TEMPLATE = """\
[Unit]
Description=narRaters hosted task ({service_name})
After=network.target

[Service]
Type=simple
User={user}
WorkingDirectory={workdir}
Environment=NARRATERS_PROJECT_ROOT={workdir}
Environment=NARRATERS_HOST={host}
Environment=NARRATERS_PORT={port}
Environment=NARRATERS_DATA_DIR={data_dir}
Environment=NARRATERS_TASK_DIR={task_dir}
EnvironmentFile=-{workdir}/.env
ExecStart={narraters_bin} serve --production --task {task} --no-browser --host {host} --port {port}
Restart=on-failure
RestartSec=5

[Install]
WantedBy=multi-user.target
"""

# A single site block. Append it to /etc/caddy/Caddyfile (or `import` it);
# do NOT copy it over the existing file, which holds the other deployments.
CADDY_SNIPPET_TEMPLATE = """\
# narRaters hosted task: {service_name}  (append to /etc/caddy/Caddyfile)
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
    task_dir: str
    data_dir: str
    service_name: str = "narraters-segcausal"
    task: str = "segment-causal"

    def service_text(self) -> str:
        return SERVICE_TEMPLATE.format(**self.__dict__)

    def caddy_snippet_text(self) -> str:
        return CADDY_SNIPPET_TEMPLATE.format(**self.__dict__)


def write_configs(config: DeployConfig, output_dir: Path) -> tuple[Path, Path]:
    """Write ``<service_name>.service`` and ``<service_name>.caddy`` into ``output_dir``."""
    output_dir.mkdir(parents=True, exist_ok=True)
    service_path = output_dir / f"{config.service_name}.service"
    caddy_path = output_dir / f"{config.service_name}.caddy"
    service_path.write_text(config.service_text(), encoding="utf-8")
    caddy_path.write_text(config.caddy_snippet_text(), encoding="utf-8")
    return service_path, caddy_path
