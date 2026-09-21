"""Synthetic lab reports in three different layouts (no real patient data)."""
import json
import random
from pathlib import Path

from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table

from .catalog import TESTS

DATES = [("2025-03-12", "12-Mar-2025"), ("2025-08-20", "20-Aug-2025"), ("2026-01-15", "15-Jan-2026")]
LABS = ["Sunrise Diagnostics", "CityCare Pathology Lab", "Metro Health Labs"]

# patient -> (age, sex, {test: [value at visit 1, 2, 3]})
PATIENTS = {
    "P001": (52, "M", {"HbA1c": [6.1, 6.6, 7.2], "Fasting Glucose": [108, 121, 138], "Creatinine": [1.0, 1.2, 1.4], "eGFR": [88, 74, 62],
                       "Urea": [30, 36, 44], "Total Cholesterol": [205, 218, 232], "LDL": [128, 140, 152], "HDL": [42, 40, 38],
                       "Triglycerides": [165, 190, 220], "Hemoglobin": [14.8, 14.6, 14.2], "TSH": [2.1, 2.3, 2.2]}),
    "P002": (34, "F", {"Hemoglobin": [11.8, 11.0, 10.2], "MCV": [76, 72, 68], "Ferritin": [18, 12, 8], "WBC": [6.8, 7.1, 6.9],
                       "Platelets": [310, 330, 350], "TSH": [2.8, 3.1, 3.5], "HbA1c": [5.2, 5.2, 5.3]}),
    "P003": (45, "M", {"ALT": [45, 68, 95], "AST": [38, 52, 70], "Triglycerides": [180, 210, 260], "Total Cholesterol": [210, 224, 236],
                       "LDL": [118, 126, 133], "HDL": [38, 36, 35], "Fasting Glucose": [96, 104, 112], "Hemoglobin": [15.1, 15.0, 15.2]}),
    "P004": (29, "F", {"Hemoglobin": [13.4, 13.2, 13.5], "HbA1c": [5.0, 5.1, 5.0], "Total Cholesterol": [168, 172, 165], "LDL": [88, 90, 86],
                       "HDL": [58, 60, 57], "Triglycerides": [98, 105, 92], "TSH": [1.9, 2.0, 1.8], "WBC": [6.2, 6.0, 6.4]}),
}


def ref_text(lo, hi) -> str:
    if lo is not None and hi is not None:
        return f"{lo:g} - {hi:g}"
    return f"< {hi:g}" if lo is None else f"> {lo:g}"


def flag_for(value, lo, hi) -> str:
    if lo is not None and value < lo:
        return "L"
    if hi is not None and value > hi:
        return "H"
    return ""


def make_rows(sex, values):
    rows = []
    for name, value in values.items():
        aliases, unit, ref_m, ref_f, dp, _ = TESTS[name]
        lo, hi = ref_m if sex == "M" else ref_f
        rows.append(dict(canonical=name, printed=aliases[0], value=round(value, dp), unit=unit, ref_low=lo, ref_high=hi,
                         flag=flag_for(value, lo, hi)))
    return rows


def write_pdf(path: Path, patient_id, age, sex, iso, printed_date, rows, layout: str, lab: str):
    styles = getSampleStyleSheet()
    body = styles["BodyText"]
    story = [Paragraph(f"<b>{lab}</b>", styles["Title"]),
             Paragraph(f"Patient ID: {patient_id} &nbsp;&nbsp; Age / Sex: {age} / {sex}", body),
             Paragraph(f"Report Date: {printed_date if layout != 'B' else iso}", body), Spacer(1, 10)]
    if layout == "A":
        table = [["Test", "Result", "Unit", "Reference Range", "Flag"]] + [
            [r["printed"], r["value"], r["unit"], ref_text(r["ref_low"], r["ref_high"]), r["flag"]] for r in rows]
        story.append(Table(table))
    elif layout == "C":
        table = [["Investigation", "Reference Interval", "Observed Value", "Units"]] + [
            [r["printed"], ref_text(r["ref_low"], r["ref_high"]), r["value"], r["unit"]] for r in rows]
        story.append(Table(table))
    else:  # layout B: plain text lines
        for r in rows:
            mark = {"H": " *HIGH*", "L": " *LOW*", "": ""}[r["flag"]]
            story.append(Paragraph(f"{r['printed']} : {r['value']} {r['unit']} ( Ref: {ref_text(r['ref_low'], r['ref_high'])} ){mark}", body))
    SimpleDocTemplate(str(path), pagesize=A4).build(story)


def generate_samples(out_dir="samples", seed=7):
    rng = random.Random(seed)
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    truth = []
    for pid, (age, sex, series) in PATIENTS.items():
        for visit, (iso, printed) in enumerate(DATES):
            values = {t: v[visit] for t, v in series.items()}
            rows = make_rows(sex, values)
            layout = "ABC"[(int(pid[-1]) + visit) % 3]
            lab = LABS[rng.randrange(len(LABS))]
            path = out / f"{pid}_{iso}_layout{layout}.pdf"
            write_pdf(path, pid, age, sex, iso, printed, rows, layout, lab)
            truth.append(dict(file=path.name, patient=pid, date=iso, sex=sex, layout=layout, rows=rows))
    (out / "truth.json").write_text(json.dumps(truth, indent=1))
    return truth
