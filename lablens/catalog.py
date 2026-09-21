"""Test catalogue: canonical names, the aliases different labs print, units and reference ranges (male, female)."""
import re

# name: (aliases, unit, ref_male, ref_female, decimals, group)   ref = (low, high), None = open ended
TESTS = {
    "HbA1c": (["Hemoglobin A1c", "HbA1c", "Glycosylated Hemoglobin HbA1c"], "%", (4.0, 5.6), (4.0, 5.6), 1, "Glycemic"),
    "Fasting Glucose": (["Fasting Blood Sugar", "Glucose Fasting"], "mg/dL", (70, 99), (70, 99), 0, "Glycemic"),
    "Creatinine": (["Serum Creatinine", "Creatinine"], "mg/dL", (0.7, 1.3), (0.6, 1.1), 2, "Renal"),
    "eGFR": (["eGFR", "Estimated GFR"], "mL/min/1.73m2", (90, None), (90, None), 0, "Renal"),
    "Urea": (["Blood Urea", "Urea"], "mg/dL", (17, 43), (17, 43), 0, "Renal"),
    "Total Cholesterol": (["Cholesterol Total", "Total Cholesterol"], "mg/dL", (None, 200), (None, 200), 0, "Lipid"),
    "LDL": (["LDL Cholesterol", "LDL-C"], "mg/dL", (None, 100), (None, 100), 0, "Lipid"),
    "HDL": (["HDL Cholesterol", "HDL-C"], "mg/dL", (40, None), (50, None), 0, "Lipid"),
    "Triglycerides": (["Triglycerides", "TG"], "mg/dL", (None, 150), (None, 150), 0, "Lipid"),
    "Hemoglobin": (["Hemoglobin", "Hb"], "g/dL", (13.0, 17.0), (12.0, 15.0), 1, "Blood count"),
    "MCV": (["MCV", "Mean Corpuscular Volume"], "fL", (80, 100), (80, 100), 0, "Blood count"),
    "WBC": (["Total Leukocyte Count", "WBC Count"], "10^3/uL", (4.0, 11.0), (4.0, 11.0), 1, "Blood count"),
    "Platelets": (["Platelet Count", "Platelets"], "10^3/uL", (150, 410), (150, 410), 0, "Blood count"),
    "Ferritin": (["Serum Ferritin", "Ferritin"], "ng/mL", (30, 400), (15, 150), 0, "Iron"),
    "ALT": (["ALT SGPT", "SGPT"], "U/L", (7, 56), (7, 45), 0, "Liver"),
    "AST": (["AST SGOT", "SGOT"], "U/L", (10, 40), (10, 35), 0, "Liver"),
    "TSH": (["TSH", "Thyroid Stimulating Hormone"], "uIU/mL", (0.4, 4.0), (0.4, 4.0), 2, "Thyroid"),
}


def norm(text: str) -> str:
    return re.sub(r"[^a-z0-9]", "", text.lower())


ALIAS_TO_CANONICAL = {norm(a): canon for canon, spec in TESTS.items() for a in spec[0] + [canon]}


def canonical(name: str):
    """Map a printed test name to a canonical name, or None if we do not know it."""
    return ALIAS_TO_CANONICAL.get(norm(name))
