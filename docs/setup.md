# Next Train Setup Guide

This guide explains how to set up the Next Train application on the remote host.

## Prerequisites

- Python 3.13 or newer
- Access to the repository at `/home/simon/next_train`

## Install dependencies

From the repository root:

```bash
cd /home/simon/next_train
python3 -m venv .venv
. .venv/bin/activate
pip install -r requirements.txt
```

## Configure application

Copy `config.example.json` to `config.json` and update the values.

Example config for WCP -> CLJ -> VIC:

```json
{
  "station": "WCP",
  "via_crs": "CLJ",
  "filter_crs": "VIC",
  "rows": 10
}
```

## Run locally

Activate the virtual environment and start the server:

```bash
. .venv/bin/activate
python server.py
```

Then browse to:

```
http://192.168.1.183:8190
```

## Set up as a systemd service

Install the service unit and enable it at boot:

```bash
sudo cp next-train.service /etc/systemd/system/next-train.service
sudo systemctl daemon-reload
sudo systemctl enable --now next-train.service
```

Verify the service is running:

```bash
sudo systemctl status next-train.service
```

## Notes

- The service runs from `/home/simon/next_train`
- The systemd unit uses `/home/simon/next_train/.venv/bin/python3`
- The app listens on port `8190`
