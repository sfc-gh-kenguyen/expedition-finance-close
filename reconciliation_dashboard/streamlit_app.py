"""Close Readiness Monitor — reads from Snowflake tables built earlier in the lab."""

from datetime import timedelta

import altair as alt
import pandas as pd
import streamlit as st

st.set_page_config(page_title="Meridian Stay: November 2026 Close", layout="wide")

conn = st.connection("snowflake")


def normalize_system(label) -> str:
    """Map source-system labels to the names the dashboard expects (CoCo may write BANK_STATEMENT, GL, ...)."""
    s = str(label).strip().lower()
    if "bank" in s:
        return "Bank Statement"
    if "ledger" in s or s.startswith("gl"):
        return "General Ledger"
    if "payroll" in s:
        return "Payroll Register"
    return label


@st.cache_data(ttl=60)
def load_transactions() -> pd.DataFrame:
    df = conn.query(
        """
        SELECT transaction_id, transaction_date, description, amount,
               department, category, source_system, reference_id
        FROM MERIDIAN_STAY_FINANCE.CURATED.TRANSACTIONS
        ORDER BY transaction_date, transaction_id
        """,
        ttl=60,
    )
    df.columns = [c.lower() for c in df.columns]
    df["transaction_date"] = pd.to_datetime(df["transaction_date"])
    df["amount"] = pd.to_numeric(df["amount"])
    df["source_system"] = df["source_system"].map(normalize_system)
    return df


@st.cache_data(ttl=60)
def load_gaps() -> set:
    df = conn.query(
        """
        SELECT transaction_id
        FROM MERIDIAN_STAY_FINANCE.CURATED.RECONCILIATION_GAPS
        """,
        ttl=60,
    )
    df.columns = [c.lower() for c in df.columns]
    return set(df["transaction_id"])


try:
    txns = load_transactions()
    gap_ids = load_gaps()
except Exception:
    st.error(
        "The reconciliation tables aren't ready yet. Finish STEP 3 and STEP 4 in the "
        "notebook (CURATED.TRANSACTIONS and CURATED.RECONCILIATION_GAPS), then rerun this app."
    )
    st.stop()
bank = txns[txns["source_system"] == "Bank Statement"].sort_values(
    ["transaction_date", "transaction_id"]
).reset_index(drop=True)

bank_total = len(bank)
if bank_total == 0:
    st.error(
        "No bank transactions found in CURATED.TRANSACTIONS. Check that STEP 3 set source_system "
        "to 'Bank Statement' for the bank rows, then rerun this app."
    )
    st.stop()
bank_matched = bank_total - len(gap_ids)
bank_unmatched = len(gap_ids)
gap_amount = bank.loc[bank["transaction_id"].isin(gap_ids), "amount"].sum()

# ══════════════════════════════════════════════════════════════════════════════
# DASHBOARD
# ══════════════════════════════════════════════════════════════════════════════

st.title("Meridian Stay: November 2026 Close")

# ── Readiness metrics ─────────────────────────────────────────────────────────
recon_pct = round(100 * bank_matched / bank_total)
ready = recon_pct == 100
m1, m2, m3 = st.columns(3)
m1.metric("Bank Reconciled", f"{bank_matched} of {bank_total} ({recon_pct}%)")
if ready:
    m2.metric("Close Readiness", ":green[Ready]")
else:
    m2.metric("Close Readiness", "Not Ready", delta=f"{bank_unmatched} gaps remain", delta_color="inverse")
m3.metric("Unreconciled", f"${gap_amount:,.0f}")

# ── Waterfall chart ───────────────────────────────────────────────────────────
st.subheader("Bank account: November cash flow")
st.caption(
    "Each bar is a payment leaving the account. "
    "**Blue** = matched to a general ledger entry. "
    "**Red** = no GL match found. "
    "Red triangles mark the unmatched transactions."
)

OPENING = 566_500.00
running = OPENING
rows = [{"label": "Open\nNov 1", "start": 0, "end": running, "amount": running,
         "description": "Opening balance Nov 1", "date": "Nov 1", "status": "balance",
         "sort": 0, "show_label": True}]

for i, (_, row) in enumerate(bank.iterrows()):
    prev = running
    running -= row["amount"]
    is_gap = row["transaction_id"] in gap_ids
    dt_str = row["transaction_date"].strftime("%b %-d")
    display = f"{row['transaction_id']}\n{dt_str}" if is_gap else ""
    rows.append({
        "label": f"_{i+1}" if not is_gap else display,
        "display_label": display,
        "start": running, "end": prev,
        "amount": row["amount"],
        "description": row["description"],
        "date": dt_str,
        "status": "unmatched" if is_gap else "matched",
        "sort": i + 1,
        "show_label": is_gap,
    })

rows.append({"label": "Close\nNov 30", "start": 0, "end": running, "amount": running,
             "description": "Closing balance Nov 30", "date": "Nov 30", "status": "balance",
             "sort": len(rows), "show_label": True})

wf = pd.DataFrame(rows)

bars = (
    alt.Chart(wf)
    .mark_bar(cornerRadiusTopLeft=3, cornerRadiusTopRight=3)
    .encode(
        x=alt.X("label:N", title=None,
                 sort=alt.SortField("sort"),
                 axis=alt.Axis(labelAngle=-45, labelFontSize=10, labelLimit=120, ticks=False,
                               labelExpr="substring(datum.value, 0, 1) == '_' ? '' : datum.value")),
        y=alt.Y("start:Q", title="Balance ($)", axis=alt.Axis(format="$,.0f"),
                 scale=alt.Scale(domain=[0, OPENING * 1.02])),
        y2="end:Q",
        color=alt.Color(
            "status:N", title="Status",
            scale=alt.Scale(domain=["matched", "unmatched", "balance"],
                            range=["#3b82f6", "#ef4444", "#9ca3af"]),
            legend=alt.Legend(orient="bottom", direction="horizontal",
                             labelFontSize=12, titleFontSize=12),
        ),
        tooltip=[
            alt.Tooltip("label:N", title="Transaction"),
            alt.Tooltip("date:N", title="Date"),
            alt.Tooltip("description:N", title="Description"),
            alt.Tooltip("amount:Q", title="Amount", format="$,.2f"),
            alt.Tooltip("status:N", title="Status"),
        ],
    )
    .properties(height=440)
)

