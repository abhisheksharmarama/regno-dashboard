import datetime
import pandas as pd
import streamlit as st
import rules
from data_sources import load_live_data, lookup_record

st.set_page_config(
    page_title="Admission & Fee Verdict Dashboard",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="collapsed",
)

# Power BI Brand Colors
MAROON = "#951D52"
DARK_MAROON = "#70123C"
CREAM = "#FDF8F0"
BORDER_COLOR = "#E2E8F0"
INK = "#1E293B"

st.markdown(f"""
<style>
  html, body, [class*="css"], .stApp {{
      font-family: "Segoe UI", -apple-system, BlinkMacSystemFont, Roboto, sans-serif;
      color: {INK};
      background-color: #F8FAFC;
  }}
  .block-container {{
      padding: 1rem 2rem 3rem;
      max-width: 100%;
  }}
  /* Top Power BI Ribbon */
  .pbi-header {{
      background: linear-gradient(90deg, {MAROON} 0%, {DARK_MAROON} 100%);
      color: white;
      padding: 0.9rem 1.4rem;
      border-radius: 6px;
      display: flex;
      justify-content: space-between;
      align-items: center;
      margin-bottom: 1rem;
      box-shadow: 0 4px 6px -1px rgba(0,0,0,0.1);
  }}
  .pbi-header h1 {{
      font-size: 1.35rem;
      font-weight: 700;
      margin: 0;
      letter-spacing: 0.02em;
  }}
  /* Power BI Slicer Bar */
  .slicer-box {{
      background: {CREAM};
      border: 1px solid #F3E8D8;
      border-left: 5px solid {MAROON};
      padding: 0.8rem 1rem 0.6rem;
      border-radius: 6px;
      margin-bottom: 1.2rem;
      box-shadow: 0 1px 3px rgba(0,0,0,0.05);
  }}
  /* KPI Cards */
  .kpi-container {{
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
      gap: 1rem;
      margin-bottom: 1.4rem;
  }}
  .kpi-card {{
      background: white;
      border: 1px solid {BORDER_COLOR};
      border-radius: 6px;
      padding: 1rem 1.2rem;
      box-shadow: 0 1px 3px rgba(0,0,0,0.04);
      border-top: 4px solid {MAROON};
  }}
  .kpi-card .label {{
      font-size: 0.75rem;
      font-weight: 700;
      color: #64748B;
      text-transform: uppercase;
      letter-spacing: 0.05em;
  }}
  .kpi-card .value {{
      font-size: 1.45rem;
      font-weight: 700;
      color: {INK};
      margin-top: 0.3rem;
  }}
  /* Hero Verdict Banner */
  .verdict-hero {{
      border-radius: 6px;
      padding: 1.2rem 1.4rem;
      margin: 0.8rem 0 1.2rem;
      border-left: 6px solid;
      box-shadow: 0 1px 3px rgba(0,0,0,0.05);
  }}
  .verdict-hero h2 {{ margin: 0; font-size: 1.4rem; font-weight: 700; }}
  .verdict-hero p {{ margin: 0.35rem 0 0; font-size: 0.95rem; opacity: 0.9; }}
  .verdict-hero.warn {{ background: #FFFBEB; border-color: #D97706; color: #92400E; }}
  .verdict-hero.ok {{ background: #F0FDF4; border-color: #16A34A; color: #166534; }}
  .verdict-hero.neutral {{ background: #F8FAFC; border-color: #64748B; color: #334155; }}
  .verdict-hero.miss {{ background: #FEF2F2; border-color: #DC2626; color: #991B1B; }}
  /* Power BI Styled Table */
  .pbi-table-container {{
      background: white;
      border: 1px solid {BORDER_COLOR};
      border-radius: 6px;
      overflow-x: auto;
      max-height: 480px;
      box-shadow: 0 1px 3px rgba(0,0,0,0.05);
  }}
  table.pbi-grid {{
      width: 100%;
      border-collapse: collapse;
      font-size: 0.85rem;
  }}
  table.pbi-grid th {{
      background: #F1F5F9;
      color: #334155;
      font-weight: 700;
      text-align: left;
      padding: 0.65rem 0.9rem;
      border-bottom: 2px solid {BORDER_COLOR};
      position: sticky;
      top: 0;
      z-index: 10;
  }}
  table.pbi-grid td {{
      padding: 0.55rem 0.9rem;
      border-bottom: 1px solid #F1F5F9;
      white-space: nowrap;
  }}
  table.pbi-grid tbody tr:nth-child(even) {{ background: #F8FAFC; }}
  table.pbi-grid tbody tr:hover {{ background: #F1F5F9; }}
  /* Badges */
  .badge {{
      display: inline-block;
      padding: 0.2rem 0.55rem;
      border-radius: 4px;
      font-size: 0.75rem;
      font-weight: 600;
  }}
  .badge.warn {{ background: #FEF3C7; color: #92400E; }}
  .badge.ok {{ background: #DCFCE7; color: #166534; }}
  .badge.neutral {{ background: #E2E8F0; color: #334155; }}
  .badge.miss {{ background: #FEE2E2; color: #991B1B; }}
</style>
""", unsafe_allow_html=True)

