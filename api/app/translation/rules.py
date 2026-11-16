import re

from .common import PYTHON_REASONS
from .sas_rules import analyze_sas
from .types import Analysis, RiskyLine
from .vba_rules import analyze_vba

PY_PATTERNS = [
    ("rounding", re.compile(r"\.round\(|np\.round|np\.around|(?<![\w.])round\(")),
    ("sort order", re.compile(r"sort_values|sort_index|\.sort\(")),
    ("integer division", re.compile(r"//")),
    ("dates", re.compile(r"to_datetime|\bdatetime\b|strptime|\.dt\.|date_range|Timestamp|pd\.Period")),
]


def analyze(code, lang):
    key = (lang or "").lower()
    if key == "sas":
        return analyze_sas(code)
    if key == "vba":
        return analyze_vba(code)
    raise ValueError("Language must be sas or vba.")


def flag_python(python, analysis):
    lines = python.split("\n")
    found = []

    def add(n, tag):
        if not any(r.line == n and r.tag == tag for r in found):
            found.append(RiskyLine(n, tag, PYTHON_REASONS[tag]))

    for i, text in enumerate(lines, 1):
        if text.lstrip().startswith("raise NotImplementedError"):
            continue
        for tag, pat in PY_PATTERNS:
            if pat.search(text):
                add(i, tag)
    stripped = [t.strip() for t in lines]
    for r in analysis.risky_lines:
        if r.tag != "missing values":
            continue
        for h in analysis.hints:
            if h.line == r.line and h.python:
                first = h.python.split("\n")[0].strip()
                if first in stripped:
                    add(stripped.index(first) + 1, "missing values")
    return sorted(found, key=lambda r: (r.line, r.tag))


def classify(failing_checks, python, analysis):
    if not failing_checks:
        return None
    tags = {r.tag for r in analysis.risky_lines}
    ids = [str(c.get("id", "")) for c in failing_checks]
    nulls = [c for c in failing_checks if str(c.get("id", "")).endswith(".nulls")]
    if nulls and "missing values" in tags:
        return "missing values"
    if "rounding" in tags and ".round(" in python and any(
        ".stat." in i or i.endswith(".cells") for i in ids
    ):
        return "rounding"
    if "missing values" in tags and nulls:
        return "missing values"
    structural = any(i.endswith(".rows") or i.endswith(".cells") for i in ids)
    if "sort order" in tags and structural:
        return "sort order"
    if "integer division" in tags and structural:
        return "integer division"
    if "dates" in tags and structural:
        return "dates"
    return None
