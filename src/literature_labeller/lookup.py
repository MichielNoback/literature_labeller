"""Quick Lookup support: local pesticide-term index and Wikipedia fallback."""

from __future__ import annotations

import ast
import json
import re
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from typing import Callable

# Collapse runs of hyphens/whitespace to a single space, matching the highlighter's
# tolerance so "1,3-dichloropropene" and "1,3 dichloropropene" normalize identically.
_WS_HYPHEN = re.compile(r"[-\s]+")

# Characters trimmed from the ends of a raw selection (quotes + sentence punctuation).
# Chemical names keep interior commas/parentheses; only the ends are cleaned.
_TRIM_CHARS = " \t\r\n\"'“”‘’.,;:!?"


# Several compendium columns store a Python collection literal rather than plain text,
# e.g. Compound_groups = "{'alkyl halide', 'fumigant'}".
_COLLECTION_REPR = re.compile(r"^[\{\[\(].*[\}\]\)]$", re.DOTALL)


def format_field(value: object) -> str:
    """Render a compendium field for display, unwrapping Python collection reprs.

    Roughly 93% of ``Compound_groups`` and ``Primary_activities`` values are stored as a
    literal ``set`` repr; show their members as a comma-separated list instead. Sets are
    sorted (a set repr has no meaningful order, and Python's is not stable across runs);
    anything that does not parse is shown unchanged.
    """
    text = "" if value is None else str(value).strip()
    if not _COLLECTION_REPR.match(text):
        return text
    try:
        parsed = ast.literal_eval(text)
    except (ValueError, SyntaxError):
        return text  # looked like a literal but is not one
    if isinstance(parsed, (set, frozenset)):
        members = sorted(str(m).strip() for m in parsed)
    elif isinstance(parsed, (list, tuple)):
        members = [str(m).strip() for m in parsed]
    else:
        return text  # a dict or scalar: not a member list
    return ", ".join(m for m in members if m)


def normalize_term(text: str) -> str:
    """Normalize a term for indexing/matching: lowercased, hyphen/space-folded."""
    return _WS_HYPHEN.sub(" ", (text or "").strip().lower()).strip()


def clean_selection(text: str) -> str:
    """Trim surrounding whitespace/quotes/sentence punctuation from a raw selection."""
    return (text or "").strip().strip(_TRIM_CHARS).strip()


class CompoundIndex:
    """Maps normalized pesticide names + synonyms to their full keyword record."""

    def __init__(self, records: list[dict[str, str]]):
        self._by_term: dict[str, dict[str, str]] = {}
        for rec in records:
            # A record is reachable by its name and by each `;`-separated synonym.
            candidates = [rec.get("name", "")]
            candidates.extend((rec.get("synonyms") or "").split(";"))
            for candidate in candidates:
                key = normalize_term(candidate)
                # First record wins on the rare synonym collision.
                if key and key not in self._by_term:
                    self._by_term[key] = rec

    def __len__(self) -> int:
        return len(self._by_term)

    def get(self, text: str) -> dict[str, str] | None:
        """Return the record for a selected word/phrase, or None if it is not a term."""
        return self._by_term.get(normalize_term(clean_selection(text)))


def compendium_link(record: dict[str, str], base_url: str) -> str | None:
    """Build the BCPC Compendium URL for a record (``base_url`` + its ``url``), or None."""
    url = (record.get("url") or "").strip()
    if not url:
        return None
    return base_url + url


# --- Wikipedia fallback ----------------------------------------------------

USER_AGENT_TEMPLATE = "literature-labeller/0.1 (+{contact})"


class HttpError(Exception):
    """HTTP status error from a lookup request; carries the status code."""

    def __init__(self, status: int):
        super().__init__(f"HTTP {status}")
        self.status = status


class NetworkError(Exception):
    """Network-level failure (timeout, DNS, connection refused, bad JSON)."""


@dataclass
class WikiResult:
    """Outcome of a Wikipedia lookup: status is 'found', 'not_found', or 'error'."""

    status: str
    title: str = ""
    extract: str = ""
    url: str = ""
    thumbnail: str = ""
    message: str = ""


# A JSON fetcher: takes a URL, returns parsed JSON, or raises HttpError/NetworkError.
Fetcher = Callable[[str], dict]


