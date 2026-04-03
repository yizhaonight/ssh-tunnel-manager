from __future__ import annotations

import uuid
from dataclasses import dataclass
from enum import Enum

from pydantic import BaseModel, Field, model_validator


class TunnelMode(str, Enum):
    local = "local"
    reverse = "reverse"


class TunnelBase(BaseModel):
    name: str
    mode: TunnelMode = TunnelMode.local
    ssh_host: str | None = None
    ssh_host_alias: str | None = None
    ssh_user: str | None = None
    ssh_port: int | None = 22
    local_port: int
    remote_host: str = "127.0.0.1"
    remote_port: int
    identity_file: str | None = None
    keepalive_interval: int | None = None
    compression: bool = False
    expose_to_lan: bool = False
    enabled: bool = True

    @model_validator(mode="after")
    def validate_target(self) -> "TunnelBase":
        if not self.ssh_host_alias:
            if not self.ssh_host:
                raise ValueError("ssh_host is required when ssh_host_alias is not set")
            if not self.ssh_user:
                raise ValueError("ssh_user is required when ssh_host_alias is not set")
        return self


class TunnelCreate(TunnelBase):
    pass


class TunnelUpdate(BaseModel):
    name: str | None = None
    mode: TunnelMode | None = None
    ssh_host: str | None = None
    ssh_host_alias: str | None = None
    ssh_user: str | None = None
    ssh_port: int | None = None
    local_port: int | None = None
    remote_host: str | None = None
    remote_port: int | None = None
    identity_file: str | None = None
    keepalive_interval: int | None = None
    compression: bool | None = None
    expose_to_lan: bool | None = None
    enabled: bool | None = None


class Tunnel(TunnelBase):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))


class Config(BaseModel):
    tunnels: list[Tunnel] = Field(default_factory=list)


@dataclass
class TunnelState:
    proc: object | None = None
    error: str = ""
    retries: int = 0
    last_restart: float = 0.0
    reachable: bool = False
    probe_error: str = ""
    probe_failures: int = 0
