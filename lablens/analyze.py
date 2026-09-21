"""Trend analysis and doctor-ready summaries built ONLY from the extracted values (no LLM, no invented numbers).

Decision support for a clinician to review. It does not diagnose.
"""
import pandas as pd

from .catalog import TESTS


def nn(x):
    """NaN -> None (pandas stores open-ended reference limits as NaN)."""
    return None if x is None or pd.isna(x) else float(x)


def fmt_ref(lo, hi) -> str:
    lo, hi = nn(lo), nn(hi)
    if lo is not None and hi is not None:
        return f"{lo:g}-{hi:g}"
    return f"<{hi:g}" if lo is None else f">{lo:g}"


DISCLAIMER = "Decision support generated from the extracted values only. Not a diagnosis. The clinician must review."


def status(v, lo, hi) -> str:
    if lo is not None and v < lo:
        return "low"
    if hi is not None and v > hi:
        return "high"
    return "normal"


def outside(v, lo, hi) -> float:
    """How far outside the reference range a value is, as a fraction of the nearest limit (0 = inside)."""
    if lo is not None and v < lo:
        return (lo - v) / abs(lo)
    if hi is not None and v > hi:
        return (v - hi) / abs(hi)
    return 0.0


def build_history(reports: list) -> pd.DataFrame:
    rows = [dict(date=rep["date"], test=r["canonical"], value=r["value"], unit=r["unit"], ref_low=r["ref_low"], ref_high=r["ref_high"],
                 status=status(r["value"], r["ref_low"], r["ref_high"]), group=TESTS[r["canonical"]][5])
            for rep in reports for r in rep["rows"] if r["canonical"]]
    return pd.DataFrame(rows).sort_values(["test", "date"]).reset_index(drop=True)


def approaching(v, lo, hi, direction) -> str:
    """Inside the range but close to a limit and moving toward it."""
    if hi is not None and direction == "rising" and ((lo is not None and (v - lo) / (hi - lo) > 0.85) or (lo is None and v >= 0.9 * hi)):
        return "upper limit"
    if lo is not None and direction == "falling" and ((hi is not None and (v - lo) / (hi - lo) < 0.15) or (hi is None and v <= 1.1 * lo)):
        return "lower limit"
    return ""


def trend_table(hist: pd.DataFrame) -> pd.DataFrame:
    out = []
    for test, g in hist.groupby("test"):
        if len(g) < 2:
            continue
        first, last = g.iloc[0], g.iloc[-1]
        pct = (last.value - first.value) / abs(first.value) * 100 if first.value else 0.0
        direction = "stable" if abs(pct) < 5 else ("rising" if pct > 0 else "falling")
        lo, hi = nn(last.ref_low), nn(last.ref_high)
        d0, d1 = outside(first.value, nn(first.ref_low), nn(first.ref_high)), outside(last.value, lo, hi)
        near = approaching(last.value, lo, hi, direction) if d1 == 0 else ""
        movement = "worsening" if d1 > d0 + 0.02 else "improving" if d1 < d0 - 0.02 else ("approaching " + near if near else "stable")
        out.append(dict(test=test, group=last.group, unit=last.unit, values=" \u2192 ".join(f"{v:g}" for v in g.value), first=first.value,
                        last=last.value, change_pct=round(pct, 1), direction=direction, latest_status=last.status, movement=movement,
                        ref_low=last.ref_low, ref_high=last.ref_high))
    return pd.DataFrame(out)


