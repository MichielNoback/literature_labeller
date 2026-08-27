# Specifications

## Feature: Quick Lookup

Let the annotator select a word or phrase in the title/abstract and get an
instant reference card in a modal. The card body is always a **Wikipedia** summary;
a selection that matches a **pesticide term** additionally resolves the query to that
compound's canonical name and carries its compendium details along, collapsed.

Status: **implemented and verified**. Originally shipped 2026-08-26 with two mutually
exclusive card types; **revised 2026-08-27** to be Wikipedia-first (see §10). Unit tests
in `tests/test_lookup.py` (40 total); verified live against the real corpus.

---

### Decisions (agreed)

- **Trigger:** explicit. Select text, then press **`q`** (Quick lookup) **or** click a
  **🔍 Look up** button in the header. No auto-popup.
- **Wikipedia fallback:** enabled by default, **toggleable** via `config.yaml`. Keyword
  lookups are always local; only non-keyword selections make an outbound request.
- **Tests:** included (CompoundIndex matching + Wikipedia parser with mocked HTTP).

---

### 1. UX / interaction

- Selection is read with `ui.run_javascript("window.getSelection().toString()")`.
- The lookup handler is **async** (awaits the JS read and any network call). A new async
  path is added; the existing sync `_on_key` gains a branch for the `q` key that schedules it.
- Result is shown in a **modal** (`ui.dialog`), styled like the existing Help modal, with a
  header badge showing the source: **"Pesticide term"** or **"Wikipedia"**.
- **Guardrails on the selection** (after trimming surrounding whitespace/punctuation):
  - empty → do nothing (optionally a brief `ui.notify`).
  - too long → `> 60` characters or `> 6` whitespace-separated words → modal shows
    "Select a shorter word or phrase."
- The `q` hotkey must not interfere with labelling (digits) or edit-previous (ArrowLeft).

### 2. Dispatch logic

1. Normalize the trimmed selection.
2. Look it up in the keyword index → `record` or `None` (§4). This selects the *query*,
   not the card type.
3. If `wikipedia_lookup` enabled → resolve + render the Wikipedia card (§5), with the
   compendium section attached when `record` is not None.
4. Else (offline mode) → `record` renders the static compendium card; otherwise
   "‘X’ is not a known pesticide term."

### 3. Config additions (`config.yaml`)

```yaml
lookup:
  compendium_base_url: http://www.bcpcpesticidecompendium.org/
  wikipedia_lookup: true
  wikipedia_lang: en
  contact_email: ""      # optional; identifies traffic to Wikipedia (see User-Agent below)
```

- All keys optional with the defaults above, so existing configs keep working.
- `config.py` gains a `LookupConfig` dataclass (defaulted) on `Config`.
- The code default contact is **generic** (the repository URL); `contact_email` only
  overrides it if set. Note `config.yaml` is tracked in git, so leave it blank unless you
  are comfortable publishing the address.

### 4. Keyword path (local: query resolution + secondary display)

- **Index:** built once at startup from the keyword records. Every `name` and every
  `;`-split synonym is normalized and mapped to its full record.
- **Normalization** reuses the highlighter rule: lowercase, and collapse runs of
  `[-\s]+` (hyphens/spaces) to a single space, so `1,3-dichloropropene` ≡ `1,3 dichloropropene`.
- **Primary role: query resolution.** A hit supplies the record's canonical `name` as the
  first Wikipedia query, because the selection is often a synonym and makes a poorer query
  (`DDT` → `clofenotane`, `1,3-dichloropropene` → `1,3-D`). The raw selection is the fallback.
- **Secondary role: display.** The fields (name, synonyms, Formula, Activity /
  Primary_activities, Compound_groups, IUPAC name, CAS Reg No, Notes truncated with a
  "show more") render inside a **collapsed "Compendium data" expansion** beneath the
  Wikipedia body — present on the card whether or not an article was found. The link
  **"View on BCPC Compendium ↗"** = `compendium_base_url` + record `url` stays visible
  outside the expansion. (`url` is already URL-encoded in the file, e.g.
  `1,3-dichloropropene.html`; 1833/1863 rows have one.)
- **Edge cases:** record with empty `url` → show the card without the linkout. If a
  synonym maps to two different records (rare), keep the first and note it internally.

### 5. Wikipedia path (remote fallback)

- **Primary call:** `GET https://{lang}.wikipedia.org/api/rest_v1/page/summary/{title}`
  → JSON: `title`, `extract`, `content_urls.desktop.page`, optional `thumbnail.source`.
- **Fallback** when the primary 404s or returns `type == "disambiguation"`: search via
  `GET https://{lang}.wikipedia.org/w/api.php?action=query&list=search&srsearch={q}&format=json`,
  take the top hit's title, then fetch its summary.
- **Relevance guard on the search hit** (`_is_relevant`): the searched article is accepted
  only if the normalized query occurs in its title or `extract`. An exact-title hit is
  authoritative (Wikipedia resolves redirects server-side) and is **never** guarded; a blind
  top-search-hit is not. Measured on 25 random compendium names, this removed 8 wrong answers
  (*List of fungicides*, *Covered smut (barley)*, *Ospedale di San Paolo*) and kept every
  genuine indirect match (`IR3535` → *Ethyl butylacetylaminopropionate*).
