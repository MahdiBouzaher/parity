import json

SOURCE_REASONS = {
    ("sas", "rounding"): "SAS rounds a tie away from zero, and pandas rounds a tie to the nearest even digit.",
    ("vba", "rounding"): "VBA rounds the stored decimal value, and pandas rounds the binary float, so ties can fall differently.",
    ("sas", "missing values"): "SAS treats a missing value as smaller than any number, and pandas compares it as false.",
    ("vba", "missing values"): "VBA counts a blank cell as zero, and pandas skips it.",
    ("sas", "sort order"): "SAS sorts missing values first, and pandas sorts them last.",
    ("vba", "sort order"): "Excel and pandas order blanks and mixed text differently.",
    ("sas", "integer division"): "This division may be meant as integer division, and pandas keeps the fraction.",
    ("vba", "integer division"): "The backslash operator drops the fraction, and a plain division keeps it.",
    ("sas", "dates"): "SAS counts dates from 1960 and pandas uses calendar timestamps.",
    ("vba", "dates"): "Excel counts dates from 1900 and pandas uses calendar timestamps.",
}

PYTHON_REASONS = {
    "rounding": "pandas rounds a tie to the nearest even digit.",
    "missing values": "pandas skips a missing value instead of counting it the way the original does.",
    "sort order": "pandas sorts missing values last.",
    "integer division": "Floor division rounds toward negative infinity.",
    "dates": "pandas dates use calendar timestamps.",
}


class Unsupported(Exception):
    pass


def not_implemented(line):
    return "raise NotImplementedError(" + json.dumps(line.strip()) + ")"


def paren(s):
    if all(c.isalnum() or c in '_."[]' for c in s):
        return s
    if s.startswith("(") and s.endswith(")") and balanced_outer(s):
        return s
    return "(" + s + ")"


def balanced_outer(s):
    depth = 0
    for i, c in enumerate(s):
        if c == "(":
            depth += 1
        elif c == ")":
            depth -= 1
            if depth == 0 and i < len(s) - 1:
                return False
    return depth == 0


def round_digits(unit):
    from decimal import Decimal, InvalidOperation

    try:
        d = Decimal(unit).normalize()
    except InvalidOperation:
        raise Unsupported("round unit")
    sign, digits, exp = d.as_tuple()
    if sign or digits != (1,):
        raise Unsupported("round unit")
    return -exp


def split_args(tokens):
    args, cur, depth = [], [], 0
    for t in tokens:
        if t[1] == "(":
            depth += 1
        elif t[1] == ")":
            depth -= 1
        if t[1] == "," and depth == 0:
            args.append(cur)
            cur = []
        else:
            cur.append(t)
    if cur or args:
        args.append(cur)
    return args


def match_paren(tokens, i):
    depth = 0
    for j in range(i, len(tokens)):
        if tokens[j][1] == "(":
            depth += 1
        elif tokens[j][1] == ")":
            depth -= 1
            if depth == 0:
                return j
    raise Unsupported("parentheses")
