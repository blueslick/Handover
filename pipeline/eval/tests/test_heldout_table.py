"""Tests for heldout_table.py, the held-out build-up table (T37). Run from the repo root:
    .venv/bin/python -m pytest pipeline/eval/tests

Every number and every patient ID here is made up. No held-out file is opened.
"""

import csv
import sys
from pathlib import Path

import pytest

EVAL = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(EVAL))

import heldout_table as ht  # noqa: E402
import score  # noqa: E402


# Made-up per-patient lines: 160 patients, 20 in each age-sex group, with simple counts.
# Patient number i in group g gets key_facts 5, matched 4 (or 5 when i is even), and so on.
def fake_patients(row_shift=0):
    lines = []
    for i in range(ht.N_PATIENTS):
        age, sex = ht.GROUPS[i % len(ht.GROUPS)]
        line = {"patient_id": f"T{i:04d}", "age_band": age, "sex": sex}
        for field in score.COUNT_FIELDS:
            for scope in score.SCOPES:
                line[f"{field}_{scope}"] = 0
        line["key_facts_all"] = 5
        line["matched_all"] = 5 if i % 2 == 0 else 4
        line["missed_all"] = 0 if i % 2 == 0 else 1
        line["output_facts_all"] = 5 + row_shift
        line["false_alarms_all"] = row_shift
        line["key_facts_critical"] = 2
        line["matched_critical"] = 2
        line["output_facts_critical"] = 2
        line["dose_correct_all"] = 1
        line["dose_wrong_all"] = 1 if i % 4 == 1 else 0
        line["conflict_facts_all"] = 1 if i < 40 else 0
        line["conflict_shown_all"] = 1 if i < 30 else 0
        lines.append(line)
    return lines


# Write per-patient lines the way score.py does, split into the two key folders (80 + 80).
def write_scores(root, row_number, lines):
    for part, chunk in zip(ht.PARTS, (lines[:80], lines[80:])):
        folder = Path(root) / f"row{row_number}" / part
        folder.mkdir(parents=True, exist_ok=True)
        with open(folder / "per_patient.csv", "w", encoding="utf-8", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=score._per_patient_fields())
            writer.writeheader()
            writer.writerows(chunk)


