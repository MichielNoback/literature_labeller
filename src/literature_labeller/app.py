"""NiceGUI dashboard: display one PubMed entry at a time and label it."""

from __future__ import annotations

import asyncio

from nicegui import app, ui

from . import lookup
from .config import Config
from .data import Dataset
from .highlight import Highlighter
from .lookup import CompoundIndex
from .store import LabelStore

# Selections longer than this (chars or words) are rejected as not word/phrase lookups.
MAX_LOOKUP_CHARS = 60
MAX_LOOKUP_WORDS = 6
# Compound Notes longer than this are collapsed into a "show more" expansion.
NOTES_PREVIEW_CHARS = 300

MARK_CSS = """
<style>
mark { background: #ffe27a; color: inherit; padding: 0 .1em; border-radius: 3px; }
.dark mark { background: #7a5c00; color: #fff; }
</style>
"""


class LabellerUI:
    """Holds session state and renders the single-entry labelling view."""

    def __init__(
        self,
        config: Config,
        dataset: Dataset,
        highlighter: Highlighter,
        store: LabelStore,
        session: str,
        compound_index: CompoundIndex,
    ):
        self.config = config
        self.dataset = dataset
        self.highlighter = highlighter
        self.store = store
        self.session = session
        self.compound_index = compound_index
        # Wikipedia results memoized for the session (common terms recur constantly).
        self._wiki_cache: lookup.WikiCache = {}
        self.index = self._first_unlabelled()
        # Skip uses the first digit not already claimed by a label (0-4 -> 5).
        self.skip_key = self._first_free_digit()

        # Widgets populated in build().
        self._progress: ui.label | None = None
        self._pmid: ui.label | None = None
        self._title: ui.html | None = None
        self._abstract: ui.html | None = None
        self._status: ui.label | None = None
        self._label_buttons: dict[int, ui.button] = {}
        self._lookup_dialog: ui.dialog | None = None
        self._lookup_body: ui.column | None = None

    # -- navigation state ---------------------------------------------------

    def _first_unlabelled(self) -> int:
        labelled = self.store.labelled_pmids()
        for i, row in enumerate(self.dataset.rows):
            if row.get("pmid", "") not in labelled:
                return i
        return 0  # everything already labelled — start at the top for review

    @property
    def current_row(self) -> dict[str, str]:
        return self.dataset.rows[self.index]

    def _first_free_digit(self) -> int | None:
        """Return the lowest 0-9 digit not used as a label hotkey, for Skip."""
        used = self.config.hotkeys_ids
        for digit in range(10):
            if digit not in used:
                return digit
        return None

    def _goto(self, index: int) -> None:
        self.index = max(0, min(index, len(self.dataset.rows) - 1))
        self._refresh()

    def _advance(self) -> None:
        """Move to the next entry, or just refresh if already at the end."""
        if self.index < len(self.dataset.rows) - 1:
            self._goto(self.index + 1)
        else:
            self._refresh()

    # -- actions ------------------------------------------------------------

    def apply_label(self, label_id: int) -> None:
        label = next((lbl for lbl in self.config.labels if lbl.id == label_id), None)
        if label is None:
            return
        pmid = self.current_row.get("pmid", "")
        self.store.upsert_label(
            pmid=pmid,
            label_id=label.id,
            label_name=label.name,
            session=self.session,
        )
        self._advance()

    def skip_entry(self) -> None:
        """Advance to the next entry without recording a label."""
        self._advance()

    def edit_previous(self) -> None:
        """Left-arrow: reopen the previous entry for re-labelling."""
        self._goto(self.index - 1)

    def move_next(self) -> None:
        """Right-arrow: move forward one entry without labelling."""
        self._goto(self.index + 1)

    # -- quick lookup -------------------------------------------------------

    async def quick_lookup(self) -> None:
        """Read the current text selection and show a reference card for it."""
        raw = await ui.run_javascript(
            "window.getSelection ? window.getSelection().toString() : ''"
        )
        text = lookup.clean_selection(raw or "")
        if not text:
            ui.notify("Select a word or phrase in the text first.", type="info")
            return
        if len(text) > MAX_LOOKUP_CHARS or len(text.split()) > MAX_LOOKUP_WORDS:
            self._render_message("Select a shorter word or phrase.")
            return

        # The local index resolves a selected synonym to its canonical compound name,
        # which makes a far better Wikipedia query. None => not a pesticide term.
        record = self.compound_index.get(text)

        # Offline mode: no outbound call, so show the static compendium data instead.
        if not self.config.lookup.wikipedia_lookup:
            if record is not None:
                self._render_compound(record)
            else:
                self._render_message(f"“{text}” is not a known pesticide term.")
            return

        self._render_loading(text)  # opens the dialog with a spinner
        result = await asyncio.to_thread(
            lookup.resolve_summary,
            text,
            record,
            lang=self.config.lookup.wikipedia_lang,
            contact=self.config.lookup.contact,
            cache=self._wiki_cache,
        )
        self._render_lookup_card(record, result)  # repopulates the already-open dialog

    def _lookup_reset(self):
        """Clear the lookup modal body and return it as a context manager."""
        self._lookup_body.clear()
        return self._lookup_body

    def _render_message(self, message: str) -> None:
        with self._lookup_reset():
            ui.label(message)
        self._lookup_dialog.open()

    def _render_loading(self, text: str) -> None:
        with self._lookup_reset():
            with ui.row().classes("items-center gap-2"):
                ui.spinner(size="sm")
                ui.label(f"Looking up “{text}” on Wikipedia…")
        self._lookup_dialog.open()

    def _compound_fields(self, record: dict) -> None:
        """Render the static compendium fields of a record; blank fields are omitted."""

        def field(label: str, value) -> None:
            text = lookup.format_field(value)
            if text:
                with ui.row().classes("gap-1 items-start"):
                    ui.label(f"{label}:").classes("font-semibold whitespace-nowrap")
                    ui.label(text)

        synonyms = (record.get("synonyms") or "").replace(";", ", ").strip(", ")
        field("Synonyms", synonyms)
        field("Formula", record.get("Formula"))
        field("Activity", record.get("Activity"))
        field("Compound groups", record.get("Compound_groups"))
        field("IUPAC name", record.get("IUPAC name") or record.get("IUPAC Name"))
        field("CAS Reg No", record.get("CAS Reg No"))

        notes = (record.get("Notes") or "").strip()
        if notes and len(notes) <= NOTES_PREVIEW_CHARS:
            field("Notes", notes)
        elif notes:
            with ui.expansion("Notes").classes("w-full"):
                ui.label(notes)

    def _compendium_link(self, record: dict) -> None:
        """Render the BCPC Compendium linkout, for records that have one."""
        link = lookup.compendium_link(record, self.config.lookup.compendium_base_url)
        if link:
            ui.link("View on BCPC Compendium ↗", link, new_tab=True)

    def _render_compound(self, record: dict) -> None:
        """Offline card (Wikipedia disabled): the static compendium data only."""
        with self._lookup_reset():
            ui.badge("Pesticide term").props("color=green")
            ui.label(record.get("name", "")).classes("text-lg font-bold")
            self._compound_fields(record)
            self._compendium_link(record)
        self._lookup_dialog.open()

    def _render_lookup_card(self, record: dict | None, result: lookup.WikiResult) -> None:
        """Wikipedia card; a known pesticide term carries its compendium data along."""
        with self._lookup_reset():
            with ui.row().classes("items-center gap-2"):
                if record is not None:
                    ui.badge("Pesticide term").props("color=green")
                ui.badge("Wikipedia").props("color=blue")

            if result.status == "found":
                ui.label(result.title).classes("text-lg font-bold")
                if result.thumbnail:
                    ui.image(result.thumbnail).classes("max-w-[160px] rounded")
                if result.extract:
                    ui.label(result.extract)
                if result.url:
                    ui.link("Read on Wikipedia ↗", result.url, new_tab=True)
            else:
                # Identical wording whether or not the selection is a pesticide term.
                ui.label(result.message or "No Wikipedia article found.")

            # A pesticide term keeps its compendium data, collapsed under the summary.
            if record is not None:
                ui.separator()
                with ui.expansion("Compendium data").classes("w-full"):
                    ui.label(record.get("name", "")).classes("font-bold")
                    self._compound_fields(record)
                self._compendium_link(record)
        self._lookup_dialog.open()

    def exit_session(self) -> None:
        written = self.store.export_csv(self.dataset, self.config.output_csv)
        self.store.close()
        ui.notify(
            f"Exported {written} labelled entries to {self.config.output_csv.name}. "
            "You can close this tab.",
            type="positive",
            timeout=0,
        )
        app.shutdown()

    # -- rendering ----------------------------------------------------------

    def _help_markdown(self) -> str:
        """Build the Help dialog content from the current label configuration."""
        label_lines = "\n".join(
            f"- `{lbl.id}` — apply **{lbl.display}** and advance" for lbl in self.config.labels
        )
        skip_line = (
            f"- `{self.skip_key}` — **Skip** this entry (advance without labelling)\n"
            if self.skip_key is not None
            else ""
        )
        return (
            "### Literature Labeller — Help\n\n"
            "**Keyboard shortcuts**\n\n"
            f"{label_lines}\n"
            f"{skip_line}"
            "- `←` (Left Arrow) — reopen the previous entry to correct its label\n"
            "- `→` (Right Arrow) — move forward one entry without labelling\n"
            "- select a word/phrase, then `q` (or the 🔍 Look up button) — quick reference lookup\n"
            "- **Exit** button — export the CSV and quit\n\n"
            "**Quick Lookup**\n\n"
            "Select a word or phrase in the title/abstract and press `q` to see a "
            "Wikipedia summary of it. If the selection is a known pesticide term (or a "
            "synonym of one), the article for the canonical compound is looked up, and "
            "its compendium details plus a BCPC Compendium link are carried along under "
            "**Compendium data**.\n\n"
            "**Correcting a mistake**\n\n"
            "Press `←` to reopen the entry you want to change, then press the correct "
            "number key. The new label overwrites the old one (last decision wins). "
            "There is no blank/un-label — you replace one label with another.\n\n"
            "**Your labels are safe**\n\n"
            "Every label is saved to the database the moment you press a key. If the app "
            "closes unexpectedly, nothing is lost — on restart you resume at the first "
            "unlabelled entry. The CSV file is written only when you press **Exit**; it is "
            "a regenerable snapshot of the database (the database is the source of truth)."
        )

    def build(self) -> None:
        ui.add_head_html(MARK_CSS)

        # Help modal, opened from the Help button in the header.
        with ui.dialog() as help_dialog, ui.card().classes("max-w-lg"):
            ui.markdown(self._help_markdown())
            ui.button("Close", on_click=help_dialog.close).props("flat")

        # Quick Lookup modal — its body is cleared and repopulated per lookup.
        with ui.dialog() as self._lookup_dialog, ui.card().classes("max-w-lg w-full"):
            self._lookup_body = ui.column().classes("w-full gap-2")
            ui.button("Close", on_click=self._lookup_dialog.close).props("flat")

        with ui.column().classes("w-full max-w-3xl mx-auto gap-3 p-4"):
            with ui.row().classes("w-full items-center justify-between"):
                self._progress = ui.label().classes("text-sm text-gray-500")
                with ui.row().classes("items-center gap-2"):
                    ui.button("🔍 Look up", on_click=self.quick_lookup).props("outline")
                    ui.button("Help", on_click=help_dialog.open).props("outline")
                    ui.button("Exit", on_click=self.exit_session, color="negative")

            with ui.card().classes("w-full"):
                self._pmid = ui.label().classes("text-sm text-gray-500")
                self._title = ui.html().classes("text-xl font-bold leading-snug")
                ui.separator()
                self._abstract = ui.html().classes("text-base leading-relaxed")

            self._status = ui.label().classes("text-sm")

            with ui.row().classes("w-full flex-wrap gap-2"):
                for label in self.config.labels:
                    btn = ui.button(
                        f"[{label.id}] {label.display}",
                        on_click=lambda _=None, lid=label.id: self.apply_label(lid),
                    )
                    self._label_buttons[label.id] = btn
                # Skip advances without labelling; it is not a config label.
                if self.skip_key is not None:
                    ui.button(
                        f"[{self.skip_key}] Skip",
                        on_click=lambda _=None: self.skip_entry(),
                    ).props("color=grey-5")

            skip_hint = f"[{self.skip_key}] skip · " if self.skip_key is not None else ""
            ui.label(
                f"Keys label & advance · {skip_hint}← back · → forward · "
                "select text + q to look up · Help for details"
            ).classes("text-xs text-gray-400")

        ui.keyboard(on_key=self._on_key)
        self._refresh()

    async def _on_key(self, e) -> None:
        if not e.action.keydown or e.action.repeat:
            return
        if e.key.arrow_left:
            self.edit_previous()
            return
        if e.key.arrow_right:
            self.move_next()
            return
        if str(e.key.name).lower() == "q":
            await self.quick_lookup()
            return
        if e.key.number is not None:
            if e.key.number in self.config.hotkeys_ids:
                self.apply_label(e.key.number)
            elif self.skip_key is not None and e.key.number == self.skip_key:
                self.skip_entry()

    def _refresh(self) -> None:
        row = self.current_row
        total = len(self.dataset.rows)
        self._progress.text = f"Entry {self.index + 1} / {total}"
        self._pmid.text = f"PMID: {row.get('pmid', '')}"
        self._title.content = self.highlighter.highlight(row.get("title", ""))
        self._abstract.content = self.highlighter.highlight(row.get("abstract", ""))

        existing = self.store.get_label(row.get("pmid", ""))
        for lid, btn in self._label_buttons.items():
            is_current = existing is not None and existing["label_id"] == lid
            btn.props(f"color={'primary' if is_current else 'grey-5'}")
        if existing is not None:
            self._status.text = (
                f"Labelled: {existing['label_name']} at {existing['timestamp']}"
            )
            self._status.classes(replace="text-sm text-green-600")
        else:
            self._status.text = "Not yet labelled"
            self._status.classes(replace="text-sm text-gray-500")