- **Transport:** stdlib `urllib.request` executed in a worker thread via
  `asyncio.to_thread(...)` so the blocking call never stalls NiceGUI's event loop.
  - Timeout: ~5 s. `User-Agent: literature-labeller/0.1 (+<contact>)` per Wikipedia policy,
    where `<contact>` is `lookup.contact_email` if set, else the generic repository URL.
  - **No new dependency** (stdlib only). `httpx` considered and rejected to keep deps minimal.
- **Card contents:** title, first paragraph of `extract`, optional thumbnail image, and
  **"Read on Wikipedia ↗"** link to `content_urls.desktop.page`.
- **Failure modes (explicit):**
  - not found (primary 404 + no search hit) → "No Wikipedia article found for ‘X’."
  - timeout / offline / HTTP error → "Wikipedia lookup unavailable (network error)." —
    keyword lookups remain fully functional.
- **Cache:** in-memory `dict` keyed by `(lang, normalized query)`, owned by `LabellerUI`
  and passed into `resolve_summary`, for the session. `found`/`not_found` are memoized;
  **`error` never is**, so a transient outage does not stick. Now load-bearing: every
  pesticide term reaches the network, and common terms recur constantly across abstracts.
- **Text safety:** external text is rendered via `ui.markdown`/`ui.label` (escaped), never
  injected as raw HTML.

### 6. Code structure

| File | Change |
|---|---|
| `data.py` | Add `load_keyword_records()` returning full row dicts (reuses `_read_csv`). Existing `load_keyword_terms()` unchanged. |
| `lookup.py` | `CompoundIndex` (build/normalize/`get`); `wikipedia_summary()` (one query: exact title → guarded search fallback) returning a typed `WikiResult`; `resolve_summary()` orchestrating canonical-name-then-selection + the session cache. Network code isolated behind the injectable `Fetcher`. |
| `config.py` | `LookupConfig` dataclass + parsing of the optional `lookup:` block. |
| `main.py` | Build `CompoundIndex`, pass it + `LookupConfig` into `LabellerUI`. |
| `app.py` | Header **🔍 Look up** button; `q` hotkey branch; async `quick_lookup()` (read selection → resolve → render modal); `_compound_fields()` shared by the offline card and the collapsed expansion; `_render_lookup_card()` as the single online renderer. |

### 7. Testing

- **CompoundIndex** (pure, fast): exact name hit; synonym hit; hyphen/space variant hit;
  punctuation-trimmed hit; miss; record with empty `url`.
- **Wikipedia parser** (mocked HTTP — no real network in tests): summary success;
  primary-404 → search fallback → success; search returns nothing → not-found; timeout /
  URLError → error result. The `urlopen` call is injected/patched so tests are offline.
- **Relevance guard:** an off-topic search hit is rejected; a hit naming the query is kept.
- **`resolve_summary`:** canonical name queried ahead of the selection; canonical miss falls
  back to the selection; both miss → not-found; a network error stops without a second
  attempt; a repeat lookup issues no request; errors are not cached.
- 40 tests total, all offline.

### 8. Out of scope (possible later)

- Auto-popup-on-selection UX; multi-language Wikipedia switching in-UI; caching Wikipedia
  results to disk; showing multiple disambiguation candidates; lookups from arbitrary
  external chemistry databases (PubChem, etc.).

### 9. Resolved

- Hotkey letter: **`q`**.
- Notes field: **truncate to ~300 chars with a "show more" expansion**.
- Contact: **generic by default** (repo URL), overridable via `lookup.contact_email`.

---

### 10. Revision 2026-08-27 — Wikipedia-first compound cards

**Change.** A pesticide-term hit no longer renders the static compendium card. The card body
is now always the Wikipedia summary; the compendium fields move into a collapsed
**Compendium data** expansion, and the BCPC link stays visible.

**Why.** The static fields answer the wrong question for this task. An annotator classifying
what a paper is *about* is not helped by `C3H8NO5P` or a CAS number; "glyphosate is a
broad-spectrum systemic herbicide" is exactly the context needed. Nothing is lost — the
compendium data is one click away.

**Decisions taken (agreed with the user):**

| Question | Decision |
|---|---|
| Static fields | Kept, in a collapsed expansion. Not deleted. |
| Wikipedia miss on a known term | Same "not found" message as any generic term — no fallback to the static card. The expansion and BCPC link still render, so the card is never empty. |
| Query text | Canonical `name` first, raw selection second. |
| `wikipedia_lookup: false` | Offline behaviour unchanged (static card for terms). |
| Wrong search hits | Guarded (§5) — discovered during verification, not part of the original request. |

**Cost.** Every pesticide-term lookup is now a network request, where previously it was purely
local. The session cache (§5) absorbs the repeats; `wikipedia_lookup: false` remains the fully
offline escape hatch. `README.md`'s privacy note was rewritten accordingly.
