import json

LANG_NAMES = {"sas": "SAS", "vba": "Excel VBA"}

CONVENTION = """Follow these conventions exactly.
1. Read the input with pd.read_csv("input.csv"). For SAS, assign it to the name of the dataset used in the first SET statement. For VBA, assign it to df.
2. Every table the original program produced must be a module-level pandas DataFrame whose variable name equals the expected table name.
3. Import only numpy, pandas and these standard modules: math, decimal, datetime, re, statistics, itertools, functools, collections, typing, calendar, string, fractions, json.
4. Do not print results and do not write files.
5. Answer with the Python file only, with no explanation and no code fences."""

TRANSLATE_SYSTEM = (
    "You translate programs into Python with pandas. Translate each statement in the plain, idiomatic pandas way. "
    "Use Series.round for rounding, use the pandas default for missing values, sums and means, and use sort_values for sorting. "
    "Do not try to reproduce special behaviour of the original language, and do not add workarounds for differences in rounding, blanks, missing values, sort order or dates. "
    "A later check compares the output with the original and handles those differences. "
    "If a statement has no direct pandas form, write raise NotImplementedError with the original line as its message.\n\n"
    + CONVENTION
)

EXPLAIN_SYSTEM = (
    "You explain why a Python translation of a SAS program or Excel VBA macro gives different numbers than the original. "
    "Write for a risk or finance analyst. Use short plain sentences, active voice, no em dashes and no exclamation marks. "
    "Answer with one JSON object and nothing else, with these keys: "
    '"tag" (one of "rounding", "missing values", "sort order", "integer division", "dates", or null), '
    '"title" (for example "Why the sum of rate differs"), '
    '"paragraphs" (a list of one or two short strings that name the cause and give real numbers from the checks), '
    '"note" (one sentence that starts with "Applying the fix" and says what the fix changes), '
    '"fixed_body" (one or two sentences for the moment the fix has made every check match).'
)

FIX_SYSTEM = (
    "You repair a Python translation so that its output matches the original program. "
    "Answer with one JSON object and nothing else: "
    '{"summary": "one short sentence", "hunks": [{"start": 12, "remove": ["exact old line"], "add": ["new line"]}]}. '
    "start is the 1-based line number of the first removed line, counted in the numbered code you are given. "
    "remove lists the exact lines to replace, copied without the line numbers, and may be empty to insert before start. "
    "Hunks must not overlap. Change as little as possible. Keep the run conventions: pandas and numpy only, module-level tables, no printing, no file output."
)


def numbered(text):
    return "\n".join(f"{i:>3}  {line}" for i, line in enumerate(text.split("\n"), 1))


def compact_checks(checks):
    keep = ("id", "label", "kind", "table", "column", "expected", "actual", "tolerance", "delta", "details", "mismatch_count", "compared")
    out = []
    for c in checks:
        item = {k: c.get(k) for k in keep if c.get(k) is not None}
        item["mismatches"] = (c.get("mismatches") or [])[:8]
        out.append(item)
    return json.dumps(out, indent=1)


def translate_messages(code, lang, analysis, ctx):
    hints = "\n".join(f"- line {h.line}: {h.text}" + (f" -> {h.python}" if h.python else "") for h in analysis.hints)
    tables = json.dumps(ctx.expected_tables)
    user = (
        f"Translate this {LANG_NAMES.get(lang, lang)} program ({ctx.filename}) into Python.\n\n"
        f"Input columns: {', '.join(ctx.input_columns)}\n"
        f"Input dtypes: {json.dumps(ctx.input_dtypes)}\n"
        f"Expected output tables and their columns: {tables}\n\n"
        f"Hints from the rule layer:\n{hints or '- none'}\n\n"
        f"Rule layer draft for reference:\n{analysis.draft_python}\n"
        f"Original program:\n{code}\n"
    )
    return [{"role": "system", "content": TRANSLATE_SYSTEM}, {"role": "user", "content": user}]


def explain_messages(code, lang, python, failing_checks, analysis, ctx):
    user = (
        f"Original {LANG_NAMES.get(lang, lang)} program:\n{code}\n\n"
        f"Python translation:\n{python}\n\n"
        f"Checks that differ:\n{compact_checks(failing_checks)}\n\n"
        f"Possible risks found in the original: {json.dumps([{'line': r.line, 'tag': r.tag} for r in analysis.risky_lines])}\n"
    )
    return [{"role": "system", "content": EXPLAIN_SYSTEM}, {"role": "user", "content": user}]


def fix_messages(code, lang, python, failing_checks, explanation):
    cause = " ".join(explanation.paragraphs) if explanation and explanation.paragraphs else "Not known."
    user = (
        f"Original {LANG_NAMES.get(lang, lang)} program:\n{code}\n\n"
        f"Python translation with line numbers:\n{numbered(python)}\n\n"
        f"Checks that differ:\n{compact_checks(failing_checks)}\n\n"
        f"Cause: {cause}\n"
    )
    return [{"role": "system", "content": FIX_SYSTEM}, {"role": "user", "content": user}]


def repair_messages(messages, previous, error):
    return messages + [
        {"role": "assistant", "content": previous},
        {"role": "user", "content": f"That patch could not be applied: {error} Send a corrected JSON object."},
    ]
