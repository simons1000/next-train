# Next Train Troubleshooting Guide

Use this guide when the app is not working as expected.

## Check service status

```bash
sudo systemctl status next-train.service
```

If the service is inactive or failed, inspect the journal:

```bash
sudo journalctl -u next-train.service -f
```

## Common issues

### Port already in use

The app listens on `8190`. If the server cannot start, check whether the port is occupied:

```bash
ss -ltnp | grep 8190
```

If another process is using the port, stop or kill that process before restarting the service.

### HTTP 404 or 502 from `/api/departures`

This usually means the upstream Huxley API request is invalid or returned no data.

The app builds routes like:

- `/departures/WCP/10`
- `/departures/WCP/to/VIC/10`
- `/departures/WCP/to/VIC/10?via=CLJ`

If the routed request returns no services, the app now falls back to the intermediate via station route:

- `/departures/WCP/to/CLJ/10`

### NO SERVICES displayed in the frontend

If the page shows `NO SERVICES` but the API is reachable, verify the upstream response:

```bash
curl -i http://127.0.0.1:8190/api/departures
```

A valid response should contain a JSON payload.

If you see `"trainServices": null`, the app may be falling back to the via-station route.

### API key issues

If the page shows an API key error, make sure `config.json` contains a valid `api_key`.

### Verify the configuration file

```bash
cat /home/simon/next_train/config.json
```

Required fields:

- `station`
- `api_key`
- `rows`
- optional: `via_crs`, `filter_crs`

## Restart the service

```bash
sudo systemctl restart next-train.service
```

Then check logs again if the problem persists.

## Remote access

The running application is available from the remote host at:

```
http://192.168.1.183:8190
```

Make sure your network allows access to port `8190`.
