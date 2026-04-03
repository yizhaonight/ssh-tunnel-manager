from __future__ import annotations

import asyncio
import contextlib
import subprocess
import time

from fastapi import HTTPException, status

from .models import Config, Tunnel, TunnelMode, TunnelState
from .settings import MAX_RETRIES, REACHABILITY_TIMEOUT, RETRY_BACKOFF_BASE


class TunnelRuntime:
    def __init__(self) -> None:
        self.states: dict[str, TunnelState] = {}

    def find_tunnel(
        self, config: Config, tunnel_id: str
    ) -> tuple[int, Tunnel] | tuple[None, None]:
        for idx, tunnel in enumerate(config.tunnels):
            if tunnel.id == tunnel_id:
                return idx, tunnel
        return None, None

    def get_state(self, tunnel_id: str) -> TunnelState:
        if tunnel_id not in self.states:
            self.states[tunnel_id] = TunnelState()
        return self.states[tunnel_id]

    def is_running(self, tunnel_id: str) -> bool:
        state = self.states.get(tunnel_id)
        if not state or not state.proc:
            return False
        return state.proc.poll() is None

    def build_ssh_command(self, tunnel: Tunnel) -> list[str]:
        target = tunnel.ssh_host_alias or f"{tunnel.ssh_user}@{tunnel.ssh_host}"
        bind_host = "0.0.0.0" if tunnel.expose_to_lan else "127.0.0.1"
        if tunnel.mode == TunnelMode.reverse:
            forward_spec = (
                f"{bind_host}:{tunnel.remote_port}:{tunnel.remote_host}:{tunnel.local_port}"
            )
            cmd = ["ssh", "-N", "-R", forward_spec]
        else:
            forward_spec = (
                f"{bind_host}:{tunnel.local_port}:{tunnel.remote_host}:{tunnel.remote_port}"
            )
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

    def collect_stderr(self, state: TunnelState) -> str:
        if not state.proc or not state.proc.stderr:
            return ""
        try:
            return state.proc.stderr.read().strip()
        except Exception:
            return ""

    def start_tunnel(self, tunnel: Tunnel, *, is_restart: bool = False) -> bool:
        if self.is_running(tunnel.id):
            return False
        state = self.get_state(tunnel.id)
        cmd = self.build_ssh_command(tunnel)
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

    def stop_tunnel(self, tunnel_id: str) -> bool:
        state = self.states.get(tunnel_id)
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

    def apply_enabled_state(self, tunnel: Tunnel) -> None:
        if tunnel.enabled:
            self.start_tunnel(tunnel)
        else:
            self.stop_tunnel(tunnel.id)

    async def probe_local_tunnel(self, tunnel: Tunnel) -> tuple[bool, str]:
        try:
            _, writer = await asyncio.wait_for(
                asyncio.open_connection("127.0.0.1", tunnel.local_port),
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

    async def check_reachability(self, tunnel: Tunnel) -> tuple[bool, str]:
        if tunnel.mode == TunnelMode.reverse:
            return True, ""
        return await self.probe_local_tunnel(tunnel)

    def schedule_restart(self, tunnel: Tunnel, state: TunnelState, reason: str) -> None:
        if state.proc and state.proc.poll() is None:
            state.proc.terminate()
            try:
                state.proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                state.proc.kill()
        state.proc = None
        state.error = reason
        state.retries += 1

    def should_wait_for_backoff(self, state: TunnelState) -> bool:
        backoff = RETRY_BACKOFF_BASE * (2 ** max(state.retries - 1, 0))
        elapsed = time.monotonic() - state.last_restart
        return elapsed < backoff

    def build_statuses(self, config: Config) -> dict[str, dict[str, str | int | bool]]:
        result: dict[str, dict[str, str | int | bool]] = {}
        for tunnel in config.tunnels:
            state = self.states.get(tunnel.id)
            if not state:
                result[tunnel.id] = {
                    "running": False,
                    "reachable": False,
                    "error": "",
                    "probe_error": "",
                    "retries": 0,
                    "probe_failures": 0,
                }
                continue
            result[tunnel.id] = {
                "running": self.is_running(tunnel.id),
                "reachable": state.reachable,
                "error": state.error,
                "probe_error": state.probe_error,
                "retries": state.retries,
                "probe_failures": state.probe_failures,
            }
        return result

    def reset_manual_start_state(self, tunnel_id: str) -> TunnelState:
        state = self.get_state(tunnel_id)
        state.error = ""
        state.retries = 0
        state.reachable = False
        state.probe_error = ""
        state.probe_failures = 0
        return state

    def exceeded_retries(self, state: TunnelState) -> bool:
        return state.retries > MAX_RETRIES
