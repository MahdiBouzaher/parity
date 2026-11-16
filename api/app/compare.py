import math

import numpy as np
import pandas as pd
from pandas.api import types as ptypes

STATS = ["sum", "mean", "min", "max", "nulls"]
STAT_LABELS = {
    "sum": "Sum of {}",
    "mean": "Mean of {}",
    "min": "Min of {}",
    "max": "Max of {}",
    "nulls": "Null count in {}",
}


def is_number(value):
    return isinstance(value, (int, float, np.integer, np.floating)) and not isinstance(value, bool)


def is_nan(value):
    return value is None or (isinstance(value, (float, np.floating)) and math.isnan(value))


def fmt(value):
    if is_nan(value):
        return "blank"
    if isinstance(value, (bool, np.bool_)):
        return "true" if value else "false"
    if isinstance(value, (int, np.integer)):
        return f"{int(value):,}"
    if isinstance(value, (float, np.floating)):
        text = f"{float(value):,.6f}"
        whole, _, frac = text.partition(".")
        frac = frac.rstrip("0")
        if len(frac) < 2:
            frac = frac.ljust(2, "0")
        return f"{whole}.{frac}"
    return str(value)


def fmt_pair(expected, actual):
    left, right = fmt(expected), fmt(actual)
    if left == right and not is_nan(expected) and not is_nan(actual) and expected != actual:
        if is_number(expected) and is_number(actual):
            left, right = format(float(expected), ".10g"), format(float(actual), ".10g")
            if left == right:
                left, right = repr(float(expected)), repr(float(actual))
    return left, right


def fmt_delta(expected, actual):
    if not (is_number(expected) and is_number(actual)) or is_nan(expected) or is_nan(actual):
        return None
    diff = actual - expected
    if diff == 0:
        return "0"
    sign = "+" if diff > 0 else "-"
    magnitude = abs(diff)
    text = fmt(magnitude)
    if is_number(magnitude) and float(text.replace(",", "")) == 0:
        text = format(float(magnitude), ".6g")
    return sign + text


def tol_text(value):
    return "exact" if value == 0 else format(value, "g")


def make(check_id, label, kind, table, column, status, expected, actual, **extra):
    check = {
        "id": check_id,
        "label": label,
        "kind": kind,
        "table": table,
        "column": column,
        "status": status,
        "expected": expected,
        "actual": actual,
        "tolerance": "exact",
        "delta": None,
        "details": None,
        "mismatch_count": None,
        "compared": None,
        "mismatches": [],
    }
    check.update(extra)
    return check


def numeric_columns(frame):
    return [
        c
        for c in frame.columns
        if ptypes.is_numeric_dtype(frame[c]) and not ptypes.is_bool_dtype(frame[c])
    ]


def stat_value(series, stat):
    numeric = series if ptypes.is_numeric_dtype(series) else pd.to_numeric(series, errors="coerce")
    if stat == "nulls":
        return int(numeric.isna().sum())
    integer = ptypes.is_integer_dtype(numeric)
    if stat == "sum":
        value = numeric.sum()
    elif stat == "mean":
        value = numeric.mean()
    elif stat == "min":
        value = numeric.min()
    else:
        value = numeric.max()
    if integer and stat != "mean" and not is_nan(value):
        return int(value)
    return float(value)


def stats_match(expected, actual, tolerance):
    if is_nan(expected) and is_nan(actual):
        return True
    if is_nan(expected) or is_nan(actual):
        return False
    if tolerance == 0:
        return actual == expected
    return abs(actual - expected) <= tolerance


def cell_mismatches(exp_col, act_col, tolerance):
    both_na = exp_col.isna() & act_col.isna()
    if ptypes.is_numeric_dtype(exp_col) and ptypes.is_numeric_dtype(act_col):
        if tolerance == 0:
            same = exp_col == act_col
        else:
            same = (exp_col - act_col).abs() <= tolerance
    else:
        same = exp_col.astype(str) == act_col.astype(str)
    return ~(same | both_na)


