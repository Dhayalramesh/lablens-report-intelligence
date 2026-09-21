"""Read lab-report PDFs into structured rows: test, value, unit, reference range, printed flag."""
import re
from datetime import datetime
from pathlib import Path

import pdfplumber

from .catalog import canonical

NUM = r"\d+(?:\.\d+)?"
RANGE = re.compile(rf"(?P<lo>{NUM})\s*-\s*(?P<hi>{NUM})")
LESS = re.compile(rf"(?:<=?|up to)\s*(?P<hi>{NUM})", re.I)
MORE = re.compile(rf">=?\s*(?P<lo>{NUM})")
FLAG = re.compile(r"\s\*?(?:HIGH|LOW|H|L)\*?\s*$")
SKIP = ("patient", "age", "report", "collected", "lab", "sample", "page", "test ", "investigation")
DATE_FORMATS = ("%d-%b-%Y", "%Y-%m-%d", "%d/%m/%Y", "%d %b %Y")


def read_text(pdf_path) -> str:
    with pdfplumber.open(pdf_path) as pdf:
        return "\n".join((page.extract_text() or "") for page in pdf.pages)


def parse_header(text: str) -> dict:
    head = {"date": None, "sex": None, "age": None, "patient": None}
    m = re.search(r"Report Date\s*[:\-]?\s*(\S+)", text)
    if m:
        for fmt in DATE_FORMATS:
            try:
                head["date"] = datetime.strptime(m.group(1), fmt).date().isoformat()
                break
            except ValueError:
                continue
    m = re.search(r"Age\s*/\s*Sex\s*[:\-]?\s*(\d+)\s*/\s*([MF])", text)
    if m:
        head["age"], head["sex"] = int(m.group(1)), m.group(2)
    m = re.search(r"Patient ID\s*[:\-]?\s*(\S+)", text)
    if m:
        head["patient"] = m.group(1)
    return head


def parse_line(line: str):
    """Return a row dict for one text line, or None if the line is not a result row."""
    line = line.strip()
    if not line or line.lower().startswith(SKIP):
        return None
    flag_m = FLAG.search(" " + line)
    flag = flag_m.group(0).strip().strip("*")[0] if flag_m else ""
    line = FLAG.sub("", " " + line).strip()
    line = re.sub(r"[()\[\]:]|\bRef\b", " ", line)
    lo = hi = None
    ref = RANGE.search(line)
    if ref:
        lo, hi = float(ref["lo"]), float(ref["hi"])
    else:
        less, more = LESS.search(line), MORE.search(line)
        if less:
            hi, ref = float(less["hi"]), less
        elif more:
            lo, ref = float(more["lo"]), more
    if ref is None:
        return None
    line = (line[:ref.start()] + " " + line[ref.end():]).split()
    for i, token in enumerate(line):
        try:
            value = float(token)
        except ValueError:
            continue
        if i == 0 or i + 1 >= len(line):
            return None
        name, unit = " ".join(line[:i]), line[i + 1]
        return dict(printed=name, canonical=canonical(name), value=value, unit=unit, ref_low=lo, ref_high=hi, flag=flag)
    return None


def extract_report(pdf_path) -> dict:
    text = read_text(pdf_path)
    rows = [r for r in (parse_line(l) for l in text.splitlines()) if r]
    return {"file": Path(pdf_path).name, **parse_header(text), "rows": rows}


def score_extraction(truth: list, folder) -> dict:
    """Field-level accuracy of the extractor against the known values of the synthetic reports."""
    fields = ok = missing = 0
    per_layout: dict = {}
    for rec in truth:
        got = {r["canonical"]: r for r in extract_report(Path(folder) / rec["file"])["rows"]}
        for row in rec["rows"]:
            g = got.get(row["canonical"])
            layout = per_layout.setdefault(rec["layout"], [0, 0])
            for key in ("value", "unit", "ref_low", "ref_high"):
                fields += 1
                layout[1] += 1
                if g is None:
                    missing += 1
                elif g[key] == row[key]:
                    ok += 1
                    layout[0] += 1
    return {"fields": fields, "correct": ok, "accuracy": round(ok / fields, 4), "missing_field_count": missing,
            "by_layout": {k: f"{a}/{b}" for k, (a, b) in sorted(per_layout.items())}}
