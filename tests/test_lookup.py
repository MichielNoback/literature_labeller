from literature_labeller.lookup import (
    CompoundIndex,
    HttpError,
    NetworkError,
    clean_selection,
    compendium_link,
    normalize_term,
    resolve_summary,
    wikipedia_summary,
)

RECORDS = [
    {
        "ID": "1",
        "name": "1,3-D",
        "synonyms": "1,3-D;1,3-dichloropropene",
        "url": "1,3-dichloropropene.html",
        "Formula": "C3H4Cl2",
    },
    {
        "ID": "2",
        "name": "Glyphosate",
        "synonyms": "",
        "url": "glyphosate.html",
        "Formula": "C3H8NO5P",
    },
    {
        "ID": "3",
        "name": "NoLinkCompound",
        "synonyms": "",
        "url": "",  # record without a linkout
    },
]


def test_normalize_folds_hyphen_and_space_and_case():
    assert normalize_term("1,3-Dichloropropene") == "1,3 dichloropropene"
    assert normalize_term("1,3 dichloropropene") == "1,3 dichloropropene"


def test_clean_selection_trims_punctuation_but_keeps_interior():
    assert clean_selection("  glyphosate.  ") == "glyphosate"
    assert clean_selection('"1,3-D",') == "1,3-D"


def test_index_hit_by_name():
    idx = CompoundIndex(RECORDS)
    assert idx.get("Glyphosate")["ID"] == "2"


def test_index_hit_by_synonym():
    idx = CompoundIndex(RECORDS)
    assert idx.get("1,3-dichloropropene")["ID"] == "1"


def test_index_hit_by_spelling_variant_and_punctuation():
    idx = CompoundIndex(RECORDS)
    # hyphen->space variant, trailing period, mixed case all resolve to the same record.
    assert idx.get("1,3 Dichloropropene.")["ID"] == "1"


def test_index_miss_returns_none():
    idx = CompoundIndex(RECORDS)
    assert idx.get("aspirin") is None
    assert idx.get("") is None


def test_compendium_link_builds_and_handles_missing_url():
    base = "http://www.bcpcpesticidecompendium.org/"
    idx = CompoundIndex(RECORDS)
    assert compendium_link(idx.get("Glyphosate"), base) == base + "glyphosate.html"
    assert compendium_link(idx.get("NoLinkCompound"), base) is None


# --- Wikipedia (all offline: the fetcher is injected) ----------------------

def _summary(title, extract="An extract.", type_="standard"):
    return {
        "type": type_,
        "title": title,
        "extract": extract,
        "content_urls": {"desktop": {"page": f"https://en.wikipedia.org/wiki/{title}"}},
        "thumbnail": {"source": "https://img/thumb.jpg"},
    }


def test_wikipedia_direct_hit():
    fetcher = lambda url: _summary("Glyphosate")  # noqa: E731
    r = wikipedia_summary("glyphosate", fetcher=fetcher)
    assert r.status == "found"
    assert r.title == "Glyphosate"
    assert r.url.endswith("/Glyphosate")
    assert r.thumbnail == "https://img/thumb.jpg"


def test_wikipedia_404_then_search_fallback():
    calls = []

    def fetcher(url):
        calls.append(url)
        if "/page/summary/" in url and "Weedkiller" not in url:
            raise HttpError(404)  # direct title miss
        if "list=search" in url:
            return {"query": {"search": [{"title": "Weedkiller"}]}}
        # Lead paragraph names the query, so the relevance guard accepts it.
        return _summary("Weedkiller", "A weed killer is a type of herbicide.")

    r = wikipedia_summary("weed killer", fetcher=fetcher)
    assert r.status == "found"
    assert r.title == "Weedkiller"
    assert any("list=search" in u for u in calls)  # search fallback was used


def test_wikipedia_not_found_when_search_empty():
    def fetcher(url):
        if "/page/summary/" in url:
            raise HttpError(404)
        return {"query": {"search": []}}

    r = wikipedia_summary("zzxqnothing", fetcher=fetcher)
    assert r.status == "not_found"


