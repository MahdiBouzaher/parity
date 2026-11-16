import re

from .common import SOURCE_REASONS, Unsupported, match_paren, not_implemented, paren, round_digits, split_args
from .types import Analysis, Hint, RiskyLine

TOKEN = re.compile(
    r"\s*(?:(?P<str>'[^']*'|\"[^\"]*\")|(?P<num>\d+\.?\d*(?:[eE][+-]?\d+)?|\.\d+)|(?P<id>[A-Za-z_][A-Za-z_0-9]*)"
    r"|(?P<op>\*\*|<=|>=|\^=|~=|<>|[-+*/()<>=,^~|&]))"
)
COMPARE_WORDS = {"eq": "==", "ne": "!=", "lt": "<", "gt": ">", "le": "<=", "ge": ">="}
SKIPPED = {"title", "footnote", "options", "label", "length", "libname", "ods", "quit"}
FUNCTIONS = {"abs": ".abs()", "sqrt": "np.sqrt", "log": "np.log", "exp": "np.exp", "floor": "np.floor", "ceil": "np.ceil", "int": "np.trunc"}
STAT_NAMES = {"n": "count", "mean": "mean", "sum": "sum", "min": "min", "max": "max", "std": "std", "var": "var", "median": "median"}
DATE_RE = re.compile(
    r"\b(mdy|today|date|datepart|intnx|intck|year|month|day|weekday|datetime|yyq)\s*\(|\b(date|yymmdd|mmddyy|ddmmyy|monyy|datetime)\d*\.",
    re.I,
)
COMPARE_RE = re.compile(r"<=|>=|<>|\^=|[<>=]|\b(eq|ne|lt|gt|le|ge)\b", re.I)


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
    def __init__(self, df):
        self.df = df
        self.numpy = False

    def column(self, name):
        return f'{self.df}["{name.lower()}"]'

    def value(self, toks):
        out = []
        i = 0
        while i < len(toks):
            kind, text = toks[i]
            low = text.lower()
            if kind == "str":
                out.append('"' + text[1:-1] + '"')
            elif kind == "num":
                out.append(text)
            elif kind == "id":
                if i + 1 < len(toks) and toks[i + 1][1] == "(":
                    j = match_paren(toks, i + 1)
                    out.append(self.call(low, split_args(toks[i + 2 : j])))
                    i = j
                elif low in COMPARE_WORDS:
                    out.append(COMPARE_WORDS[low])
                elif low == "mod":
                    out.append("%")
                elif low == "div":
                    out.append("//")
                else:
                    out.append(self.column(text))
            elif text == "(":
                j = match_paren(toks, i)
                out.append("(" + self.value(toks[i + 1 : j]) + ")")
                i = j
            elif text in ("^", "~", "|", "&"):
                raise Unsupported(text)
            elif text == "=":
                out.append("==")
            elif text in ("^=", "~=", "<>"):
                out.append("!=")
            else:
                out.append(text)
            i += 1
        return self.join(out)

    @staticmethod
    def join(parts):
        res = ""
        for idx, p in enumerate(parts):
            if p in ("+", "-") and (idx == 0 or parts[idx - 1] in ("+", "-", "*", "/", "**", "//", "%", "(", "==", "!=", "<", ">", "<=", ">=")):
                res += p
            elif p in ("+", "-", "*", "/", "**", "//", "%", "==", "!=", "<", ">", "<=", ">="):
                res += " " + p + " "
            else:
                res += p
        return res

    def call(self, name, args):
        if name == "round":
            inner = self.value(args[0])
            digits = round_digits(args[1][0][1]) if len(args) > 1 and len(args[1]) == 1 else 0
            return f"{paren(inner)}.round({digits})"
        if name in FUNCTIONS:
            inner = self.value(args[0])
            if name == "abs":
                return paren(inner) + ".abs()"
            self.numpy = True
            return f"{FUNCTIONS[name]}({inner})"
        raise Unsupported(name)

    def condition(self, toks):
        groups, cur, depth, ops = [], [], 0, []
        for t in toks:
            if t[1] == "(":
                depth += 1
            elif t[1] == ")":
                depth -= 1
            if depth == 0 and t[0] == "id" and t[1].lower() in ("and", "or"):
                groups.append(cur)
                ops.append("&" if t[1].lower() == "and" else "|")
                cur = []
            elif depth == 0 and t[0] == "op" and t[1] in ("&", "|"):
                groups.append(cur)
                ops.append(t[1])
                cur = []
            else:
                cur.append(t)
        groups.append(cur)
        parts = [self.compare(g) for g in groups]
        if len(parts) == 1:
            return parts[0]
        res = "(" + parts[0] + ")"
        for op, p in zip(ops, parts[1:]):
            res += f" {op} ({p})"
        return res

    def compare(self, toks):
        if toks and toks[0][0] == "id" and toks[0][1].lower() == "not":
            return "~(" + self.compare(toks[1:]) + ")"
        for i, t in enumerate(toks):
            if t[0] == "id" and t[1].lower() == "in":
                left = self.value(toks[:i])
                rest = toks[i + 1 :]
                if not rest or rest[0][1] != "(":
                    raise Unsupported("in")
                items = [self.value(a) for a in split_args(rest[1:-1])]
                return f"{paren(left)}.isin([{', '.join(items)}])"
        if len(toks) > 2 and toks[0][1] == "(" and match_paren(toks, 0) == len(toks) - 1:
            return self.condition(toks[1:-1])
        return self.value(toks)


