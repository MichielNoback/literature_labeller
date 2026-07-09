#!/usr/bin/env python3
"""Stage 1: draw a random sample from the full PubMed corpus.

Reads ``data/pubmed_scan_2026_02_02_all_data_filtered.txt`` and writes a random
sample of 15000 lines to ``data/pubmed_scan_2026_02_02_sample.txt``. Both paths
are gitignored. Runs only when the source file is present locally.
"""

from __future__ import annotations

import random
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
SOURCE = REPO_ROOT / "data" / "pubmed_scan_2026_02_02_all_data_filtered.txt"
DEST = REPO_ROOT / "data" / "pubmed_scan_2026_02_02_sample.txt"
SAMPLE_SIZE = 15000
SEED = 20260202


def main() -> int:
    if not SOURCE.is_file():
        print(f"Source corpus not found: {SOURCE}", file=sys.stderr)
        print("Add the file locally, then re-run. (It is gitignored on purpose.)", file=sys.stderr)
        return 1

    with SOURCE.open("r", encoding="utf-8") as fh:
        header = fh.readline()
        lines = fh.readlines()

    rng = random.Random(SEED)
    n = min(SAMPLE_SIZE, len(lines))
    sample = rng.sample(lines, n)

    with DEST.open("w", encoding="utf-8") as fh:
        if header:
            fh.write(header)
        fh.writelines(sample)

    print(f"Wrote {n} sampled entries to {DEST}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
