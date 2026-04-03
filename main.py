import asyncio
import contextlib
import subprocess
import time
from dataclasses import dataclass

from fastapi import FastAPI, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware


from config import (
    Config,
    Tunnel,
    TunnelCreate,
    TunnelMode,
    TunnelUpdate,
    load_config,
    save_config,
)


HEALTH_CHECK_INTERVAL = 10  # seconds between health checks
MAX_RETRIES = 5             # stop retrying after this many consecutive failures
RETRY_BACKOFF_BASE = 5      # base seconds for exponential backoff
REACHABILITY_TIMEOUT = 2    # seconds to wait for a tunnel probe


@dataclass
class TunnelState:
    proc: subprocess.Popen | None = None
    error: str = ""
    retries: int = 0
    last_restart: float = 0.0
    reachable: bool = False
    probe_error: str = ""
    probe_failures: int = 0


app = FastAPI(title="SSH Tunnel Manager")
TUNNEL_STATES: dict[str, TunnelState] = {}
_health_task: asyncio.Task | None = None
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)


def _find_tunnel(config: Config, tunnel_id: str) -> tuple[int, Tunnel] | tuple[None, None]:
    for idx, tunnel in enumerate(config.tunnels):
        if tunnel.id == tunnel_id:
            return idx, tunnel
    return None, None


def _get_state(tunnel_id: str) -> TunnelState:
    if tunnel_id not in TUNNEL_STATES:
        TUNNEL_STATES[tunnel_id] = TunnelState()
    return TUNNEL_STATES[tunnel_id]


def _is_running(tunnel_id: str) -> bool:
    state = TUNNEL_STATES.get(tunnel_id)
    if not state or not state.proc:
        return False
    if state.proc.poll() is None:
        return True
    return False


def _build_ssh_command(tunnel: Tunnel) -> list[str]:
    target = tunnel.ssh_host_alias or f"{tunnel.ssh_user}@{tunnel.ssh_host}"
    bind_host = "0.0.0.0" if tunnel.expose_to_lan else "127.0.0.1"
    if tunnel.mode == TunnelMode.reverse:
        # -R [bind_address:]remote_port:local_host:local_port
        # Remote side listens on remote_port, forwards to local_host:local_port
        forward_spec = f"{bind_host}:{tunnel.remote_port}:{tunnel.remote_host}:{tunnel.local_port}"
        cmd = ["ssh", "-N", "-R", forward_spec]
    else:
        # -L [bind_address:]local_port:remote_host:remote_port
        forward_spec = f"{bind_host}:{tunnel.local_port}:{tunnel.remote_host}:{tunnel.remote_port}"
        cmd = ["ssh", "-N", "-L", forward_spec]
    cmd += ["-o", "ExitOnForwardFailure=yes"]
    if not tunnel.ssh_host_alias:
        if tunnel.ssh_port:
            cmd += ["-p", str(tunnel.ssh_port)]
        if tunnel.identity_file:
            cmd += ["-i", tunnel.identity_file]
    if tunnel.keepalive_interval:
        cmd += ["-o", f"ServerAliveInterval={tunnel.keepalive_interval}"]
    if tunnel.compression:
        cmd.append("-C")
    cmd.append(target)
    return cmd


def _collect_stderr(state: TunnelState) -> str:
    """Read any available stderr from a finished process."""
    if not state.proc or not state.proc.stderr:
        return ""
    try:
        return state.proc.stderr.read().strip()
    except Exception:
        return ""


def _start_tunnel(tunnel: Tunnel, *, is_restart: bool = False) -> bool:
    if _is_running(tunnel.id):
        return False
    state = _get_state(tunnel.id)
    cmd = _build_ssh_command(tunnel)
    try:
        proc = subprocess.Popen(
            cmd,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.PIPE,
            text=True,
        )
    except OSError as exc:
        state.error = str(exc)
        state.retries += 1
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to start tunnel: {exc}",
        ) from exc
    state.proc = proc
    if not is_restart:
        state.error = ""
        state.retries = 0
    state.reachable = False
    state.probe_error = ""
    state.probe_failures = 0
    state.last_restart = time.monotonic()
    return True


