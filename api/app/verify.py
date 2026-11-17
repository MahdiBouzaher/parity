import io
import json

from fastapi import APIRouter, File, UploadFile
from pypdf import PdfReader

from . import signing
from .errors import ApiError
from .hashing import canonical_sha256

router = APIRouter(prefix="/api")

MAX_BYTES = 20 * 1024 * 1024
NOT_SIGNED = "This file is not a signed Parity report."


def not_signed():
    return ApiError(422, "unreadable_report", NOT_SIGNED)


def extract_report(data):
    try:
        if data[:5] == b"%PDF-":
            attachments = PdfReader(io.BytesIO(data)).attachments
            payloads = attachments.get("parity-report.json")
            if not payloads:
                raise ValueError
            report = json.loads(payloads[0].decode("utf-8"))
        else:
            report = json.loads(data.decode("utf-8-sig"))
    except Exception:
        raise not_signed()
    if not isinstance(report, dict) or not isinstance(report.get("signature"), dict):
        raise not_signed()
    return report


def inner_hash_ok(report):
    claimed = report.get("report_sha256")
    inner = {k: v for k, v in report.items() if k not in ("signature", "signed_at", "report_sha256")}
    return isinstance(claimed, str) and canonical_sha256(inner) == claimed


def field(obj, *path):
    for key in path:
        if not isinstance(obj, dict):
            return None
        obj = obj.get(key)
    return obj


def text_or_none(value):
    return value if isinstance(value, str) else None


def int_or_none(value):
    return value if isinstance(value, int) and not isinstance(value, bool) else None


@router.post("/verify")
async def verify(file: UploadFile = File(...)):
    data = await file.read(MAX_BYTES + 1)
    if len(data) > MAX_BYTES:
        raise ApiError(413, "too_large", "This file is larger than 20 MB.")
    report = extract_report(data)
    ok, reason, fingerprint = signing.verify_report(report)
    if ok and not inner_hash_ok(report):
        ok, reason = False, "The report hash does not match the report content."
    block = report["signature"]
    if fingerprint is None:
        fingerprint = text_or_none(block.get("key_fingerprint"))
    return {
        "status": "valid" if ok else "modified",
        "this_instance": bool(fingerprint == signing.local_fingerprint()),
        "signed_at": text_or_none(report.get("signed_at")),
        "key_fingerprint": fingerprint,
        "filename": text_or_none(field(report, "program", "filename")),
        "matched": int_or_none(field(report, "result", "matched")),
        "total": int_or_none(field(report, "result", "total")),
        "state": text_or_none(field(report, "result", "state")),
        "keep_reason": text_or_none(field(report, "result", "keep_reason")),
        "reason": reason,
    }
