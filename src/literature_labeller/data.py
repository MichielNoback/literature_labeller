"""Read and validate the PubMed dataset and the (read-only) keywords file."""

from __future__ import annotations

import csv
from dataclasses import dataclass
from pathlib import Path

REQUIRED_DATASET_COLUMNS = ("pmid", "title", "abstract")
REQUIRED_KEYWORD_COLUMNS = ("ID", "name", "synonyms")


class DataError(Exception):
    """Raised when an input file is missing required columns or cannot be read."""


@dataclass
class Dataset:
    """PubMed entries plus the original column order, for lossless export."""

    fieldnames: list[str]
    rows: list[dict[str, str]]

    def __len__(self) -> int:
        return len(self.rows)


def _read_csv(
    path: Path, required: tuple[str, ...], delimiter: str = ","
) -> tuple[list[str], list[dict[str, str]]]:
    if not path.is_file():
        raise DataError(f"File not found: {path}")
    with path.open("r", encoding="utf-8", newline="") as fh:
        # The PubMed corpus is tab-separated; the keywords file is comma-separated.
        reader = csv.DictReader(fh, delimiter=delimiter)
        fieldnames = reader.fieldnames or []
        missing = [c for c in required if c not in fieldnames]
        if missing:
            raise DataError(
                f"{path.name} is missing required column(s): {', '.join(missing)}. "
                f"Found: {', '.join(fieldnames)}"
            )
        rows = [dict(row) for row in reader]
    return list(fieldnames), rows


def load_dataset(path: str | Path) -> Dataset:
    """Load the tab-separated PubMed dataset; requires pmid/title/abstract, preserves all other columns."""
    fieldnames, rows = _read_csv(Path(path), REQUIRED_DATASET_COLUMNS, delimiter="\t")
    return Dataset(fieldnames=fieldnames, rows=rows)


def load_keyword_records(path: str | Path) -> list[dict[str, str]]:
    """Return the full keyword rows (all columns) from the comma-separated file.

    Used by Quick Lookup to show compound details; ``load_keyword_terms`` remains the
    lighter call used for highlighting.
    """
    _, rows = _read_csv(Path(path), REQUIRED_KEYWORD_COLUMNS, delimiter=",")
    return rows


def load_keyword_terms(path: str | Path) -> list[str]:
    """Return every distinct keyword term (names + `;`-separated synonyms) from the comma-separated file."""
    _, rows = _read_csv(Path(path), REQUIRED_KEYWORD_COLUMNS, delimiter=",")
    terms: list[str] = []
    seen: set[str] = set()
    for row in rows:
        candidates = [row.get("name", "")]
        candidates.extend((row.get("synonyms") or "").split(";"))
        for term in candidates:
            term = term.strip()
            key = term.lower()
            if term and key not in seen:
                seen.add(key)
                terms.append(term)
    return terms
