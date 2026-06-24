# Next Train

Next Train is a small Python backend and frontend for displaying departures from Worcester Park (WCP), with optional routing via Clapham Junction (CLJ) to Victoria (VIC).

## Features

- Proxy departures from the Darwin/Huxley API
- Supports `station`, `filter_crs`, and new `via_crs` routing
- Uses `config.json` for local configuration
- Runs as a systemd service via `next-train.service`

## Requirements

- Python 3.13+
- `requests` is not required; the app uses standard library HTTP clients

## Configuration

Copy `config.example.json` to `config.json` and update the values.

Example configuration for WCP -> CLJ -> VIC:

```json
{
  "station": "WCP",
  "via_crs": "CLJ",
  "filter_crs": "VIC",
  "rows": 10
}
```

- `station`: departure station code (default `WCP`)
- `via_crs`: optional intermediate station code (e.g. `CLJ`)
- `filter_crs`: optional final destination station code (e.g. `VIC`)
- `rows`: number of departures to request

## Running locally

Activate the virtual environment and start the server:

```bash
. .venv/bin/activate
python server.py
```

Then open the board in your browser at:

```
http://192.168.1.183:8190
```

## Running as a service

The repository includes a systemd unit file: `next-train.service`.

Install and start it with:

```bash
sudo cp next-train.service /etc/systemd/system/next-train.service
sudo systemctl daemon-reload
sudo systemctl enable --now next-train.service
```

Check service status:

```bash
sudo systemctl status next-train.service
```

View runtime logs:

```bash
sudo journalctl -u next-train.service -f
```

## Testing

Run the backend unit tests with:

```bash
. .venv/bin/activate
pytest test_server.py
```

## Documentation

Additional project documentation is available in the `docs/` folder:

- `docs/setup.md` — setup, configuration, and systemd installation
- `docs/troubleshooting.md` — common issues, service status, and debugging steps

## Upstream routing behavior

The backend builds Huxley URLs as follows:

- `station` only: `/departures/WCP/10`
- `station + filter_crs`: `/departures/WCP/to/VIC/10`
- `station + filter_crs + via_crs`: `/departures/WCP/to/VIC/10?via=CLJ`

If the routed request returns no services, the server falls back to the intermediate route using `via_crs` only.
