import json
import threading
import time
from pathlib import Path

import pandas as pd

from . import config, db, dev_stub, patching, runner
from .compare import compare
from .datasets import load_run_inputs
from .errors import ApiError, conflict, not_found
from .hashing import sha256_text

TERMINAL = {"done", "error", "cancelled"}
BUFFERS = {}


class RunEvents:
    def __init__(self):
        self.items = []
        self.closed = False
        self.cond = threading.Condition()

    def push(self, name, payload):
        with self.cond:
            self.items.append((len(self.items) + 1, name, payload))
            if name in TERMINAL:
                self.closed = True
            self.cond.notify_all()

    def stream(self, after=0):
        index = after
        while True:
            with self.cond:
                if index >= len(self.items) and not self.closed:
                    self.cond.wait(15)
                batch = self.items[index:]
                closed = self.closed
            if not batch:
                if closed:
                    return
                yield ": ping\n\n"
                continue
            for number, name, payload in batch:
                yield f"id: {number}\nevent: {name}\ndata: {json.dumps(payload)}\n\n"
            index += len(batch)
            if batch[-1][1] in TERMINAL:
                return


def step_event(events, index, key, state, detail, percent):
    events.push(
        "step",
        {"index": index, "key": key, "state": state, "detail": detail, "percent": percent},
    )


def run_status(run_id):
    with db.session() as conn:
        row = conn.execute("select status from runs where id = ?", (run_id,)).fetchone()
    return row["status"] if row else None


def error_message(error):
    if error["type"] in ("Timeout", "Cancelled", "RunError"):
        return error["message"]
    return f"{error['type']}: {error['message']}"


def error_payload(step, error):
    tail = (error.get("traceback") or "").splitlines()[-40:]
    return {"step": step, "message": error_message(error), "stderr": "\n".join(tail)}


def make_summary(checks, expected_rows, seconds, tolerances):
    matched = sum(1 for c in checks if c["status"] == "match")
    custom = any(float(v or 0) > 0 for v in tolerances.values())
    return {
        "total": len(checks),
        "matched": matched,
        "differs": len(checks) - matched,
        "rows_compared": expected_rows,
        "run_seconds": round(seconds, 2),
        "tolerance": "custom" if custom else "exact",
    }


def evaluate(run_id, python, dataset_id):
    row, input_file, expected_files = load_run_inputs(dataset_id)
    tolerances = db.loads(row["tolerances_json"], {})
    names = [f["table_name"] for f in expected_files]
    input_bytes = Path(input_file["path"]).read_bytes()
    result = runner.run_python(python, input_bytes, names, config.RUN_TIMEOUT, key=run_id)
    if not result.ok:
        return result, None, None
    if not result.tables:
        result.ok = False
        result.error = {
            "type": "RunError",
            "message": "The Python did not produce any of the expected tables.",
            "traceback": "",
        }
        return result, None, None
    expected = {f["table_name"]: pd.read_csv(f["path"]) for f in expected_files}
    input_columns = {
        str(c).lower() for c in pd.read_csv(input_file["path"], nrows=0).columns
    }
    checks = compare(expected, result.tables, tolerances, input_columns)
    rows = sum(f["rows"] for f in expected_files)
    return result, checks, make_summary(checks, rows, result.seconds, tolerances)


def save_revision(
    run_id, idx, label, python, risky, changed, checks, summary, explanation, patch
):
    with db.session() as conn:
        conn.execute(
            "insert into revisions (run_id, idx, label, python, python_sha256, risky_python_json, "
            "changed_lines_json, checks_json, summary_json, explanation_json, patch_json, created_at) "
            "values (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                run_id,
                idx,
                label,
                python,
                sha256_text(python),
                db.dumps(risky),
                db.dumps(changed),
                db.dumps(checks),
                db.dumps(summary),
                db.dumps(explanation) if explanation is not None else None,
                db.dumps(patch) if patch is not None else None,
                db.now_iso(),
            ),
        )


def create_run(lang, filename, source, dataset_id):
    run_id = db.new_id()
    now = db.now_iso()
    with db.session() as conn:
        conn.execute(
            "insert into runs (id, created_at, updated_at, lang, filename, status, source, source_sha256, "
            "dataset_id, translation_source, model, accepted, risky_source_json) "
            "values (?, ?, ?, ?, ?, 'running', ?, ?, ?, 'rules', null, 0, '[]')",
            (run_id, now, now, lang, filename, source, sha256_text(source), dataset_id),
        )
    BUFFERS[run_id] = RunEvents()
    threading.Thread(target=execute, args=(run_id,), daemon=True).start()
    return run_id


