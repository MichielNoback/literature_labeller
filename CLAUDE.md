# Literature Labeller

Config-driven dashboard for manually labelling PubMed publications one at a time,
across many sessions. The corpus is pesticide-related literature; each abstract is
assigned one of five classes by keypress. Built with NiceGUI; labels persist to
SQLite and export to CSV.

## Resume the session

- Requirements and stage breakdown: `INSTRUCTIONS.md`.
- Full design rationale and data findings: the plan file at
  `~/.claude/plans/dapper-honking-wadler.md` (there is no `SPECIFICATIONS.md`).
- The code in `src/` was produced by a cloud "ultraplan" session (commit `dc4de07`, now on
  `main` and pushed). Data-path/format reconciliation is done and verified against the real
  corpus (2026-08-26); the app itself has not yet been launched against live data — see Open items.

## Architecture

Package lives under `src/literature_labeller/` (installable; `pyproject.toml` uses a
src-layout). NiceGUI + PyYAML only — no pandas.

| File | Role |
|---|---|
| `config.py` | Load/validate `config.yaml` into a config object |
| `data.py` | Read dataset (tab-sep) + keyword terms (comma-sep) via `csv.DictReader`; verify required columns; split synonyms on `;` |
| `highlight.py` | `Highlighter` — regex-highlight keyword terms in title/abstract |
| `store.py` | `LabelStore` — SQLite persistence of decisions |
| `app.py` | `LabellerUI` — NiceGUI page, key bindings, edit-previous |
| `main.py` | Entry point: wires config→data→store→UI, `ui.run` |
| `scripts/make_sample.py` | Stage 1: sample 15k from the real tab-separated corpus |
| `scripts/make_synthetic.py` | Generate a small synthetic CSV for dev/testing |
| `tests/` | `test_data.py`, `test_highlight.py`, `test_store.py` |

### Run / preview

```bash
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"          # nicegui>=2.0, pyyaml, pytest
python scripts/make_synthetic.py # or make_sample.py for the real corpus
python -m literature_labeller.main   # serves http://127.0.0.1:8080
pytest                               # test env needs pytest; base conda lacks it
```

## Key decisions (Stage 2)

- **NiceGUI** for the UI — native `ui.keyboard` gives single-keystroke labelling and
  ArrowLeft edit-previous with no custom JS.
- **SQLite**, written per decision (crash-safe), exported to CSV on exit. The input
  file is never written to.
- **Short pesticide acronyms** (≤4 chars, e.g. `DEET`, `IPX`) matched case-sensitively;
  longer terms case-insensitively — avoids false highlights in prose.
- Corpus is **tab-separated** despite its `.txt` name, is sparsely quoted (15,906
  abstracts wrapped in `"` because they contain a literal quote), and has **no keywords
  column**. Pesticide-term **synonyms are `;`-separated** while term names contain commas.

## Current status

- Repo bootstrapped; large corpora gitignored (only the 1.1 MB pesticide-terms CSV is
  tracked). Public remote `origin` = github.com/MichielNoback/literature_labeller.
- Cloud session implemented all modules + tests in commit `dc4de07` (now on `main`).
- **Data format standardized on TSV (2026-08-26).** `data.py` reads the dataset tab-separated
  and the keywords file comma-separated; `config.yaml` points at the real
  `data/pubmed_scan_2026_02_02_sample.txt`; `make_sample.py` parses the corpus with `csv`,
  excludes empty-abstract rows, and writes clean TSV. Verified locally: 19/19 tests pass;
  `make_sample.py` wrote 15,000 rows (of 406,124 with abstracts; 32,558 empty ones excluded);
  `load_dataset` reads all 12 columns with 0 empty abstracts; 2,043 keyword terms load.
- Local `.venv` (gitignored) has `pytest` + `pyyaml` only — `nicegui` not yet installed.

## Open items / next steps

1. **Verify the app against real data (next chunk).** Install nicegui (`pip install -e ".[dev]"`),
   launch `python -m literature_labeller.main`, label a few of the 15k entries, edit one via
   ArrowLeft, exit, and confirm the CSV export + `label_events` history. Confirm short-acronym
   case-sensitivity and `;`-synonym splitting on live abstracts.
2. **Commit the reconciliation changes** (config.yaml, data.py, make_sample.py, tests/test_data.py,
   .gitignore, CLAUDE.md) — not yet committed as of this session.
3. **INSTRUCTIONS.md Stage 3** still names the historical `data/pubmed_sample_with_keywords.cs`
   path; it is the original spec, superseded by the TSV decision above. Leave as-is or annotate.
