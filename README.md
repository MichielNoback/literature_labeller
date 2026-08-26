# Literature Labeller

A config-driven desktop dashboard for manually labelling PubMed publications **one
at a time, across many sessions**. Each abstract is assigned exactly one class by a
single keypress (or mouse click); keyword terms are highlighted in the title and
abstract to speed up the decision. Labels persist to a local SQLite database (crash
safe) and export to a cumulative CSV.

Built with [NiceGUI](https://nicegui.io/) — the app runs a small local web server and
opens in your browser, but all data stays on your machine.

---

## Features

- **Single-keystroke labelling** — press `0`–`9` (per your config) to assign a label
  and automatically advance to the next entry.
- **Skip** — press the next free digit after your labels (e.g. `5`) or click **Skip**
  to advance without labelling the current entry.
- **Edit-previous** — press **←** (ArrowLeft) to reopen the last entry and relabel it.
- **In-app Help** — a **Help** button opens a modal summarising the shortcuts and how
  labels are saved/recovered.
- **Keyword highlighting** — terms from a keywords file are highlighted in the title
  and abstract, case-insensitively and tolerant of hyphen/space spelling variants
  (e.g. `1,3-D` matches `1,3 D`).
- **Resume across sessions** — on start-up the app jumps to the first *unlabelled*
  entry; already-labelled entries are skipped. The SQLite DB accumulates every
  session's decisions.
- **Lossless export** — the input file is never modified. Export writes every dataset
  column (in original order) plus four label columns to a single CSV.
- **Fully config-driven** — dataset, keywords file, output paths, and the label set
  (names, display text, hotkeys) are all defined in `config.yaml`.

---

## Requirements

- **Python ≥ 3.10**
- Runtime dependencies (installed automatically): `nicegui`, `pyyaml`
- Verified working on `nicegui 3.16` (declared minimum is `>=2.0`)

---

## Installation

```bash
# from the repository root
python -m venv .venv
source .venv/bin/activate           # Windows: .venv\Scripts\activate
pip install -e ".[dev]"             # app + pytest; drop [dev] to skip tests
```

`pip install -e .` installs the package in editable/src-layout mode, so the
`literature-labeller` console script and `python -m literature_labeller.main` both work.

---

## How To Run

### Option A — the real corpus (production use)

1. **Place the source corpus locally.** The full, tab-separated PubMed export
   `data/pubmed_scan_2026_02_02_all_data_filtered.txt` is **gitignored** (it is large)
   and must be present on your machine.

2. **Create the working sample** (once). This draws a reproducible random sample of
   15 000 entries that actually have an abstract (rows with an empty abstract are
   excluded) and writes the tab-separated `data/pubmed_scan_2026_02_02_sample.txt`:

   ```bash
   python scripts/make_sample.py
   ```

3. **Launch the app** (uses `config.yaml` in the repo root by default):

   ```bash
   python -m literature_labeller.main
   # or, equivalently, the installed console script:
   literature-labeller
   ```

   Then open **http://127.0.0.1:8080** in your browser (it does not auto-open).

   Optional flags:

   ```bash
   python -m literature_labeller.main --config path/to/config.yaml --host 127.0.0.1 --port 8080
   ```

### Option B — synthetic data (development / trying it out)

No corpus needed. This generates a small synthetic comma-CSV with realistic pesticide
terms (including hyphen/space variants) so highlighting is exercised end to end:

```bash
python scripts/make_synthetic.py     # writes data/pubmed_sample_with_keywords.csv
```

> **Note:** the synthetic file is a **comma-CSV**, whereas the production sample is
> **tab-separated**. To run the app against the synthetic file you must point
> `dataset_path` at it **and** adjust the reader — see *Data format* below. The default
> `config.yaml` and `data.py` are configured for the real tab-separated corpus.

### Labelling workflow

| Action | Result |
|---|---|
| Press `0`–`4` (or click a label button) | Assigns that label to the current entry and advances |
| Press `5` (or click **Skip**) | Advances **without** labelling — the entry stays unlabelled |
| Press **←** (ArrowLeft) | Reopens the previous entry; its current label is shown and can be overwritten |
| Click **Help** | Opens a modal with the shortcuts and data-safety notes |
| Click **Exit** | Exports the cumulative CSV and shuts the server down |

The Skip hotkey is the first digit not used by a label — with labels `0`–`4` that is `5`.

Your position is remembered via the database — you can Exit and relaunch later and the
app resumes at the first unlabelled entry.

---

## Configuration (`config.yaml`)

```yaml
# Paths are resolved relative to this config file's directory (or may be absolute).
dataset_path: data/pubmed_scan_2026_02_02_sample.txt   # entries to label (TAB-separated)
keywords_path: data/PESTICIDE_TERMS_20260323_with_compound_data.csv  # highlight terms (comma CSV, read-only)
output_csv: data/pubmed_labels.csv                      # cumulative export target
db_path: data/labels.db                                 # SQLite store (source of truth)

# Labels the annotator can assign. `id` doubles as the keyboard shortcut (0–9).
labels:
  - {id: 0, name: negative,      display: Negative}
  - {id: 1, name: human_animal,  display: Human/Animal}
  - {id: 2, name: environmental, display: Environmental}
  - {id: 3, name: foodstuff,     display: Foods and Fluids}
  - {id: 4, name: other,         display: Other}
```

**Validation on start-up:**

- The dataset must contain at least the columns `pmid`, `title`, `abstract`. Any other
  columns are preserved and re-emitted on export.
- The keywords file must contain at least `ID`, `name`, `synonyms`. Synonyms are
  `;`-separated (term names themselves may contain commas).
- Label `id`s must be unique integers in `0–9` (each doubles as a hotkey).

---

## Data format

| File | Delimiter | Notes |
|---|---|---|
| Dataset (`dataset_path`) | **Tab** | Real corpus is tab-separated despite the `.txt` name; abstracts may be quoted because they contain literal quotes. |
| Keywords (`keywords_path`) | **Comma** | Read-only reference of pesticide terms + `;`-separated synonyms. |
| Output (`output_csv`) | Comma | Standard CSV export. |

`data.py` reads the dataset with `delimiter="\t"` and the keywords file with
`delimiter=","`. To use a comma-separated dataset (e.g. the synthetic file), change the
dataset delimiter in `load_dataset` accordingly.

---

## Output

The export (`output_csv`) contains **every dataset row** with the original columns
preserved in order, plus four appended label columns. Rows that have not been labelled
have blank label columns.

| Appended column | Example |
|---|---|
| `label_id` | `2` |
| `label_name` | `environmental` |
| `timestamp` | `2026-08-26;10:23` |
| `session` | `2026-08-26T10:21:07` |

The **SQLite database (`db_path`) is the source of truth** — it stores one (latest)
label per `pmid` and accumulates across all sessions. The CSV is a snapshot regenerated
on each Exit; deleting it is harmless. The input dataset file is never written to.

---

## Data safety, correcting mistakes & recovery

**Every label is saved instantly.** Each keypress commits the decision to `labels.db`
immediately (one atomic SQLite commit per label). There is no unsaved buffer.

**If the app crashes or is closed unexpectedly:** nothing is lost. On the next launch
the app reopens `labels.db` and resumes at the first *unlabelled* entry. The only thing
a crash skips is the CSV export (written on Exit) — but that is just a regenerable
snapshot of the database; press Exit in a later session to rebuild it.

**To correct a wrong label:** press **←** to reopen the entry (it shows its current
label), then press the correct number key. Labels are *last-decision-wins*, so the new
one overwrites the old. Notes on the current behaviour:

- There is **no dedicated one-key undo**, and **no way to blank a label back to empty**
  via the UI — you replace one label with another.
- The database keeps only the **latest** label per `pmid` (no per-decision history).
- **Skip** (`5`) advances without labelling, so a skipped entry simply stays unlabelled
  and will reappear as an unlabelled entry on the next run.

> Practical takeaway: treat `labels.db` as precious (back it up periodically); treat
> `pubmed_labels.csv` as disposable output.

---

## Highlighting

- Terms shorter than 3 characters are ignored (too noisy).
- Matching is **case-insensitive** and treats runs of hyphens/spaces as
  interchangeable, so chemical-name spelling variants still match.
- Matches must not be flanked by alphanumerics, so `DDT` will not highlight inside
  `muDDTy`.

---

## Testing

```bash
pytest            # 18 unit tests over config/data/highlight/store
```

The suite covers config validation, TSV/CSV reading and column checks, keyword-term
extraction, highlighting behaviour, SQLite upsert/overwrite, cumulative export, and
column preservation.

---

## Project structure

```
literature_labeler/
├── config.yaml                 # runtime configuration
├── pyproject.toml              # package metadata + deps (src-layout)
├── requirements.txt            # runtime deps mirror
├── data/                       # datasets (large files gitignored)
├── scripts/
│   ├── make_sample.py          # sample 15k abstract-bearing rows from the real corpus
│   └── make_synthetic.py       # generate a small synthetic dev dataset
├── src/literature_labeller/
│   ├── config.py               # load/validate config.yaml -> Config
│   ├── data.py                 # read dataset (TSV) + keyword terms (CSV); verify columns
│   ├── highlight.py            # Highlighter: regex highlight of keyword terms
│   ├── store.py                # LabelStore: SQLite persistence + CSV export
│   ├── app.py                  # LabellerUI: NiceGUI page, key bindings, edit-previous
│   └── main.py                 # entry point: wires config -> data -> store -> UI
└── tests/                      # test_data.py, test_highlight.py, test_store.py
```

---

## Notes & limitations

- The app serves on `127.0.0.1` (localhost) only; it is a single-user local tool.
- `make_sample.py` uses a fixed random seed, so the sample is reproducible.
- Large corpora and generated data (`*.db`, sample/label CSVs) are gitignored; only the
  pesticide-terms reference CSV is tracked.
