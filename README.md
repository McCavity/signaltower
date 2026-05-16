# Signaltower

A FastAPI service that runs on a Raspberry Pi and controls a physical signal tower (traffic-light-style lamp) via a Velleman K8055 USB interface board.

A background watchdog thread monitors heartbeat requests and sets the tower colour automatically based on how recently a heartbeat was received.

## Hardware requirements

- Raspberry Pi (any model with USB)
- Velleman K8055 USB experiment interface board
- Signal tower with BLUE, WHITE, AMBER, RED, and GREEN lamps wired to K8055 digital outputs

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

### Watchdog behaviour

The watchdog loops continuously (0.1 s tick) and overrides the GREEN and RED outputs:

| Time since last heartbeat | Tower state |
|--------------------------|-------------|
| < 120 seconds | GREEN on, RED off |
| ≥ 120 seconds | RED on, GREEN off |

BLUE, WHITE, and AMBER outputs are not touched by the watchdog — they are controlled exclusively via `POST /signal`. A 0.5 s debounce smooths brief threshold crossings to prevent visible flicker.

## Authentication

All endpoints require authentication. The key is generated during installation and stored in `/etc/signaltower/env`. To retrieve it:

```sh
sudo cat /etc/signaltower/env
```

Pass the key either as a header or as a query parameter:

```sh
# header
curl -H "X-API-Key: <your-key>" http://<pi-address>:5000/heartbeat

# query parameter (useful for browser URLs and tools without header support)
curl http://<pi-address>:5000/heartbeat?key=<your-key>
```

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
