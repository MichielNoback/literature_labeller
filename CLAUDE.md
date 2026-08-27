# Literature Labeller

Config-driven dashboard for manually labelling PubMed publications one at a time,
across many sessions. The corpus is pesticide-related literature; each abstract is
assigned one of five classes by keypress. Built with NiceGUI; labels persist to
SQLite and export to CSV.

## Resume the session

- **User-facing guide (start here):** `README.md` — features, How To Run, config, data
  safety/recovery, and the Quick Lookup feature.
- **Quick Lookup design + rationale:** `SPECIFICATIONS.md`.
- **Original staged requirements:** `INSTRUCTIONS.md`.
- **Early design/data findings:** the plan file `~/.claude/plans/dapper-honking-wadler.md`.
- The app is **feature-complete for the core workflow, fully tested, verified live, and
  pushed** to `origin/main`. See Open items for the few remaining decisions.
- Quick Lookup was reworked to be **Wikipedia-first** on 2026-08-27; the rationale, the
  decisions taken and their cost are recorded in `SPECIFICATIONS.md` §10 — read that before
  changing lookup behaviour, rather than re-deriving it from the code.

## Architecture

Package under `src/literature_labeller/` (installable; `pyproject.toml`, src-layout).
Dependencies: NiceGUI + PyYAML only (stdlib `urllib` for the Wikipedia lookup — no pandas,
no requests/httpx).

| File | Role |
|---|---|
| `config.py` | Load/validate `config.yaml` → `Config` (+ optional `lookup:` block → `LookupConfig`) |
| `data.py` | Read dataset (tab-sep) + keyword terms (comma-sep) via `csv.DictReader`; `load_keyword_records()` for full rows; verify columns; split synonyms on `;` |
| `highlight.py` | `Highlighter` — regex-highlight keyword terms in title/abstract |
| `lookup.py` | Quick Lookup: `CompoundIndex` (term→record), `wikipedia_summary()` (stdlib urllib, injectable fetcher, relevance-guarded search fallback), `resolve_summary()` (canonical-name-then-selection + session cache) |
| `store.py` | `LabelStore` — SQLite persistence + cumulative CSV export |
| `app.py` | `LabellerUI` — NiceGUI page, key bindings, edit-previous, Skip, arrow-nav, Quick Lookup, Help modal |
| `main.py` | Entry point: wires config→data→highlighter→CompoundIndex→store→UI, `ui.run` |
| `scripts/make_sample.py` | Stage 1: sample 15k abstract-bearing rows from the real tab-separated corpus |
| `scripts/make_synthetic.py` | Generate a small synthetic CSV for dev/testing |
| `tests/` | `test_data.py`, `test_highlight.py`, `test_store.py`, `test_lookup.py` (46 tests) |

### Run / test

A local `.venv` (gitignored) already exists with `pytest`, `pyyaml`, `nicegui` 3.16, and
`playwright` (+ Chromium). Call its binaries directly — no activation needed (and global
settings allow `Bash(.venv/bin/python:*)`):

```bash
.venv/bin/python scripts/make_sample.py        # build the real 15k TSV sample (once)
.venv/bin/python -m literature_labeller.main    # serves http://127.0.0.1:8080
.venv/bin/python -m pytest -q                   # 46 tests
# console script also works after `pip install -e .`:  literature-labeller
```

### Keyboard / UI

Keys `0`–`4` label & advance · `5` Skip (advance, no label) · `←` back · `→` forward ·
select text + `q` (or 🔍 Look up) for Quick Lookup · Help button for the in-app guide ·
Exit exports the CSV.

## Key decisions

- **NiceGUI** — native `ui.keyboard` gives single-keystroke labelling and arrow nav with no
  custom JS; async handlers support the selection-read for Quick Lookup.
- **SQLite** written per decision (crash-safe), exported to CSV on Exit. Input file never
  written to. DB is the source of truth; the CSV is a regenerable snapshot.
- **Data format standardized on TSV.** Corpus is tab-separated despite the `.txt` name and
  sparsely quoted (abstracts wrapped in `"` when they contain a literal quote). Keywords file
  is comma-separated with `;`-separated synonyms (term names contain commas). Empty-abstract
  rows (32,558 of 438,682) are excluded at sampling time.
