import re

from .common import SOURCE_REASONS, Unsupported, match_paren, not_implemented, paren, round_digits, split_args
from .types import Analysis, Hint, RiskyLine

TOKEN = re.compile(
    r"\s*(?:(?P<str>\"[^\"]*\")|(?P<num>\d+\.?\d*(?:[eE][+-]?\d+)?|\.\d+)|(?P<id>[A-Za-z_][A-Za-z_0-9\.]*)"
    r"|(?P<op>[-+*/\\^()<>=,&]))"
)
LAYOUT = {1: "loan_id", 2: "pd", 3: "lgd", 4: "exposure", 5: "prov"}
IGNORED = ("sub ", "end sub", "function ", "end function", "dim ", "option ", "private sub", "public sub", "application.screenupdating", "application.calculation", "application.displayalerts")
DATE_RE = re.compile(r"\b(DateSerial|DateAdd|DateDiff|DatePart|DateValue|CDate|Now|Date|Year|Month|Day|Weekday|Format)\b", re.I)
AGG = {"sum": "sum", "average": "mean", "min": "min", "max": "max", "count": "count"}


def col_name(n):
    return LAYOUT.get(n, f"col{n}")


def letter_index(letters):
    n = 0
    for ch in letters.upper():
        n = n * 26 + ord(ch) - 64
    return n


def strip_comment(line):
    quote = False
    for i, ch in enumerate(line):
        if ch == '"':
            quote = not quote
        elif ch == "'" and not quote:
            return line[:i]
    return line


def tokenize(text):
    toks, pos = [], 0
    text = text.rstrip()
    while pos < len(text):
        m = TOKEN.match(text, pos)
        if not m:
            raise Unsupported(text[pos:])
        kind = m.lastgroup
        toks.append((kind, m.group(kind)))
        pos = m.end()
    return toks


class Translator:
    def __init__(self, loopvar, locals_, pyvars):
        self.loopvar = loopvar
        self.locals = locals_
        self.pyvars = pyvars
        self.numpy = False

    def value(self, toks):
        out = []
        i = 0
        while i < len(toks):
            kind, text = toks[i]
            low = text.lower()
            if kind == "str":
                out.append(text)
            elif kind == "num":
                out.append(text)
            elif kind == "id":
                if i + 1 < len(toks) and toks[i + 1][1] == "(":
                    j = match_paren(toks, i + 1)
                    out.append(self.call(low, split_args(toks[i + 2 : j])))
                    i = j
                elif low == "mod":
                    out.append("%")
                elif low == "lastrow":
                    out.append("(len(df) + 1)")
                elif low in self.locals:
                    out.append(f'df["{low}"]')
                elif low in self.pyvars:
                    out.append(self.pyvars[low])
                elif low == self.loopvar:
                    raise Unsupported(text)
                else:
                    out.append(text)
            elif text == "(":
                j = match_paren(toks, i)
                out.append("(" + self.value(toks[i + 1 : j]) + ")")
                i = j
            elif text == "^":
                out.append("**")
            elif text == "\\":
                out.append("//")
            elif text in ("&", "<", ">", "="):
                raise Unsupported(text)
            else:
                out.append(text)
            i += 1
        return join(out)

    def call(self, name, args):
        if name == "cells":
            if len(args) != 2 or len(args[0]) != 1 or len(args[1]) != 1:
                raise Unsupported("Cells")
            if args[0][0][1].lower() != self.loopvar or args[1][0][0] != "num":
                raise Unsupported("Cells")
            return f'df["{col_name(int(args[1][0][1]))}"]'
        if name == "round":
            inner = self.value(args[0])
            digits = int(args[1][0][1]) if len(args) > 1 and len(args[1]) == 1 and args[1][0][0] == "num" else 0
            return f"{paren(inner)}.round({digits})"
        if name == "abs":
            return paren(self.value(args[0])) + ".abs()"
        if name in ("sqr", "int", "log", "exp"):
            self.numpy = True
            fn = {"sqr": "np.sqrt", "int": "np.floor", "log": "np.log", "exp": "np.exp"}[name]
            return f"{fn}({self.value(args[0])})"
        short = name.replace("application.", "").replace("worksheetfunction.", "")
        if short in AGG and len(args) == 1:
            col = self.range_column(args[0])
            return f'df["{col}"].{AGG[short]}()'
        raise Unsupported(name)

    def range_column(self, toks):
        if len(toks) == 4 and toks[0][1].lower() == "range" and toks[1][1] == "(" and toks[2][0] == "str":
            m = re.fullmatch(r'"([A-Za-z]+)\d*(?::([A-Za-z]+)\d*)?"', toks[2][1])
            if m and (m.group(2) is None or m.group(2).upper() == m.group(1).upper()):
                return col_name(letter_index(m.group(1)))
        raise Unsupported("Range")


def join(parts):
    ops = ("+", "-", "*", "/", "**", "//", "%")
    res = ""
    for idx, p in enumerate(parts):
        if p in ("+", "-") and (idx == 0 or parts[idx - 1] in ops or parts[idx - 1] == "("):
            res += p
        elif p in ops:
            res += " " + p + " "
        else:
            res += p
    return res


def vector_source(expr):
    return expr if re.fullmatch(r'df\["\w+"\]', expr) else paren(expr)


