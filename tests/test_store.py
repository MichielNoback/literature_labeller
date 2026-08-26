import csv
import re
from datetime import datetime

from literature_labeller.data import Dataset
from literature_labeller.store import LabelStore, format_timestamp


def _dataset():
    return Dataset(
        fieldnames=["pmid", "title", "abstract", "journal"],
        rows=[
            {"pmid": "1", "title": "t1", "abstract": "a1", "journal": "J1"},
            {"pmid": "2", "title": "t2", "abstract": "a2", "journal": "J2"},
        ],
    )


def test_timestamp_format():
    ts = format_timestamp(datetime(2026, 7, 10, 21, 21))
    assert ts == "2026-07-10;21:21"
    assert re.fullmatch(r"\d{4}-\d{2}-\d{2};\d{2}:\d{2}", ts)


def test_upsert_overwrites(tmp_path):
    store = LabelStore(tmp_path / "labels.db")
    store.upsert_label("1", 0, "negative", "s1")
    store.upsert_label("1", 2, "environmental", "s2")  # edit
    row = store.get_label("1")
    assert row["label_id"] == 2
    assert row["label_name"] == "environmental"
    assert row["session"] == "s2"
    store.close()


def test_labelled_pmids(tmp_path):
    store = LabelStore(tmp_path / "labels.db")
    store.upsert_label("2", 1, "human_animal", "s1")
    assert store.labelled_pmids() == {"2"}
    store.close()


def test_export_preserves_columns_and_is_cumulative(tmp_path):
    db = tmp_path / "labels.db"
    out = tmp_path / "out.csv"

    store = LabelStore(db)
    store.upsert_label("1", 3, "foodstuff", "s1")
    store.close()

    # New session appends to the same DB; export must include both.
    store2 = LabelStore(db)
    store2.upsert_label("2", 4, "other", "s2")
    written = store2.export_csv(_dataset(), out)
    store2.close()

    assert written == 2
    with out.open() as fh:
        rows = list(csv.DictReader(fh))
    assert [r["pmid"] for r in rows] == ["1", "2"]
    # Original extra column preserved.
    assert rows[0]["journal"] == "J1"
    # Label columns appended.
    assert rows[0]["label_name"] == "foodstuff"
    assert rows[1]["label_name"] == "other"


def test_export_leaves_unlabelled_blank(tmp_path):
    store = LabelStore(tmp_path / "labels.db")
    store.upsert_label("1", 0, "negative", "s1")
    out = tmp_path / "out.csv"
    store.export_csv(_dataset(), out)
    store.close()
    with out.open() as fh:
        rows = list(csv.DictReader(fh))
    assert rows[1]["label_name"] == ""
