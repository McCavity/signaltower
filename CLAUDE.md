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

## Package management

Uses `uv`. Edit `pyproject.toml`, then run `uv sync`.

## K8055 USB protocol

- VID `0x10CF`, PID `0x5500`–`0x5503` (one per board address 0–3)
- HID device; communicate via 8-byte interrupt transfers to endpoint `0x01`
- Packet: `byte[0] = 0x05` (SET_ANALOG_DIGITAL), `byte[1]` = digital output bitmask
- Colour bitmask: BLUE=1, WHITE=2, AMBER=4, RED=8, GREEN=16
- Must detach kernel HID driver before claiming interface

## Thread safety

All shared state lives in `state.py` behind a single `threading.Lock`. The watchdog thread and FastAPI request handlers both call `state.*` functions — never touch the underlying `_lamp_states` or `_last_seen` variables directly.

## Hardware absence

`hardware.K8055` connects lazily (on first `set_outputs` call). `K8055NotFoundError` is caught in both `app.py` and `watchdog.py` and silently swallowed, so the app runs normally on a dev machine without a device attached.
