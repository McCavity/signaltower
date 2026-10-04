# CLAUDE.md

This file provides guidance to Claude Code when working with code in this repository.

## What this project does

A FastAPI service that runs on a Raspberry Pi and controls a physical signal tower via a Velleman K8055 USB interface board. A background watchdog thread monitors heartbeat requests and automatically adjusts the tower colour.

## Project structure

```
signaltower/
  app.py        — FastAPI app, endpoints, lifespan startup
  hardware.py   — K8055 USB abstraction (PyUSB)
  state.py      — thread-safe shared state
  watchdog.py   — background daemon thread
deploy/
  signaltower.service  — systemd unit
  99-k8055.rules       — udev permissions for K8055
  install.sh           — production install script
  upgrade.sh           — reinstall package and restart service
```

## Running locally

```sh
uv sync
uv run signaltower
```

## Deployment

Runs on a Raspberry Pi in the home lab (host name and address: see the private
asset DB, not this public repo). The repo lives at `~/git/projects/own/signaltower`
on the Pi as well. Update sequence (from Pi shell or via SSH):

```sh
cd ~/git/projects/own/signaltower
git pull
sudo ./deploy/upgrade.sh
```

The `upgrade.sh` script reinstalls the package into the systemd-managed
virtualenv at `/opt/signaltower` and restarts the `signaltower.service`. The API
listens on `:5000`; the API key is in `/etc/signaltower/env` (preserved across
upgrades).

Health check after deploy — no key needed:

```sh
curl -s http://<host>:5000/health
```

Expect `"status":"ok"` with HTTP 200. A 503 means the watchdog loop is not ticking
or the tower is not being written; see `README.md`.

## Local environment

⚠️ **Never print the API key** — no `cat` of the env file, no `echo`, no full log
lines that may contain `?key=`. The session transcript is a publication channel too.
The key's source of truth is the password manager; clients receive it from there.

API key for outgoing tests from this Mac lives in a gitignored `.env` next to
this CLAUDE.md. Template:

```sh
cp .env.example .env
chmod 600 .env
# paste the key from the password manager — do not read it off the Pi
```

Loading the key into a shell session, and checking it without showing it:

```sh
set -a; source .env; set +a
test -n "$SIGNALTOWER_API_KEY" && echo "key loaded"
```

The development server also reads `SIGNALTOWER_API_KEY` from the environment, so
the same `.env` works for `uv run signaltower` against the prod key during local
testing.

## Package management

Uses `uv`. Edit `pyproject.toml`, then run `uv sync`.

## K8055 USB protocol

- VID `0x10CF`, PID `0x5500`–`0x5503` (one per board address 0–3)
- HID device; communicate via 8-byte interrupt transfers to endpoint `0x01`
- Packet: `byte[0] = 0x05` (SET_ANALOG_DIGITAL), `byte[1]` = digital output bitmask
- Colour bitmask: BLUE=1, WHITE=2, AMBER=4, RED=8, GREEN=16
- Must detach kernel HID driver before claiming interface

⚠️ **The bitmask above is the wiring, and it contradicts both written sources.**
The OCC2904 manual specifies X1 as `1 red · 2 green · 3 yellow · 4 blue · 5 white`;
the original 2021 design sketch used `1 green · 2 red · 3 orange · 4 white · 5 blue`.
Neither matches. The code is authoritative because it is what actually lights the
right lamp — do not "correct" it against a document. See the wiring section in
`README.md` for supply voltage (12 V DC), the ULN2803 driver stage and its current
limits, and the lamp/module types.

## Thread safety

All shared state lives in `state.py` behind a single `threading.Lock`. The watchdog thread and FastAPI request handlers both call `state.*` functions — never touch the underlying `_lamp_states` or `_last_seen` variables directly.

## Hardware absence

`hardware.K8055` connects lazily (on first `set_outputs` call). `K8055NotFoundError` is caught in `watchdog.py` and silently swallowed, so the app runs normally on a dev machine without a device attached — `/health` then reports 503, correctly.

## Watchdog resilience (since 2026-10-04)

On 2026-10-02 one `usb.core.USBTimeoutError` ended the watchdog thread. The process
lived on, the API reported the *intended* lamp states, and the physical tower stayed
frozen for 34 hours; systemd saw nothing to restart. Hence:

- `watchdog.step()` wraps every tick — no exception may end the thread.
- Any write failure calls `hardware.device.reset()`; the next tick reconnects.
- The bitmask is rewritten every `REASSERT_INTERVAL_S` (5 s) even if unchanged.
- Liveness is recorded in `state` (`record_loop_tick`, `record_write_ok`) and
  exposed as `GET /health` — monitor that, never just the unit.
- uvicorn's access log runs through `logredact.RedactKeyFilter` (`key=***`).

Tests: `uv run pytest` — `tests/fakes.py` simulates the K8055, including timeouts.

## Organisation Context

This repository is one of several personal repos that sit side by side in a single
parent directory on the development machine. That parent directory is itself a git
repo and carries the cross-repo tooling. Paths below are relative to this repo, so
they hold wherever the collection is checked out.

- **Org index**: `../org-index.json` — machine-readable metadata for all repos
  (last commit, CLAUDE.md presence, file count, etc.)
- **Org instructions**: `../CLAUDE.md` — guidance for cross-repo maintenance
  tasks (checking sync status, stale repos, etc.)

For project-specific work, operate within this directory. For questions spanning
multiple repos, consult the org index first.

**Tooling rule**: Skills, plugins, and MCP servers are always installed at project level
(`.claude/settings.json` in this directory), never at user/global level.
