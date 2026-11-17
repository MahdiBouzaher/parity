import io
from xml.sax.saxutils import escape

from pypdf import PdfWriter
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from reportlab.lib.colors import HexColor
from reportlab.platypus import (
    KeepTogether,
    Paragraph,
    Preformatted,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

from .export import KIND_LABELS, format_lines
from .signing import canonical_bytes

ATTACHMENT_NAME = "parity-report.json"
TEXT = HexColor("#111111")
MUTED = HexColor("#555555")
LINE = HexColor("#bbbbbb")
OK = "#1c7a47"
WARN = "#9a6200"

MARGIN = 18 * mm
WIDTH = A4[0] - 2 * MARGIN
CODE_SIZE = 7.5
CODE_CHARS = int(WIDTH / (0.6 * CODE_SIZE)) - 1

BODY = ParagraphStyle("body", fontName="Helvetica", fontSize=9.5, leading=13, textColor=TEXT)
MUTED_STYLE = ParagraphStyle("muted", parent=BODY, textColor=MUTED)
TITLE = ParagraphStyle("title", parent=BODY, fontSize=22, leading=26, spaceAfter=4)
H2 = ParagraphStyle("h2", parent=BODY, fontName="Helvetica-Bold", fontSize=12, leading=16,
                    spaceBefore=16, spaceAfter=6, keepWithNext=1)
CELL = ParagraphStyle("cell", parent=BODY, fontSize=8, leading=10.5)
HEAD = ParagraphStyle("head", parent=CELL, fontName="Helvetica-Bold", textColor=MUTED)
MONO = ParagraphStyle("mono", parent=CELL, fontName="Courier", fontSize=7, leading=9, wordWrap="CJK")
CODE = ParagraphStyle("code", parent=BODY, fontName="Courier", fontSize=CODE_SIZE,
                      leading=CODE_SIZE * 1.35, textColor=TEXT)


def safe(text):
    """Make text renderable with the standard fonts: unsupported characters become '?'."""
    text = "" if text is None else str(text)
    text = "".join(ch if ch in "\n\t" or ch >= " " else "?" for ch in text)
    return text.encode("cp1252", "replace").decode("cp1252")


def para(text, style=BODY):
    return Paragraph(escape(safe(text)), style)


SIGNATURE_LINE = 64


def even_lines(value):
    """Break a long value into equal lines on purpose, so no line holds a stray last character."""
    text = safe(value)
    count = -(-len(text) // SIGNATURE_LINE) if text else 1
    size = -(-len(text) // count) if text else 1
    chunks = [text[i : i + size] for i in range(0, len(text), size)] or [""]
    return Paragraph("<br/>".join(escape(c) for c in chunks), MONO)


def markup(text, style=BODY):
    return Paragraph(text, style)


def status_markup(status):
    if status == "match":
        return f'<font color="{OK}">Match</font>'
    return f'<font color="{WARN}">Differs</font>'


def listing(text):
    lines = safe(text).replace("\t", "    ").split("\n")
    if lines and lines[-1] == "":
        lines = lines[:-1]
    gutter = max(3, len(str(len(lines))))
    room = max(10, CODE_CHARS - gutter - 2)
    out = []
    for number, line in enumerate(lines, start=1):
        line = line.rstrip("\r")
        chunks = [line[i : i + room] for i in range(0, len(line), room)] or [""]
        for index, chunk in enumerate(chunks):
            label = str(number).rjust(gutter) if index == 0 else " " * gutter
            out.append(f"{label}  {chunk}")
    return Preformatted("\n".join(out), CODE)


def grid(rows, widths, header=True):
    table = Table(rows, colWidths=widths, repeatRows=1 if header else 0)
    table.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LINEBELOW", (0, 0), (-1, -1), 0.4, LINE),
        ("LEFTPADDING", (0, 0), (-1, -1), 4),
        ("RIGHTPADDING", (0, 0), (-1, -1), 4),
        ("TOPPADDING", (0, 0), (-1, -1), 3),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
    ]))
    return table


def footer(canvas, doc):
    canvas.saveState()
    canvas.setFont("Helvetica", 8)
    canvas.setFillColor(MUTED)
    canvas.drawString(MARGIN, 10 * mm, "Parity report")
    canvas.drawRightString(A4[0] - MARGIN, 10 * mm, f"Page {doc.page}")
    canvas.restoreState()


