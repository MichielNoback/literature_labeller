# Specifications

## Feature: Quick Lookup

Let the annotator select a word or phrase in the title/abstract and get an
instant reference card in a modal:

1. If the selection matches a **pesticide term** (from the keywords file), show
   its details from the static file, with a linkout to the BCPC Compendium.
2. Otherwise, show a **Wikipedia** summary if one exists.

Status: **implemented and verified** (2026-08-26). Unit tests in `tests/test_lookup.py`;
both paths verified live in a browser (keyword → Compendium card, plain word → Wikipedia card).

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
2. **Keyword index hit?** → render the compound card (§4).
3. Else if `wikipedia_lookup` enabled → fetch + render the Wikipedia card (§5).
4. Else → "‘X’ is not a known pesticide term."

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

### 4. Keyword path (local, no network)

- **Index:** built once at startup from the keyword records. Every `name` and every
  `;`-split synonym is normalized and mapped to its full record.
- **Normalization** reuses the highlighter rule: lowercase, and collapse runs of
  `[-\s]+` (hyphens/spaces) to a single space, so `1,3-dichloropropene` ≡ `1,3 dichloropropene`.
- **Card contents** (omit blank fields): name (bold), synonyms, Formula, Activity /
  Primary_activities, Compound_groups, IUPAC name, CAS Reg No, Notes (truncated with a
  "show more"), and a prominent link **"View on BCPC Compendium ↗"** =
  `compendium_base_url` + record `url`, opened in a new tab. (`url` is already
  URL-encoded in the file, e.g. `1,3-dichloropropene.html`; 1833/1863 rows have one.)
- **Edge cases:** record with empty `url` → show the card without the linkout. If a
  synonym maps to two different records (rare), keep the first and note it internally.

### 5. Wikipedia path (remote fallback)

- **Primary call:** `GET https://{lang}.wikipedia.org/api/rest_v1/page/summary/{title}`
  → JSON: `title`, `extract`, `content_urls.desktop.page`, optional `thumbnail.source`.
- **Fallback** when the primary 404s or returns `type == "disambiguation"`: search via
  `GET https://{lang}.wikipedia.org/w/api.php?action=query&list=search&srsearch={q}&format=json`,
  take the top hit's title, then fetch its summary.
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
- **Cache:** in-memory `dict` keyed by `(lang, normalized query)` for the session, to
  avoid refetching the same term.
- **Text safety:** external text is rendered via `ui.markdown`/`ui.label` (escaped), never
  injected as raw HTML.

### 6. Code structure

| File | Change |
|---|---|
| `data.py` | Add `load_keyword_records()` returning full row dicts (reuses `_read_csv`). Existing `load_keyword_terms()` unchanged. |
| `lookup.py` (new) | `CompoundIndex` (build/normalize/`get`) and `wikipedia_summary(query, lang, *, timeout)` returning a small typed result (found/not-found/error). Network code isolated + mockable. |
| `config.py` | `LookupConfig` dataclass + parsing of the optional `lookup:` block. |
| `main.py` | Build `CompoundIndex`, pass it + `LookupConfig` into `LabellerUI`. |
| `app.py` | Header **🔍 Look up** button; `q` hotkey branch; async `quick_lookup()` (read selection → dispatch → render modal); modal renderers for both card types. |

### 7. Testing

- **CompoundIndex** (pure, fast): exact name hit; synonym hit; hyphen/space variant hit;
  punctuation-trimmed hit; miss; record with empty `url`.
- **Wikipedia parser** (mocked HTTP — no real network in tests): summary success;
  primary-404 → search fallback → success; search returns nothing → not-found; timeout /
  URLError → error result. The `urlopen` call is injected/patched so tests are offline.
- Existing 18 tests must stay green.

### 8. Out of scope (possible later)

- Auto-popup-on-selection UX; multi-language Wikipedia switching in-UI; caching Wikipedia
  results to disk; showing multiple disambiguation candidates; lookups from arbitrary
  external chemistry databases (PubChem, etc.).

### 9. Resolved

- Hotkey letter: **`q`**.
- Notes field: **truncate to ~300 chars with a "show more" expansion**.
- Contact: **generic by default** (repo URL), overridable via `lookup.contact_email`.
