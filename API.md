# SSH Tunnel Manager API

Base URL
- Default base path is `/api`.
- All endpoints accept and return JSON.

Authentication
- None.

Content Type
- Requests with a body must use `Content-Type: application/json`.

Common Errors
- `404 Not Found`: Returned when a tunnel ID does not exist. Response body: `{ "detail": "Tunnel not found" }`.

Data Model

Tunnel
- `id` (string, UUID): Server-generated unique identifier.
- `name` (string): Human-readable tunnel name.
- `mode` (string, default `"local"`): Tunnel mode — `"local"` for local port forwarding (`ssh -L`) or `"reverse"` for reverse port forwarding (`ssh -R`).
- `ssh_host` (string, optional): SSH server hostname or IP. Required if `ssh_host_alias` is not provided.
- `ssh_host_alias` (string, optional): Host alias from `~/.ssh/config`. Required if `ssh_host` is not provided.
- `ssh_user` (string, optional): SSH username. Required if `ssh_host_alias` is not provided.
- `ssh_port` (integer, optional, default `22`): SSH server port. Ignored if `ssh_host_alias` is provided.
- `local_port` (integer): Local port to bind.
- `remote_host` (string, default `127.0.0.1`): Remote host to forward to from the SSH server.
- `remote_port` (integer): Remote port to forward to from the SSH server.
- `identity_file` (string, nullable): Path to SSH private key.
- `identity_file` (string, nullable): Path to SSH private key. Ignored if `ssh_host_alias` is provided.
- `keepalive_interval` (integer, nullable): SSH keepalive interval in seconds.
- `compression` (boolean, default `false`): Enable SSH compression.
- `expose_to_lan` (boolean, default `false`): Bind the local forwarded port to `0.0.0.0` instead of `127.0.0.1`.
- `enabled` (boolean, default `true`): Whether the service should keep this tunnel running.

TunnelCreate
- Same fields as `Tunnel` except `id` (server-generated).

TunnelUpdate
- All fields optional. Only provided fields are updated.

Endpoints

1) List Tunnels
- Method: `GET`
- Path: `/api/tunnels`
- Response: `200 OK`
- Response body: Array of `Tunnel`

Example response
```json
[
  {
    "id": "2c1b9f0f-9a3f-4c4e-9a56-1c1af1451d6b",
    "name": "Prod DB",
    "ssh_host": "ssh.example.com",
    "ssh_user": "deploy",
    "ssh_port": 22,
    "local_port": 5433,
    "remote_host": "127.0.0.1",
    "remote_port": 5432,
    "identity_file": "~/.ssh/id_rsa",
    "keepalive_interval": 30,
    "compression": false
  }
]
```

2) Create Tunnel
- Method: `POST`
- Path: `/api/tunnels`
- Request body: `TunnelCreate`
- Response: `201 Created`
- Response body: `Tunnel`

Example request
```json
{
  "name": "Staging Redis",
  "ssh_host_alias": "staging-ssh",
  "ssh_user": "dev",
  "ssh_port": 22,
  "local_port": 6380,
  "remote_host": "127.0.0.1",
  "remote_port": 6379,
  "identity_file": "~/.ssh/id_ed25519",
  "keepalive_interval": 20,
  "compression": true,
  "expose_to_lan": false,
  "enabled": true
}
```

Example response
```json
{
  "id": "a4e9f6c2-5ffb-4b13-9c73-01c45b17d3b3",
  "name": "Staging Redis",
  "ssh_host_alias": "staging-ssh",
  "ssh_user": "dev",
  "ssh_port": 22,
  "local_port": 6380,
  "remote_host": "127.0.0.1",
  "remote_port": 6379,
  "identity_file": "~/.ssh/id_ed25519",
  "keepalive_interval": 20,
  "compression": true,
  "expose_to_lan": false,
  "enabled": true
}
```

3) Get Tunnel by ID
- Method: `GET`
- Path: `/api/tunnels/{tunnel_id}`
- Response: `200 OK`
- Response body: `Tunnel`