def _stop_tunnel(tunnel_id: str) -> bool:
    state = TUNNEL_STATES.get(tunnel_id)
    if not state or not state.proc:
        return False
    if state.proc.poll() is None:
        state.proc.terminate()
        try:
            state.proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            state.proc.kill()
    state.proc = None
    state.error = ""
    state.retries = 0
    state.reachable = False
    state.probe_error = ""
    state.probe_failures = 0
    return True


def _apply_enabled_state(tunnel: Tunnel) -> None:
    if tunnel.enabled:
        _start_tunnel(tunnel)
    else:
        _stop_tunnel(tunnel.id)


async def _probe_local_tunnel(tunnel: Tunnel) -> tuple[bool, str]:
    bind_host = "127.0.0.1"
    try:
        reader, writer = await asyncio.wait_for(
            asyncio.open_connection(bind_host, tunnel.local_port),
            timeout=REACHABILITY_TIMEOUT,
        )
    except (TimeoutError, asyncio.TimeoutError):
        return False, "Timed out probing local forwarded port"
    except OSError as exc:
        return False, f"Local forwarded port probe failed: {exc}"
    writer.close()
    with contextlib.suppress(Exception):
        await writer.wait_closed()
    return True, ""


async def _check_reachability(tunnel: Tunnel) -> tuple[bool, str]:
    if tunnel.mode == TunnelMode.reverse:
        return True, ""
    return await _probe_local_tunnel(tunnel)


def _schedule_restart(tunnel: Tunnel, state: TunnelState, reason: str) -> None:
    if state.proc and state.proc.poll() is None:
        state.proc.terminate()
        try:
            state.proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            state.proc.kill()
    state.proc = None
    state.error = reason
    state.retries += 1


def _should_wait_for_backoff(state: TunnelState) -> bool:
    backoff = RETRY_BACKOFF_BASE * (2 ** max(state.retries - 1, 0))
    elapsed = time.monotonic() - state.last_restart
    return elapsed < backoff


async def _health_loop() -> None:
    """Periodically check tunnel processes and forwarded port reachability."""
    while True:
        await asyncio.sleep(HEALTH_CHECK_INTERVAL)
        config = load_config()
        for tunnel in config.tunnels:
            if not tunnel.enabled:
                continue
            state = _get_state(tunnel.id)
            if state.proc is None:
                continue
            if state.proc.poll() is not None:
                # process exited — collect error
                stderr = _collect_stderr(state)
                exit_code = state.proc.returncode
                state.proc = None
                state.reachable = False
                state.probe_error = ""
                state.probe_failures = 0
                if stderr:
                    state.error = stderr
                else:
                    state.error = f"Process exited with code {exit_code}"
                state.retries += 1
                if state.retries > MAX_RETRIES:
                    state.error = f"Gave up after {MAX_RETRIES} retries. Last: {state.error}"
                    continue
                if _should_wait_for_backoff(state):
                    continue
                try:
                    _start_tunnel(tunnel, is_restart=True)
                except HTTPException:
                    pass  # error already recorded in state
                continue

            reachable, probe_error = await _check_reachability(tunnel)
            state.reachable = reachable
            state.probe_error = probe_error

            if reachable:
                state.probe_failures = 0
                if state.retries > 0:
                    state.error = ""
                    state.retries = 0
                continue

            state.probe_failures += 1
            reason = (
                f"Reachability probe failed {state.probe_failures} time(s): {probe_error}"
            )
            _schedule_restart(tunnel, state, reason)
            if state.retries > MAX_RETRIES:
                state.reachable = False
                state.error = f"Gave up after {MAX_RETRIES} retries. Last: {state.error}"
                continue
            if _should_wait_for_backoff(state):
                continue
            try:
                _start_tunnel(tunnel, is_restart=True)
            except HTTPException:
                pass  # error already recorded in state


@app.on_event("startup")
async def startup() -> None:
    global _health_task
    config = load_config()
    for tunnel in config.tunnels:
        if tunnel.enabled:
            _start_tunnel(tunnel)
    _health_task = asyncio.create_task(_health_loop())


@app.on_event("shutdown")
async def shutdown() -> None:
    global _health_task
    if _health_task:
        _health_task.cancel()
        try:
            await _health_task
        except asyncio.CancelledError:
            pass
        _health_task = None
    for tunnel_id in list(TUNNEL_STATES.keys()):
        _stop_tunnel(tunnel_id)