def _http_get_json(url: str, contact: str, timeout: float) -> dict:
    """Default fetcher: GET ``url`` with a polite User-Agent and parse JSON."""
    req = urllib.request.Request(
        url, headers={"User-Agent": USER_AGENT_TEMPLATE.format(contact=contact)}
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        raise HttpError(exc.code) from exc
    except (urllib.error.URLError, TimeoutError, ValueError, OSError) as exc:
        raise NetworkError(str(exc)) from exc


def _summary_url(lang: str, title: str) -> str:
    quoted = urllib.parse.quote(title.replace(" ", "_"), safe="")
    return f"https://{lang}.wikipedia.org/api/rest_v1/page/summary/{quoted}"


def _search_url(lang: str, query: str) -> str:
    params = urllib.parse.urlencode(
        {"action": "query", "list": "search", "srsearch": query, "srlimit": 1, "format": "json"}
    )
    return f"https://{lang}.wikipedia.org/w/api.php?{params}"


def _is_relevant(query: str, data: dict) -> bool:
    """Is a *search-fallback* article actually about ``query``?

    An exact-title hit is authoritative (Wikipedia resolves redirects server-side),
    but the top search hit for an obscure compound is often a list or chemical-class
    page that merely mentions it — or nothing related at all. Require the query to
    appear in the article's title or lead paragraph before accepting it.
    """
    q = normalize_term(query)
    if not q:
        return False
    return q in normalize_term(f"{data.get('title', '')} {data.get('extract', '')}")


def _from_summary(data: dict) -> WikiResult:
    return WikiResult(
        status="found",
        title=data.get("title", ""),
        extract=data.get("extract", ""),
        url=(data.get("content_urls", {}).get("desktop", {}) or {}).get("page", ""),
        thumbnail=(data.get("thumbnail") or {}).get("source", ""),
    )


def wikipedia_summary(
    query: str,
    *,
    lang: str = "en",
    contact: str = "",
    timeout: float = 5.0,
    fetcher: Fetcher | None = None,
) -> WikiResult:
    """Look up ``query`` on Wikipedia: try the exact title, then a search fallback.

    Network access is confined to ``fetcher`` (injectable for tests). Returns a
    ``WikiResult`` and never raises for expected miss/network conditions.
    """
    get: Fetcher = fetcher or (lambda url: _http_get_json(url, contact, timeout))
    q = clean_selection(query)
    if not q:
        return WikiResult("not_found", message="Empty selection.")

    # 1. Try the title directly.
    try:
        data = get(_summary_url(lang, q))
        if data.get("type") != "disambiguation":
            return _from_summary(data)
    except HttpError as exc:
        if exc.status != 404:
            return WikiResult("error", message=f"Wikipedia lookup failed (HTTP {exc.status}).")
    except NetworkError:
        return WikiResult("error", message="Wikipedia lookup unavailable (network error).")

    # 2. Fall back to full-text search for the best-matching title.
    try:
        search = get(_search_url(lang, q))
    except (HttpError, NetworkError):
        return WikiResult("error", message="Wikipedia lookup unavailable (network error).")

    hits = (search.get("query", {}) or {}).get("search", [])
    if not hits:
        return WikiResult("not_found", message=f"No Wikipedia article found for {q!r}.")

    try:
        data = get(_summary_url(lang, hits[0]["title"]))
    except (HttpError, NetworkError):
        return WikiResult("error", message="Wikipedia lookup unavailable (network error).")

    if data.get("type") == "disambiguation":
        return WikiResult("not_found", message=f"No specific Wikipedia article for {q!r}.")
    if not _is_relevant(q, data):
        # The best search hit is off-topic; reporting nothing beats reporting the wrong compound.
        return WikiResult("not_found", message=f"No Wikipedia article found for {q!r}.")
    return _from_summary(data)


# --- Lookup orchestration --------------------------------------------------

# Session cache of Wikipedia results, keyed by (lang, normalized query).
WikiCache = dict[tuple[str, str], WikiResult]


def _query_candidates(selection: str, record: dict[str, str] | None) -> list[str]:
    """Ordered, de-duplicated queries: canonical compound name first, then the selection."""
    candidates: list[str] = []
    seen: set[str] = set()
    for text in ((record or {}).get("name", ""), selection):
        cleaned = clean_selection(text)
        key = normalize_term(cleaned)
        # A selection that already *is* the canonical name yields a single query.
        if key and key not in seen:
            seen.add(key)
            candidates.append(cleaned)
    return candidates


def resolve_summary(
    selection: str,
    record: dict[str, str] | None = None,
    *,
    lang: str = "en",
    contact: str = "",
    timeout: float = 5.0,
    fetcher: Fetcher | None = None,
    cache: WikiCache | None = None,
) -> WikiResult:
    """Find the best Wikipedia article for a selection, using its compound record.

    When the selection is a known pesticide term, its canonical ``name`` is queried
    first — a selection is often a synonym, which makes a poorer query — falling back
    to the raw selection. Outcomes are memoized in the caller-owned ``cache``.
    """
    result = WikiResult(
        "not_found", message=f"No Wikipedia article found for {clean_selection(selection)!r}."
    )
    for query in _query_candidates(selection, record):
        key = (lang, normalize_term(query))
        if cache is not None and key in cache:
            result = cache[key]
        else:
            result = wikipedia_summary(
                query, lang=lang, contact=contact, timeout=timeout, fetcher=fetcher
            )
            # Errors are transient, so only definitive outcomes are memoized.
            if cache is not None and result.status != "error":
                cache[key] = result
        # A hit ends the search; a network error stops it (never retry a failing host).
        if result.status in ("found", "error"):
            return result
    return result
