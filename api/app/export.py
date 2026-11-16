from html import escape

from .hashing import canonical_sha256

CSS = """
:root{--bg:#0A0B0D;--surface:#111216;--surface-2:#17181D;--line:#23252B;--line-2:#34373F;--text:#E7E8EA;--muted:#8A8D96;--faint:#767983;--ghost:#4A4D55;--ok:#63C68F;--ok-tint:#14211A;--warn:#E3A64B;--warn-tint:#29231B}
*{box-sizing:border-box}
body{margin:0;background:var(--bg);color:var(--text);font-family:"Helvetica Neue",Arial,system-ui,sans-serif;font-size:15px;line-height:1.5}
main{max-width:1040px;margin:0 auto;padding:48px 24px}
h1{font-size:34px;font-weight:400;margin:0 0 8px}
h2{font-size:18px;font-weight:400;margin:40px 0 12px}
.muted{color:var(--muted)}
.mono,code,pre,td.num{font-family:Menlo,"SF Mono",ui-monospace,Consolas,monospace;font-variant-numeric:tabular-nums}
.chip{display:inline-block;height:26px;line-height:24px;padding:0 12px;border-radius:13px;border:1px solid var(--line-2);font-size:13px}
.chip.ok{color:var(--ok);background:var(--ok-tint);border-color:var(--ok)}
.chip.warn{color:var(--warn);background:var(--warn-tint);border-color:var(--warn)}
table{width:100%;border-collapse:collapse;font-size:13px}
th{font-size:11.5px;text-transform:uppercase;letter-spacing:.12em;color:var(--faint);font-weight:400;text-align:left}
th,td{padding:8px 10px;border-bottom:1px solid var(--line);vertical-align:top}
td.hash{word-break:break-all;font-family:Menlo,"SF Mono",ui-monospace,Consolas,monospace;font-size:12px}
.ok-word{color:var(--ok)}
.warn-word{color:var(--warn)}
pre{background:var(--surface);border:1px solid var(--line);border-radius:12px;padding:16px;overflow:auto;font-size:13px;line-height:1.6;margin:0}
.ln{display:inline-block;width:3em;color:var(--ghost);user-select:none}
@media print{body{background:#fff;color:#111}.muted,th{color:#444}.chip,pre,th,td{border-color:#999;background:#fff}.chip,.chip.ok,.chip.warn{background:#fff;color:#111}.ok-word{color:#1c7a47}.warn-word{color:#9a6200}.ln{color:#777}pre{overflow:visible;white-space:pre-wrap}main{padding:0}}
"""


def accepted_differences(run):
    if run["state"] != "kept":
        return []
    return [c["id"] for c in run["current"]["checks"] if c["status"] == "differs"]


def build_json(run):
    current = run["current"]
    body = {
        "format": "parity-report",
        "version": 1,
        "generated_at": run["updated_at"],
        "run_id": run["id"],
        "program": {"filename": run["filename"], "lang": run["lang"]},
        "result": {
            "state": run["state"],
            "matched": current["summary"]["matched"],
            "total": current["summary"]["total"],
            "accepted_differences": accepted_differences(run),
        },
        "translation": {
            "source": run["translation"]["source"],
            "model": run["translation"]["model"],
            "revisions": [
                {"index": r["index"], "label": r["label"], "python_sha256": r["python_sha256"]}
                for r in run["revisions"]
            ],
        },
        "hashes": {
            "original_code": run["source_sha256"],
            "python": current["python_sha256"],
            "input": {
                "name": run["dataset"]["input"]["name"],
                "sha256": run["dataset"]["input"]["sha256"],
            },
            "expected": [
                {"table": e["table"], "name": e["name"], "sha256": e["sha256"]}
                for e in run["dataset"]["expected"]
            ],
        },
        "tolerances": run["dataset"]["tolerances"],
        "checks": current["checks"],
        "explanation": current["explanation"],
        "code": {"original": run["source"], "python": current["python"]},
    }
    body["report_sha256"] = canonical_sha256(body)
    return body