@app.get("/api/tunnels", response_model=list[Tunnel])
def list_tunnels() -> list[Tunnel]:
    config = load_config()
    return config.tunnels


@app.post("/api/tunnels", response_model=Tunnel, status_code=status.HTTP_201_CREATED)
def create_tunnel(payload: TunnelCreate) -> Tunnel:
    config = load_config()
    tunnel = Tunnel(**payload.model_dump())
    config.tunnels.append(tunnel)
    save_config(config)
    if tunnel.enabled:
        _start_tunnel(tunnel)
    return tunnel


@app.get("/api/tunnels/{tunnel_id}", response_model=Tunnel)
def get_tunnel(tunnel_id: str) -> Tunnel:
    config = load_config()
    _, tunnel = _find_tunnel(config, tunnel_id)
    if not tunnel:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Tunnel not found")
    return tunnel


@app.put("/api/tunnels/{tunnel_id}", response_model=Tunnel)
def replace_tunnel(tunnel_id: str, payload: TunnelCreate) -> Tunnel:
    config = load_config()
    idx, existing = _find_tunnel(config, tunnel_id)
    if not existing or idx is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Tunnel not found")
    updated = Tunnel(id=tunnel_id, **payload.model_dump())
    config.tunnels[idx] = updated
    save_config(config)
    _stop_tunnel(tunnel_id)
    _apply_enabled_state(updated)
    return updated


@app.patch("/api/tunnels/{tunnel_id}", response_model=Tunnel)
def update_tunnel(tunnel_id: str, payload: TunnelUpdate) -> Tunnel:
    config = load_config()
    idx, existing = _find_tunnel(config, tunnel_id)
    if not existing or idx is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Tunnel not found")
    update_data = payload.model_dump(exclude_unset=True)
    updated = existing.model_copy(update=update_data)
    config.tunnels[idx] = updated
    save_config(config)
    _stop_tunnel(tunnel_id)
    _apply_enabled_state(updated)
    return updated


@app.delete("/api/tunnels/{tunnel_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_tunnel(tunnel_id: str) -> None:
    config = load_config()
    idx, existing = _find_tunnel(config, tunnel_id)
    if not existing or idx is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Tunnel not found")
    config.tunnels.pop(idx)
    save_config(config)
    _stop_tunnel(tunnel_id)
    return None


@app.get("/api/tunnel-status")
def list_statuses() -> dict:
    config = load_config()
    result = {}
    for tunnel in config.tunnels:
        state = TUNNEL_STATES.get(tunnel.id)
        if not state:
            result[tunnel.id] = {
                "running": False,
                "reachable": False,
                "error": "",
                "probe_error": "",
                "retries": 0,
                "probe_failures": 0,
            }
        else:
            result[tunnel.id] = {
                "running": _is_running(tunnel.id),
                "reachable": state.reachable,
                "error": state.error,
                "probe_error": state.probe_error,
                "retries": state.retries,
                "probe_failures": state.probe_failures,
            }
    return result


@app.post("/api/tunnels/{tunnel_id}/start")
def start_tunnel(tunnel_id: str) -> dict:
    config = load_config()
    _, tunnel = _find_tunnel(config, tunnel_id)
    if not tunnel:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Tunnel not found")
    # Manual start resets error state
    state = _get_state(tunnel_id)
    state.error = ""
    state.retries = 0
    state.reachable = False
    state.probe_error = ""
    state.probe_failures = 0
    started = _start_tunnel(tunnel)
    return {
        "id": tunnel_id,
        "running": _is_running(tunnel_id),
        "reachable": state.reachable,
        "started": started,
    }


@app.post("/api/tunnels/{tunnel_id}/stop")
def stop_tunnel(tunnel_id: str) -> dict:
    config = load_config()
    _, tunnel = _find_tunnel(config, tunnel_id)
    if not tunnel:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Tunnel not found")
    stopped = _stop_tunnel(tunnel_id)
    return {
        "id": tunnel_id,
        "running": _is_running(tunnel_id),
        "reachable": False,
        "stopped": stopped,
    }


def main():
    import uvicorn
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--port")
    args = parser.parse_args()
    port = args.port
    if port is None or port == 0:
        port = 8100
    uvicorn.run(app, host="0.0.0.0", port=int(port))


if __name__ == '__main__':
    main()
