"""LabLens: lab-report intelligence demo. Synthetic reports only. Decision support, not a diagnosis."""
import tempfile
from pathlib import Path

import altair as alt
import pandas as pd
import streamlit as st

from lablens.analyze import DISCLAIMER, analyse_patient, fmt_ref, nn
from lablens.extract import extract_report, score_extraction
from lablens.generate import generate_samples

SAMPLES = Path("samples")
st.set_page_config(page_title="LabLens", page_icon="🧪", layout="wide")


@st.cache_resource(show_spinner="Preparing synthetic sample reports...")
def prepare() -> list:
    if not (SAMPLES / "truth.json").exists():
        generate_samples(str(SAMPLES))
    import json
    return json.loads((SAMPLES / "truth.json").read_text())


@st.cache_data(show_spinner=False)
def read_sample(patient: str) -> list:
    return [extract_report(p) for p in sorted(SAMPLES.glob(f"{patient}_*.pdf"))]


@st.cache_data(show_spinner=False)
def accuracy() -> dict:
    return score_extraction(prepare(), SAMPLES)


def read_uploads(files) -> list:
    reports = []
    for f in files:
        with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp:
            tmp.write(f.getvalue())
        rep = extract_report(tmp.name)
        rep["file"] = f.name
        reports.append(rep)
    return reports


truth = prepare()
with st.sidebar:
    st.markdown("### LabLens")
    st.caption("Lab report intelligence: extract, trend, summarise. **Synthetic data only. Never upload real patient reports.**")
    mode = st.radio("Reports", ["Sample patient", "Upload PDFs"])
    if mode == "Sample patient":
        patient = st.selectbox("Patient", ["P001", "P002", "P003", "P004"],
                               format_func=lambda p: {"P001": "P001 (52 M, glucose, kidney, lipids)", "P002": "P002 (34 F, blood count)",
                                                      "P003": "P003 (45 M, liver and lipids)", "P004": "P004 (29 F, stable)"}[p])
        reports = read_sample(patient)
    else:
        files = st.file_uploader("Upload 2-3 synthetic lab report PDFs (same patient)", type="pdf", accept_multiple_files=True)
        reports = read_uploads(files) if files else []

st.title("LabLens: Lab Report Intelligence")
st.warning(DISCLAIMER + " Demo on synthetic reports, not a medical device.")

usable = [r for r in reports if r.get("date") and r["rows"]]
if len(usable) < 2:
    st.info("Pick a sample patient, or upload at least 2 report PDFs that show a report date and result rows.")
    st.stop()

res = analyse_patient(usable)
hist, trends = res["history"], res["trends"]
tab_sum, tab_rows, tab_trend, tab_eval, tab_safe = st.tabs(["Doctor-ready summary", "Extracted results", "Trends", "Extraction check", "Safety and limits"])

with tab_sum:
    a, b, c = st.columns(3)
    latest = hist[hist.date == hist.date.max()]
    a.metric("Reports read", len(usable))
    b.metric("Latest results outside range", int((latest.status != "normal").sum()))
    c.metric("Worsening markers", int((trends.movement == "worsening").sum()) if len(trends) else 0)
    st.markdown("##### Summary for the consultation")
    st.text(res["summary"])
    if res["patterns"]:
        st.markdown("##### Patterns for clinician review")
        for title, why, tests, talk in res["patterns"]:
            with st.expander(title, expanded=True):
                st.write(why)
                st.markdown("**Follow-up tests to consider:** " + "; ".join(tests))
                st.markdown("**Discussion points:** " + "; ".join(talk))
    st.download_button("Download summary (text)", res["summary"], "lablens_summary.txt")

with tab_rows:
    for rep in sorted(usable, key=lambda r: r["date"]):
        st.markdown(f"**{rep['file']}**  |  report date {rep['date']}  |  {len(rep['rows'])} results")
        df = pd.DataFrame(rep["rows"])
        df["reference"] = [fmt_ref(lo, hi) for lo, hi in zip(df.ref_low, df.ref_high)]
        st.dataframe(df[["printed", "canonical", "value", "unit", "reference", "flag"]].rename(columns={"canonical": "mapped test"}),
                     width="stretch", hide_index=True)
        unmapped = [r["printed"] for r in rep["rows"] if r["canonical"] is None]
        if unmapped:
            st.warning("Names not in the catalogue (not analysed): " + ", ".join(unmapped))

with tab_trend:
    if len(trends):
        st.dataframe(trends[["test", "group", "values", "unit", "change_pct", "latest_status", "movement"]], width="stretch", hide_index=True)
        test = st.selectbox("Chart a marker", list(trends.test))
        g = hist[hist.test == test]
        line = alt.Chart(g).mark_line(point=True, color="#2dd4bf").encode(x=alt.X("date:N", title="Report date"), y=alt.Y("value:Q", title=g.unit.iloc[0], scale=alt.Scale(zero=False)),
                                                                           tooltip=["date", "value", "status"])
        rules = [alt.Chart(pd.DataFrame({"y": [v]})).mark_rule(strokeDash=[4, 4], color="#f5a524").encode(y="y:Q")
                 for v in (nn(g.ref_low.iloc[-1]), nn(g.ref_high.iloc[-1])) if v is not None]
        st.altair_chart(alt.layer(line, *rules).properties(height=300, title=f"{test} (dashed lines = reference range)"), width="stretch")
    else:
        st.info("Trends need the same test in at least two reports.")

with tab_eval:
    acc = accuracy()
    st.markdown("Field-level check of the extractor on the 12 synthetic reports in 3 layouts (value, unit and reference limits).")
    a, b, c = st.columns(3)
    a.metric("Fields checked", acc["fields"])
    b.metric("Correct", acc["correct"])
    c.metric("Accuracy", f"{acc['accuracy']:.0%}")
    st.json(acc["by_layout"])
    st.caption("The reports and the parser were written by the same author, so this shows the pipeline works, not how it would do on real lab formats.")

with tab_safe:
    st.markdown("""
- Every number in the summary comes from the extracted values. No language model writes numbers.
- Wording is deliberately hedged: patterns are for clinician review, follow-up tests are for consideration, nothing is a diagnosis.
- Reference ranges are the ones printed on each report. The pattern rules are simple and were written by the author, not clinically validated.
- Only digital PDFs are read. Scanned reports would need OCR, which is the next step.
- Synthetic data only. Do not upload real patient information.
""")
