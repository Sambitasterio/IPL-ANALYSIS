"""Step 8 — IPL Analytics Dashboard (Streamlit).

Run with:  streamlit run app.py
Reads the star schema from Supabase (connection from .env) and renders KPIs +
four charts, all filterable by season.
"""
import os

import pandas as pd
import plotly.express as px
import streamlit as st
from dotenv import load_dotenv
from sqlalchemy import create_engine, text

import queries as q

st.set_page_config(page_title="IPL Analytics", page_icon="🏏", layout="wide")

# Shared chart styling so every figure feels like one dashboard.
SCALE = "Tealgrn"          # more = better (runs, win %, venue scoring)
SCALE_R = "Tealgrn_r"      # less = better (economy)
PLOTLY_CONFIG = {"displayModeBar": False}


@st.cache_resource
def get_engine():
    # Local dev reads .env; Streamlit Community Cloud reads st.secrets.
    load_dotenv()
    url = os.getenv("SUPABASE_DB_URL")
    if not url:
        try:
            url = st.secrets["SUPABASE_DB_URL"]
        except Exception:
            url = None
    if not url:
        st.error(
            "SUPABASE_DB_URL not set. Locally: add it to .env. "
            "On Streamlit Cloud: add it under Manage app → Settings → Secrets."
        )
        st.stop()
    if url.startswith("postgresql://"):
        url = url.replace("postgresql://", "postgresql+psycopg2://", 1)
    return create_engine(url, pool_pre_ping=True)


@st.cache_data(ttl=600)
def run(sql, params):
    with get_engine().connect() as conn:
        return pd.read_sql(text(sql), conn, params=params)


def _style(fig, height=400, bottom=0):
    fig.update_layout(
        template="plotly_dark",
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        coloraxis_showscale=False,
        height=height,
        margin=dict(l=0, r=30, t=10, b=bottom),
        font=dict(size=13),
    )
    fig.update_xaxes(showgrid=False)
    fig.update_yaxes(showgrid=False)
    return fig


def hbar(df, x, y, fmt="%{text:.0f}", scale=SCALE, order="total ascending"):
    fig = px.bar(df, x=x, y=y, orientation="h", text=x,
                 color=x, color_continuous_scale=scale)
    fig.update_traces(texttemplate=fmt, textposition="outside", cliponaxis=False)
    fig.update_layout(yaxis={"categoryorder": order, "title": ""}, xaxis={"title": ""})
    return _style(fig)


# ------------------------------------------------------------------- sidebar
st.sidebar.title("🏏 IPL Analytics")
season_df = run(*q.seasons())
season = st.sidebar.selectbox(
    "Season", ["All"] + [str(s) for s in season_df["season"].tolist()]
)
st.sidebar.caption("Data: IPL 2008–2024 ball-by-ball")
st.sidebar.caption("Source: Kaggle · Warehouse: Supabase (PostgreSQL)")

# -------------------------------------------------------------- header + KPIs
scope = "All Seasons (2008–2024)" if season == "All" else f"Season {season}"
st.title("🏏 IPL Analytics Dashboard")
st.markdown(f"##### {scope}")
st.write("")

k = run(*q.kpis(season)).iloc[0]
cards = [
    ("🏟️ Matches", int(k["matches"])),
    ("🏏 Total Runs", int(k["runs"])),
    ("🎯 Wickets", int(k["wickets"])),
    ("💥 Sixes", int(k["sixes"])),
]
for col, (label, value) in zip(st.columns(4), cards):
    with col.container(border=True):
        st.metric(label, f"{value:,}")

st.write("")

# ----------------------------------------------------------------- charts 2x2
left, right = st.columns(2)

with left:
    with st.container(border=True):
        st.subheader("Top 10 Run Scorers")
        df = run(*q.top_run_scorers(season))
        if df.empty:
            st.info("No data for this selection.")
        else:
            st.plotly_chart(hbar(df, "runs", "player_name"),
                            use_container_width=True, config=PLOTLY_CONFIG)

with right:
    with st.container(border=True):
        st.subheader("Best Bowling Economy")
        df = run(*q.bowling_economy(season))
        if df.empty:
            st.info("Not enough deliveries for this selection.")
        else:
            fig = hbar(df, "economy", "player_name", fmt="%{text:.2f}",
                       scale=SCALE_R, order="total descending")
            fig.update_xaxes(title="runs / over")
            st.plotly_chart(fig, use_container_width=True, config=PLOTLY_CONFIG)

left2, right2 = st.columns(2)

with left2:
    with st.container(border=True):
        st.subheader("Team Win %")
        df = run(*q.team_win_pct(season))
        if df.empty:
            st.info("No data for this selection.")
        else:
            fig = px.bar(df, x="team_name", y="win_pct", text="win_pct",
                         color="win_pct", color_continuous_scale=SCALE)
            fig.update_traces(texttemplate="%{text:.1f}%", textposition="outside",
                              cliponaxis=False)
            fig.update_layout(
                xaxis={"title": "", "categoryorder": "total descending"},
                yaxis={"title": "Win %"},
            )
            fig.update_xaxes(tickangle=-45)
            st.plotly_chart(_style(fig, height=430, bottom=120),
                            use_container_width=True, config=PLOTLY_CONFIG)

with right2:
    with st.container(border=True):
        st.subheader("Highest Scoring Venues")
        df = run(*q.venue_scoring(season))
        if df.empty:
            st.info("No data for this selection.")
        else:
            fig = hbar(df, "avg_runs", "venue_name")
            fig.update_xaxes(title="avg runs / match")
            st.plotly_chart(fig, use_container_width=True, config=PLOTLY_CONFIG)

st.caption(
    "Economy ≈ total runs conceded ÷ overs bowled (includes byes/legbyes). "
    "Win % over matches played; renamed franchises are merged into one team."
)