def strip_comments(code):
    code = re.sub(r"/\*.*?\*/", lambda m: "\n" * m.group(0).count("\n"), code, flags=re.S)
    return code


def split_statements(code):
    stmts, buf, quote, line, start = [], [], None, 1, None
    for ch in code:
        if start is None and not ch.isspace():
            start = line
        if ch == "\n":
            line += 1
        if quote:
            buf.append(ch)
            if ch == quote:
                quote = None
        elif ch in "'\"":
            quote = ch
            buf.append(ch)
        elif ch == ";":
            text = "".join(buf).strip()
            if text and not text.startswith("*"):
                stmts.append((start, re.sub(r"\s+", " ", text), text))
            buf, start = [], None
        else:
            buf.append(ch)
    tail = "".join(buf).strip()
    if tail:
        stmts.append((start, re.sub(r"\s+", " ", tail), tail))
    return stmts


class Builder:
    def __init__(self, lines):
        self.src = lines
        self.blocks = []
        self.hints = []
        self.risky = []
        self.outputs = []
        self.input_name = None
        self.numpy = False
        self.cur = None

    def raw(self, n):
        return self.src[n - 1] if 0 < n <= len(self.src) else ""

    def risk(self, line, tag):
        if not any(r.line == line and r.tag == tag for r in self.risky):
            self.risky.append(RiskyLine(line, tag, SOURCE_REASONS[("sas", tag)]))

    def scan_risks(self, line, text):
        for m in re.finditer(r"\bround\s*\(", text, re.I):
            self.risk(line + text[: m.start()].count("\n"), "rounding")
        if re.search(r"\bdiv\b", text, re.I):
            self.risk(line, "integer division")
        if DATE_RE.search(text):
            self.risk(line, "dates")

    def add_hint(self, line, kind, text, python):
        self.hints.append(Hint(line, kind, text, python))

    def start_block(self):
        self.cur = []
        self.blocks.append(self.cur)
        return self.cur

    def output(self, name):
        if name not in self.outputs:
            self.outputs.append(name)


def render_assignment(tr, name, rhs_toks):
    top_round = (
        len(rhs_toks) >= 3
        and rhs_toks[0][0] == "id"
        and rhs_toks[0][1].lower() == "round"
        and rhs_toks[1][1] == "("
        and match_paren(rhs_toks, 1) == len(rhs_toks) - 1
    )
    target = tr.column(name)
    if top_round:
        args = split_args(rhs_toks[2:-1])
        inner = tr.value(args[0])
        digits = round_digits(args[1][0][1]) if len(args) > 1 and len(args[1]) == 1 else 0
        return [f"{target} = (", f"    {inner}", f").round({digits})"]
    return [f"{target} = (", f"    {tr.value(rhs_toks)}", ")"]


