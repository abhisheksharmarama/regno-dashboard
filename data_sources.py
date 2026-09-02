import re
import pandas as pd
import streamlit as st
import rules

REGNO_ALIASES = ["regno", "reg_no", "registration_no", "registration number", "reg no", "student_reg_no"]
PROGRAM_ALIASES = ["all_program", "program", "program_name", "course", "program name"]
FEE_ALIASES = ["fees_paid", "fee_paid", "fees", "fee", "amount_paid", "paid_amount"]
DATE_ALIASES = ["joining_date", "joining_date_timestamp", "admission_date", "date", "timestamp", "call date", "created_at"]

def clean_regno(value) -> str:
    if value is None:
        return ""
    if isinstance(value, float) and value.is_integer():
        value = int(value)
    text = str(value).strip()
    text = re.sub(r"\.0+$", "", text)
    return re.sub(r"\D", "", text)

def find_column(df: pd.DataFrame, aliases: list[str]) -> str | None:
    lowered = {str(c).strip().casefold(): c for c in df.columns}
    for alias in aliases:
        if alias in lowered:
            return lowered[alias]
    return None

# Disabled default spinner; UI handles it now for a lag-free visual experience
@st.cache_data(show_spinner=False)
def load_live_data(sync_key: str) -> pd.DataFrame:
    cfg = dict(st.secrets.get("sheet", {}))
    url = cfg.get("csv_url")
    if not url:
        raise ValueError("Google Sheet CSV URL is missing in Streamlit Secrets.")

    # High-speed pyarrow engine parses massive files significantly faster
    df = pd.read_csv(url, dtype=str, keep_default_na=False, engine="pyarrow")
    df.columns = [str(c).strip() for c in df.columns]

    reg_col = find_column(df, REGNO_ALIASES) or df.columns[0]
    prog_col = find_column(df, PROGRAM_ALIASES)
    fee_col = find_column(df, FEE_ALIASES)
    date_col = find_column(df, DATE_ALIASES)

    df["_regno_clean"] = df[reg_col].map(clean_regno)
    df["_program_clean"] = df[prog_col] if prog_col else "Unknown"
    df["_fee_clean"] = df[fee_col].map(rules.parse_fee) if fee_col else 0.0

    if date_col:
        df["_date_clean"] = pd.to_datetime(df[date_col], errors="coerce", dayfirst=True).dt.date
    else:
        df["_date_clean"] = pd.NaT

    df["_verdict_code"] = rules.evaluate_frame(df["_program_clean"], df[fee_col] if fee_col else pd.Series())
    df["_verdict_label"] = df["_verdict_code"].map(rules.LABELS)

    return df.set_index("_regno_clean", drop=False)

def lookup_record(df: pd.DataFrame, regno: str):
    key = clean_regno(regno)
    if not key or key not in df.index:
        return None
    row = df.loc[key]
    if isinstance(row, pd.DataFrame):
        row = row.iloc[0]
    return row
