"""Case-insensitive keyword highlighting with hyphen/space spelling tolerance."""

from __future__ import annotations

import html
import re

# Minimum term length to highlight; shorter terms (single letters, "3") are too noisy.
MIN_TERM_LENGTH = 3

# A match may not be flanked by alphanumerics, so "DDT" does not fire inside "muDDTy".
_BOUNDARY_LEFT = r"(?<![A-Za-z0-9])"
_BOUNDARY_RIGHT = r"(?![A-Za-z0-9])"


def _term_pattern(term: str) -> str:
    """Escape a term so hyphens and spaces become interchangeable ("1,3-D" ~ "1,3 D")."""
    parts = [re.escape(p) for p in re.split(r"[-\s]+", term) if p]
    return r"[-\s]+".join(parts)


class Highlighter:
    """Compiles a keyword set into one regex and wraps matches in ``<mark>`` spans."""

    def __init__(self, terms: list[str], min_length: int = MIN_TERM_LENGTH):
        # Longest terms first so the alternation prefers the most specific match.
        usable = sorted(
            {t for t in terms if len(t) >= min_length},
            key=len,
            reverse=True,
        )
        self._pattern: re.Pattern[str] | None = None
        if usable:
            alternation = "|".join(_term_pattern(t) for t in usable)
            self._pattern = re.compile(
                f"{_BOUNDARY_LEFT}(?:{alternation}){_BOUNDARY_RIGHT}",
                re.IGNORECASE,
            )

    def highlight(self, text: str | None) -> str:
        """Return HTML-escaped ``text`` with keyword matches wrapped in ``<mark>``."""
        if not text:
            return ""
        if self._pattern is None:
            return html.escape(text)

        out: list[str] = []
        last = 0
        for match in self._pattern.finditer(text):
            out.append(html.escape(text[last : match.start()]))
            out.append(f"<mark>{html.escape(match.group(0))}</mark>")
            last = match.end()
        out.append(html.escape(text[last:]))
        return "".join(out)
