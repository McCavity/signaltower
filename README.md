# Signaltower

A FastAPI service that runs on a Raspberry Pi and controls a physical signal tower (traffic-light-style lamp) via a Velleman K8055 USB interface board.

A background watchdog thread monitors heartbeat requests and sets the tower colour automatically based on how recently a heartbeat was received.

## Hardware requirements

- Raspberry Pi (any model with USB)
- Velleman K8055 / VM110N USB experiment interface board
- A driver stage between the board and the lamps (see below) — the K8055 outputs
  alone cannot power signal tower lamps
- Signal tower with BLUE, WHITE, AMBER, RED, and GREEN lamps

## Signal tower wiring

This section documents the production tower. Getting it wrong is easy: three
different channel mappings exist for this setup, and only one of them is real.

### Supply voltage: 12 V DC

The tower runs on **12 V DC** from an external power supply. The K8055/VM110N is
powered separately over USB; the two supplies are galvanically isolated by the
driver stage.

### Driver stage

The lamps are **not** driven by the K8055 directly. Between board and tower sits
an **OCC2904 "Octo Channel Control"** — a galvanic converter built for the
VM110N (by Jens Kelting / Radio K.R.E., Elmshorn, 2021). Signal path:

```
USB → VM110N → optocouplers → buffer → ULN2803 → X1 → signal tower
```

The output driver is a **ULN2803**, rated **500 mA per channel switched to
ground** (the OCC2904 manual quotes a more conservative 250 mA for its auxiliary
channels on X3). Consequences:

- **+12 V is common** to all lamps; the ULN pulls the selected channel to ground.
  Polarity is therefore fixed — LED retrofits should be the "DC/AC" kind with an
  onboard bridge rectifier, so orientation stops mattering.
- **Incandescent bulbs are impractical here.** A 7 W / 12 V bulb draws ~583 mA,
  which exceeds the driver; even 5 W (~417 mA) is marginal once several channels
  are lit at the same time. Use LED retrofits (tens of mA).

### Channel mapping

> [!WARNING]
> **Three mappings exist for this hardware. Only the one below is wired.**
> The OCC2904 manual specifies X1 as `1 red · 2 green · 3 yellow · 4 blue ·
> 5 white`, and the original 2021 design sketch used `1 green · 2 red ·
> 3 orange · 4 white · 5 blue`. **The tower was wired differently from both.**
> Anyone following the manual or the sketch will swap colours.

The mapping below is the one in `hardware.py` and the one that is physically
wired. It is the authoritative one:

| K8055 output | Bitmask | Colour |
|---|---|---|
| 1 | 1 | BLUE |
| 2 | 2 | WHITE |
| 3 | 4 | AMBER |
| 4 | 8 | RED |
| 5 | 16 | GREEN |

### Lamps

Bayonet socket **BA15d** in every module — verified by fit test across all five
sockets, not by the module labels: the AMBER and BLUE modules are stamped
"BA16d", which is not a socket standard that exists (no hits in the Schneider
catalogues, not listed in IEC 60061, no supplier carries it). Treat that marking
as a printing error.

Tower modules are Schneider Electric / Telemecanique Harmony Ø 70, mixed across
two series — which is why they lock differently:

| Module | Series | Colour | Mounting |
|---|---|---|---|
| XVB C33 | XVB | green | clamping ring |
| XVB C34 | XVB | red | clamping ring |
| XVD C35 | XVD | orange | stacked |
| XVD C36 | XVD | blue | stacked |
| XVD C37 | XVD | clear | stacked |

XVB modules each carry their own clamping ring. XVD modules are held by **one
threaded rod running the full height** (Schneider part XVD C03…C08, discontinued;
**M3 or M4** is the practical substitute). Lamp type currently fitted: 12 V
automotive LED retrofits, ~Ø 15 mm socket, 40 mm overall.

### When a single channel goes dark

Check the **ULN2803 first**, not the lamp. Its manual states that in most failure
cases a short damages the output driver. Input-side test: bridge pins 5 and 8 of
the input optocoupler; the control signal then passes straight through.

## API reference

### `GET /heartbeat`

Resets the watchdog timer. Call this regularly from your monitored system to keep the tower green.

**Response**
```json
{"status": "ok"}
```

### `GET /signal`

Returns the last 100 signal requests as a JSON array. Both successful requests and failed validation attempts are logged.

**Successful request entry**
```json
{
  "timestamp": "2024-01-01T12:00:00",
  "remote_addr": "192.168.1.10",
  "endpoint": "/signal",
  "colour": "WHITE",
  "mode": "slow_blink",
  "duration": 30
}
```

**Failed validation entry**
```json
{
  "timestamp": "2024-01-01T12:00:00",
  "remote_addr": "192.168.1.10",
  "endpoint": "/signal",
  "error": "validation_error",
  "validation_errors": [...],
  "payload": {"colour": "WHITE", "mode": "on"}
}
```