# Data Initialization
try:
    df = load_live_data()
except Exception as exc:
    st.error(f"Error loading live Google Sheet: {exc}")
    st.stop()

# Header Ribbon
st.markdown(f"""
<div class="pbi-header">
  <div>
    <h1>Registration Lookup & Fee Verification Dashboard</h1>
    <div style="font-size: 0.8rem; opacity: 0.85;">Enterprise Admission Analytics • Power BI View</div>
  </div>
  <div style="text-align: right; font-size: 0.82rem;">
    <span>Connected to Google Sheet</span>
  </div>
</div>
""", unsafe_allow_html=True)

# Slicer Strip
st.markdown('<div class="slicer-box">', unsafe_allow_html=True)
c1, c2, c3, c4 = st.columns([1.5, 1.2, 1.2, 0.6])

# 1. Date Range Slicer
valid_dates = df["_date_clean"].dropna()
if not valid_dates.empty:
    min_date, max_date = valid_dates.min(), valid_dates.max()
    with c1:
        date_selection = st.date_input(
            "📅 Date Range",
            value=(min_date, max_date),
            min_value=min_date,
            max_value=max_date,
        )
else:
    date_selection = ()
    with c1:
        st.info("No valid dates found in sheet")

# 2. Program Multiselect Slicer
programs = sorted(df["_program_clean"].dropna().unique())
with c2:
    selected_programs = st.multiselect("🎓 Program", options=programs, placeholder="All Programs")

# 3. Status/Verdict Slicer
verdict_options = list(rules.LABELS.values())
with c3:
    selected_verdicts = st.multiselect("⚖️ Fee Verdict", options=verdict_options, placeholder="All Statuses")

# 4. Refresh Button
with c4:
    st.write("")
    st.write("")
    if st.button("↻ Sync", help="Force reload latest sheet data"):
        st.cache_data.clear()
        st.rerun()
st.markdown("</div>", unsafe_allow_html=True)

# Apply Slicers
filtered_df = df.copy()

if len(date_selection) == 2:
    start_d, end_d = date_selection
    filtered_df = filtered_df[
        (filtered_df["_date_clean"] >= start_d) & (filtered_df["_date_clean"] <= end_d)
    ]

if selected_programs:
    filtered_df = filtered_df[filtered_df["_program_clean"].isin(selected_programs)]

if selected_verdicts:
    filtered_df = filtered_df[filtered_df["_verdict_label"].isin(selected_verdicts)]

# Power BI Executive KPI Metric Cards
total_records = len(filtered_df)
free_count = int((filtered_df["_verdict_code"] == rules.FREE).sum())
low_count = int((filtered_df["_verdict_code"] == rules.LOW).sum())
total_fees = filtered_df["_fee_clean"].sum()

st.markdown(f"""
<div class="kpi-container">
  <div class="kpi-card">
    <div class="label">Total In Range</div>
    <div class="value">{total_records:,}</div>
  </div>
  <div class="kpi-card" style="border-top-color: #10B981;">
    <div class="label">Total Fees Collected</div>
    <div class="value">₹ {total_fees:,.0f}</div>
  </div>
  <div class="kpi-card" style="border-top-color: #F59E0B;">
    <div class="label">Free Admissions</div>
    <div class="value">{free_count:,}</div>
  </div>
  <div class="kpi-card" style="border-top-color: #EF4444;">
    <div class="label">Paid Below ₹5,000</div>
    <div class="value">{low_count:,}</div>
  </div>
</div>
""", unsafe_allow_html=True)

