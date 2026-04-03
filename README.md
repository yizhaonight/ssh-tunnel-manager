# SSH Tunnel Manager

SSH Tunnel Manager is a small FastAPI service with a Svelte frontend for creating, starting, stopping, and monitoring SSH port-forwarding tunnels.

It is built for long-running local use:

- manage multiple `ssh -L` and `ssh -R` tunnels from one UI
- persist tunnel definitions in `config.json`
- auto-start enabled tunnels on service startup
- restart failed tunnels with backoff
- actively probe local forwarded ports to catch tunnels that look alive but are no longer reachable

## What It Manages

Each tunnel definition includes:

- local or reverse forwarding mode
- SSH destination by host alias or explicit host/user/port
- local port, remote host, and remote port
- optional identity file
- optional SSH keepalive interval
- optional compression
- whether the local bind should be exposed to LAN
- whether the manager should keep the tunnel running

The backend shells out to the system `ssh` binary. This project does not implement SSH itself.

## Architecture

- Root entrypoint: [main.py](/Users/yizhao/home/projects/python/ssh-tunnel-manager/main.py)
- Backend package: [src/ssh_tunnel_manager/app.py](/Users/yizhao/home/projects/python/ssh-tunnel-manager/src/ssh_tunnel_manager/app.py)
- Tunnel models: [src/ssh_tunnel_manager/models.py](/Users/yizhao/home/projects/python/ssh-tunnel-manager/src/ssh_tunnel_manager/models.py)
- Config persistence: [src/ssh_tunnel_manager/store.py](/Users/yizhao/home/projects/python/ssh-tunnel-manager/src/ssh_tunnel_manager/store.py)
- Frontend: [frontend/src/App.svelte](/Users/yizhao/home/projects/python/ssh-tunnel-manager/frontend/src/App.svelte)

## Requirements

- Python 3.13+
- Node.js and npm
- OpenSSH client available as `ssh`

## Installation

### Backend

Using `uv`:

```bash
uv sync
```

Or using `venv` and `pip`:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -U pip
pip install fastapi pydantic uvicorn
```

### Frontend

```bash
cd frontend
npm install
```

## Running

### Start the backend

```bash
uv run main.py --port 8100
```

Or:

```bash
python3 main.py --port 8100
```

The backend listens on `0.0.0.0` and defaults to port `8100`.

### Start the frontend in development

```bash
cd frontend
npm run dev
```

The frontend uses `VITE_API_BASE` to find the backend. If unset, it defaults to:

```text
http://localhost:9091
```

If your backend is running on `8100`, start the frontend like this:

```bash
cd frontend
VITE_API_BASE=http://localhost:8100 npm run dev
```

### Build the frontend

```bash
cd frontend
npm run build
```

### SSH Target Rules

You can configure the SSH endpoint in one of two ways:

- `ssh_host_alias`: use a `Host` entry from `~/.ssh/config`
- `ssh_host` plus `ssh_user`: connect directly without an alias

When `ssh_host_alias` is set, the backend ignores:

- `ssh_host`
- `ssh_user`
- `ssh_port`
- `identity_file`

## Health Checks and Recovery

The manager does more than watch whether the `ssh` process is still running.

For enabled local tunnels:

- it probes the local forwarded port every 10 seconds
- if the port does not accept a TCP connection, the tunnel is marked unreachable
- unreachable tunnels are terminated and restarted with exponential backoff
- after 5 consecutive failed restart attempts, the manager gives up and leaves the tunnel in an error state until it is started again manually or updated

The backend also starts SSH with:

```text
-o ExitOnForwardFailure=yes
```

This avoids treating failed forwards as healthy startups.

### Reverse Tunnel Caveat

Reverse tunnels are not actively probed on the remote side right now. For `reverse` mode, the manager treats the tunnel as reachable while the `ssh` process is running.

