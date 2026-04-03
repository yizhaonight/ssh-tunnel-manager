from __future__ import annotations

import argparse
import os

import uvicorn

from .app import app

DEFAULT_PORT = int(os.environ.get("PORT", "8100"))


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser()
    parser.add_argument("--port", type=int, default=DEFAULT_PORT)
    return parser


def main() -> None:
    args = build_parser().parse_args()
    uvicorn.run(app, host="0.0.0.0", port=args.port)
