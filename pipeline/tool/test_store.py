"""Tests for store.py (T25). Run: python -m pytest pipeline/tool/test_store.py
or simply: python pipeline/tool/test_store.py

Uses only the demo sample and working answer keys, copied into a temporary folder.
No held-out file is read.
"""
import json
import shutil
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(HERE))
from store import StoreError, build, publish  # noqa: E402

SAMPLE = ROOT / "shared" / "sample" / "D001_compiled.json"
WORKING = ROOT / "pipeline" / "data" / "working"
RUN = "20261115-test-store"


def make_run(tmp, pids=("P001", "P002", "P003"), kind="compiled"):
    """A fake run folder: the sample plus working answer keys relabelled as compiled."""
    run_dir = Path(tmp) / "compiled" / RUN
    run_dir.mkdir(parents=True)
    docs = [json.loads(SAMPLE.read_text(encoding="utf-8"))]
    docs += [json.loads((WORKING / p / f"{p}_key.json").read_text(encoding="utf-8")) for p in pids]
    for d in docs:
        d["kind"], d["run_id"] = kind, RUN
        (run_dir / f"{d['patient_id']}.json").write_text(json.dumps(d), encoding="utf-8")
    return run_dir, docs


def test_build_one_line_per_fact():
    with tempfile.TemporaryDirectory() as tmp:
        run_dir, docs = make_run(tmp)
        index = build(run_dir)
        lines = (run_dir / "facts.jsonl").read_text(encoding="utf-8").splitlines()
        assert len(lines) == sum(len(d["facts"]) for d in docs)
        first = json.loads(lines[0])
        assert first["run_id"] == RUN and first["kind"] == "compiled"
        assert {k: v for k, v in first.items() if k not in ("run_id", "kind")} == docs[0]["facts"][0]
        assert [p["patient_id"] for p in index["patients"]] == ["D001", "P001", "P002", "P003"]
        assert json.loads((run_dir / "index.json").read_text(encoding="utf-8")) == index


def test_demo_counts():
    with tempfile.TemporaryDirectory() as tmp:
        run_dir, _ = make_run(tmp, pids=())
        d001 = build(run_dir)["patients"][0]
        assert d001["facts"] == 7
        assert d001["conflicts"] == 1          # penicillin vs no known allergies
        assert d001["critical_warnings"] == 2  # both sides of that conflict


def test_build_is_repeatable():
    with tempfile.TemporaryDirectory() as tmp:
        run_dir, _ = make_run(tmp)
        build(run_dir)
        first = (run_dir / "facts.jsonl").read_bytes()
        build(run_dir)
        assert (run_dir / "facts.jsonl").read_bytes() == first


def test_bad_file_stops_everything():
    with tempfile.TemporaryDirectory() as tmp:
        run_dir, _ = make_run(tmp)
        bad = json.loads((run_dir / "P001.json").read_text(encoding="utf-8"))
        bad["facts"][0]["status"] = "maybe"
        (run_dir / "P001.json").write_text(json.dumps(bad), encoding="utf-8")
        try:
            build(run_dir)
        except StoreError:
            pass
        else:
            raise AssertionError("invalid file should stop the build")
        assert not (run_dir / "facts.jsonl").exists()


def test_wrong_file_name_stops():
    with tempfile.TemporaryDirectory() as tmp:
        run_dir, _ = make_run(tmp)
        shutil.move(run_dir / "P002.json", run_dir / "P009.json")
        try:
            build(run_dir)
        except StoreError as e:
            assert "P009.json" in str(e)
        else:
            raise AssertionError("mismatched file name should stop the build")


def test_publish_copies_run_and_baseline():
    with tempfile.TemporaryDirectory() as tmp:
        make_run(tmp)
        base = Path(tmp) / "baseline_keyword"
        base.mkdir()
        d = json.loads(SAMPLE.read_text(encoding="utf-8"))
        d["kind"], d["run_id"] = "baseline_keyword", None
        (base / "D001.json").write_text(json.dumps(d), encoding="utf-8")
        stale = Path(tmp) / "published" / "compiled"
        stale.mkdir(parents=True)
        (stale / "P099.json").write_text("{}", encoding="utf-8")

        index = publish(RUN, tmp, patients=["D001", "P001"])
        pub = Path(tmp) / "published"
        assert sorted(p.name for p in (pub / "compiled").iterdir()) == ["D001.json", "P001.json"]
        assert [p.name for p in (pub / "baseline_keyword").iterdir()] == ["D001.json"]
        assert index["compiled_run_id"] == RUN
        assert [(p["patient_id"], p["has_baseline"]) for p in index["patients"]] == [("D001", True), ("P001", False)]


def test_publish_unknown_patient_stops():
    with tempfile.TemporaryDirectory() as tmp:
        make_run(tmp)
        try:
            publish(RUN, tmp, patients=["P050"])
        except StoreError as e:
            assert "P050" in str(e)
        else:
            raise AssertionError("patient not in the run should stop publish")


if __name__ == "__main__":
    tests = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    for t in tests:
        t()
        print(f"ok  {t.__name__}")
    print(f"{len(tests)} tests passed")
