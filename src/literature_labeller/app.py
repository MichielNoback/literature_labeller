"""NiceGUI dashboard: display one PubMed entry at a time and label it."""

from __future__ import annotations

from nicegui import app, ui

from .config import Config
from .data import Dataset
from .highlight import Highlighter
from .store import LabelStore

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
    ):
        self.config = config
        self.dataset = dataset
        self.highlighter = highlighter
        self.store = store
        self.session = session
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
            "- **Exit** button — export the CSV and quit\n\n"
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

        with ui.column().classes("w-full max-w-3xl mx-auto gap-3 p-4"):
            with ui.row().classes("w-full items-center justify-between"):
                self._progress = ui.label().classes("text-sm text-gray-500")
                with ui.row().classes("items-center gap-2"):
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
                f"Keys label & advance · {skip_hint}← re-edit previous · Help for details"
            ).classes("text-xs text-gray-400")

        ui.keyboard(on_key=self._on_key)
        self._refresh()

    def _on_key(self, e) -> None:
        if not e.action.keydown or e.action.repeat:
            return
        if e.key.arrow_left:
            self.edit_previous()
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