Example response
```json
{
  "id": "a4e9f6c2-5ffb-4b13-9c73-01c45b17d3b3",
  "name": "Staging Redis",
  "ssh_host_alias": "staging-ssh",
  "ssh_user": "dev",
  "ssh_port": 22,
  "local_port": 6380,
  "remote_host": "127.0.0.1",
  "remote_port": 6379,
  "identity_file": "~/.ssh/id_ed25519",
  "keepalive_interval": 20,
  "compression": true,
  "expose_to_lan": false,
  "enabled": true
}
```

4) Replace Tunnel (Full Update)
- Method: `PUT`
- Path: `/api/tunnels/{tunnel_id}`
- Request body: `TunnelCreate` (all required)
- Response: `200 OK`
- Response body: `Tunnel`

Example request
```json
{
  "name": "Staging Redis (Updated)",
  "ssh_host_alias": "staging-ssh",
  "ssh_user": "dev",
  "ssh_port": 2222,
  "local_port": 6381,
  "remote_host": "127.0.0.1",
  "remote_port": 6379,
  "identity_file": "~/.ssh/id_ed25519",
  "keepalive_interval": 25,
  "compression": false,
  "expose_to_lan": true,
  "enabled": true
}
```

Example response
```json
{
  "id": "a4e9f6c2-5ffb-4b13-9c73-01c45b17d3b3",
  "name": "Staging Redis (Updated)",
  "ssh_host_alias": "staging-ssh",
  "ssh_user": "dev",
  "ssh_port": 2222,
  "local_port": 6381,
  "remote_host": "127.0.0.1",
  "remote_port": 6379,
  "identity_file": "~/.ssh/id_ed25519",
  "keepalive_interval": 25,
  "compression": false,
  "expose_to_lan": true,
  "enabled": true
}
```

5) Update Tunnel (Partial Update)
- Method: `PATCH`
- Path: `/api/tunnels/{tunnel_id}`
- Request body: `TunnelUpdate` (any subset)
- Response: `200 OK`
- Response body: `Tunnel`

Example request
```json
{
  "ssh_port": 2222,
  "compression": true
}
```

Example response
```json
{
  "id": "a4e9f6c2-5ffb-4b13-9c73-01c45b17d3b3",
  "name": "Staging Redis",
  "ssh_host_alias": "staging-ssh",
  "ssh_user": "dev",
  "ssh_port": 2222,
  "local_port": 6380,
  "remote_host": "127.0.0.1",
  "remote_port": 6379,
  "identity_file": "~/.ssh/id_ed25519",
  "keepalive_interval": 20,
  "compression": true,
  "expose_to_lan": false,
  "enabled": true
}
```

6) Delete Tunnel
- Method: `DELETE`
- Path: `/api/tunnels/{tunnel_id}`
- Response: `204 No Content`
- Response body: empty

7) Start Tunnel
- Method: `POST`
- Path: `/api/tunnels/{tunnel_id}/start`
- Response: `200 OK`
- Response body: `{ "id": "string", "running": true, "started": true }`

8) Stop Tunnel
- Method: `POST`
- Path: `/api/tunnels/{tunnel_id}/stop`
- Response: `200 OK`
- Response body: `{ "id": "string", "running": false, "stopped": true }`

9) Tunnel Status
- Method: `GET`
- Path: `/api/tunnel-status`
- Response: `200 OK`
- Response body: Object keyed by tunnel ID.

Status fields
- `running` (boolean): Whether the managed `ssh` process is currently alive.
- `reachable` (boolean): Whether the manager's active reachability probe currently succeeds. For local tunnels this means the forwarded local port accepts a TCP connection. Reverse tunnels currently report `true` while the process is running because no remote probe is performed.
- `error` (string): Last restart or process failure reason.
- `probe_error` (string): Last reachability probe failure reason.
- `retries` (integer): Consecutive restart attempts due to process exit or failed probe.
- `probe_failures` (integer): Consecutive failed reachability probes since the last successful probe.

Notes for Frontend
- Each tunnel has a stable `id` used in routes and updates.
- `PUT` requires all fields; `PATCH` only updates provided fields.
- When `ssh_host_alias` is present, the backend ignores `ssh_user`, `ssh_host`, `ssh_port`, and `identity_file`.
- Display defaults when fields are missing in UI forms: `ssh_port=22`, `remote_host=127.0.0.1`, `compression=false`.
- Tunnels with `enabled=true` are started on creation and on service startup.