def fail_run(run_id, events, step, error):
    payload = error_payload(step, error)
    with db.session() as conn:
        conn.execute(
            "update runs set status = 'failed', error_json = ?, updated_at = ? where id = ?",
            (db.dumps(payload), db.now_iso(), run_id),
        )
    events.push("error", payload)


def cancelled(run_id, events):
    if run_status(run_id) == "cancelled":
        events.push("cancelled", {})
        return True
    return False


def execute(run_id):
    events = BUFFERS[run_id]
    try:
        with db.session() as conn:
            run = dict(conn.execute("select * from runs where id = ?", (run_id,)).fetchone())
        lang = run["lang"]
        events.push(
            "run",
            {
                "run_id": run_id,
                "filename": run["filename"],
                "lang": lang,
                "model_configured": config.model_configured(),
            },
        )
        step_event(
            events, 0, "parse", "active", f"{dev_stub.statements(lang, run['source'])} statements", 10
        )
        risky = dev_stub.risky_source(lang, run["source"])
        with db.session() as conn:
            conn.execute(
                "update runs set risky_source_json = ? where id = ?", (db.dumps(risky), run_id)
            )
        events.push("risks", {"risky_lines": risky})
        step_event(
            events, 0, "parse", "done", f"{dev_stub.statements(lang, run['source'])} statements", 20
        )
        if cancelled(run_id, events):
            return

        step_event(events, 1, "translate", "active", "Writing Python", 30)
        python = dev_stub.draft(lang)
        for start in range(0, len(python), 6):
            events.push("python", {"chunk": python[start : start + 6]})
            time.sleep(0.008)
        events.push("python_done", {"lines": len(python.splitlines()), "source": "rules"})
        if not config.model_configured():
            events.push(
                "notice",
                {
                    "code": "no_key",
                    "message": "Translation model is not set up, using the rule layer.",
                },
            )
        step_event(events, 1, "translate", "done", f"{len(python.splitlines())} lines", 40)
        if cancelled(run_id, events):
            return

        row, input_file, _ = load_run_inputs(run["dataset_id"])
        step_event(events, 2, "run", "active", f"{input_file['rows']:,} rows", 55)
        result, checks, summary = evaluate(run_id, python, run["dataset_id"])
        if run_status(run_id) == "cancelled":
            events.push("cancelled", {})
            return
        if not result.ok:
            step_event(events, 2, "run", "error", result.error["message"], 55)
            fail_run(run_id, events, "run", result.error)
            return
        step_event(events, 2, "run", "done", f"{result.seconds:.1f} seconds", 70)

        step_event(events, 3, "compare", "active", f"{summary['total']} checks", 80)
        events.push(
            "checks",
            {
                "total": summary["total"],
                "matched": summary["matched"],
                "differs": summary["differs"],
                "rows_compared": summary["rows_compared"],
                "run_seconds": summary["run_seconds"],
            },
        )
        step_event(events, 3, "compare", "done", f"{summary['matched']} of {summary['total']} match", 90)
        if cancelled(run_id, events):
            return

        step_event(events, 4, "report", "active", "Writing the report", 90)
        patch = dev_stub.rule_patch(lang, python) if summary["differs"] else None
        save_revision(
            run_id,
            0,
            "original",
            python,
            dev_stub.flag_python(lang, python),
            [],
            checks,
            summary,
            None,
            patch,
        )
        with db.session() as conn:
            conn.execute(
                "update runs set status = 'done', updated_at = ? where id = ? and status = 'running'",
                (db.now_iso(), run_id),
            )
        step_event(events, 4, "report", "done", "Report ready", 100)
        state = "differs" if summary["differs"] else "match"
        events.push(
            "done",
            {
                "run_id": run_id,
                "report": f"/api/runs/{run_id}",
                "state": state,
                "matched": summary["matched"],
                "total": summary["total"],
            },
        )
    except Exception as exc:
        fail_run(
            run_id,
            events,
            "run",
            {"type": "RunError", "message": "The run stopped because of an internal error.", "traceback": repr(exc)},
        )