def analyze_sas(code):
    src_lines = code.splitlines()
    stmts = split_statements(strip_comments(code))
    b = Builder(src_lines)
    state = {"kind": None}

    def flush():
        kind = state.get("kind")
        if kind == "proc":
            finish_proc(b, state)
        state.clear()
        state["kind"] = None
        b.cur = None

    for line, text, raw_text in stmts:
        low = text.lower()
        word = low.split(" ", 1)[0]
        rest = text[len(word) :].strip()
        b.scan_risks(line, raw_text)

        if word == "data":
            flush()
            m = re.fullmatch(r"(\w+)", rest)
            if not m:
                blk = b.start_block()
                blk.append(not_implemented(text + ";"))
                state.update(kind="skip")
                continue
            name = m.group(1)
            state.update(kind="data", name=name, df=name, copied=False, line=line)
            b.start_block()
            b.output(name)
            b.add_hint(line, "data_step", f"DATA step creating {name}", None)
            continue

        if word == "proc":
            flush()
            m = re.match(r"(\w+)\s*(.*)", rest)
            kind = m.group(1).lower() if m else ""
            opts = m.group(2) if m else ""
            blk = b.start_block()
            if kind in ("means", "summary", "sort", "freq"):
                state.update(kind="proc", proc=kind, opts=opts, line=line, text=text, vars=[], by=[], tables=[], out=None, cls=[])
                if kind == "sort":
                    b.risk(line, "sort order")
                if kind in ("means", "summary"):
                    b.risk(line, "missing values")
            else:
                blk.append(not_implemented(text + ";"))
                state.update(kind="skip")
            continue

        if word in ("run", "quit"):
            flush()
            continue

        kind = state.get("kind")
        if kind == "skip":
            continue
        if kind == "data":
            blk = b.cur
            handle_data(b, state, blk, line, text, low, word, rest)
            continue
        if kind == "proc":
            handle_proc_stmt(b, state, line, text, word, rest)
            continue
        if word in SKIPPED:
            continue
        blk = b.start_block()
        blk.append(not_implemented(text + ";"))

    flush()

    needs_np = b.numpy
    header = (["import numpy as np"] if needs_np else []) + ["import pandas as pd"]
    out = list(header) + [""]
    if b.input_name:
        out += [f'{b.input_name} = pd.read_csv("input.csv")', ""]
    for blk in b.blocks:
        if blk:
            out += blk + [""]
    while out and out[-1] == "":
        out.pop()
    draft = "\n".join(out) + "\n"
    return Analysis(
        lang="sas",
        statements=len(stmts),
        hints=b.hints,
        risky_lines=sorted(b.risky, key=lambda r: r.line),
        input_name=b.input_name,
        output_tables=b.outputs,
        draft_python=draft,
    )


def handle_data(b, st, blk, line, text, low, word, rest):
    name = st["name"]
    tr = Translator(name)
    try:
        if word == "set":
            ds = rest.split()
            if len(ds) != 1 or "(" in rest:
                raise Unsupported("set")
            src = ds[0]
            if b.input_name is None:
                b.input_name = src
            if src != name:
                blk.append(f"{name} = {src}.copy()")
            st["copied"] = True
            b.add_hint(line, "data_step", f"Read {src}", f"{name} = {src}.copy()")
            return
        if word == "where" or (word == "if" and not re.search(r"\bthen\b", low)):
            cond = tr.condition(tokenize(rest))
            if re.search(r"<=|>=|<>|\^=|[<>=]", rest) or re.search(r"\b(eq|ne|lt|gt|le|ge)\b", low):
                b.risk(line, "missing values")
            py = f"{name} = {name}[{cond}]"
            blk.append(py)
            b.add_hint(line, "filter", f"Keep rows where {rest}", py)
            b.numpy = b.numpy or tr.numpy
            return
        if word in ("keep", "drop"):
            cols = [c.lower() for c in rest.split()]
            lst = "[" + ", ".join(f'"{c}"' for c in cols) + "]"
            py = f"{name} = {name}[{lst}]" if word == "keep" else f"{name} = {name}.drop(columns={lst})"
            blk.append(py)
            b.add_hint(line, "assign", f"{word.capitalize()} columns", py)
            return
        m = re.fullmatch(r"(\w+)\s*=\s*(.+)", text)
        if m and not re.match(r"(if|where)\b", low):
            rhs = tokenize(m.group(2))
            lines = render_assignment(tr, m.group(1), rhs)
            blk.extend(lines)
            b.numpy = b.numpy or tr.numpy
            has_round = any(t[0] == "id" and t[1].lower() == "round" for t in rhs)
            b.add_hint(line, "round" if has_round else "assign", f"Assign {m.group(1)}", "\n".join(lines))
            return
        raise Unsupported(word)
    except Unsupported:
        blk.append(not_implemented(text + ";"))


def handle_proc_stmt(b, st, line, text, word, rest):
    if word == "var":
        st["vars"] = [v.lower() for v in rest.split()]
    elif word == "by":
        st["by"] = [v.lower() for v in rest.split() if v.lower() not in ("notsorted", "descending")]
        st["by_raw"] = rest
    elif word == "class":
        st["cls"] = [v.lower() for v in rest.split()]
    elif word == "tables":
        st["tables"] = [t.lower() for t in re.split(r"\s+", rest.split("/")[0].strip()) if t]
    elif word == "output":
        m = re.search(r"out\s*=\s*(\w+)", rest, re.I)
        st["out"] = m.group(1) if m else None
    else:
        b.cur.append(not_implemented(text + ";"))


