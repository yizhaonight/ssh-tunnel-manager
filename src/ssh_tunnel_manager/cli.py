from __future__ import annotations

import argparse

import uvicorn

from .app import app


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser()
    parser.add_argument("--port", type=int, default=8100)
    return parser


def main() -> None:
    args = build_parser().parse_args()
    uvicorn.run(app, host="0.0.0.0", port=args.port)
