# SSH Tunnel Manager

A lightweight self-hosted service for managing SSH port-forwarding tunnels through a web dashboard.

Manage all your `ssh -L` and `ssh -R` tunnels from one place — create, start, stop, and monitor them without touching the terminal.

## Features

- **Local & reverse forwarding** — supports both `ssh -L` and `ssh -R` modes
- **Web dashboard** — built-in UI at `/dashboard`, no separate frontend server needed
- **Persistent config** — tunnel definitions are saved to `config.json` and survive restarts
- **Auto-start** — enabled tunnels start automatically when the service launches
- **Health monitoring** — probes forwarded ports every 10s and restarts failed tunnels with exponential backoff
- **SSH config support** — use `~/.ssh/config` Host aliases or specify host/user/port directly
- **REST API** — fully documented API for scripting and automation (see [API.md](API.md))

## Requirements

- Python 3.13+
- OpenSSH client (`ssh` on PATH)

> Node.js is only needed if you want to modify the frontend. The built dashboard is included in the repo.

## Quick Start

```bash
# Clone and install
git clone https://github.com/yizhaonight/ssh-tunnel-manager.git
cd ssh-tunnel-manager
uv sync

# Start the service
uv run main.py
```

Open **http://localhost:8100/dashboard** to access the web UI.

### Options

```
--port PORT    Server port (default: 8100)
```

### Alternative install (without uv)

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install fastapi pydantic uvicorn
python3 main.py
```

## Usage

### Web Dashboard

The dashboard lets you:

- Create and edit tunnel configurations
- Start/stop individual tunnels or start all at once
- See live status — running, reachable, degraded, or errored
- View error details and retry counts inline

### SSH Target Configuration

You can specify the SSH endpoint in two ways:

| Method | Fields used |
|---|---|
| **Host alias** | `ssh_host_alias` (from `~/.ssh/config`) — all other SSH fields are ignored |
| **Direct** | `ssh_host`, `ssh_user`, `ssh_port`, `identity_file` |

### Health Checks

For **local** tunnels, the service actively probes the forwarded port every 10 seconds. If the port stops accepting TCP connections, the tunnel is killed and restarted with backoff. After 5 consecutive failures, the tunnel enters an error state until manually restarted or updated.

For **reverse** tunnels, the service monitors the SSH process but does not probe the remote port.

All SSH tunnels are started with `ExitOnForwardFailure=yes` to avoid treating failed forwards as healthy connections.

## API

The service exposes a REST API under `/api`. See [API.md](API.md) for full endpoint documentation.

Quick reference:

| Method | Endpoint | Description |
|---|---|---|
| `GET` | `/api/tunnels` | List all tunnels |
| `POST` | `/api/tunnels` | Create a tunnel |
| `GET` | `/api/tunnels/{id}` | Get tunnel by ID |
| `PUT` | `/api/tunnels/{id}` | Replace tunnel |
| `PATCH` | `/api/tunnels/{id}` | Partial update |
| `DELETE` | `/api/tunnels/{id}` | Delete tunnel |
| `POST` | `/api/tunnels/{id}/start` | Start tunnel |
| `POST` | `/api/tunnels/{id}/stop` | Stop tunnel |
| `GET` | `/api/tunnel-status` | Status of all tunnels |

## Frontend Development

The built frontend is committed to `frontend/dist/` and served by the backend automatically. To make frontend changes:

```bash
cd frontend
npm install
VITE_API_BASE=http://localhost:8100 npm run dev   # dev server with hot reload
npm run build                                      # rebuild dist/
```