def finish_proc(b, st):
    text = st["text"]
    blk = b.cur
    kind, opts, line = st["proc"], st["opts"], st["line"]
    dm = re.search(r"data\s*=\s*(\w+)", opts, re.I)
    data = dm.group(1) if dm else (b.outputs[-1] if b.outputs else b.input_name)
    if data is None:
        blk.append(not_implemented(text + ";"))
        return
    if kind == "sort":
        om = re.search(r"out\s*=\s*(\w+)", opts, re.I)
        out = om.group(1) if om else data
        raw = st.get("by_raw", "")
        cols, asc = [], []
        toks = raw.split()
        desc = False
        for t in toks:
            if t.lower() == "descending":
                desc = True
                continue
            if t.lower() == "notsorted":
                continue
            cols.append(f'"{t.lower()}"')
            asc.append("False" if desc else "True")
            desc = False
        if not cols:
            blk.append(not_implemented(text + ";"))
            return
        by = "[" + ", ".join(cols) + "]"
        call = f"{data}.sort_values({by}"
        if "False" in asc:
            call += ", ascending=[" + ", ".join(asc) + "]"
        call += ")"
        if re.search(r"\bnodupkey\b", opts, re.I):
            call = f"{call}.drop_duplicates(subset={by})"
        py = f"{out} = {call}.reset_index(drop=True)"
        blk.append(py)
        b.output(out)
        b.add_hint(line, "proc_sort", f"Sort {data} by {raw}", py)
        return
    if kind == "freq":
        tables = st["tables"]
        if not tables:
            blk.append(not_implemented(text + ";"))
            return
        pys = []
        for t in tables:
            if "*" in t:
                a, c = t.split("*", 1)
                pys.append(f'freq_{a}_{c} = pd.crosstab({data}["{a}"], {data}["{c}"])')
            else:
                pys.append(f'freq_{t} = {data}["{t}"].value_counts().sort_index().rename_axis("{t}").reset_index(name="count")')
        blk.extend(pys)
        b.add_hint(line, "proc_freq", f"Frequency table of {', '.join(tables)}", "\n".join(pys))
        return
    stats = [s for s in re.findall(r"\b(n|mean|sum|min|max|std|var|median)\b", re.sub(r"data\s*=\s*\w+", "", opts, flags=re.I).lower())]
    stats = list(dict.fromkeys(stats)) or ["n", "mean", "std", "min", "max"]
    group = st["cls"] or st["by"]
    variables = st["vars"]
    if group or st["out"]:
        gname = st["out"] or "summary"
        if variables:
            aggs = [f'{v}_{s}=("{v}", "{STAT_NAMES[s]}")' for v in variables for s in stats]
            if group:
                glist = "[" + ", ".join(f'"{g}"' for g in group) + "]"
                lines = [f"{gname} = {data}.groupby({glist}).agg("]
                lines += [f"    {a}," for a in aggs]
                lines += [").reset_index()"]
            else:
                lines = [f"{gname} = pd.DataFrame({{"]
                for v in variables:
                    for s in stats:
                        lines.append(f'    "{v}_{s}": [{data}["{v}"].{STAT_NAMES[s]}()],')
                lines += ["})"]
        else:
            lines = [f'{gname} = {data}.select_dtypes("number").agg({[STAT_NAMES[s] for s in stats]!r}).T']
            lines[0] = lines[0].replace("'", '"')
        blk.extend(lines)
        b.output(gname)
        b.add_hint(line, "proc_means", f"Summary statistics of {', '.join(variables) or 'numeric columns'}", "\n".join(lines))
        return
    if not variables:
        py = f'summary = {data}.select_dtypes("number").agg({[STAT_NAMES[s] for s in stats]!r}).T'.replace("'", '"')
        blk.append(py)
        b.add_hint(line, "proc_means", "Summary statistics of numeric columns", py)
        return
    lines = []
    single = len(variables) == 1 and len(stats) == 1
    for v in variables:
        for s in stats:
            if single and s == "sum":
                nm = "total"
            elif single and s == "mean":
                nm = "avg"
            else:
                nm = f"{v}_{s}"
            lines.append(f'{nm} = {data}["{v}"].{STAT_NAMES[s]}()')
    blk.extend(lines)
    b.add_hint(line, "sum" if stats == ["sum"] else "proc_means", f"Statistics of {', '.join(variables)}", "\n".join(lines))
