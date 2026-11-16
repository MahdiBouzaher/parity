import io
import re
import shutil
from pathlib import Path

import pandas as pd
from fastapi import APIRouter, File, Form, UploadFile
from pandas.api import types as ptypes
from pandas.errors import EmptyDataError

from . import config, db
from .errors import ApiError, bad_request, not_found
from .hashing import sha256_bytes
from .schemas import SampleCreate, TolerancesUpdate

router = APIRouter(prefix="/api/datasets")
samples_router = APIRouter(prefix="/api")

LANGS = {
    "sas": ("loss_provision.sas", "sas"),
    "vba": ("loss_provision.bas", "vba"),
}


def bad_csv(message):
    return ApiError(400, "bad_csv", message)


def check_lang(lang):
    if lang not in LANGS:
        raise ApiError(400, "bad_lang", "The language must be sas or vba.")


def table_name(raw):
    name = re.sub(r"[^a-z0-9]+", "_", raw.lower()).strip("_")
    return name or "table"


def parse_csv(data):
    if len(data) > config.MAX_UPLOAD_BYTES:
        raise ApiError(413, "too_large", "This file is larger than 10 MB.")
    if not data.strip():
        raise bad_csv("This file has no header row.")
    try:
        frame = pd.read_csv(io.BytesIO(data))
    except EmptyDataError:
        raise bad_csv("This file has no header row.")
    except (pd.errors.ParserError, UnicodeDecodeError, ValueError):
        raise bad_csv("This file is not a valid CSV.")
    if len(frame.columns) == 0:
        raise bad_csv("This file has no header row.")
    if len(frame) > config.MAX_ROWS:
        raise ApiError(413, "too_large", "This file has more than 200,000 rows.")
    return frame


def dtype_name(series):
    if ptypes.is_bool_dtype(series):
        return "text"
    if ptypes.is_integer_dtype(series):
        return "int"
    if ptypes.is_float_dtype(series):
        return "float"
    return "text"


def describe_file(path, frame=None):
    if frame is None:
        frame = pd.read_csv(path)
    head = pd.read_csv(path, dtype=str, keep_default_na=False, nrows=8)
    preview = [[cell if cell != "" else None for cell in row] for row in head.values.tolist()]
    columns = [{"name": str(name), "dtype": dtype_name(frame[name])} for name in frame.columns]
    return columns, preview


def dataset_dir(dataset_id):
    return config.DATASETS_DIR / dataset_id


def fetch_dataset(conn, dataset_id):
    row = conn.execute("select * from datasets where id = ?", (dataset_id,)).fetchone()
    if row is None:
        raise not_found("This dataset does not exist.")
    return row


def file_rows(conn, dataset_id):
    return conn.execute(
        "select * from dataset_files where dataset_id = ? order by kind, seq, rowid",
        (dataset_id,),
    ).fetchall()


def dataset_json(dataset_id, full=True):
    with db.session() as conn:
        row = fetch_dataset(conn, dataset_id)
        files = file_rows(conn, dataset_id)
    input_file = None
    expected = []
    for item in files:
        entry = {"name": item["filename"], "rows": item["rows"], "sha256": item["sha256"]}
        if full:
            columns, preview = describe_file(item["path"])
            entry["columns"] = columns
            entry["preview"] = preview
        if item["kind"] == "input":
            input_file = entry
        else:
            expected.append({"table": item["table_name"], **entry})
    result = {
        "id": dataset_id,
        "ready": input_file is not None and len(expected) > 0,
        "input": input_file,
        "expected": expected,
        "tolerances": db.loads(row["tolerances_json"], {}),
    }
    return result


def create_dataset(lang=None):
    dataset_id = db.new_id()
    dataset_dir(dataset_id).mkdir(parents=True, exist_ok=True)
    with db.session() as conn:
        conn.execute(
            "insert into datasets (id, created_at, lang, tolerances_json) values (?, ?, ?, '{}')",
            (dataset_id, db.now_iso(), lang),
        )
    return dataset_id


