from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse, Response, StreamingResponse

from . import db, export, pdf_report, pipeline
from .datasets import check_lang, dataset_json, fetch_dataset
from .errors import ApiError, not_found
from .schemas import KeepBody, RunCreate

router = APIRouter(prefix="/api/runs")


def state_of(accepted, revisions):
    if not revisions:
        return "differs"
    first = revisions[0]["summary"].get("differs", 0)
    current = revisions[-1]
    if accepted:
        return "kept"
    if current["summary"].get("differs", 0) == 0:
        return "match" if current["idx"] == 0 and first == 0 else "fixed"
    return "differs"


def load_revisions(conn, run_id):
    rows = conn.execute(
        "select * from revisions where run_id = ? order by idx", (run_id,)
    ).fetchall()
    result = []
    for row in rows:
        item = dict(row)
        item["summary"] = db.loads(row["summary_json"], {})
        result.append(item)
    return result


def revision_json(rev):
    return {
        "index": rev["idx"],
        "label": rev["label"],
        "python": rev["python"],
        "python_sha256": rev["python_sha256"],
        "risky_python": db.loads(rev["risky_python_json"], []),
        "changed_lines": db.loads(rev["changed_lines_json"], []),
        "checks": db.loads(rev["checks_json"], []),
        "summary": rev["summary"],
        "explanation": db.loads(rev["explanation_json"]),
        "patch": db.loads(rev["patch_json"]),
    }


def run_json(run_id):
    with db.session() as conn:
        run = pipeline.load_run(conn, run_id)
        revisions = load_revisions(conn, run_id)
    try:
        dataset = dataset_json(run["dataset_id"], full=False)
    except ApiError:
        dataset = {"id": run["dataset_id"], "input": None, "expected": [], "tolerances": {}}
    dataset_view = {
        "id": dataset["id"],
        "input": dataset["input"],
        "expected": dataset["expected"],
        "tolerances": dataset["tolerances"],
    }
    current = revisions[-1] if revisions else None
    return {
        "id": run["id"],
        "created_at": run["created_at"],
        "lang": run["lang"],
        "filename": run["filename"],
        "status": run["status"],
        "state": state_of(bool(run["accepted"]), revisions),
        "source": run["source"],
        "source_sha256": run["source_sha256"],
        "dataset": dataset_view,
        "translation": {"source": run["translation_source"], "model": run["model"]},
        "risky_source": db.loads(run["risky_source_json"], []),
        "current": revision_json(current) if current else None,
        "revisions": [
            {
                "index": r["idx"],
                "label": r["label"],
                "python_sha256": r["python_sha256"],
                "matched": r["summary"].get("matched", 0),
                "total": r["summary"].get("total", 0),
            }
            for r in revisions
        ],
        "accepted": bool(run["accepted"]),
        "keep_reason": run["keep_reason"] if run["accepted"] else None,
        "error": db.loads(run["error_json"]),
    }


@router.post("", status_code=201)
def create(body: RunCreate):
    check_lang(body.lang)
    with db.session() as conn:
        fetch_dataset(conn, body.dataset_id)
    dataset = dataset_json(body.dataset_id, full=False)
    if not dataset["ready"]:
        raise ApiError(
            409, "conflict", "The dataset needs an input file and at least one expected output."
        )
    run_id = pipeline.create_run(body.lang, body.filename, body.source, body.dataset_id)
    return {"run_id": run_id}


