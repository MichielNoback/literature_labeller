# Literature Labeller

Config-driven dashboard for manually labelling PubMed publications one at a time,
across many sessions. The corpus is pesticide-related literature; each abstract is
assigned one of five classes by keypress. Built with NiceGUI; labels persist to
SQLite and export to CSV.

## Resume the session

- Requirements and stage breakdown: `INSTRUCTIONS.md`.
- Full design rationale and data findings: the plan file at
  `~/.claude/plans/dapper-honking-wadler.md` (there is no `SPECIFICATIONS.md`).
- The code in `src/` was produced by a cloud "ultraplan" session (commit `dc4de07`),
  **local-only, not yet pushed** and not yet run against the real corpus. Review before
  relying on it — see Open items.

## Architecture

Package lives under `src/literature_labeller/` (installable; `pyproject.toml` uses a
src-layout). NiceGUI + PyYAML only — no pandas.

| File | Role |
|---|---|
| `config.py` | Load/validate `config.yaml` into a config object |
| `data.py` | Read dataset + keyword terms via `csv.DictReader`; verify required columns; split synonyms on `;` |
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
- Cloud session implemented all modules + tests in commit `dc4de07`. Code has **not**
  been run or tested locally (base conda env lacks pytest).

## Open items / next steps

1. **Reconcile the data path (blocking).** `scripts/make_sample.py` correctly reads the
   real tab-separated corpus and writes `data/pubmed_scan_2026_02_02_sample.txt`, but
   `config.yaml` points the app at `data/pubmed_sample_with_keywords.csv` and `data.py`
   reads with a comma `csv.DictReader`. As delivered, the app + tests run only against the
   **synthetic comma-CSV** from `make_synthetic.py`; it cannot yet read the real sample
   (wrong path *and* wrong delimiter). Decide the working format and align all three.
2. **Verify against real data** once (1) is resolved: run `make_sample.py`, launch the
   app, label a few entries, edit one via ArrowLeft, exit, and confirm the CSV export +
   `label_events` history. Confirm short-acronym case-sensitivity and `;`-synonym splitting
   on live abstracts.
3. **Empty abstracts:** confirm `make_sample.py` excludes the 32,558 abstract-less rows
   (the plan requires it; not yet verified in the delivered script).
4. **INSTRUCTIONS.md Stage 3** still references the stale `data/pubmed_sample_with_keywords.cs`
   path; harmonise with whatever (1) decides.
