from __future__ import annotations

import json
import uuid
from enum import Enum
from pathlib import Path
from typing import Optional

from pydantic import BaseModel, Field, model_validator


class TunnelMode(str, Enum):
    local = "local"
    reverse = "reverse"


CONFIG_PATH = Path(__file__).with_name("config.json")


class TunnelBase(BaseModel):
    name: str
    mode: TunnelMode = TunnelMode.local
    ssh_host: Optional[str] = None
    ssh_host_alias: Optional[str] = None
    ssh_user: Optional[str] = None
    ssh_port: Optional[int] = 22
    local_port: int
    remote_host: str = "127.0.0.1"
    remote_port: int
    identity_file: Optional[str] = None
    keepalive_interval: Optional[int] = None
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
    name: Optional[str] = None
    mode: Optional[TunnelMode] = None
    ssh_host: Optional[str] = None
    ssh_host_alias: Optional[str] = None
    ssh_user: Optional[str] = None
    ssh_port: Optional[int] = None
    local_port: Optional[int] = None
    remote_host: Optional[str] = None
    remote_port: Optional[int] = None
    identity_file: Optional[str] = None
    keepalive_interval: Optional[int] = None
    compression: Optional[bool] = None
    expose_to_lan: Optional[bool] = None
    enabled: Optional[bool] = None


class Tunnel(TunnelBase):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))


class Config(BaseModel):
    tunnels: list[Tunnel] = Field(default_factory=list)


def load_config(path: Path = CONFIG_PATH) -> Config:
    if not path.exists():
        return Config()
    raw = path.read_text().strip()
    if not raw:
        return Config()
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        return Config()
    return Config.model_validate(data)


def save_config(config: Config, path: Path = CONFIG_PATH) -> None:
    tmp_path = path.with_suffix(path.suffix + ".tmp")
    tmp_path.write_text(config.model_dump_json(indent=2))
    tmp_path.replace(path)
