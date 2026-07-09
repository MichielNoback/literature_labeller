import csv

import pytest

from literature_labeller.data import DataError, load_dataset, load_keyword_terms


def _write_csv(path, fieldnames, rows):
    with path.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow(row)


def test_load_dataset_ok(tmp_path):
    p = tmp_path / "ds.csv"
    _write_csv(
        p,
        ["pmid", "title", "abstract", "journal"],
        [{"pmid": "1", "title": "t", "abstract": "a", "journal": "J"}],
    )
    ds = load_dataset(p)
    assert len(ds) == 1
    assert ds.fieldnames == ["pmid", "title", "abstract", "journal"]
    assert ds.rows[0]["journal"] == "J"


def test_load_dataset_missing_column(tmp_path):
    p = tmp_path / "ds.csv"
    _write_csv(p, ["pmid", "title"], [{"pmid": "1", "title": "t"}])
    with pytest.raises(DataError, match="abstract"):
        load_dataset(p)


def test_load_dataset_missing_file(tmp_path):
    with pytest.raises(DataError, match="not found"):
        load_dataset(tmp_path / "nope.csv")


def test_load_keyword_terms(tmp_path):
    p = tmp_path / "kw.csv"
    _write_csv(
        p,
        ["ID", "name", "synonyms"],
        [
            {"ID": "1", "name": "Atrazine", "synonyms": "atrazin;ATRAZINE"},
            {"ID": "2", "name": "1,3-D", "synonyms": "1,3-dichloropropene"},
        ],
    )
    terms = load_keyword_terms(p)
    # Case-insensitive de-duplication keeps the first spelling only.
    assert "Atrazine" in terms
    assert terms.count("Atrazine") == 1
    assert "atrazin" in terms
    assert "1,3-D" in terms
    assert "1,3-dichloropropene" in terms


def test_load_keyword_terms_missing_column(tmp_path):
    p = tmp_path / "kw.csv"
    _write_csv(p, ["ID", "name"], [{"ID": "1", "name": "Atrazine"}])
    with pytest.raises(DataError, match="synonyms"):
        load_keyword_terms(p)
