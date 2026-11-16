import json
import os
import shutil
import signal
import subprocess
import sys
import tempfile
import threading
import time
from dataclasses import dataclass, field
from pathlib import Path

import pandas as pd

HARNESS = Path(__file__).with_name("harness.py")
_processes = {}
_cancelled = set()
_lock = threading.Lock()


@dataclass
class RunResult:
    ok: bool
    tables: dict = field(default_factory=dict)
    seconds: float = 0.0
    stdout: str = ""
    error: dict | None = None


def kill_group(proc):
    try:
        os.killpg(proc.pid, signal.SIGKILL)
    except (ProcessLookupError, PermissionError):
        pass


def cancel(key):
    with _lock:
        proc = _processes.get(key)
        _cancelled.add(key)
    if proc is not None:
        kill_group(proc)


def failure(message, kind="RunError", seconds=0.0, stdout="", traceback=""):
    return RunResult(
        False,
        {},
        seconds,
        stdout,
        {"type": kind, "message": message, "traceback": traceback},
    )


def run_python(code, input_csv_bytes, expected_tables, timeout, key=None):
    with tempfile.TemporaryDirectory(prefix="parity-") as tmp:
        work = Path(tmp)
        (work / "input.csv").write_bytes(input_csv_bytes)
        (work / "code.py").write_text(code, encoding="utf-8")
        (work / "meta.json").write_text(
            json.dumps({"expected": list(expected_tables), "timeout": timeout}), encoding="utf-8"
        )
        shutil.copyfile(HARNESS, work / "harness.py")
        env = {
            "PATH": "/usr/bin:/bin",
            "PYTHONHASHSEED": "0",
            "HOME": tmp,
            "OPENBLAS_NUM_THREADS": "1",
        }
        started = time.monotonic()
        proc = subprocess.Popen(
            [sys.executable, "-I", "-B", "harness.py"],
            cwd=tmp,
            env=env,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            start_new_session=True,
        )
        if key is not None:
            with _lock:
                _processes[key] = proc
        try:
            try:
                _, stderr = proc.communicate(timeout=timeout)
            except subprocess.TimeoutExpired:
                kill_group(proc)
                proc.communicate()
                seconds = time.monotonic() - started
                return failure(
                    f"The Python ran longer than {timeout} seconds.", "Timeout", seconds
                )
        finally:
            if key is not None:
                with _lock:
                    _processes.pop(key, None)
        seconds = time.monotonic() - started
        if key is not None:
            with _lock:
                was_cancelled = key in _cancelled
                _cancelled.discard(key)
            if was_cancelled:
                return failure("The run was cancelled.", "Cancelled", seconds)
        result_path = work / "result.json"
        if not result_path.exists():
            tail = stderr.decode("utf-8", "replace").strip().splitlines()[-40:]
            return failure(
                "The Python stopped before it finished.", "RunError", seconds, traceback="\n".join(tail)
            )
        result = json.loads(result_path.read_text(encoding="utf-8"))
        if result["error"] is not None:
            error = result["error"]
            return RunResult(False, {}, seconds, result["stdout"], error)
        tables = {}
        for name in result["tables"]:
            tables[name] = pd.read_csv(work / "out" / f"{name}.csv")
        return RunResult(True, tables, seconds, result["stdout"], None)