def listing(text):
    lines = text.split("\n")
    if lines and lines[-1] == "":
        lines = lines[:-1]
    rows = [f'<span class="ln">{i}</span>{escape(line)}' for i, line in enumerate(lines, start=1)]
    return "<pre>" + "\n".join(rows) + "</pre>"


def status_word(status):
    if status == "match":
        return '<span class="ok-word">Match</span>'
    return '<span class="warn-word">Differs</span>'


def build_html(run):
    report = build_json(run)
    result = report["result"]
    differing = result["total"] - result["matched"]
    if run["state"] == "kept":
        chip = f'<span class="chip warn">{len(result["accepted_differences"])} accepted differences</span>'
    elif differing:
        chip = f'<span class="chip warn">{differing} differences</span>'
    else:
        chip = '<span class="chip ok">All checks match</span>'
    hashes = report["hashes"]
    hash_rows = [
        ("Original code", run["filename"], hashes["original_code"]),
        ("Python", "Revision " + str(run["current"]["index"]), hashes["python"]),
        ("Input", hashes["input"]["name"], hashes["input"]["sha256"]),
    ]
    for item in hashes["expected"]:
        hash_rows.append(("Expected output", item["name"], item["sha256"]))
    hash_rows.append(("Report", "JSON body without this hash", report["report_sha256"]))
    hash_html = "".join(
        f"<tr><td>{escape(a)}</td><td>{escape(b)}</td><td class=\"hash\">{escape(c)}</td></tr>"
        for a, b, c in hash_rows
    )
    check_html = "".join(
        "<tr>"
        f"<td>{escape(c['label'])}</td>"
        f"<td>{status_word(c['status'])}</td>"
        f"<td class=\"num\">{escape(str(c['expected']))}</td>"
        f"<td class=\"num\">{escape(str(c['actual']))}</td>"
        f"<td>{escape(c['tolerance'])}</td>"
        "</tr>"
        for c in report["checks"]
    )
    explanation = ""
    expl = report["explanation"]
    if run["state"] in ("fixed", "match"):
        body = (expl["fixed_body"] if expl and expl["fixed_body"] else f"All {result['total']} checks match.")
        explanation = f"<h2>Parity reached</h2><p>{escape(body)}</p>"
    elif expl:
        paragraphs = "".join(f"<p>{escape(p)}</p>" for p in expl["paragraphs"])
        explanation = f"<h2>{escape(expl['title'])}</h2>{paragraphs}"
    accepted = ""
    if result["accepted_differences"]:
        items = "".join(f"<li class=\"mono\">{escape(i)}</li>" for i in result["accepted_differences"])
        accepted = f"<h2>Accepted differences</h2><ul>{items}</ul>"
    lang = "SAS" if run["lang"] == "sas" else "VBA"
    title = f"Parity report for {escape(run['filename'])}"
    return (
        "<!doctype html><html lang=\"en\"><head><meta charset=\"utf-8\">"
        "<meta name=\"viewport\" content=\"width=device-width, initial-scale=1\">"
        f"<title>{title}</title><style>{CSS}</style></head><body><main>"
        f"<h1>{title}</h1>"
        f"<p class=\"muted\">{escape(report['generated_at'])} &middot; {lang} &middot; "
        f"{result['matched']} of {result['total']} checks match</p>"
        f"<p>{chip}</p>"
        "<h2>Hashes</h2><table><thead><tr><th>Item</th><th>Name</th><th>SHA-256</th></tr></thead>"
        f"<tbody>{hash_html}</tbody></table>"
        "<h2>Checks</h2><table><thead><tr><th>Check</th><th>Status</th><th>Expected</th>"
        f"<th>Actual</th><th>Tolerance</th></tr></thead><tbody>{check_html}</tbody></table>"
        f"{explanation}{accepted}"
        f"<h2>Original code</h2>{listing(run['source'])}"
        f"<h2>Python</h2>{listing(run['current']['python'])}"
        "</main></body></html>"
    )


def file_stem(filename):
    return filename.rsplit(".", 1)[0] or "program"
