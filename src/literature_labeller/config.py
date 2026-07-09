"""Load and validate the Literature Labeller config file."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import yaml


class ConfigError(Exception):
    """Raised when the config file is missing required fields or is malformed."""


@dataclass(frozen=True)
class Label:
    id: int
    name: str
    display: str


@dataclass(frozen=True)
class Config:
    dataset_path: Path
    keywords_path: Path
    output_csv: Path
    db_path: Path
    labels: tuple[Label, ...]

    @property
    def hotkeys(self) -> dict[str, Label]:
        """Map single-character keyboard shortcuts (the label id) to labels."""
        return {str(label.id): label for label in self.labels}

    @property
    def hotkeys_ids(self) -> set[int]:
        """Set of integer label ids usable as numeric keyboard shortcuts."""
        return {label.id for label in self.labels}


def load_config(path: str | Path) -> Config:
    """Read and validate ``config.yaml``, resolving relative paths against its directory."""
    path = Path(path)
    if not path.is_file():
        raise ConfigError(f"Config file not found: {path}")

    with path.open("r", encoding="utf-8") as fh:
        raw = yaml.safe_load(fh) or {}
    if not isinstance(raw, dict):
        raise ConfigError("Config root must be a mapping.")

    base = path.resolve().parent

    def resolve(key: str) -> Path:
        value = raw.get(key)
        if not value:
            raise ConfigError(f"Missing required config key: {key!r}")
        p = Path(value)
        return p if p.is_absolute() else base / p

    dataset_path = resolve("dataset_path")
    keywords_path = resolve("keywords_path")
    output_csv = resolve("output_csv")
    db_path = resolve("db_path")

    labels = _parse_labels(raw.get("labels"))

    return Config(
        dataset_path=dataset_path,
        keywords_path=keywords_path,
        output_csv=output_csv,
        db_path=db_path,
        labels=labels,
    )


def _parse_labels(raw_labels: object) -> tuple[Label, ...]:
    if not isinstance(raw_labels, list) or not raw_labels:
        raise ConfigError("Config must define a non-empty 'labels' list.")

    labels: list[Label] = []
    seen_ids: set[int] = set()
    for entry in raw_labels:
        if not isinstance(entry, dict):
            raise ConfigError(f"Each label must be a mapping, got: {entry!r}")
        try:
            label_id = int(entry["id"])
            name = str(entry["name"])
            display = str(entry["display"])
        except (KeyError, TypeError, ValueError) as exc:
            raise ConfigError(f"Invalid label entry {entry!r}: {exc}") from exc
        if label_id in seen_ids:
            raise ConfigError(f"Duplicate label id: {label_id}")
        if not (0 <= label_id <= 9):
            raise ConfigError(f"Label id {label_id} out of range 0-9 (used as hotkey).")
        seen_ids.add(label_id)
        labels.append(Label(id=label_id, name=name, display=display))

    return tuple(labels)
