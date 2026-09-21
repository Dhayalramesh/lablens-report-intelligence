# LabLens: Lab Report Intelligence

Reads a patient's last three lab-report PDFs (in three different layouts), extracts each test with its value, unit and
reference range, flags abnormal results, computes trends across visits, finds cross-panel patterns, and writes a
doctor-ready summary with follow-up tests to consider.

**Live demo:** https://lablens-report-intelligence-bzhxffsgmzdvmisr2vpkrw.streamlit.app/

> **Synthetic data only. Decision support, not a diagnosis. Not a medical device.** Never upload real patient reports.

## What it does

| Step | What happens | Where |
|---|---|---|
| 1. Extract | Reads digital PDFs and parses every result row: test name, value, unit, reference range (`a - b`, `< x`, `> x`) and the printed H/L flag. Handles three layouts: table, text lines, and a table with the columns in a different order. | `lablens/extract.py` |
| 2. Normalise | Maps the different names labs print (for example "Hemoglobin A1c", "HbA1c") to one canonical test. | `lablens/catalog.py` |
| 3. Analyse | Flags results outside the report's own reference range, computes the direction and size of change across visits, and marks markers that are worsening, improving, or approaching a limit. | `lablens/analyze.py` |
| 4. Patterns | Looks for cross-panel patterns, for example rising glucose markers with worsening kidney markers, lipids with glucose, a low hemoglobin with low MCV pattern, and liver enzymes rising together. | `lablens/analyze.py` |
| 5. Summarise | Writes the consultation summary, follow-up tests to consider, discussion points and what to monitor next. | `lablens/analyze.py` |
| 6. Test data | Generates 12 synthetic reports (4 patients x 3 visits, 3 layouts) with known values. | `lablens/generate.py` |

## Safety design

- **No language model writes any number.** Every value in the summary comes from the extracted report values.
- **Hedged wording on purpose.** Patterns are "for clinician review", tests are "to consider", and every summary ends with the line: *Not a diagnosis. The clinician must review.*
- **Reference ranges are the ones printed on each report**, so a lab's own limits are used.
- Unknown test names are shown and skipped, not guessed.

## Check on the synthetic reports

| Check | Result |
|---|---|
| Extraction, 12 reports, 3 layouts (value, unit, reference limits) | 408 of 408 fields correct |
| Expected patterns found for the 4 synthetic patients | All as expected (a stable patient gets none) |

**Read these honestly:** the reports and the parser were written by the same author, so the extraction result shows the
pipeline works end to end. It does not measure accuracy on real lab formats.

## Run it

```bash
pip install -r requirements.txt
streamlit run app.py
```

The first start generates the sample PDFs into `samples/`. You can also switch the sidebar to **Upload PDFs** and use
your own synthetic reports (2 or 3 PDFs from the same patient, each showing a report date and result rows).

## Limitations and next steps

- Digital PDFs only. Scanned reports need OCR (for example Tesseract) before the same parser can read them.
- Three synthetic layouts. Real Indian lab formats vary far more, so a language-model extractor with schema
  validation, and a review step for low-confidence rows, would be the next step.
- The pattern rules are simple, hand-written and not clinically validated. Treat them as a demonstration of the design.
- A small test catalogue (17 common tests). Adding tests means adding a row in `catalog.py`.

## Layout

```
app.py                  Streamlit app (summary, extracted results, trends, extraction check, safety)
lablens/catalog.py      test names, aliases, units, reference ranges
lablens/generate.py     synthetic reports and ground truth
lablens/extract.py      PDF to structured rows, and the extraction check
lablens/analyze.py      flags, trends, patterns, summary
requirements.txt
```
