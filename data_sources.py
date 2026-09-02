import re
import pandas as pd
import streamlit as st
import rules

def clean_regno(value) -> str:
    """Reduce anything that looks like a reg no to bare digits."""
    if value is None:
        return ""
    if isinstance(value, float) and value.is_integer():
        value = int(value)
    text = str(value).strip()
    text = re.sub(r"\.0+$", "", text)
    return re.sub(r"\D", "", text)

@st.cache_data(ttl=60, show_spinner="Syncing live with Google Sheets...")
def load_live_data() -> pd.DataFrame:
    """Fetches the ERP dump directly from the published Google Sheet CSV."""
    cfg = dict(st.secrets.get("sheet", {}))
    url = cfg.get("csv_url")
    
    if not url:
        raise ValueError("Google Sheet CSV URL is missing in Streamlit secrets.")
        
    df = pd.read_csv(url, dtype=str, keep_default_na=False)
    
    # Standardize column names to lowercase for easier matching internally
    df.columns = [str(c).strip().casefold() for c in df.columns]
    
    # Find registration column
    regcol = "regno" if "regno" in df.columns else df.columns[0]
    df["regno_key"] = df[regcol].map(clean_regno)
    
    # Precompute verdicts
    if "all_program" in df.columns and "fees_paid" in df.columns:
        df["verdict"] = rules.evaluate_frame(df["all_program"], df["fees_paid"])
        
    return df.set_index("regno_key", drop=False)

def lookup_record(df: pd.DataFrame, regno: str):
    """Finds a single registration instantly."""
    key = clean_regno(regno)
    if not key or key not in df.index:
        return None
    row = df.loc[key]
    if isinstance(row, pd.DataFrame): 
        row = row.iloc[0]
    return row
