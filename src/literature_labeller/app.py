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

    def _goto(self, index: int) -> None:
        self.index = max(0, min(index, len(self.dataset.rows) - 1))
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
        # Advance to the next entry unless we are at the end.
        if self.index < len(self.dataset.rows) - 1:
            self._goto(self.index + 1)
        else:
            self._refresh()

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

    def build(self) -> None:
        ui.add_head_html(MARK_CSS)
        with ui.column().classes("w-full max-w-3xl mx-auto gap-3 p-4"):
            with ui.row().classes("w-full items-center justify-between"):
                self._progress = ui.label().classes("text-sm text-gray-500")
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

            ui.label("Keys 0-4 label · ← re-edit previous entry").classes(
                "text-xs text-gray-400"
            )

        ui.keyboard(on_key=self._on_key)
        self._refresh()

    def _on_key(self, e) -> None:
        if not e.action.keydown or e.action.repeat:
            return
        if e.key.arrow_left:
            self.edit_previous()
            return
        if e.key.number is not None and e.key.number in self.config.hotkeys_ids:
            self.apply_label(e.key.number)

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
