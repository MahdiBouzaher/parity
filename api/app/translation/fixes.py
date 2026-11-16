import os
import re

from .patch import PatchError, apply_patch
from .rules import classify, flag_python
from .types import Explanation, Hunk, Patch

NO_KEY_NOTE = "The translation model is not configured, so there is no explanation for this difference. Add its key in the environment settings to get one."
NO_ANSWER_NOTE = "No explanation could be written for this difference."


def none_note():
    return NO_ANSWER_NOTE if os.environ.get("OPENROUTER_API_KEY", "").strip() else NO_KEY_NOTE
HELPER = [
    "def round_half_up(s, n):",
    "    q = 10 ** n",
    "    return np.sign(s) * np.floor(np.abs(s) * q + 0.5 + 1e-9) / q",
]
REF = re.compile(r'(\w+)\["(\w+)"\]')


def ordinal(n):
    if 10 <= n % 100 <= 20:
        return f"{n}th"
    return f"{n}" + {1: "st", 2: "nd", 3: "rd"}.get(n % 10, "th")


def lower_first(text):
    return text[:1].lower() + text[1:]


def to_int(text):
    try:
        return int(float(str(text).replace(",", "")))
    except (TypeError, ValueError):
        return None


def first_diff_decimal(a, b):
    a, b = str(a), str(b)
    if "e" in a.lower() or "e" in b.lower() or "." not in a or "." not in b:
        return None
    fa, fb = a.split(".")[1], b.split(".")[1]
    size = max(len(fa), len(fb))
    fa, fb = fa.ljust(size, "0"), fb.ljust(size, "0")
    for i in range(size):
        if fa[i] != fb[i]:
            return i + 1
    return None


def title_for(checks):
    pick = next((c for c in checks if c.get("kind") == "stat" or ".stat." in str(c.get("id", ""))), checks[0])
    label = str(pick.get("label", "values"))
    plural = pick.get("kind") in ("cells", "columns") or label.lower() in ("cells", "columns")
    return f"Why the {lower_first(label)} {'differ' if plural else 'differs'}"


def table_rows(cells, ctx):
    table = cells.get("table")
    compared = cells.get("compared")
    if ctx is not None and compared and table in ctx.expected_tables and ctx.expected_tables[table]:
        return compared // len(ctx.expected_tables[table])
    return None


def rounding_paragraph(checks, ctx):
    stat = next((c for c in checks if c.get("column") and ".stat." in str(c.get("id", ""))), None)
    cells = next((c for c in checks if str(c.get("id", "")).endswith(".cells")), None)
    column = stat.get("column") if stat else None
    n = m = d = None
    if cells:
        mism = cells.get("mismatches") or []
        if column is None and mism:
            column = mism[0].get("column")
        in_col = [x for x in mism if str(x.get("column", "")).lower() == str(column).lower()]
        if not in_col and mism:
            column = mism[0].get("column")
            in_col = [x for x in mism if x.get("column") == column]
        count = cells.get("mismatch_count")
        if mism and count is not None and in_col:
            n = len(in_col) if count <= len(mism) else round(count * len(in_col) / len(mism))
            d = first_diff_decimal(in_col[0].get("expected"), in_col[0].get("actual"))
        m = table_rows(cells, ctx)
    column = column or "the result"
    if n is None:
        return f"Some values in {column} differ in the last decimals."
    where = f"at the {ordinal(d)} decimal" if d else "in the last decimals"
    if m:
        return f"{n:,} of {m:,} values in {column} differ {where}."
    return f"{n:,} values in {column} differ {where}."


def referenced_input_column(python, analysis, ctx):
    flagged = [r for r in flag_python(python, analysis) if r.tag == "missing values"]
    lines = python.split("\n")
    assigned = set()
    for i, text in enumerate(lines):
        if flagged and i + 1 == flagged[0].line:
            refs = [c for _, c in REF.findall(text.split("=", 1)[-1])]
            known = [c for c in refs if ctx is not None and c in ctx.input_columns]
            pool = known or [c for c in refs if c not in assigned]
            if pool:
                return pool[0]
        m = re.match(r'\s*\w+\["(\w+)"\]\s*=', text)
        if m:
            assigned.add(m.group(1))
    return None


