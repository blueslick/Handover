"""Tests for saved_calls.py (T20). Run: python -m pytest pipeline/tool/test_saved_calls.py
or simply: python pipeline/tool/test_saved_calls.py

No real model calls and no API key: a pretend model stands in for the API and counts
how often it is called. Uses the demo patient's records (D001) and a temporary outputs
folder only. No held-out file is read.
"""
import json
import shutil
import sys
import tempfile
from pathlib import Path
from types import SimpleNamespace

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(HERE))
from saved_calls import (SavedCallError, call_or_replay, count_new_calls,  # noqa: E402
                         is_saved, load_saved, usage_rows, write_usage_csv)

DEMO = ROOT / "pipeline" / "data" / "demo" / "D001"
RUN = "20261115-v1-test-saved"


class PretendModel:
    """Stands in for client.messages.create. Replies like the real API and counts calls."""
    def __init__(self, reply='{"facts": []}', input_tokens=800, output_tokens=100):
        self.calls, self.reply = 0, reply
        self.input_tokens, self.output_tokens = input_tokens, output_tokens

    def __call__(self, **request):
        self.calls += 1
        return SimpleNamespace(
            id=f"msg_test_{self.calls}", model=request["model"], stop_reason="end_turn",
            content=[SimpleNamespace(type="text", text=self.reply)],
            usage=SimpleNamespace(input_tokens=self.input_tokens,
                                  output_tokens=self.output_tokens))


def setup(tmp):
    """A temporary outputs folder, a copy of D001's records and a pretend prompt file."""
    tmp = Path(tmp)
    records = tmp / "records"
    shutil.copytree(DEMO, records)
    prompt = tmp / "extract_v1.md"
    prompt.write_text("Pretend prompt for tests.\n", encoding="utf-8")
    return tmp / "outputs", records, prompt


def request_for(record):
    return {"model": "claude-test-model", "max_tokens": 2000,
            "system": "Pretend prompt for tests.",
            "messages": [{"role": "user", "content": record.read_text(encoding="utf-8")}]}


def run_one(outputs, records, prompt, model, hospital="C", attempt=1):
    record = records / f"D001_{hospital}.{'csv' if hospital == 'A' else 'txt'}"
    return call_or_replay(RUN, "D001", hospital, record, prompt, "v1", request_for(record),
                          model, attempt=attempt, outputs=outputs)


def test_first_call_saves_reply_and_usage():
    with tempfile.TemporaryDirectory() as tmp:
        outputs, records, prompt = setup(tmp)
        model = PretendModel()
        got = run_one(outputs, records, prompt, model)
        assert model.calls == 1 and not got.replayed
        folder = outputs / "extracted" / RUN
        assert (folder / "D001_C.raw.txt").read_text(encoding="utf-8") == '{"facts": []}'
        details = json.loads((folder / "D001_C.call.json").read_text(encoding="utf-8"))
        assert details["usage"] == {"input_tokens": 800, "output_tokens": 100}
        assert details["model"] == "claude-test-model"
        assert details["source_file"] == "D001_C.txt"
        assert details["stop_reason"] == "end_turn"


def test_second_run_replays_without_a_call():
    with tempfile.TemporaryDirectory() as tmp:
        outputs, records, prompt = setup(tmp)
        model = PretendModel()
        first = run_one(outputs, records, prompt, model)
        again = run_one(outputs, records, prompt, model)
        assert model.calls == 1, "a saved call must not be made again"
        assert again.replayed and again.text == first.text and again.usage == first.usage


def test_load_saved_never_calls_and_fails_clearly_when_missing():
    with tempfile.TemporaryDirectory() as tmp:
        outputs, records, prompt = setup(tmp)
        try:
            load_saved(RUN, "D001", "C", outputs=outputs)
            assert False, "should have stopped"
        except SavedCallError as e:
            assert "no saved reply" in str(e)
        run_one(outputs, records, prompt, PretendModel())
        assert load_saved(RUN, "D001", "C", outputs=outputs).replayed


