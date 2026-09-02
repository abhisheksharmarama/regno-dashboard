from __future__ import annotations
from dataclasses import dataclass
import math
import numpy as np
import pandas as pd

RULES_PROGRAMS = {
    "vidyapeeth",
    "tuition center",
    "pathshala",
    "vprp",
}

NO_RULE_PROGRAMS = {
    "vp-mip",
    "fastrack",
    "vpmip dt",
    "aits",
}

LOW_FEE_PROGRAMS = RULES_PROGRAMS
LOW_FEE_THRESHOLD = 5000.0

FREE = "free"
LOW = "low"
CLEAR = "clear"
EXEMPT = "exempt"
NO_FEE_DATA = "no_fee_data"
UNKNOWN_PROGRAM = "unknown_program"

TONE = {
    FREE: "warn",
    LOW: "warn",
    CLEAR: "ok",
    EXEMPT: "neutral",
    NO_FEE_DATA: "neutral",
    UNKNOWN_PROGRAM: "neutral",
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

def _is_missing(value) -> bool:
    if value is None:
        return True
    if isinstance(value, str) and value.strip() == "":
        return True
    try:
        return math.isnan(float(value))
    except (TypeError, ValueError):
        return True

def evaluate(program, fees_paid) -> Verdict:
    key = normalise_program(program)
    shown = str(program).strip() if program is not None else "(blank)"

    if key in NO_RULE_PROGRAMS:
        return Verdict(EXEMPT, "No fee rule for this program", f"{shown} is outside the rule set.")

    if key not in RULES_PROGRAMS:
        return Verdict(UNKNOWN_PROGRAM, "Program not recognised", f"'{shown}' is in neither the rules list nor the exempt list.")

    if _is_missing(fees_paid):
        return Verdict(NO_FEE_DATA, "Fees not recorded", "This registration has no fees_paid value.")

    fee = float(fees_paid)

    if fee < 0:
        return Verdict(FREE, "Free admission", f"Recorded fee is negative ({fee:,.2f}), treated as zero.")

    if fee == 0:
        return Verdict(FREE, "Free admission", "No fee was collected.")

    if key in LOW_FEE_PROGRAMS and fee < LOW_FEE_THRESHOLD:
        return Verdict(LOW, "Amount paid is less than 5000", f"Collected {fee:,.2f} against a {LOW_FEE_THRESHOLD:,.0f} floor.")

    return Verdict(CLEAR, "Fee is in range", f"Collected {fee:,.2f}.")

def evaluate_frame(programs: pd.Series, fees: pd.Series) -> pd.Series:
    key = programs.astype("string").str.strip().str.casefold()
    fee = pd.to_numeric(fees, errors="coerce")

    conditions = [
        key.isin(NO_RULE_PROGRAMS),
        ~key.isin(RULES_PROGRAMS),
        fee.isna(),
        fee <= 0,
        key.isin(LOW_FEE_PROGRAMS) & (fee < LOW_FEE_THRESHOLD),
    ]
    outcomes = [EXEMPT, UNKNOWN_PROGRAM, NO_FEE_DATA, FREE, LOW]

    return pd.Series(
        np.select(conditions, outcomes, default=CLEAR),
        index=programs.index,
        dtype="string",
    )