def missing_paragraph(checks, python, analysis, ctx):
    nulls = next((c for c in checks if str(c.get("id", "")).endswith(".nulls")), None)
    cells = next((c for c in checks if str(c.get("id", "")).endswith(".cells")), None)
    column = referenced_input_column(python, analysis, ctx) or "value"
    n = None
    if nulls:
        a, b = to_int(nulls.get("expected")), to_int(nulls.get("actual"))
        if a is not None and b is not None:
            n = abs(a - b)
    m = table_rows(cells, ctx) if cells else None
    if n is None:
        return f"Some rows have a blank {column}."
    if m:
        return f"{n:,} of {m:,} rows have a blank {column}."
    return f"{n:,} rows have a blank {column}."


def rule_explanation(failing_checks, python, analysis, ctx=None, total=None):
    tag = classify(failing_checks, python, analysis) if failing_checks else None
    if tag == "missing values" and analysis.lang != "vba":
        tag = None
    if tag not in ("rounding", "missing values"):
        return Explanation("none", None, "No explanation available", [], none_note(), "")
    count = f"All {total} checks match." if total else "All checks match."
    if tag == "rounding":
        return Explanation(
            "rules",
            tag,
            title_for(failing_checks),
            [
                "SAS rounds a tie away from zero. pandas rounds a tie to the nearest even digit.",
                rounding_paragraph(failing_checks, ctx),
            ],
            "Applying the fix switches the translation to round half up and runs it again.",
            f"{count} The translation now uses a round half up helper, the same rule SAS applies.",
        )
    return Explanation(
        "rules",
        tag,
        title_for(failing_checks),
        ["VBA counts a blank cell as zero. pandas skips it.", missing_paragraph(failing_checks, python, analysis, ctx)],
        "Applying the fix fills blank cells with 0 before the arithmetic and runs it again.",
        f"{count} The translation now treats blank cells as zero, the same rule VBA applies.",
    )


def replace_line(i, old, new):
    return Hunk(i + 1, [old], [new])


def round_fix(python):
    lines = python.split("\n")
    hunks = []
    idx = [i for i, t in enumerate(lines) if re.search(r"\.round\(\d+\)", t)]
    if not idx:
        return None
    imports = [i for i, t in enumerate(lines) if re.match(r"(import|from)\s", t)]
    has_np = any(re.match(r"import numpy as np\s*$", t) for t in lines)
    pd_line = next((i for i, t in enumerate(lines) if re.match(r"import pandas as pd\s*$", t)), None)
    if not has_np:
        hunks.append(Hunk((pd_line if pd_line is not None else 0) + 1, [], ["import numpy as np"]))
    last = imports[-1] if imports else -1
    if last + 1 < len(lines) and lines[last + 1].strip() == "":
        hunks.append(Hunk(last + 3, [], HELPER + [""]))
    else:
        hunks.append(Hunk(last + 2, [], [""] + HELPER + [""]))
    for i in idx:
        new = re.sub(r"\.round\((\d+)\)", r".pipe(round_half_up, \1)", lines[i])
        hunks.append(replace_line(i, lines[i], new))
    return Patch("Round half up like SAS.", hunks)


def missing_fix(python, analysis):
    flagged = [r.line for r in flag_python(python, analysis) if r.tag == "missing values"]
    lines = python.split("\n")
    hunks = []
    for n in flagged:
        i = n - 1
        m = re.match(r'(\s*)(\w+)\["(\w+)"\]\s*=\s*(.*)$', lines[i])
        if not m:
            continue
        assigned = {m.group(3)}
        for t in lines[:i]:
            a = re.match(r'\s*\w+\["(\w+)"\]\s*=', t)
            if a:
                assigned.add(a.group(1))
        head, rhs = lines[i].split("=", 1)
        last = i
        if rhs.strip().endswith("("):
            j = i + 1
            while j < len(lines) and not lines[j].strip().startswith(")"):
                j += 1
            last = j - 1
        for k in range(i, last + 1):
            text = lines[k]
            prefix, body = (head + "=", rhs) if k == i else ("", text)

            new_body = re.sub(
                r'(\w+)\["(\w+)"\](?!\.fillna)',
                lambda mm: mm.group(0) if mm.group(2) in assigned else mm.group(0) + ".fillna(0)",
                body,
            )
            new = prefix + new_body
            if new != text:
                hunks.append(replace_line(k, text, new))
    if not hunks:
        return None
    return Patch("Treat blank cells as zero like VBA.", hunks)


def rule_fix(python, analysis, failing_checks=None, tag=None):
    if tag is None and failing_checks:
        tag = classify(failing_checks, python, analysis)
    patch = None
    if tag == "rounding":
        patch = round_fix(python)
    elif tag == "missing values" and analysis.lang == "vba":
        patch = missing_fix(python, analysis)
    if patch is None:
        return None
    try:
        apply_patch(python, patch)
    except PatchError:
        return None
    return patch