def patterns(trends: pd.DataFrame) -> list:
    """Cross-panel patterns: (title, why, follow-up tests to consider, what to discuss)."""
    t = {r.test: r for r in trends.itertuples()}
    high = lambda n: n in t and t[n].latest_status == "high"          # noqa: E731
    low = lambda n: n in t and t[n].latest_status == "low"            # noqa: E731
    moving = lambda n, d: n in t and t[n].direction == d              # noqa: E731
    found = []
    glyc = [n for n in ("HbA1c", "Fasting Glucose") if high(n) and moving(n, "rising")]
    renal = (moving("Creatinine", "rising") and t["Creatinine"].movement != "stable") or (moving("eGFR", "falling") and t["eGFR"].movement != "stable") \
        if ("Creatinine" in t or "eGFR" in t) else False
    if glyc and renal:
        found.append(("Rising glucose markers with declining kidney-function markers",
                      f"{' and '.join(glyc)} above range and rising, while creatinine/eGFR are worsening across visits.",
                      ["Urine albumin-to-creatinine ratio", "Repeat creatinine and eGFR", "Repeat HbA1c in about 3 months"],
                      ["Glycemic control and medication adherence", "Kidney-safe prescribing"]))
    if (high("LDL") or high("Total Cholesterol")) and (glyc or high("Triglycerides")):
        found.append(("Lipid markers and glucose/triglycerides above range together",
                      "LDL or total cholesterol is high alongside high triglycerides or rising glucose markers.",
                      ["Fasting lipid profile repeat", "Blood pressure and cardiovascular risk assessment"],
                      ["Diet, activity and weight", "Whether lipid-lowering treatment is under review"]))
    if low("Hemoglobin") and low("MCV"):
        extra = " Ferritin is also low." if low("Ferritin") else ""
        found.append(("Low hemoglobin with low MCV (microcytic pattern)",
                      "Hemoglobin and MCV are both below range and trending down." + extra,
                      ["Iron studies (serum iron, TIBC, transferrin saturation)", "Peripheral blood smear", "Repeat complete blood count"],
                      ["Diet, blood-loss history and menstrual history", "Symptoms of anaemia"]))
    if high("ALT") and high("AST") and moving("ALT", "rising"):
        found.append(("Liver enzymes above range and rising",
                      "ALT and AST are both above range, with ALT rising across visits." + (" Triglycerides are also high." if high("Triglycerides") else ""),
                      ["Repeat liver panel", "Bilirubin and GGT", "Imaging as clinically indicated"],
                      ["Medicines, supplements and alcohol history", "Weight and metabolic risk"]))
    return found


def summarise(patient: dict, hist: pd.DataFrame, trends: pd.DataFrame, pats: list) -> str:
    dates = sorted(hist.date.unique())
    latest = hist[hist.date == dates[-1]]
    lines = [f"Patient {patient.get('patient')} ({patient.get('age')} {patient.get('sex')}): {len(dates)} reports, {dates[0]} to {dates[-1]}."]
    flagged = latest[latest.status != "normal"]
    lines.append("Latest results outside the reference range: " + (
        "; ".join(f"{r.test} {r.value:g} {r.unit} ({r.status}, ref {fmt_ref(r.ref_low, r.ref_high)})"
                  for r in flagged.itertuples()) or "none") + ".")
    worse = trends[trends.movement == "worsening"]
    if len(worse):
        lines.append("Worsening across visits: " + "; ".join(f"{r.test} {r.values} {r.unit} ({r.change_pct:+g}%)" for r in worse.itertuples()) + ".")
    better = trends[trends.movement == "improving"]
    if len(better):
        lines.append("Improving: " + "; ".join(f"{r.test} {r.values} {r.unit}" for r in better.itertuples()) + ".")
    near = trends[trends.movement.str.startswith("approaching")]
    if len(near):
        lines.append("Within range but moving toward a limit: " + "; ".join(f"{r.test} {r.values} {r.unit}" for r in near.itertuples()) + ".")
    for title, why, tests, talk in pats:
        lines.append(f"Pattern for clinician review: {title}. {why}")
    if pats:
        lines.append("Follow-up tests to consider: " + "; ".join(dict.fromkeys(x for p in pats for x in p[2])) + ".")
        lines.append("Discussion points: " + "; ".join(dict.fromkeys(x for p in pats for x in p[3])) + ".")
    watch = list(worse.test) + list(near.test)
    lines.append("Monitor next: " + (", ".join(dict.fromkeys(watch)) if watch else "no marker is trending toward a limit") + ".")
    lines.append(DISCLAIMER)
    return "\n".join(lines)


def analyse_patient(reports: list) -> dict:
    reports = sorted(reports, key=lambda r: r["date"])
    hist = build_history(reports)
    trends = trend_table(hist)
    pats = patterns(trends) if len(trends) else []
    meta = {k: reports[-1].get(k) for k in ("patient", "age", "sex")}
    return dict(history=hist, trends=trends, patterns=pats, summary=summarise(meta, hist, trends, pats), meta=meta)
