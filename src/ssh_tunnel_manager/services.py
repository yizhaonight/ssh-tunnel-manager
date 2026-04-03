from __future__ import annotations

import asyncio

from fastapi import HTTPException, status

from .models import Tunnel, TunnelCreate, TunnelUpdate
from .runtime import TunnelRuntime
from .settings import HEALTH_CHECK_INTERVAL, MAX_RETRIES
from .store import load_config, save_config


class TunnelService:
    def __init__(self, runtime: TunnelRuntime) -> None:
        self.runtime = runtime

    async def startup(self) -> None:
        config = load_config()
        for tunnel in config.tunnels:
            if tunnel.enabled:
                self.runtime.start_tunnel(tunnel)

    async def shutdown(self) -> None:
        for tunnel_id in list(self.runtime.states.keys()):
            self.runtime.stop_tunnel(tunnel_id)

    async def health_loop(self) -> None:
        while True:
            await asyncio.sleep(HEALTH_CHECK_INTERVAL)
            config = load_config()
            for tunnel in config.tunnels:
                await self._reconcile_tunnel(tunnel)

    async def _reconcile_tunnel(self, tunnel: Tunnel) -> None:
        if not tunnel.enabled:
            return

        state = self.runtime.get_state(tunnel.id)
        if state.proc is None:
            return

        if state.proc.poll() is not None:
            stderr = self.runtime.collect_stderr(state)
            exit_code = state.proc.returncode
            state.proc = None
            state.reachable = False
            state.probe_error = ""
            state.probe_failures = 0
            state.error = stderr or f"Process exited with code {exit_code}"
            state.retries += 1
            if self.runtime.exceeded_retries(state):
                state.error = f"Gave up after {MAX_RETRIES} retries. Last: {state.error}"
                return
            if self.runtime.should_wait_for_backoff(state):
                return
            try:
                self.runtime.start_tunnel(tunnel, is_restart=True)
            except HTTPException:
                return
            return

        reachable, probe_error = await self.runtime.check_reachability(tunnel)
        state.reachable = reachable
        state.probe_error = probe_error

        if reachable:
            state.probe_failures = 0
            if state.retries > 0:
                state.error = ""
                state.retries = 0
            return

        state.probe_failures += 1
        reason = f"Reachability probe failed {state.probe_failures} time(s): {probe_error}"
        self.runtime.schedule_restart(tunnel, state, reason)
        if self.runtime.exceeded_retries(state):
            state.reachable = False
            state.error = f"Gave up after {MAX_RETRIES} retries. Last: {state.error}"
            return
        if self.runtime.should_wait_for_backoff(state):
            return
        try:
            self.runtime.start_tunnel(tunnel, is_restart=True)
        except HTTPException:
            return

    def list_tunnels(self) -> list[Tunnel]:
        return load_config().tunnels

    def create_tunnel(self, payload: TunnelCreate) -> Tunnel:
        config = load_config()
        tunnel = Tunnel(**payload.model_dump())
        config.tunnels.append(tunnel)
        save_config(config)
        if tunnel.enabled:
            self.runtime.start_tunnel(tunnel)
        return tunnel

    def get_tunnel(self, tunnel_id: str) -> Tunnel:
        config = load_config()
        _, tunnel = self.runtime.find_tunnel(config, tunnel_id)
        if not tunnel:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Tunnel not found",
            )
        return tunnel

    def replace_tunnel(self, tunnel_id: str, payload: TunnelCreate) -> Tunnel:
        config = load_config()
        idx, existing = self.runtime.find_tunnel(config, tunnel_id)
        if not existing or idx is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Tunnel not found",
            )
        updated = Tunnel(id=tunnel_id, **payload.model_dump())
        config.tunnels[idx] = updated
        save_config(config)
        self.runtime.stop_tunnel(tunnel_id)
        self.runtime.apply_enabled_state(updated)
        return updated

    def update_tunnel(self, tunnel_id: str, payload: TunnelUpdate) -> Tunnel:
        config = load_config()
        idx, existing = self.runtime.find_tunnel(config, tunnel_id)
        if not existing or idx is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Tunnel not found",
            )
        updated = existing.model_copy(update=payload.model_dump(exclude_unset=True))
        config.tunnels[idx] = updated
        save_config(config)
        self.runtime.stop_tunnel(tunnel_id)
        self.runtime.apply_enabled_state(updated)
        return updated

    def delete_tunnel(self, tunnel_id: str) -> None:
        config = load_config()
        idx, existing = self.runtime.find_tunnel(config, tunnel_id)
        if not existing or idx is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Tunnel not found",
            )
        config.tunnels.pop(idx)
        save_config(config)
        self.runtime.stop_tunnel(tunnel_id)

    def list_statuses(self) -> dict[str, dict[str, str | int | bool]]:
        return self.runtime.build_statuses(load_config())

    def start_tunnel(self, tunnel_id: str) -> dict[str, str | bool]:
        tunnel = self.get_tunnel(tunnel_id)
        state = self.runtime.reset_manual_start_state(tunnel_id)
        started = self.runtime.start_tunnel(tunnel)
        return {
            "id": tunnel_id,
            "running": self.runtime.is_running(tunnel_id),
            "reachable": state.reachable,
            "started": started,
        }

    def stop_tunnel(self, tunnel_id: str) -> dict[str, str | bool]:
        self.get_tunnel(tunnel_id)
        stopped = self.runtime.stop_tunnel(tunnel_id)
        return {
            "id": tunnel_id,
            "running": self.runtime.is_running(tunnel_id),
            "reachable": False,
            "stopped": stopped,
        }
