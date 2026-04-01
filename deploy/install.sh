#!/usr/bin/env bash
set -euo pipefail

groupadd --system k8055 2>/dev/null || true
useradd --system --no-create-home --gid k8055 signaltower 2>/dev/null || true

cp deploy/99-k8055.rules /etc/udev/rules.d/99-k8055.rules
udevadm control --reload-rules
udevadm trigger

if [ ! -f /etc/signaltower/env ]; then
    mkdir -p /etc/signaltower
    echo "SIGNALTOWER_API_KEY=$(openssl rand -hex 32)" > /etc/signaltower/env
    chmod 640 /etc/signaltower/env
    chown root:k8055 /etc/signaltower/env
fi

python3 -m venv /opt/signaltower
/opt/signaltower/bin/pip install --quiet .

cp deploy/signaltower.service /etc/systemd/system/signaltower.service
systemctl daemon-reload
systemctl enable --now signaltower