### `POST /signal`

Sets a lamp state. `BLUE`, `WHITE`, and `AMBER` are available for manual control; `RED` and `GREEN` are managed exclusively by the watchdog. AMBER is conventionally used to signal "unacknowledged alarms present" — set `on` from your alarm-management system when alarms appear, and back to `off` once they are acknowledged.

**Request body**
```json
{
  "colour": "BLUE",
  "mode": "slow_blink",
  "duration": 30
}
```

| Field | Type | Values |
|-------|------|--------|
| `colour` | string | `BLUE`, `WHITE`, `AMBER` |
| `mode` | string | `off`, `on`, `slow_blink`, `fast_blink` |
| `duration` | integer | seconds until auto-revert to `off`; `-1` or omitted = indefinite |

- `slow_blink`: 1 second cycle (0.5s on, 0.5s off)
- `fast_blink`: 0.5 second cycle (0.25s on, 0.25s off)
- A new request always replaces the current state, including cancelling any active timer
- `duration: 0` is rejected with `422`

**Response**: `204 No Content`

### `GET /lamps`

Returns the current effective mode for all five lamps. RED/GREEN states are derived from heartbeat elapsed time (same logic as the watchdog); BLUE/WHITE/AMBER reflect the last `POST /signal` request.

**Response**
```json
{"BLUE": "off", "WHITE": "slow_blink", "AMBER": "off", "RED": "off", "GREEN": "on"}
```

### `GET /ui`

Serves a browser status page showing an SVG signal tower in its current state. BLUE, WHITE, and AMBER have mode/duration controls. RED and GREEN are read-only (watchdog-managed). The page polls `GET /lamps` every 2 seconds.

Open in a browser:
```
http://<pi-address>:5000/ui?key=<your-key>
```

### `GET /health`

Unauthenticated liveness check for monitoring. It reveals no secrets.

```sh
curl -s http://<pi-address>:5000/health
# {"status":"ok","loop_age_s":0.0,"write_age_s":2.3}
```

Returns **200** only if the watchdog loop ticked within the last 3 s **and** the tower
was written successfully within the last 15 s; otherwise **503** with
`"status":"fail"`. A running process alone proves nothing: on 2026-10-02 a single USB
timeout ended the watchdog thread, the tower froze for 34 hours, and the API kept
answering `200 OK` the whole time. Point your monitoring at this endpoint, not at the
systemd unit.

On a development machine without a K8055, `/health` always returns 503 — there is
nothing to write to.

### Watchdog behaviour

The watchdog loops continuously (0.1 s tick) and overrides the GREEN and RED outputs:

| Time since last heartbeat | Tower state |
|--------------------------|-------------|
| < 120 seconds | GREEN on, RED off |
| ≥ 120 seconds | RED on, GREEN off |

BLUE, WHITE, and AMBER outputs are not touched by the watchdog — they are controlled exclusively via `POST /signal`. A 0.5 s debounce smooths brief threshold crossings to prevent visible flicker.

**Resilience.** No error ends the watchdog thread. A failed USB write drops the
device handle; the next tick reconnects and writes again. The current bitmask is
rewritten every 5 s even when nothing changed, so a write that got lost heals by
itself. Faults are logged once, then at most once a minute while they persist, and
recovery is logged as well.

## Authentication

All endpoints except `/health` require authentication. The key is generated during
installation and stored in `/etc/signaltower/env` (readable by root only).

**Never print the key** — not with `cat`, not with `echo`, not in a log. Keep it in a
password manager and hand it to clients from there (paste it, or inject it into the
environment of the one process that needs it).

Pass the key as a header — preferred:

```sh
curl -H "X-API-Key: $SIGNALTOWER_API_KEY" http://<pi-address>:5000/heartbeat
```

The query parameter `?key=…` is still accepted for tools without header support and
for the browser UI. The service masks it in its own access log (`key=***`), but a
URL can still end up in browser history or proxy logs — prefer the header wherever
the client allows it.

The key file is preserved across upgrades. To rotate the key, replace it in `/etc/signaltower/env` and restart the service.

## Installation

Run from the project root directory:

```sh
sudo ./deploy/install.sh
```

The install script:
1. Creates the `k8055` group and `signaltower` system user
2. Installs the udev rule so the K8055 is accessible without root
3. Creates a virtualenv at `/opt/signaltower` and installs the package
4. Installs and enables the `signaltower.service` systemd unit

## Upgrading

After pulling new code, run from the project root:

```sh
sudo ./deploy/upgrade.sh
```

## Development

```sh
uv sync
uv run signaltower
```

The app starts on `http://0.0.0.0:5000`. If the K8055 is not present, USB writes are silently dropped — the rest of the API works normally.
