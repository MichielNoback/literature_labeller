"""SQLite-backed label store with cumulative CSV export across sessions."""

from __future__ import annotations

import csv
import sqlite3
from datetime import datetime
from pathlib import Path

from .data import Dataset

TIMESTAMP_FORMAT = "%Y-%m-%d;%H:%M"

# Columns appended to the dataset's own columns on export.
LABEL_COLUMNS = ("label_id", "label_name", "timestamp", "session")


def format_timestamp(when: datetime | None = None) -> str:
    """Format a timestamp as e.g. ``2026-07-10;21:21``."""
    return (when or datetime.now()).strftime(TIMESTAMP_FORMAT)


class LabelStore:
    """Persists one (latest) label per pmid; supports re-editing and CSV export."""

    def __init__(self, db_path: str | Path):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(str(self.db_path))
        self._conn.row_factory = sqlite3.Row
        self._conn.execute(
            """
            CREATE TABLE IF NOT EXISTS labels (
                pmid       TEXT PRIMARY KEY,
                label_id   INTEGER NOT NULL,
                label_name TEXT NOT NULL,
                timestamp  TEXT NOT NULL,
                session    TEXT NOT NULL
            )
            """
        )
        self._conn.commit()

    def close(self) -> None:
        self._conn.close()

    def upsert_label(
        self,
        pmid: str,
        label_id: int,
        label_name: str,
        session: str,
        when: datetime | None = None,
    ) -> None:
        """Insert or overwrite the label for ``pmid`` (last decision wins)."""
        self._conn.execute(
            """
            INSERT INTO labels (pmid, label_id, label_name, timestamp, session)
            VALUES (?, ?, ?, ?, ?)
            ON CONFLICT(pmid) DO UPDATE SET
                label_id   = excluded.label_id,
                label_name = excluded.label_name,
                timestamp  = excluded.timestamp,
                session    = excluded.session
            """,
            (pmid, label_id, label_name, format_timestamp(when), session),
        )
        self._conn.commit()

    def get_label(self, pmid: str) -> sqlite3.Row | None:
        """Return the stored label row for ``pmid``, or None."""
        cur = self._conn.execute("SELECT * FROM labels WHERE pmid = ?", (pmid,))
        return cur.fetchone()

    def labelled_pmids(self) -> set[str]:
        """Return the set of pmids that already carry a label."""
        cur = self._conn.execute("SELECT pmid FROM labels")
        return {row["pmid"] for row in cur.fetchall()}

    def export_csv(self, dataset: Dataset, output_csv: str | Path) -> int:
        """Write every dataset row joined with its label to ``output_csv``.

        All sessions are included (the DB is cumulative). Dataset columns are
        preserved in their original order; label columns are appended. Returns
        the number of labelled rows written with a label.
        """
        output_csv = Path(output_csv)
        output_csv.parent.mkdir(parents=True, exist_ok=True)

        labels = {row["pmid"]: row for row in self._conn.execute("SELECT * FROM labels")}
        fieldnames = list(dataset.fieldnames) + list(LABEL_COLUMNS)

        written = 0
        with output_csv.open("w", encoding="utf-8", newline="") as fh:
            writer = csv.DictWriter(fh, fieldnames=fieldnames, extrasaction="ignore")
            writer.writeheader()
            for entry in dataset.rows:
                out = dict(entry)
                label = labels.get(entry.get("pmid", ""))
                if label is not None:
                    out.update(
                        label_id=label["label_id"],
                        label_name=label["label_name"],
                        timestamp=label["timestamp"],
                        session=label["session"],
                    )
                    written += 1
                else:
                    for col in LABEL_COLUMNS:
                        out.setdefault(col, "")
                writer.writerow(out)
        return written