def story_for(report):
    result = report["result"]
    sig = report["signature"]
    hashes = report["hashes"]
    flow = []
    flow.append(markup("Parity", MUTED_STYLE))
    flow.append(para(report["program"]["filename"], TITLE))
    lang = "SAS" if report["program"]["lang"] == "sas" else "VBA"
    flow.append(para(f"{report['signed_at'].replace('T', ' ').replace('Z', '')} UTC  |  {lang}", MUTED_STYLE))
    flow.append(Spacer(1, 6))
    differing = result["total"] - result["matched"]
    colour = OK if not differing else WARN
    if result["state"] == "kept":
        word = f"{len(result['accepted_differences'])} accepted differences"
    elif differing:
        word = f"{differing} differences"
    else:
        word = "All checks match"
    flow.append(markup(
        f'<b>{result["matched"]} of {result["total"]} checks</b> match  |  '
        f'<font color="{colour}">{escape(word)}</font>'
    ))

    flow.append(para("Checks", H2))
    rows = [[para(h, HEAD) for h in ("Check", "Status", "Expected", "Actual", "Tolerance")]]
    for c in report["checks"]:
        rows.append([
            para(c["label"], CELL),
            markup(status_markup(c["status"]), CELL),
            para(c["expected"], CELL),
            para(c["actual"], CELL),
            para(c["tolerance"], CELL),
        ])
    flow.append(grid(rows, [WIDTH * f for f in (0.34, 0.12, 0.18, 0.18, 0.18)]))

    history = report["history"]
    flow.append(para("History", H2))
    if len(history) == 1 and history[0]["kind"] == "first_run" and history[0]["matched"] == history[0]["total"]:
        flow.append(para("No fix needed"))
    else:
        rows = [[para(h, HEAD) for h in ("#", "Step", "Checks", "Change", "Lines")]]
        for h in history:
            change = h["change"] + (f" ({h['reason']})" if h.get("reason") else "")
            rows.append([
                para(h["step"], CELL),
                para(KIND_LABELS.get(h["kind"], h["kind"]), CELL),
                para(f"{h['matched']} of {h['total']}", CELL),
                para(change, CELL),
                para(format_lines(h["lines"]) or "-", CELL),
            ])
        flow.append(grid(rows, [WIDTH * f for f in (0.06, 0.16, 0.14, 0.46, 0.18)]))

    flow.append(para("Outcome", H2))
    flow.append(para(report["closing"]))
    expl = report.get("explanation")
    if result["state"] not in ("fixed", "match") and expl:
        flow.append(Spacer(1, 6))
        flow.append(para(expl["title"], H2))
        for p in expl["paragraphs"]:
            flow.append(para(p))
            flow.append(Spacer(1, 4))
    if result["state"] == "kept":
        flow.append(para("Kept difference", H2))
        for check_id in result["accepted_differences"]:
            flow.append(para(check_id, MONO))

    flow.append(para("Original code", H2))
    flow.append(listing(report["code"]["original"]))
    flow.append(para("Python", H2))
    flow.append(listing(report["code"]["python"]))

    flow.append(para("Hashes (SHA-256)", H2))
    hash_rows = [[para(h, HEAD) for h in ("Item", "Name", "SHA-256")]]
    items = [
        ("Original code", report["program"]["filename"], hashes["original_code"]),
        ("Python", "Final revision", hashes["python"]),
        ("Input", hashes["input"]["name"], hashes["input"]["sha256"]),
    ]
    items += [("Expected output", e["name"], e["sha256"]) for e in hashes["expected"]]
    for a, b, c in items:
        hash_rows.append([para(a, CELL), para(b, CELL), para(c, MONO)])
    flow.append(grid(hash_rows, [WIDTH * f for f in (0.2, 0.22, 0.58)]))

    sig_rows = [
        ("Report hash", report["report_sha256"]),
        ("Signed payload hash", sig["payload_sha256"]),
        ("Algorithm", sig["algorithm"]),
        ("Signature (base64)", sig["signature"]),
        ("Key fingerprint", sig["key_fingerprint"]),
        ("Signed at", sig["signed_at"]),
    ]
    block = [para("Signature", H2)]
    block.append(grid([[para(a, HEAD), even_lines(b)] for a, b in sig_rows],
                      [WIDTH * 0.24, WIDTH * 0.76], header=False))
    block.append(Spacer(1, 6))
    block.append(para(
        "Tamper-evident: any change to this report breaks the signature. "
        "The key fingerprint identifies the signing key, not a person.",
        MUTED_STYLE,
    ))
    block.append(Spacer(1, 4))
    block.append(para(
        f"The signed report is attached to this file as {ATTACHMENT_NAME}. "
        "Upload this file on the Verify screen to check that it has not changed.",
        MUTED_STYLE,
    ))
    flow.append(KeepTogether(block))
    return flow


def signed_json_bytes(report):
    """Serialize the signed report with a stable body: canonical body, then the signature block."""
    body = {k: v for k, v in report.items() if k != "signature"}
    return canonical_bytes({**body, "signature": report["signature"]})


def build_pdf(report):
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        leftMargin=MARGIN,
        rightMargin=MARGIN,
        topMargin=MARGIN,
        bottomMargin=18 * mm,
        title=f"Parity report for {safe(report['program']['filename'])}",
        author="Parity",
    )
    doc.build(story_for(report), onFirstPage=footer, onLaterPages=footer)
    writer = PdfWriter(clone_from=io.BytesIO(buffer.getvalue()))
    writer.add_attachment(ATTACHMENT_NAME, signed_json_bytes(report))
    out = io.BytesIO()
    writer.write(out)
    return out.getvalue()