gap_wf = wf[wf["status"] == "unmatched"].copy()
gap_wf["marker_y"] = gap_wf["end"] + (OPENING * 0.025)
gap_wf["marker_label"] = gap_wf["amount"].map(lambda a: f"${a:,.0f}")

markers = (
    alt.Chart(gap_wf)
    .mark_point(shape="triangle-down", size=200, filled=True)
    .encode(x=alt.X("label:N", sort=alt.SortField("sort")), y="marker_y:Q", color=alt.value("#ef4444"))
)
marker_labels = (
    alt.Chart(gap_wf)
    .mark_text(fontSize=12, fontWeight="bold", dy=-14)
    .encode(x=alt.X("label:N", sort=alt.SortField("sort")), y="marker_y:Q", text="marker_label:N", color=alt.value("#ef4444"))
)

st.altair_chart(bars + markers + marker_labels, width="stretch")

# ── Gap investigation ─────────────────────────────────────────────────────────
st.subheader("Investigate the gaps")

gap_df = bank[bank["transaction_id"].isin(gap_ids)].sort_values("amount", ascending=False)
gl_txns = txns[txns["source_system"] == "General Ledger"]

for _, gap in gap_df.iterrows():
    gap_date = gap["transaction_date"]
    gap_amt = gap["amount"]
    tid = gap["transaction_id"]

    with st.container(border=True):
        st.markdown(f"### {tid} — :red[${gap_amt:,.2f}]")
        st.caption(f"{gap['description']} — {gap_date.strftime('%b %-d, %Y')}")

        # What was the bank looking for?
        st.markdown(f"**The bank paid ${gap_amt:,.2f} on {gap_date.strftime('%b %-d')}. "
                    f"Is there a matching journal entry in the general ledger?**")

        # Find GL entries on the same day or close
        window = gl_txns[
            (gl_txns["transaction_date"] >= gap_date - timedelta(days=3)) &
            (gl_txns["transaction_date"] <= gap_date + timedelta(days=3))
        ].sort_values("transaction_date")

        if window.empty:
            st.error(f"No GL entries within 3 days of {gap_date.strftime('%b %-d')}.")
        else:
            exact = window[window["amount"] == gap_amt]
            if exact.empty:
                st.markdown(f"GL entries within 3 days of {gap_date.strftime('%b %-d')} "
                            f"(none match **${gap_amt:,.2f}**):")
                st.dataframe(
                    window.assign(
                        transaction_date=lambda d: d["transaction_date"].dt.strftime("%b %-d"),
                        amount=lambda d: d["amount"].map("${:,.2f}".format),
                    )[["transaction_id", "transaction_date", "description", "amount", "category"]].rename(columns={
                        "transaction_id": "GL Entry", "transaction_date": "Date",
                        "description": "Description", "amount": "Amount", "category": "Category",
                    }),
                    hide_index=True, width="stretch",
                )
                st.error(f"No GL entry for ${gap_amt:,.2f} — the journal entry was never created.")

        if tid == "BK-3006":
            st.info(
                "**Root cause:** The wire transfer for the Grand Ballroom venue deposit was "
                "authorized and paid on Nov 12, but nobody created the corresponding GL journal "
                "entry. This is the same type of gap the auditors flagged last quarter.",
                icon="\U0001f50d",
            )
        elif tid == "BK-3018":
            st.info(
                "**Root cause:** Monthly bank service fees ($200) are charged automatically "
                "but never get journaled in the GL. It\u2019s a small recurring gap that adds up \u2014 "
                "and the kind of thing that shows up as an audit finding when someone finally "
                "looks.",
                icon="\U0001f50d",
            )

# ── Next steps ────────────────────────────────────────────────────────────────
st.subheader("Next steps to close")
for gap_row in gap_df.itertuples():
    st.checkbox(
        f"Create journal entry for **{gap_row.transaction_id}** "
        f"(${gap_row.amount:,.2f} — {gap_row.description})",
        value=False, disabled=True,
    )
st.caption(
    "Once journal entries are posted for every gap, "
    "reconciliation reaches 100% and the month is ready to close."
)

st.divider()

# ── Full ledger ───────────────────────────────────────────────────────────────
with st.expander("Full ledger (all 46 transactions)", expanded=False):
    f1, f2 = st.columns(2)
    systems = sorted(txns["source_system"].unique())
    sel_sys = f1.selectbox("Source system", ["All systems"] + systems)
    cats = sorted(txns["category"].unique())
    sel_cat = f2.selectbox("Category", ["All categories"] + cats)

    detail = txns.copy()
    if sel_sys != "All systems":
        detail = detail[detail["source_system"] == sel_sys]
    if sel_cat != "All categories":
        detail = detail[detail["category"] == sel_cat]

    st.dataframe(
        detail.assign(
            transaction_date=lambda d: d["transaction_date"].dt.date,
            amount=lambda d: d["amount"].map("${:,.2f}".format),
        )[["transaction_id", "transaction_date", "description", "amount",
           "department", "category", "source_system"]],
        hide_index=True, width="stretch",
    )