- **Quick Lookup is Wikipedia-first** (revised 2026-08-27, see `SPECIFICATIONS.md` §10).
  The card body is always a Wikipedia summary; `CompoundIndex` no longer picks the card type,
  it resolves the *query* — a hit supplies the canonical `name` (selections are often synonyms:
  `DDT`→`clofenotane`), with the raw selection as fallback. A pesticide term additionally gets
  a **Pesticide term** badge, a collapsed **Compendium data** expansion and the BCPC link.
  Fetched off the event loop via `asyncio.to_thread`; memoized in a session cache
  (`found`/`not_found` only — never `error`). `lookup.wikipedia_lookup: false` restores the
  fully-offline static card.
- **Relevance guard on the search fallback.** An exact-title hit is authoritative (Wikipedia
  resolves redirects server-side) and is never guarded; a blind top-search-hit is accepted only
  if the query appears in that article's title or extract. Measured on 25 random compendium
  names this killed 8 wrong answers (*List of fungicides*, *Ospedale di San Paolo*) with zero
  loss of genuine matches. Without it ~1 in 3 compound lookups was confidently wrong.
- **Highlighting** is currently fully case-insensitive (`re.IGNORECASE`, `MIN_TERM_LENGTH=3`).
  Note: this diverges from an earlier plan note about case-sensitive short acronyms — tracked
  in Open items.

## Current status

- Repo bootstrapped; large corpora gitignored (only the 1.1 MB pesticide-terms CSV tracked).
  Remote `origin` = github.com/MichielNoback/literature_labeller.
- **46/46 tests pass. `main` == `origin/main` at `8dba69c` — all code and docs pushed.**
  The 2026-08-27 Wikipedia-first work landed as `e79eeb0` (core), `d8b6e35` (docs),
  `50326a8` (compendium field formatting) and `8dba69c` (status). `main` is now the only
  local branch — the merged `wikipedia-first-lookup` and the stale `literature-labeller`
  (an artefact of the original cloud session) were both deleted.
- Only pending change: this `CLAUDE.md` session note itself, left uncommitted deliberately.
- Verified live (Playwright, nicegui 3.16) against a 4-row scratch dataset with its own
  db/config, so the real `data/labels.db` was never written to:
  - Quick Lookup: `glyphosate` → both badges + Wikipedia body + collapsed Compendium data +
    BCPC link; `1,3-dichloropropene` (a synonym) → correctly resolved via canonical `1,3-D`;
    `bentaluron` → uniform "not found" with the expansion still present; `mitochondria` →
    Wikipedia only, no badge/expansion; repeat lookup served from cache in 0.11 s;
    `wikipedia_lookup: false` → static compendium card / "not a known pesticide term".
  - No keyboard regression: `2` labels + advances (one DB row written), `5` Skip and `→`
    advance without writing, `←` walks back and shows the existing label.
  - Earlier session verified the full 15k sample end to end incl. Exit → CSV export.

## Open items / next steps

1. **Highlighter case-sensitivity divergence.** `highlight.py` is fully case-insensitive;
   the plan's "short acronyms (≤4 chars) case-sensitive" idea is NOT implemented. Decide:
   implement it (+ tests) or drop the note. (Satisfies `INSTRUCTIONS.md` as-is.)
2. **`→` vs `5` Skip redundancy.** Both advance without labelling. Fine as-is (arrow = navigate,
   Skip = deliberately pass), but could differentiate later (e.g. record skips in the DB).
3. **INSTRUCTIONS.md Stage 3** still names the historical `data/pubmed_sample_with_keywords.cs`
   path (superseded by the TSV decision). Cosmetic — leave or annotate.

Resolved 2026-08-27: `lookup.format_field()` unwraps the Python set reprs the source CSV
stores in `Compound_groups`/`Primary_activities` (3568 fields cleaned corpus-wide, 0 mangled;
the 13 IUPAC names that legitimately use braces fall through `ast.literal_eval` untouched);
Quick Lookup made Wikipedia-first for pesticide compounds (canonical-name
query resolution, collapsed Compendium data, session cache, search-fallback relevance guard);
README + SPECIFICATIONS updated to match.
Resolved earlier: TSV reconciliation + empty-abstract exclusion; removed unused
`store.get_prev()`; added Skip + Help modal + forward-arrow nav; added Quick Lookup
(keyword card + Wikipedia); README + SPECIFICATIONS written.