def store_file(dataset_id, kind, name, filename, data):
    frame = parse_csv(data)
    base = dataset_dir(dataset_id)
    if kind == "input":
        path = base / "input.csv"
    else:
        (base / "expected").mkdir(parents=True, exist_ok=True)
        path = base / "expected" / f"{name}.csv"
    path.write_bytes(data)
    with db.session() as conn:
        fetch_dataset(conn, dataset_id)
        previous = conn.execute(
            "select seq from dataset_files where dataset_id = ? and kind = ? and table_name = ?",
            (dataset_id, kind, name),
        ).fetchone()
        if previous is None:
            top = conn.execute(
                "select coalesce(max(seq), 0) from dataset_files where dataset_id = ? and kind = ?",
                (dataset_id, kind),
            ).fetchone()[0]
            seq = top + 1
        else:
            seq = previous["seq"]
        conn.execute(
            "insert or replace into dataset_files "
            "(dataset_id, kind, table_name, filename, rows, sha256, path, seq) values (?, ?, ?, ?, ?, ?, ?, ?)",
            (dataset_id, kind, name, filename, len(frame), sha256_bytes(data), str(path), seq),
        )


def ensure_exists(dataset_id):
    with db.session() as conn:
        fetch_dataset(conn, dataset_id)


@router.post("", status_code=201)
def create_empty(payload: dict | None = None):
    return dataset_json(create_dataset())


@router.post("/sample", status_code=201)
def create_sample(body: SampleCreate):
    check_lang(body.lang)
    filename, folder = LANGS[body.lang]
    dataset_id = create_dataset(body.lang)
    loans = config.SAMPLES_DIR / "loans.csv"
    store_file(dataset_id, "input", "input", loans.name, loans.read_bytes())
    for path in sorted((config.SAMPLES_DIR / folder / "expected").glob("*.csv")):
        store_file(dataset_id, "expected", table_name(path.stem), path.name, path.read_bytes())
    return dataset_json(dataset_id)


@router.get("/{dataset_id}")
def get_dataset(dataset_id: str):
    return dataset_json(dataset_id)


@router.put("/{dataset_id}/input")
async def put_input(dataset_id: str, file: UploadFile = File(...)):
    ensure_exists(dataset_id)
    data = await file.read()
    store_file(dataset_id, "input", "input", file.filename or "input.csv", data)
    return dataset_json(dataset_id)


@router.post("/{dataset_id}/expected")
async def add_expected(
    dataset_id: str, file: UploadFile = File(...), table: str | None = Form(None)
):
    ensure_exists(dataset_id)
    data = await file.read()
    filename = file.filename or "expected.csv"
    name = table_name(table if table else Path(filename).stem)
    store_file(dataset_id, "expected", name, filename, data)
    return dataset_json(dataset_id)


@router.delete("/{dataset_id}/expected/{table}")
def delete_expected(dataset_id: str, table: str):
    with db.session() as conn:
        fetch_dataset(conn, dataset_id)
        row = conn.execute(
            "select path from dataset_files where dataset_id = ? and kind = 'expected' and table_name = ?",
            (dataset_id, table),
        ).fetchone()
        if row is None:
            raise not_found("This expected output does not exist.")
        conn.execute(
            "delete from dataset_files where dataset_id = ? and kind = 'expected' and table_name = ?",
            (dataset_id, table),
        )
    Path(row["path"]).unlink(missing_ok=True)
    return dataset_json(dataset_id)


@router.put("/{dataset_id}/tolerances")
def put_tolerances(dataset_id: str, body: TolerancesUpdate):
    cleaned = {}
    for key, value in body.tolerances.items():
        if value < 0 or value != value:
            raise bad_request("Tolerances must be zero or larger.")
        cleaned[key.strip().lower()] = value
    with db.session() as conn:
        fetch_dataset(conn, dataset_id)
        conn.execute(
            "update datasets set tolerances_json = ? where id = ?", (db.dumps(cleaned), dataset_id)
        )
    return dataset_json(dataset_id)


@samples_router.get("/samples")
def list_samples():
    result = []
    for lang, (filename, folder) in LANGS.items():
        source = (config.SAMPLES_DIR / folder / filename).read_text(encoding="utf-8")
        expected = [p.name for p in sorted((config.SAMPLES_DIR / folder / "expected").glob("*.csv"))]
        result.append(
            {
                "lang": lang,
                "filename": filename,
                "source": source,
                "input_name": "loans.csv",
                "expected": expected,
            }
        )
    return result


def load_run_inputs(dataset_id):
    with db.session() as conn:
        row = fetch_dataset(conn, dataset_id)
        files = file_rows(conn, dataset_id)
    input_file = next((f for f in files if f["kind"] == "input"), None)
    expected = [f for f in files if f["kind"] == "expected"]
    return row, input_file, expected


def delete_dataset_files(dataset_id):
    shutil.rmtree(dataset_dir(dataset_id), ignore_errors=True)
