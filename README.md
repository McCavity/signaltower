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

Returns the last 100 signal requests as a JSON array.

**Response**
```json
[
  {
    "timestamp": "2024-01-01T12:00:00",
    "remote_addr": "192.168.1.10",
    "endpoint": "/signal",
    "colour": "RED",
    "mode": "on",
    "interval": 0
  }
]
```

### `POST /signal`

Switches a lamp on or off.

**Request body**
```json
{
  "colour": "RED",
  "mode": "on",
  "interval": 0
}
```

| Field | Type | Values |
|-------|------|--------|
| `colour` | string | `BLUE`, `WHITE`, `AMBER`, `RED`, `GREEN` |
| `mode` | string | `on`, `off`, `blink`, `once` |
| `interval` | integer | milliseconds; used only with `once` mode |

**Response**: `204 No Content`

### Watchdog behaviour

The watchdog runs every 10 seconds and overrides the RED/AMBER/GREEN outputs:

| Time since last heartbeat | Tower state |
|--------------------------|-------------|
| < 60 seconds | GREEN on, AMBER+RED off |
| 60–300 seconds | AMBER on, GREEN+RED off |
| > 300 seconds | RED on, GREEN+AMBER off |

BLUE and WHITE outputs are not touched by the watchdog.

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

## Development

```sh
uv sync
uv run signaltower
```

The app starts on `http://0.0.0.0:5000`. If the K8055 is not present, USB writes are silently dropped — the rest of the API works normally.