@router.get("")
def history(limit: int = 50, offset: int = 0):
    limit = max(1, min(limit, 200))
    offset = max(0, offset)
    items = []
    with db.session() as conn:
        total = conn.execute("select count(*) from runs").fetchone()[0]
        runs = conn.execute(
            "select * from runs order by created_at desc, rowid desc limit ? offset ?",
            (limit, offset),
        ).fetchall()
        for run in runs:
            revisions = load_revisions(conn, run["id"])
            summary = revisions[-1]["summary"] if revisions else {}
            input_row = conn.execute(
                "select filename from dataset_files where dataset_id = ? and kind = 'input'",
                (run["dataset_id"],),
            ).fetchone()
            items.append(
                {
                    "id": run["id"],
                    "created_at": run["created_at"],
                    "filename": run["filename"],
                    "lang": run["lang"],
                    "status": run["status"],
                    "state": state_of(bool(run["accepted"]), revisions),
                    "matched": summary.get("matched", 0),
                    "total": summary.get("total", 0),
                    "input_name": input_row["filename"] if input_row else None,
                }
            )
    return {"items": items, "total": total}


@router.get("/{run_id}/events")
def events(run_id: str, request: Request):
    last = request.headers.get("last-event-id", "")
    after = int(last) if last.isdigit() else 0
    buffer = pipeline.BUFFERS.get(run_id)
    if buffer is None:
        buffer = pipeline.synthesize_events(run_id)
    return StreamingResponse(
        buffer.stream(after),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@router.post("/{run_id}/cancel")
def cancel(run_id: str):
    pipeline.cancel_run(run_id)
    return {"ok": True}


@router.get("/{run_id}/python")
def python_file(run_id: str):
    data = run_json(run_id)
    if data["current"] is None:
        raise not_found("This run has no Python yet.")
    stem = data["filename"].rsplit(".", 1)[0] or "program"
    return Response(
        data["current"]["python"],
        media_type="text/x-python",
        headers={"Content-Disposition": f'attachment; filename="{stem}.py"'},
    )


def export_source(run_id):
    data = run_json(run_id)
    if data["current"] is None or data["dataset"]["input"] is None:
        raise ApiError(409, "conflict", "This run has no report to export.")
    with db.session() as conn:
        data["updated_at"] = pipeline.load_run(conn, run_id)["updated_at"]
    return data


@router.get("/{run_id}/export")
def export_view(run_id: str):
    return export.build_signed_json(export_source(run_id))


@router.get("/{run_id}/export.json")
def export_json(run_id: str):
    data = export_source(run_id)
    stem = export.file_stem(data["filename"])
    return JSONResponse(
        export.build_signed_json(data),
        headers={"Content-Disposition": f'attachment; filename="{stem}-report.json"'},
    )


@router.get("/{run_id}/export.html")
def export_html(run_id: str, inline: int = 0):
    data = export_source(run_id)
    headers = {}
    if not inline:
        stem = export.file_stem(data["filename"])
        headers["Content-Disposition"] = f'attachment; filename="{stem}-report.html"'
    return Response(export.build_html(data), media_type="text/html", headers=headers)


@router.get("/{run_id}/export.pdf")
def export_pdf(run_id: str, inline: int = 0):
    data = export_source(run_id)
    headers = {}
    if not inline:
        stem = export.file_stem(data["filename"])
        headers["Content-Disposition"] = f'attachment; filename="{stem}-report.pdf"'
    return Response(
        pdf_report.build_pdf(export.build_signed_json(data)),
        media_type="application/pdf",
        headers=headers,
    )


@router.post("/{run_id}/fix")
def fix(run_id: str):
    pipeline.apply_fix(run_id)
    return run_json(run_id)


@router.post("/{run_id}/keep")
def keep(run_id: str, body: KeepBody):
    reason = (body.reason or "").strip()
    if not reason or len(reason) > 1000:
        raise ApiError(422, "invalid_reason", "Say why this difference is acceptable.")
    current = run_json(run_id)
    pipeline.keep_run(run_id, current["state"], reason)
    return run_json(run_id)


@router.post("/{run_id}/undo")
def undo(run_id: str):
    pipeline.undo_run(run_id)
    return run_json(run_id)


@router.get("/{run_id}")
def get_run(run_id: str):
    return run_json(run_id)


@router.delete("/{run_id}")
def delete(run_id: str):
    pipeline.delete_run(run_id)
    return {"ok": True}
