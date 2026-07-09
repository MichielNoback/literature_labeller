from literature_labeller.highlight import Highlighter


def test_case_insensitive_match():
    h = Highlighter(["Atrazine"])
    assert h.highlight("Traces of ATRAZINE found") == "Traces of <mark>ATRAZINE</mark> found"


def test_hyphen_space_variants():
    h = Highlighter(["1,3-dichloropropene"])
    # Hyphen variant.
    assert "<mark>1,3-dichloropropene</mark>" in h.highlight("about 1,3-dichloropropene here")
    # Space variant of the same term.
    assert "<mark>1,3 dichloropropene</mark>" in h.highlight("about 1,3 dichloropropene here")


def test_longest_match_wins():
    h = Highlighter(["chlor", "chlorpyrifos"])
    out = h.highlight("dose of chlorpyrifos")
    assert "<mark>chlorpyrifos</mark>" in out


def test_word_boundary_prevents_substring():
    h = Highlighter(["DDT"])
    # Should not fire inside a larger alphanumeric run.
    assert "<mark>" not in h.highlight("muDDTy water")
    assert "<mark>DDT</mark>" in h.highlight("residual DDT levels")


def test_html_is_escaped():
    h = Highlighter(["atrazine"])
    out = h.highlight("<script> atrazine & co")
    assert "&lt;script&gt;" in out
    assert "&amp;" in out
    assert "<mark>atrazine</mark>" in out


def test_short_terms_ignored():
    h = Highlighter(["D", "3"])  # below MIN_TERM_LENGTH
    assert h.highlight("D and 3") == "D and 3"


def test_empty_and_none():
    h = Highlighter(["atrazine"])
    assert h.highlight("") == ""
    assert h.highlight(None) == ""


def test_no_terms():
    h = Highlighter([])
    assert h.highlight("<b>plain</b>") == "&lt;b&gt;plain&lt;/b&gt;"