def cancel_run(run_id):
    with db.session() as conn:
        row = conn.execute("select status from runs where id = ?", (run_id,)).fetchone()
        if row is None:
            raise not_found("This run does not exist.")
        if row["status"] != "running":
            raise conflict("This run is not running.")
        conn.execute(
            "update runs set status = 'cancelled', updated_at = ? where id = ?",
            (db.now_iso(), run_id),
        )
    runner.cancel(run_id)
    events = BUFFERS.get(run_id)
    if events is not None and not events.closed:
        events.push("cancelled", {})


def latest_revision(conn, run_id):
    return conn.execute(
        "select * from revisions where run_id = ? order by idx desc limit 1", (run_id,)
    ).fetchone()


def load_run(conn, run_id):
    row = conn.execute("select * from runs where id = ?", (run_id,)).fetchone()
    if row is None:
        raise not_found("This run does not exist.")
    return row


def apply_fix(run_id):
    with db.session() as conn:
        run = load_run(conn, run_id)
        rev = latest_revision(conn, run_id)
    if run["status"] == "failed":
        raise ApiError(400, "run_failed", "This run failed, so there is nothing to fix.")
    if run["status"] != "done" or rev is None:
        raise conflict("This run is not finished.")
    patch = db.loads(rev["patch_json"])
    if patch is None:
        raise conflict("There is no fix to apply.")
    try:
        python, changed = patching.apply(rev["python"], patch)
    except patching.PatchFailed:
        raise conflict("The fix no longer applies to this Python.")
    result, checks, summary = evaluate(run_id, python, run["dataset_id"])
    if not result.ok:
        raise ApiError(400, "run_failed", error_message(result.error))
    lang = run["lang"]
    next_patch = dev_stub.rule_patch(lang, python) if summary["differs"] else None
    save_revision(
        run_id,
        rev["idx"] + 1,
        "fix",
        python,
        dev_stub.flag_python(lang, python),
        changed,
        checks,
        summary,
        None,
        next_patch,
    )
    with db.session() as conn:
        conn.execute(
            "update runs set accepted = 0, updated_at = ? where id = ?", (db.now_iso(), run_id)
        )


def keep_run(run_id, state):
    if state != "differs":
        raise conflict("Only a run with differences can be kept as is.")
    with db.session() as conn:
        conn.execute(
            "update runs set accepted = 1, updated_at = ? where id = ?", (db.now_iso(), run_id)
        )


def undo_run(run_id):
    with db.session() as conn:
        run = load_run(conn, run_id)
        rev = latest_revision(conn, run_id)
        if run["accepted"]:
            conn.execute(
                "update runs set accepted = 0, updated_at = ? where id = ?",
                (db.now_iso(), run_id),
            )
            return
        if rev is None or rev["idx"] == 0:
            raise conflict("There is nothing to undo.")
        conn.execute("delete from revisions where run_id = ? and idx = ?", (run_id, rev["idx"]))
        conn.execute("update runs set updated_at = ? where id = ?", (db.now_iso(), run_id))


def delete_run(run_id):
    with db.session() as conn:
        load_run(conn, run_id)
        conn.execute("delete from revisions where run_id = ?", (run_id,))
        conn.execute("delete from runs where id = ?", (run_id,))
    BUFFERS.pop(run_id, None)


def synthesize_events(run_id):
    with db.session() as conn:
        run = load_run(conn, run_id)
        rev = latest_revision(conn, run_id)
    events = RunEvents()
    events.push(
        "run",
        {
            "run_id": run_id,
            "filename": run["filename"],
            "lang": run["lang"],
            "model_configured": config.model_configured(),
        },
    )
    if run["status"] == "failed":
        events.push("error", db.loads(run["error_json"], {"step": "run", "message": "", "stderr": ""}))
    elif run["status"] == "cancelled":
        events.push("cancelled", {})
    elif run["status"] == "done" and rev is not None:
        summary = db.loads(rev["summary_json"], {})
        events.push(
            "done",
            {
                "run_id": run_id,
                "report": f"/api/runs/{run_id}",
                "state": "differs" if summary.get("differs") else "match",
                "matched": summary.get("matched", 0),
                "total": summary.get("total", 0),
            },
        )
    else:
        events.push("cancelled", {})
    return events
