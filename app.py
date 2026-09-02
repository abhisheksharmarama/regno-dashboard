import pandas as pd
import streamlit as st
import rules
from data_sources import load_live_data, lookup_record

st.set_page_config(page_title="Registration lookup", layout="wide", initial_sidebar_state="collapsed")

MAROON, CREAM, ROW_ALT, INK, RULE = "#951D52", "#F7EAD3", "#EBECEE", "#161C30", "#E1E1E1"

st.markdown(f"""
<style>
  html, body, [class*="css"], .stApp {{ font-family: "Segoe UI", sans-serif; color: {INK}; }}
  .stApp {{ background: #FFFFFF; }}
  header[data-testid="stHeader"] {{ background: transparent; }}
  .block-container {{ padding: 0.75rem 1.25rem 3rem; max-width: 100%; }}
  .search-wrap .stTextInput input {{ font-size: 1.35rem; font-weight: 600; border: 2px solid {MAROON}; border-radius: 2px; padding: 0.6rem 0.9rem; color: {INK}; }}
  .verdict {{ border-left: 6px solid; padding: 0.9rem 1.1rem; margin: 0.6rem 0 1rem; }}
  .verdict h3 {{ margin: 0; font-size: 1.35rem; font-weight: 700; }}
  .verdict p  {{ margin: 0.3rem 0 0; font-size: 0.92rem; opacity: 0.8; }}
  .verdict.warn {{ background: #FDF1E4; border-color: #C2571A; color: #7A3308; }}
  .verdict.ok {{ background: #EDF6EE; border-color: #2E7D32; color: #1B4D1E; }}
  .verdict.neutral {{ background: #F2F2F3; border-color: #7A7A7A; color: #3B3B3B; }}
  .verdict.miss {{ background: #FBECEF; border-color: {MAROON}; color: {MAROON}; }}
  .facts {{ display: flex; flex-wrap: wrap; gap: 2.5rem; padding: 0.25rem 0 1.1rem; }}
  .fact {{ min-width: 130px; }}
  .fact .k {{ font-size: 0.72rem; font-weight: 700; color: #6B6B6B; }}
  .fact .v {{ font-size: 1.15rem; font-weight: 600; color: {INK}; }}
  .pbi-scroll {{ overflow-x: auto; border-top: 1px solid {RULE}; }}
  table.pbi {{ border-collapse: collapse; width: 100%; font-size: 0.86rem; }}
  table.pbi th {{ text-align: left; font-weight: 600; color: {INK}; padding: 0.55rem 0.85rem 0.55rem 0; white-space: nowrap; border-bottom: 1px solid {RULE}; }}
  table.pbi td {{ padding: 0.45rem 0.85rem 0.45rem 0; white-space: nowrap; color: {INK}; }}
  table.pbi tbody tr:nth-child(even) {{ background: {ROW_ALT}; }}
</style>
""", unsafe_allow_html=True)

def fact(label: str, value: str) -> str:
    return f'<div class="fact"><div class="k">{label}</div><div class="v">{value}</div></div>'

try:
    df = load_live_data()
except Exception as exc:
    st.error(f"Failed to load Google Sheet: {exc}")
    st.stop()

st.markdown('<div class="search-wrap">', unsafe_allow_html=True)
query = st.text_input("Reg No", placeholder="e.g. 23570543", help="Enter a registration number and press Enter.")
st.markdown("</div>", unsafe_allow_html=True)

if not query.strip():
    st.caption(f"{len(df):,} registrations loaded directly from Google Sheets.")
    st.stop()

record = lookup_record(df, query)

if record is None:
    st.markdown(f'<div class="verdict miss"><h3>No registration {query.strip()}</h3><p>This number is not in the Sheet.</p></div>', unsafe_allow_html=True)
    st.stop()

program = record.get("all_program")
fees = record.get("fees_paid")
verdict = rules.evaluate(program, fees)

st.markdown(f'<div class="verdict {verdict.tone}"><h3>{verdict.headline}</h3><p>{verdict.detail}</p></div>', unsafe_allow_html=True)

fees_txt = "—" if pd.isna(fees) or str(fees).strip() == "" else f"{float(fees):,.2f}"

st.markdown(
    '<div class="facts">'
    + fact("Reg No", str(record.get("regno", query)))
    + fact("Program", str(program))
    + fact("Fees paid", fees_txt)
    + "</div>",
    unsafe_allow_html=True,
)

st.markdown("### Record Details")
row_df = pd.DataFrame([record]).drop(columns=["regno_key", "verdict"], errors="ignore")

head = "".join(f"<th>{c}</th>" for c in row_df.columns)
body = "".join("<tr>" + "".join(f"<td>{'' if pd.isna(v) else v}</td>" for v in row) + "</tr>" for row in row_df.itertuples(index=False))
st.markdown(f'<div class="pbi-scroll"><table class="pbi"><thead><tr>{head}</tr></thead><tbody>{body}</tbody></table></div>', unsafe_allow_html=True)
