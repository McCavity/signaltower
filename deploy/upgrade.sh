#!/usr/bin/env bash
set -euo pipefail

/opt/signaltower/bin/pip install --quiet .
systemctl restart signaltower
