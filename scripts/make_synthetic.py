#!/usr/bin/env python3
"""Generate a synthetic PubMed dataset for building and testing the app.

Produces ``data/pubmed_sample_with_keywords.csv`` with columns
``pmid,title,abstract,journal`` (``journal`` proves that extra columns are
preserved through export). Abstracts embed real pesticide terms — including
hyphen/space spelling variants — so highlighting is exercised end to end.
"""

from __future__ import annotations

import csv
import random
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
KEYWORDS = REPO_ROOT / "data" / "PESTICIDE_TERMS_20260323_with_compound_data.csv"
DEST = REPO_ROOT / "data" / "pubmed_sample_with_keywords.csv"
N_ROWS = 40
SEED = 42

CONTEXTS = [
    "environmental",
    "human_animal",
    "foodstuff",
    "other",
]

TEMPLATES = {
    "environmental": (
        "Residues of {a} were detected in surface water and soil samples, "
        "raising concern about the environmental persistence of {b}."
    ),
    "human_animal": (
        "Occupational exposure to {a} was associated with adverse effects in "
        "agricultural workers; toxicity of {b} was assessed in a rodent model."
    ),
    "foodstuff": (
        "This study quantified {a} in fruit and vegetable produce, comparing "
        "dietary intake estimates for {b} against regulatory limits."
    ),
    "other": (
        "A new analytical method for the determination of {a} is described. "
        "The approach also resolves {b} in complex matrices."
    ),
}


def load_terms(limit: int = 200) -> list[str]:
    terms: list[str] = []
    with KEYWORDS.open("r", encoding="utf-8", newline="") as fh:
        for row in csv.DictReader(fh):
            name = (row.get("name") or "").strip()
            if len(name) >= 4:
                terms.append(name)
            if len(terms) >= limit:
                break
    return terms


def space_variant(term: str) -> str:
    """Swap hyphens for spaces to test alternative spelling matching."""
    return term.replace("-", " ")


def main() -> int:
    rng = random.Random(SEED)
    terms = load_terms()
    if len(terms) < 2:
        raise SystemExit(f"Not enough terms loaded from {KEYWORDS}")

    DEST.parent.mkdir(parents=True, exist_ok=True)
    with DEST.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=["pmid", "title", "abstract", "journal"])
        writer.writeheader()
        for i in range(N_ROWS):
            ctx = CONTEXTS[i % len(CONTEXTS)]
            a, b = rng.sample(terms, 2)
            # Use the space-variant for `b` in half the rows to exercise the matcher.
            b_text = space_variant(b) if i % 2 == 0 else b
            abstract = TEMPLATES[ctx].format(a=a, b=b_text)
            writer.writerow(
                {
                    "pmid": f"{30000000 + i}",
                    "title": f"Analysis of {a} and related compounds ({ctx} context)",
                    "abstract": abstract,
                    "journal": rng.choice(
                        ["J. Agric. Food Chem.", "Environ. Sci. Technol.", "Chemosphere"]
                    ),
                }
            )

    print(f"Wrote {N_ROWS} synthetic entries to {DEST}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
