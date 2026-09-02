from __future__ import annotations
from dataclasses import dataclass
import re
import math
import numpy as np
import pandas as pd

# Programs with rules applied
RULES_PROGRAMS = {
    "vidyapeeth",
    "tuition center",
    "pathshala",
    "vprp",
}

# Exempt programs
NO_RULE_PROGRAMS = {
    "vp-mip",
    "fastrack",
    "vpmip dt",
    "aits",
}

# The < 5000 floor applies to all four target programs
LOW_FEE_PROGRAMS = RULES_PROGRAMS
LOW_FEE_THRESHOLD = 5000.0

FREE = "free"
LOW = "low"
CLEAR = "clear"
EXEMPT = "exempt"
NO_FEE_DATA = "no_fee_data"
UNKNOWN_PROGRAM = "unknown_program"

LABELS = {
    FREE: "Free admission",
    LOW: "Amount paid is less than 5000",
    CLEAR: "Fee in range",
    EXEMPT: "No fee rule for this program",
    NO_FEE_DATA: "Fees not recorded",
    UNKNOWN_PROGRAM: "Program not recognised",
}

TONE = {
    FREE: "warn",
    LOW: "warn",
    CLEAR: "ok",
    EXEMPT: "neutral",
    NO_FEE_DATA: "neutral",
    UNKNOWN_PROGRAM: "miss",
}

@dataclass(frozen=True)
class Verdict:
    code: str
    headline: str
    detail: str

    @property
    def tone(self) -> str:
        return TONE.get(self.code, "neutral")

def normalise_program(program) -> str:
    if program is None:
        return ""
    return str(program).strip().casefold()

def parse_fee(val) -> float | None:
    """Safely extracts numeric float from strings with currency signs, commas, or blanks."""
    if val is None or pd.isna(val):
        return None
    s = str(val).strip()
    if not s or s.lower() in {"na", "n/a", "none", "null", "-", "nil"}:
        return None
    cleaned = re.sub(r"[^\d.-]", "", s)
    if not cleaned or cleaned in {"-", ".", "-."}:
        return None
    try:
        return float(cleaned)
    except Exception:
        return None

def evaluate(program, fees_paid) -> Verdict:
    key = normalise_program(program)
    shown = str(program).strip() if program is not None else "(blank)"

    if key in NO_RULE_PROGRAMS:
        return Verdict(EXEMPT, LABELS[EXEMPT], f"{shown} is exempt from fee checks.")

    if key not in RULES_PROGRAMS:
        return Verdict(UNKNOWN_PROGRAM, LABELS[UNKNOWN_PROGRAM], f"'{shown}' is unrecognised in rule policies.")

    fee = parse_fee(fees_paid)
    if fee is None:
        return Verdict(NO_FEE_DATA, LABELS[NO_FEE_DATA], "This record has no fee recorded.")

    if fee <= 0:
        return Verdict(FREE, LABELS[FREE], f"Recorded fee is ₹ {fee:,.2f}. Marked as Free Admission.")

    if key in LOW_FEE_PROGRAMS and fee < LOW_FEE_THRESHOLD:
        return Verdict(LOW, LABELS[LOW], f"Collected ₹ {fee:,.2f} against the ₹ {LOW_FEE_THRESHOLD:,.0f} threshold.")

    return Verdict(CLEAR, LABELS[CLEAR], f"Collected ₹ {fee:,.2f} (Standard).")

def evaluate_frame(programs: pd.Series, fees: pd.Series) -> pd.Series:
    """Vectorised evaluator for high-speed table filtering."""
    key = programs.astype("string").str.strip().str.casefold()
    cleaned_fees = fees.astype(str).str.replace(r"[^\d.-]", "", regex=True)
    numeric_fees = pd.to_numeric(cleaned_fees, errors="coerce")

    conditions = [
        key.isin(NO_RULE_PROGRAMS),
        ~key.isin(RULES_PROGRAMS),
        numeric_fees.isna(),
        numeric_fees <= 0,
        key.isin(LOW_FEE_PROGRAMS) & (numeric_fees < LOW_FEE_THRESHOLD),
    ]
    outcomes = [EXEMPT, UNKNOWN_PROGRAM, NO_FEE_DATA, FREE, LOW]
    return pd.Series(np.select(conditions, outcomes, default=CLEAR), index=programs.index, dtype="string")