def analyze_vba(code):
    raw = code.splitlines()
    risky, hints, py = [], [], []
    locals_, accs, pyvars, pending = set(), {}, {}, []
    state = {"loop": None, "numpy": False, "means": 0}
    statements = 0

    def risk(line, tag):
        if not any(r.line == line and r.tag == tag for r in risky):
            risky.append(RiskyLine(line, tag, SOURCE_REASONS[("vba", tag)]))

    def emit(line, kind, text, lines):
        py.extend(lines)
        hints.append(Hint(line, kind, text, "\n".join(lines)))

    def fail(line, text):
        py.append(not_implemented(text))

    def tr():
        t = Translator(state["loop"], locals_, pyvars)
        return t

    for n, original in enumerate(raw, 1):
        text = strip_comment(original).strip()
        if not text:
            continue
        statements += 1
        low = text.lower()
        if re.search(r"\bRound\s*\(", text, re.I):
            risk(n, "rounding")
        if re.search(r"\\", re.sub(r'"[^"]*"', "", text)):
            risk(n, "integer division")
        if DATE_RE.search(re.sub(r'"[^"]*"', "", text)) and not re.match(r"(sub|end)\b", low):
            risk(n, "dates")
        if re.search(r"\.Sort\b|\bSort\s*\(", text, re.I):
            risk(n, "sort order")

        if low.startswith(IGNORED):
            continue

        m = re.fullmatch(r"for\s+(\w+)\s*=\s*(.+?)\s+to\s+(.+)", text, re.I)
        if m:
            if state["loop"] or re.search(r"\bstep\b", text, re.I):
                fail(n, text)
            else:
                state["loop"] = m.group(1).lower()
                hints.append(Hint(n, "loop", f"Loop over rows {m.group(2)} to {m.group(3)}", None))
            continue
        if re.fullmatch(r"next(\s+\w+)?", low):
            if state["loop"]:
                for pn, pkind, ptext, plines in pending:
                    emit(pn, pkind, ptext, plines)
                pending.clear()
                state["loop"] = None
            else:
                fail(n, text)
            continue

        m = re.fullmatch(r"(.+?)\s*=\s*(.+)", text)
        if not m:
            fail(n, text)
            continue
        lhs, rhs = m.group(1).strip(), m.group(2).strip()
        t = tr()
        try:
            cell = re.fullmatch(r"cells\s*\(\s*(\w+)\s*,\s*(\d+)\s*\)(\.value)?", lhs, re.I)
            rng = re.fullmatch(r'range\s*\(\s*"([A-Za-z]+)(\d+)"\s*\)(\.value)?', lhs, re.I)
            ident = re.fullmatch(r"\w+", lhs)
            loop = state["loop"]
            if loop:
                acc = re.fullmatch(rf"{re.escape(lhs)}\s*\+\s*(.+)", rhs, re.I) if ident else None
                if ident and acc:
                    rest = tokenize(acc.group(1))
                    if len(rest) == 1 and rest[0][0] == "num" and rest[0][1] == "1":
                        expr, kind = "len(df)", "count"
                    else:
                        src = t.value(rest)
                        expr, kind = f"{vector_source(src)}.sum()", "sum"
                    name = lhs
                    accs[name.lower()] = (vector_source(t.value(rest)) if kind == "sum" else None, kind)
                    pyvars[name.lower()] = name
                    pending.append((n, "sum", f"Total of {acc.group(1)}", [f"{name} = {expr}"]))
                elif cell and cell.group(1).lower() == loop:
                    name = col_name(int(cell.group(2)))
                    value = t.value(tokenize(rhs))
                    emit(n, "assign", f"Write column {name}", [f'df["{name}"] = {value}'])
                    if re.search(r"cells\s*\(", rhs, re.I) and re.search(r"[-+*/\\^]", re.sub(r"cells\s*\([^)]*\)", "", rhs, flags=re.I)):
                        risk(n, "missing values")
                elif ident:
                    value = t.value(tokenize(rhs))
                    locals_.add(lhs.lower())
                    emit(n, "assign", f"Compute {lhs}", [f'df["{lhs.lower()}"] = {value}'])
                else:
                    raise Unsupported(lhs)
            else:
                mean = re.fullmatch(r"(\w+)\s*/\s*\(\s*\w+\s*-\s*1\s*\)", rhs)
                if (cell or rng or ident) and mean and mean.group(1).lower() in accs and accs[mean.group(1).lower()][1] == "sum":
                    src = accs[mean.group(1).lower()][0]
                    name = "avg" if state["means"] == 0 else f"avg{state['means'] + 1}"
                    state["means"] += 1
                    emit(n, "sum", f"Mean of {mean.group(1)}", [f"{name} = {src}.mean()"])
                    pyvars[name] = name
                elif cell or rng or ident:
                    if cell:
                        name = f"cell_{cell.group(1)}_{cell.group(2)}"
                    elif rng:
                        name = f"cell_{rng.group(1).lower()}{rng.group(2)}"
                    else:
                        name = lhs
                    value = t.value(tokenize(rhs))
                    emit(n, "assign", f"Compute {name}", [f"{name} = {value}"])
                    pyvars[name.lower()] = name
                else:
                    raise Unsupported(lhs)
            state["numpy"] = state["numpy"] or t.numpy
        except Unsupported:
            fail(n, text)

    for pn, pkind, ptext, plines in pending:
        emit(pn, pkind, ptext, plines)

    header = (["import numpy as np"] if state["numpy"] else []) + ["import pandas as pd", "", 'df = pd.read_csv("input.csv")']
    body = py + ["result = df"]
    draft = "\n".join(header + body) + "\n"
    return Analysis(
        lang="vba",
        statements=statements,
        hints=hints,
        risky_lines=sorted(risky, key=lambda r: r.line),
        input_name="df",
        output_tables=["result"],
        draft_python=draft,
    )
