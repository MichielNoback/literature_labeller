#!/usr/bin/env python3
"""Stage 1: draw a random sample from the full PubMed corpus.

Reads the tab-separated ``data/pubmed_scan_2026_02_02_all_data_filtered.txt`` and
writes a random sample of 15000 entries to ``data/pubmed_scan_2026_02_02_sample.txt``
(also tab-separated). Rows without an abstract are excluded before sampling, since
they cannot be labelled. Both paths are gitignored. Runs only when the source file
is present locally.
"""

from __future__ import annotations

import csv
import random
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
SOURCE = REPO_ROOT / "data" / "pubmed_scan_2026_02_02_all_data_filtered.txt"
DEST = REPO_ROOT / "data" / "pubmed_scan_2026_02_02_sample.txt"
SAMPLE_SIZE = 15000
SEED = 20260202

# Some abstracts contain embedded quotes/newlines, so the corpus must be parsed
# with the csv module (delimiter="\t") rather than read line by line.
DELIMITER = "\t"


def main() -> int:
    if not SOURCE.is_file():
        print(f"Source corpus not found: {SOURCE}", file=sys.stderr)
        print("Add the file locally, then re-run. (It is gitignored on purpose.)", file=sys.stderr)
        return 1

    with SOURCE.open("r", encoding="utf-8", newline="") as fh:
        reader = csv.DictReader(fh, delimiter=DELIMITER)
        fieldnames = reader.fieldnames or []
        if "abstract" not in fieldnames:
            print(f"Corpus is missing an 'abstract' column. Found: {fieldnames}", file=sys.stderr)
            return 1
        # Keep only rows that actually carry an abstract to label.
        rows = [row for row in reader if (row.get("abstract") or "").strip()]

    if not rows:
        print("No rows with a non-empty abstract were found.", file=sys.stderr)
        return 1

    rng = random.Random(SEED)
    n = min(SAMPLE_SIZE, len(rows))
    sample = rng.sample(rows, n)

    with DEST.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=fieldnames, delimiter=DELIMITER)
        writer.writeheader()
        writer.writerows(sample)

    print(f"Wrote {n} sampled entries (of {len(rows)} with abstracts) to {DEST}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