def test_wikipedia_disambiguation_falls_through_to_not_found():
    def fetcher(url):
        if "/page/summary/" in url:
            return _summary("Mercury", type_="disambiguation")
        return {"query": {"search": []}}

    r = wikipedia_summary("mercury", fetcher=fetcher)
    assert r.status == "not_found"


def test_wikipedia_network_error():
    def fetcher(url):
        raise NetworkError("timed out")

    r = wikipedia_summary("glyphosate", fetcher=fetcher)
    assert r.status == "error"
    assert "network" in r.message.lower()


def test_wikipedia_empty_query():
    r = wikipedia_summary("   ", fetcher=lambda url: {})
    assert r.status == "not_found"


# --- resolve_summary: canonical-name resolution + caching (offline) --------

def test_resolve_prefers_canonical_name_over_selection():
    calls = []

    def fetcher(url):
        calls.append(url)
        return _summary("Glyphosate")

    r = resolve_summary("Roundup", {"name": "Glyphosate"}, fetcher=fetcher)
    assert r.status == "found"
    assert len(calls) == 1
    assert "Glyphosate" in calls[0]  # the canonical name, not the selected synonym


def test_resolve_falls_back_to_raw_selection():
    def fetcher(url):
        if "list=search" in url:
            return {"query": {"search": []}}  # no search hit for either query
        if "Obscurine" in url:
            raise HttpError(404)  # the canonical name has no article
        return _summary("Roundup")  # ...but the selection does

    r = resolve_summary("Roundup", {"name": "Obscurine"}, fetcher=fetcher)
    assert r.status == "found"
    assert r.title == "Roundup"


def test_resolve_not_found_when_both_queries_miss():
    def fetcher(url):
        if "list=search" in url:
            return {"query": {"search": []}}
        raise HttpError(404)

    r = resolve_summary("Roundup", {"name": "Obscurine"}, fetcher=fetcher)
    assert r.status == "not_found"


def test_resolve_stops_on_network_error():
    calls = []

    def fetcher(url):
        calls.append(url)
        raise NetworkError("timed out")

    r = resolve_summary("Roundup", {"name": "Glyphosate"}, fetcher=fetcher)
    assert r.status == "error"
    assert len(calls) == 1  # the second query is never attempted


def test_resolve_without_record_queries_selection_only():
    calls = []

    def fetcher(url):
        calls.append(url)
        return _summary("Mitochondrion")

    r = resolve_summary("mitochondria", None, fetcher=fetcher)
    assert r.status == "found"
    assert len(calls) == 1


def test_resolve_serves_repeat_lookups_from_cache():
    calls = []
    cache = {}

    def fetcher(url):
        calls.append(url)
        return _summary("Glyphosate")

    first = resolve_summary("glyphosate", None, fetcher=fetcher, cache=cache)
    second = resolve_summary("Glyphosate.", None, fetcher=fetcher, cache=cache)
    assert first.title == second.title == "Glyphosate"
    assert len(calls) == 1  # normalized key: the repeat is served from cache


def test_resolve_does_not_cache_errors():
    cache = {}

    def fetcher(url):
        raise NetworkError("timed out")

    resolve_summary("glyphosate", None, fetcher=fetcher, cache=cache)
    assert cache == {}  # transient failures must not stick for the session


# --- relevance guard on the search fallback --------------------------------

def test_search_fallback_rejects_off_topic_article():
    def fetcher(url):
        if "list=search" in url:
            return {"query": {"search": [{"title": "List of fungicides"}]}}
        if "List_of_fungicides" in url:
            # A list page whose lead never names the compound: a wrong answer.
            return _summary("List of fungicides", "This is a list of fungicides.")
        raise HttpError(404)

    r = wikipedia_summary("bentaluron", fetcher=fetcher)
    assert r.status == "not_found"


def test_search_fallback_accepts_article_naming_the_query():
    def fetcher(url):
        if "list=search" in url:
            return {"query": {"search": [{"title": "Mercury(II) chloride"}]}}
        if "Mercury" in url:
            return _summary(
                "Mercury(II) chloride", "Mercury(II) chloride, also known as mercuric chloride..."
            )
        raise HttpError(404)

    r = wikipedia_summary("mercuric chloride", fetcher=fetcher)
    assert r.status == "found"
    assert r.title == "Mercury(II) chloride"