def test_changed_record_or_prompt_stops_replay():
    with tempfile.TemporaryDirectory() as tmp:
        outputs, records, prompt = setup(tmp)
        model = PretendModel()
        run_one(outputs, records, prompt, model)
        prompt.write_text("A different prompt.\n", encoding="utf-8")
        try:
            run_one(outputs, records, prompt, model)
            assert False, "should have stopped"
        except SavedCallError as e:
            assert "prompt" in str(e) and "new run ID" in str(e)
        assert model.calls == 1


def test_edited_reply_is_caught():
    with tempfile.TemporaryDirectory() as tmp:
        outputs, records, prompt = setup(tmp)
        run_one(outputs, records, prompt, PretendModel())
        raw = outputs / "extracted" / RUN / "D001_C.raw.txt"
        raw.write_text('{"facts": ["edited"]}', encoding="utf-8")
        try:
            load_saved(RUN, "D001", "C", outputs=outputs)
            assert False, "should have stopped"
        except SavedCallError as e:
            assert "never be edited" in str(e)


def test_retry_saved_separately_and_only_after_attempt_1():
    with tempfile.TemporaryDirectory() as tmp:
        outputs, records, prompt = setup(tmp)
        model = PretendModel()
        try:
            run_one(outputs, records, prompt, model, attempt=2)
            assert False, "retry before attempt 1 should stop"
        except SavedCallError:
            pass
        run_one(outputs, records, prompt, model)
        run_one(outputs, records, prompt, model, attempt=2)
        assert model.calls == 2
        assert (outputs / "extracted" / RUN / "D001_C.attempt2.raw.txt").exists()
        assert is_saved(RUN, "D001", "C", 2, outputs)


def test_prompt_text_not_copied_into_details():
    with tempfile.TemporaryDirectory() as tmp:
        outputs, records, prompt = setup(tmp)
        run_one(outputs, records, prompt, PretendModel(), hospital="B")
        details = (outputs / "extracted" / RUN / "D001_B.call.json").read_text(encoding="utf-8")
        record_text = (records / "D001_B.txt").read_text(encoding="utf-8")
        assert record_text[:40] not in details
        assert "messages_sha256" in details and "system_sha256" in details


def test_pending_count_and_usage_table():
    with tempfile.TemporaryDirectory() as tmp:
        outputs, records, prompt = setup(tmp)
        assert count_new_calls(RUN, ["D001"], outputs) == 3
        run_one(outputs, records, prompt, PretendModel(input_tokens=900, output_tokens=120), "A")
        run_one(outputs, records, prompt, PretendModel(input_tokens=700, output_tokens=80), "C")
        assert count_new_calls(RUN, ["D001"], outputs) == 1
        rows = write_usage_csv(RUN, outputs)
        assert [(r["hospital"], r["input_tokens"], r["output_tokens"]) for r in rows] == \
            [("A", 900, 120), ("C", 700, 80)]
        assert (outputs / "extracted" / RUN / "usage.csv").exists()
        assert usage_rows(RUN, outputs) == rows


def test_wrong_ids_and_mismatched_prompt_version_stop_before_any_call():
    with tempfile.TemporaryDirectory() as tmp:
        outputs, records, prompt = setup(tmp)
        model = PretendModel()
        record = records / "D001_C.txt"
        for bad in (dict(run_id="v1-no-date"), dict(patient_id="P14"), dict(hospital="D"),
                    dict(prompt_version="v2")):
            args = dict(run_id=RUN, patient_id="D001", hospital="C", prompt_version="v1")
            args.update(bad)
            try:
                call_or_replay(args["run_id"], args["patient_id"], args["hospital"], record,
                               prompt, args["prompt_version"], request_for(record), model,
                               outputs=outputs)
                assert False, f"should have stopped for {bad}"
            except SavedCallError:
                pass
        assert model.calls == 0


if __name__ == "__main__":
    tests = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    for t in tests:
        t()
        print("ok ", t.__name__)
    print(f"{len(tests)} tests passed")
