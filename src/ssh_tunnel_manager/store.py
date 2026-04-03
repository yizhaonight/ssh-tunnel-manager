from __future__ import annotations

import json
from pathlib import Path

from .models import Config


CONFIG_PATH = Path(__file__).resolve().parents[2] / "config.json"


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