def compare(expected, actual, tolerances, input_columns):
    checks = []
    multi = len(expected) > 1
    for table, exp in expected.items():
        suffix = f" in {table}" if multi else ""
        act = actual.get(table)
        emap = {str(c).lower(): c for c in exp.columns}

        def tol_for(column):
            return float(tolerances.get(f"{table}.{column}".lower(), 0) or 0)

        n_exp = len(exp)
        if act is None:
            checks.append(
                make(
                    f"{table}.rows",
                    "Row count" + suffix,
                    "rows",
                    table,
                    None,
                    "differs",
                    fmt(n_exp),
                    "missing",
                )
            )
            checks.append(
                make(
                    f"{table}.columns",
                    "Columns" + suffix,
                    "columns",
                    table,
                    None,
                    "differs",
                    f"{len(exp.columns)} columns",
                    "missing",
                    details=f"The Python did not produce a table named {table}.",
                )
            )
            continue

        amap = {str(c).lower(): c for c in act.columns}
        n_act = len(act)
        rows_equal = n_exp == n_act
        checks.append(
            make(
                f"{table}.rows",
                "Row count" + suffix,
                "rows",
                table,
                None,
                "match" if rows_equal else "differs",
                fmt(n_exp),
                fmt(n_act),
                delta=None if rows_equal else fmt_delta(n_exp, n_act),
            )
        )

        missing = [str(emap[k]) for k in emap if k not in amap]
        extra = [str(amap[k]) for k in amap if k not in emap]
        parts = []
        if missing:
            parts.append("missing in Python: " + ", ".join(missing))
        if extra:
            parts.append("extra in Python: " + ", ".join(extra))
        columns_equal = not missing and not extra
        checks.append(
            make(
                f"{table}.columns",
                "Columns" + suffix,
                "columns",
                table,
                None,
                "match" if columns_equal else "differs",
                f"{len(exp.columns)} columns",
                f"{len(act.columns)} columns",
                details=". ".join(parts) if parts else None,
            )
        )

        numeric = numeric_columns(exp)
        stat_columns = [c for c in numeric if str(c).lower() not in input_columns] or numeric
        for column in stat_columns:
            key = str(column).lower()
            tol = tol_for(key)
            for stat in STATS:
                check_id = f"{table}.stat.{column}.{stat}"
                label = STAT_LABELS[stat].format(column) + suffix
                e_val = stat_value(exp[column], stat)
                if key not in amap:
                    checks.append(
                        make(
                            check_id,
                            label,
                            "stat",
                            table,
                            str(column),
                            "differs",
                            fmt(e_val),
                            "missing",
                        )
                    )
                    continue
                a_val = stat_value(act[amap[key]], stat)
                allowed = 0.0 if stat == "nulls" else (tol * n_exp if stat == "sum" else tol)
                ok = stats_match(e_val, a_val, allowed)
                left, right = fmt_pair(e_val, a_val)
                checks.append(
                    make(
                        check_id,
                        label,
                        "stat",
                        table,
                        str(column),
                        "match" if ok else "differs",
                        left,
                        right,
                        tolerance=tol_text(0.0 if stat == "nulls" else tol),
                        delta=None if ok else fmt_delta(e_val, a_val),
                    )
                )

        common = [k for k in emap if k in amap]
        n = min(n_exp, n_act)
        compared = n * len(common)
        mismatch_count = 0
        mismatches = []
        first = None
        if common and n:
            cols = {}
            for k in common:
                cols[k] = cell_mismatches(
                    exp[emap[k]].iloc[:n].reset_index(drop=True),
                    act[amap[k]].iloc[:n].reset_index(drop=True),
                    tol_for(k),
                )
            matrix = np.column_stack([cols[k].to_numpy() for k in common])
            mismatch_count = int(matrix.sum())
            for r, c in np.argwhere(matrix)[:20]:
                k = common[c]
                e_cell = exp[emap[k]].iloc[r]
                a_cell = act[amap[k]].iloc[r]
                left, right = fmt_pair(
                    e_cell.item() if hasattr(e_cell, "item") else e_cell,
                    a_cell.item() if hasattr(a_cell, "item") else a_cell,
                )
                mismatches.append(
                    {
                        "row": int(r) + 1,
                        "column": str(emap[k]),
                        "expected": left,
                        "actual": right,
                    }
                )
            if mismatches:
                first = mismatches[0]
        notes = []
        if mismatch_count:
            notes.append(
                f"{mismatch_count:,} of {compared:,} cells differ. First at row {first['row']}, "
                f"column {first['column']}: {first['expected']} expected, {first['actual']} actual."
            )
        if not rows_equal:
            notes.append(f"Row counts differ, so cells were compared over the first {n:,} rows.")
        if not columns_equal:
            notes.append("Column sets differ, so cells were compared over the shared columns.")
        cells_equal = mismatch_count == 0 and rows_equal and columns_equal
        any_tol = any(tol_for(k) > 0 for k in common)
        checks.append(
            make(
                f"{table}.cells",
                "Cells" + suffix,
                "cells",
                table,
                None,
                "match" if cells_equal else "differs",
                f"{compared:,} cells",
                f"{compared - mismatch_count:,} cells",
                tolerance="custom" if any_tol else "exact",
                details=" ".join(notes) if notes else None,
                mismatch_count=mismatch_count,
                compared=compared,
                mismatches=mismatches,
            )
        )
    return checks
