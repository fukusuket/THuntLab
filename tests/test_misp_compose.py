"""Offline checks for the MISP web entry point in the rendered Compose config."""

import json
import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent


def test_misp_http_entry_point_uses_nginx():
    result = subprocess.run(
        [
            "docker", "compose", "--env-file", ".env.example", "-f", "docker-compose.yml",
            "config", "--format", "json",
        ],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
    )
    services = json.loads(result.stdout)["services"]
    core = services["misp-core"]
    nginx = services["misp-nginx"]

    assert "ports" not in core
    assert core["image"].rsplit(":", 1)[-1] == nginx["image"].rsplit(":", 1)[-1]
    assert "9002" in core["expose"]
    assert "9002" in core["healthcheck"]["test"][-1]
    assert nginx["depends_on"]["misp-core"]["condition"] == "service_healthy"
    assert nginx["environment"]["FASTCGI_LISTEN"] == "misp-core:9002"
    assert nginx["environment"]["BASE_URL"] == "http://localhost"
    assert nginx["ports"] == [{
        "mode": "ingress",
        "target": 8080,
        "published": "80",
        "protocol": "tcp",
        "host_ip": "127.0.0.1",
    }]
    assert services["jenkins"]["environment"]["MISP_URL"] == "http://misp-nginx:8080"
    assert int(services["jenkins"]["environment"]["MISP_URL"].rsplit(":", 1)[-1]) == nginx["ports"][0]["target"]
