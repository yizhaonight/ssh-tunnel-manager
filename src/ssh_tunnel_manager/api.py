from __future__ import annotations

from fastapi import APIRouter, status

from .models import Tunnel, TunnelCreate, TunnelUpdate
from .services import TunnelService


def build_router(service: TunnelService) -> APIRouter:
    router = APIRouter()

    @router.get("/api/tunnels", response_model=list[Tunnel])
    def list_tunnels() -> list[Tunnel]:
        return service.list_tunnels()

    @router.post("/api/tunnels", response_model=Tunnel, status_code=status.HTTP_201_CREATED)
    def create_tunnel(payload: TunnelCreate) -> Tunnel:
        return service.create_tunnel(payload)

    @router.get("/api/tunnels/{tunnel_id}", response_model=Tunnel)
    def get_tunnel(tunnel_id: str) -> Tunnel:
        return service.get_tunnel(tunnel_id)

    @router.put("/api/tunnels/{tunnel_id}", response_model=Tunnel)
    def replace_tunnel(tunnel_id: str, payload: TunnelCreate) -> Tunnel:
        return service.replace_tunnel(tunnel_id, payload)

    @router.patch("/api/tunnels/{tunnel_id}", response_model=Tunnel)
    def update_tunnel(tunnel_id: str, payload: TunnelUpdate) -> Tunnel:
        return service.update_tunnel(tunnel_id, payload)

    @router.delete("/api/tunnels/{tunnel_id}", status_code=status.HTTP_204_NO_CONTENT)
    def delete_tunnel(tunnel_id: str) -> None:
        service.delete_tunnel(tunnel_id)
        return None

    @router.get("/api/tunnel-status")
    def list_statuses() -> dict[str, dict[str, str | int | bool]]:
        return service.list_statuses()

    @router.post("/api/tunnels/{tunnel_id}/start")
    def start_tunnel(tunnel_id: str) -> dict[str, str | bool]:
        return service.start_tunnel(tunnel_id)

    @router.post("/api/tunnels/{tunnel_id}/stop")
    def stop_tunnel(tunnel_id: str) -> dict[str, str | bool]:
        return service.stop_tunnel(tunnel_id)

    return router