# Registration Lookup Bar
st.markdown('<div style="margin-top: 0.5rem; margin-bottom: 0.2rem; font-weight: 700; font-size: 0.95rem;">⚡ Direct Registration Lookup</div>', unsafe_allow_html=True)
search_query = st.text_input("Search Reg No", placeholder="Type registration number (e.g. 23580777)...", label_visibility="collapsed")

# Hero Verdict Rendering
if search_query.strip():
    record = lookup_record(df, search_query)
    if record is None:
        st.markdown(f"""
        <div class="verdict-hero miss">
          <h2>Registration Not Found: {search_query.strip()}</h2>
          <p>This registration number does not exist in the active Google Sheet.</p>
        </div>
        """, unsafe_allow_html=True)
    else:
        program_val = record.get("_program_clean", "—")
        fee_val = record.get("_fee_clean", None)
        raw_fee = record.get("fees_paid", "")
        verdict = rules.evaluate(program_val, fee_val)

        fee_display = f"₹ {fee_val:,.2f}" if fee_val is not None else "—"
        date_display = str(record.get("_date_clean", "—"))

        st.markdown(f"""
        <div class="verdict-hero {verdict.tone}">
          <h2>{verdict.headline}</h2>
          <p>{verdict.detail}</p>
        </div>
        """, unsafe_allow_html=True)

        # Quick Fact Strip
        st.markdown(f"""
        <div style="background: white; border: 1px solid {BORDER_COLOR}; border-radius: 6px; padding: 0.9rem 1.2rem; margin-bottom: 1.2rem; display: flex; gap: 3rem; flex-wrap: wrap;">
          <div><span style="font-size: 0.72rem; color: #64748B; font-weight: 700;">REG NO</span><br><strong style="font-size: 1.1rem;">{record.get('_regno_clean', search_query)}</strong></div>
          <div><span style="font-size: 0.72rem; color: #64748B; font-weight: 700;">PROGRAM</span><br><strong style="font-size: 1.1rem;">{program_val}</strong></div>
          <div><span style="font-size: 0.72rem; color: #64748B; font-weight: 700;">FEES PAID</span><br><strong style="font-size: 1.1rem;">{fee_display}</strong></div>
          <div><span style="font-size: 0.72rem; color: #64748B; font-weight: 700;">DATE</span><br><strong style="font-size: 1.1rem;">{date_display}</strong></div>
        </div>
        """, unsafe_allow_html=True)

# Power BI Tabular Data Grid
st.markdown(f'<div style="font-weight: 700; margin-bottom: 0.4rem; display: flex; justify-content: space-between; align-items: center;"><span>📋 Records View ({len(filtered_df):,} rows)</span></div>', unsafe_allow_html=True)

if filtered_df.empty:
    st.info("No records match the selected date range and slicers.")
else:
    display_cols = [c for c in filtered_df.columns if not c.startswith("_")]
    ordered_cols = ["_verdict_label"] + display_cols

    # HTML Table Generation
    header_html = "".join([f"<th>{'Status' if c == '_verdict_label' else c}</th>" for c in ordered_cols])
    rows_html = []
    
    # Cap displayed rows in HTML grid for smooth performance
    sample_df = filtered_df.head(250)
    for row in sample_df.itertuples(index=False):
        row_dict = row._asdict()
        cells = []
        for c in ordered_cols:
            val = row_dict.get(c, "")
            if c == "_verdict_label":
                code = row_dict.get("_verdict_code", "neutral")
                tone = rules.TONE.get(code, "neutral")
                cells.append(f'<td><span class="badge {tone}">{val}</span></td>')
            else:
                cells.append(f"<td>{'' if pd.isna(val) else val}</td>")
        rows_html.append("<tr>" + "".join(cells) + "</tr>")

    st.markdown(f"""
    <div class="pbi-table-container">
      <table class="pbi-grid">
        <thead><tr>{header_html}</tr></thead>
        <tbody>{''.join(rows_html)}</tbody>
      </table>
    </div>
    """, unsafe_allow_html=True)

    # Download Button
    export_df = filtered_df.drop(columns=[c for c in filtered_df.columns if c.startswith("_")])
    st.download_button(
        "📥 Download Filtered Results as CSV",
        export_df.to_csv(index=False).encode(),
        file_name=f"admissions_audit_{datetime.date.today()}.csv",
        mime="text/csv",
    )
