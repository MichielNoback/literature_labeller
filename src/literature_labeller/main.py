"""Entry point: wire config, data, and store into the NiceGUI app."""

from __future__ import annotations

import argparse
from datetime import datetime
from pathlib import Path

from nicegui import ui

from .app import LabellerUI
from .config import load_config
from .data import load_dataset, load_keyword_terms
from .highlight import Highlighter
from .store import LabelStore

DEFAULT_CONFIG = Path(__file__).resolve().parents[2] / "config.yaml"


def _build(config_path: str | Path) -> LabellerUI:
    config = load_config(config_path)
    dataset = load_dataset(config.dataset_path)
    terms = load_keyword_terms(config.keywords_path)
    highlighter = Highlighter(terms)
    store = LabelStore(config.db_path)
    session = datetime.now().strftime("%Y-%m-%dT%H:%M:%S")
    return LabellerUI(config, dataset, highlighter, store, session)


def cli() -> None:
    parser = argparse.ArgumentParser(description="Literature Labeller dashboard")
    parser.add_argument("--config", default=str(DEFAULT_CONFIG), help="Path to config.yaml")
    parser.add_argument("--port", type=int, default=8080)
    parser.add_argument("--host", default="127.0.0.1")
    args = parser.parse_args()

    labeller = _build(args.config)

    @ui.page("/")
    def index() -> None:
        labeller.build()

    ui.run(
        host=args.host,
        port=args.port,
        title="Literature Labeller",
        reload=False,
        show=False,
    )


# `ui.run` must execute at import time under `python -m`, so guard on __main__.
if __name__ in {"__main__", "__mp_main__"}:
    cli()
