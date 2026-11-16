import builtins
import contextlib
import io
import json
import os
import resource
import socket
import sys
import traceback
import types
from pathlib import Path

import numpy
import pandas

ALLOWED = {
    "numpy",
    "pandas",
    "math",
    "decimal",
    "datetime",
    "re",
    "statistics",
    "itertools",
    "functools",
    "collections",
    "typing",
    "calendar",
    "string",
    "fractions",
    "json",
}
REMOVED = ("exec", "eval", "compile", "input", "breakpoint")
WORKDIR = Path.cwd().resolve()
STDOUT_LIMIT = 65536


def limit(kind, value):
    try:
        resource.setrlimit(kind, (value, value))
    except (ValueError, OSError):
        pass


def apply_limits(timeout):
    limit(resource.RLIMIT_CPU, int(timeout) + 5)
    limit(resource.RLIMIT_FSIZE, 100 * 1024 * 1024)
    limit(resource.RLIMIT_NOFILE, 256)
    if sys.platform.startswith("linux"):
        limit(resource.RLIMIT_AS, 2 * 1024 * 1024 * 1024)


def block_network():
    def refuse(*args, **kwargs):
        raise OSError("network is disabled")

    socket.socket = refuse
    socket.create_connection = refuse
    socket.getaddrinfo = refuse


def inside_workdir(path):
    try:
        resolved = (WORKDIR / path).resolve()
    except (OSError, ValueError):
        return None
    if resolved == WORKDIR or WORKDIR in resolved.parents:
        return resolved
    return None


def make_open(real_open):
    def safe_open(file, *args, **kwargs):
        if isinstance(file, int):
            raise PermissionError("file access is limited to the working directory")
        resolved = inside_workdir(os.fspath(file))
        if resolved is None:
            raise PermissionError("file access is limited to the working directory")
        return real_open(resolved, *args, **kwargs)

    return safe_open


def build_namespace(recorded):
    real_import = builtins.__import__

    def redirect(path):
        if isinstance(path, (str, os.PathLike)):
            resolved = inside_workdir(os.fspath(path))
            if resolved is not None and resolved.is_file():
                return str(resolved)
        else:
            return path
        return "input.csv"

    def read_csv(path, *args, **kwargs):
        frame = pandas.read_csv(redirect(path), *args, **kwargs)
        recorded.append(frame)
        return frame

    def read_excel(path, *args, **kwargs):
        target = redirect(path)
        if target == "input.csv" or str(target).lower().endswith(".csv"):
            frame = pandas.read_csv("input.csv")
        else:
            frame = pandas.read_excel(target, *args, **kwargs)
        recorded.append(frame)
        return frame

    class PandasView(types.ModuleType):
        def __getattr__(self, name):
            return getattr(pandas, name)

    view = PandasView("pandas")
    view.read_csv = read_csv
    view.read_excel = read_excel

    def guarded_import(name, globals=None, locals=None, fromlist=(), level=0):
        if level == 0:
            top = name.split(".")[0]
            if top not in ALLOWED:
                raise ImportError(f"module {name} is not available")
            if name == "pandas" or (top == "pandas" and not fromlist):
                return view
        return real_import(name, globals, locals, fromlist, level)

    scope = dict(vars(builtins))
    for name in REMOVED:
        scope.pop(name, None)
    scope["__import__"] = guarded_import
    scope["open"] = make_open(builtins.open)
    return {"__builtins__": scope, "__name__": "__main__"}


def format_error(exc, source_lines):
    frames = []
    for frame in traceback.extract_tb(exc.__traceback__):
        if frame.filename == "code.py":
            text = source_lines[frame.lineno - 1].strip() if 0 < frame.lineno <= len(source_lines) else ""
            frames.append(f"line {frame.lineno}: {text}")
    return {
        "type": type(exc).__name__,
        "message": str(exc),
        "traceback": "\n".join(frames),
    }


def collect(namespace, expected, recorded):
    inputs = {id(frame) for frame in recorded}
    frames = {
        name: value
        for name, value in namespace.items()
        if isinstance(value, pandas.DataFrame) and not name.startswith("__")
    }
    lowered = {name.lower(): name for name in frames}
    outputs = {}
    for table in expected:
        key = lowered.get(table.lower())
        if key is not None:
            outputs[table] = frames[key]
    if len(expected) == 1 and not outputs:
        for name in reversed(list(frames)):
            if id(frames[name]) not in inputs:
                outputs[expected[0]] = frames[name]
                break
    return outputs


def write_outputs(outputs):
    out = Path("out")
    out.mkdir(exist_ok=True)
    described = {}
    for table, frame in outputs.items():
        if not isinstance(frame.index, pandas.RangeIndex) or frame.index.name is not None:
            frame = frame.reset_index()
        frame.to_csv(out / f"{table}.csv", index=False)
        described[table] = {"rows": int(len(frame)), "columns": [str(c) for c in frame.columns]}
    return described


def main():
    meta = json.loads(Path("meta.json").read_text(encoding="utf-8"))
    apply_limits(meta.get("timeout", 30))
    block_network()
    source = Path("code.py").read_text(encoding="utf-8")
    recorded = []
    namespace = build_namespace(recorded)
    buffer = io.StringIO()
    error = None
    try:
        code = builtins.compile(source, "code.py", "exec")
        with contextlib.redirect_stdout(buffer):
            builtins.exec(code, namespace)
    except BaseException as exc:
        error = format_error(exc, source.splitlines())
    tables = {}
    if error is None:
        try:
            tables = write_outputs(collect(namespace, meta["expected"], recorded))
        except BaseException as exc:
            error = format_error(exc, source.splitlines())
    result = {"tables": tables, "stdout": buffer.getvalue()[:STDOUT_LIMIT], "error": error}
    Path("result.json").write_text(json.dumps(result), encoding="utf-8")


main()