def read_csv(path):
    with open(path, encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


@pytest.fixture
def scores(tmp_path):
    root = tmp_path / "scores"
    write_scores(root, 1, fake_patients(0))
    write_scores(root, 7, fake_patients(1))
    return root


def test_totals_are_summed_and_rates_recomputed(scores, tmp_path):
    out = tmp_path / "out"
    result = ht.run(scores, out, rows=[1, 7])
    table = read_csv(out / "buildup_table.csv")
    row1_all = next(r for r in table if r["row"] == "1" and r["scope"] == "all")
    # 160 patients x 5 key facts; 80 even patients match 5, 80 odd patients match 4.
    assert row1_all["key_facts"] == "800"
    assert row1_all["matched"] == str(80 * 5 + 80 * 4)
    assert row1_all["missed"] == "80"
    assert row1_all["false_alarms"] == "0"
    assert row1_all["recall"] == str(round(720 / 800, 3))
    assert row1_all["precision"] == str(round(720 / 800, 3))
    assert row1_all["dose_correct"] == "160"
    assert row1_all["dose_wrong"] == "40"
    assert (row1_all["conflict_shown"], row1_all["conflict_facts"]) == ("30", "40")
    # Row 7 has 1 extra output fact and 1 false alarm per patient: precision drops, recall does not.
    row7_all = next(r for r in table if r["row"] == "7" and r["scope"] == "all")
    assert row7_all["false_alarms"] == "160"
    assert row7_all["precision"] == str(round(720 / 960, 3))
    assert row7_all["recall"] == row1_all["recall"]
    row1_critical = next(r for r in table if r["row"] == "1" and r["scope"] == "critical")
    assert row1_critical["key_facts"] == "320" and row1_critical["recall"] == "1.0"
    assert result["sanity"][0].startswith("ok: key facts (all)")


def test_age_sex_file_has_the_chosen_rows_and_eight_groups(scores, tmp_path):
    out = tmp_path / "out"
    ht.run(scores, out, rows=[1, 7], age_sex_rows=(7,))
    lines = read_csv(out / "by_age_sex.csv")
    assert {line["row"] for line in lines} == {"7"}
    assert len(lines) == 8 * 2  # 8 groups x (all, critical)
    assert {line["patients"] for line in lines} == {"20"}
    assert sum(int(l["key_facts"]) for l in lines if l["scope"] == "all") == 800


def test_output_files_hold_no_patient_ids(scores, tmp_path):
    out = tmp_path / "out"
    ht.run(scores, out, rows=[1, 7])
    for name in ("buildup_table.csv", "by_age_sex.csv"):
        text = (out / name).read_text(encoding="utf-8")
        assert "T0" not in text  # the made-up IDs
        assert not ht.ID_SHAPE.search(text)


def test_writer_refuses_text_that_looks_like_an_id(tmp_path):
    line = {"row": 1, "name": "P001 oops", "scope": "all", "patients": 160,
            **{field: 0 for field in ht.TABLE_COUNTS}, "recall": "", "precision": ""}
    with pytest.raises(ht.TableError):
        ht.write_tables(tmp_path, [line], [])
    assert not (tmp_path / "buildup_table.csv").exists()


def test_stops_when_a_patient_is_missing(tmp_path):
    root = tmp_path / "scores"
    write_scores(root, 1, fake_patients()[:159])
    with pytest.raises(ht.TableError, match="159 patient lines"):
        ht.run(root, tmp_path / "out", rows=[1])
    assert not (tmp_path / "out").exists()


def test_stops_when_a_patient_is_counted_twice(tmp_path):
    lines = fake_patients()
    lines[5]["patient_id"] = lines[4]["patient_id"]
    root = tmp_path / "scores"
    write_scores(root, 1, lines)
    with pytest.raises(ht.TableError, match="159 different"):
        ht.run(root, tmp_path / "out", rows=[1])


def test_stops_when_a_group_is_not_20(tmp_path):
    lines = fake_patients()
    lines[0]["age_band"], lines[0]["sex"] = "65+", "M"  # moves one patient: 19 in one group, 21 in another
    root = tmp_path / "scores"
    write_scores(root, 1, lines)
    with pytest.raises(ht.TableError, match="without exactly 20"):
        ht.run(root, tmp_path / "out", rows=[1])


def test_stops_when_ids_are_not_the_expected_ones(tmp_path):
    root = tmp_path / "scores"
    write_scores(root, 1, fake_patients())
    expected = {f"T{i:04d}" for i in range(159)} | {"T9999"}
    with pytest.raises(ht.TableError, match="1 held-out patients missing, 1 not held-out"):
        ht.run(root, tmp_path / "out", rows=[1], expected_ids=expected)


def test_stops_when_a_row_was_not_scored(tmp_path):
    with pytest.raises(ht.TableError, match="scores are missing"):
        ht.run(tmp_path / "scores", tmp_path / "out", rows=[1])


def test_sanity_flags_key_facts_that_differ_between_rows(tmp_path):
    root = tmp_path / "scores"
    write_scores(root, 1, fake_patients())
    changed = fake_patients()
    changed[0]["key_facts_all"] = 6
    write_scores(root, 2, changed)
    result = ht.run(root, tmp_path / "out", rows=[1, 2], age_sex_rows=())
    assert any(m.startswith("PROBLEM: key facts (all)") for m in result["sanity"])
    assert result["sanity"][1].startswith("ok: key facts (critical)")


def test_screen_table_shows_every_row_for_both_scopes(scores, tmp_path):
    result = ht.run(scores, tmp_path / "out", rows=[1, 7])
    text = ht.format_table(result["buildup"])
    assert "ALL FACTS" in text and "CRITICAL FACTS" in text
    # The long row names appear once, in the legend under the table.
    assert text.count(ht.ROW_NAMES[7]) == 1 and "Rows:" in text

