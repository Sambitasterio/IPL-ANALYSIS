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


@st.cache_resource
def get_engine():
    load_dotenv()
    url = os.getenv("SUPABASE_DB_URL")
    if not url:
        st.error("SUPABASE_DB_URL not set — check your .env file.")
        st.stop()
    if url.startswith("postgresql://"):
        url = url.replace("postgresql://", "postgresql+psycopg2://", 1)
    return create_engine(url, pool_pre_ping=True)


@st.cache_data(ttl=600)
def run(sql, params):
    with get_engine().connect() as conn:
        return pd.read_sql(text(sql), conn, params=params)


def hbar(df, x, y, fmt=":.0f"):
    fig = px.bar(df, x=x, y=y, orientation="h", text=x)
    fig.update_traces(texttemplate="%{text" + fmt + "}", textposition="outside")
    fig.update_layout(
        yaxis={"categoryorder": "total ascending", "title": ""},
        xaxis={"title": ""}, height=400, margin=dict(l=0, r=10, t=10, b=0),
    )
    return fig


# ------------------------------------------------------------------- sidebar
st.sidebar.title("🏏 IPL Analytics")
season_df = run(*q.seasons())
season = st.sidebar.selectbox(
    "Season", ["All"] + [str(s) for s in season_df["season"].tolist()]
)
st.sidebar.caption("Data: IPL 2008–2024 ball-by-ball")

# -------------------------------------------------------------- header + KPIs
scope = "All Seasons" if season == "All" else f"Season {season}"
st.title("IPL Analytics Dashboard")
st.caption(f"Showing: **{scope}**")

k = run(*q.kpis(season)).iloc[0]
c1, c2, c3, c4 = st.columns(4)
c1.metric("Matches", f"{int(k['matches']):,}")
c2.metric("Total Runs", f"{int(k['runs']):,}")
c3.metric("Wickets", f"{int(k['wickets']):,}")
c4.metric("Sixes", f"{int(k['sixes']):,}")

st.divider()

# ----------------------------------------------------------------- charts 2x2
left, right = st.columns(2)

with left:
    st.subheader("Top 10 Run Scorers")
    df = run(*q.top_run_scorers(season))
    st.info("No data for this selection.") if df.empty else st.plotly_chart(
        hbar(df, "runs", "player_name"), use_container_width=True
    )

with right:
    st.subheader("Best Bowling Economy")
    df = run(*q.bowling_economy(season))
    if df.empty:
        st.info("Not enough deliveries for this selection.")
    else:
        fig = px.bar(df, x="economy", y="player_name", orientation="h", text="economy")
        fig.update_traces(texttemplate="%{text:.2f}", textposition="outside")
        fig.update_layout(
            yaxis={"categoryorder": "total descending", "title": ""},
            xaxis={"title": "runs/over"}, height=400, margin=dict(l=0, r=10, t=10, b=0),
        )
        st.plotly_chart(fig, use_container_width=True)

left2, right2 = st.columns(2)

with left2:
    st.subheader("Team Win %")
    df = run(*q.team_win_pct(season))
    if df.empty:
        st.info("No data for this selection.")
    else:
        fig = px.bar(df, x="team_name", y="win_pct", text="win_pct")
        fig.update_traces(texttemplate="%{text:.1f}%", textposition="outside")
        fig.update_layout(
            xaxis={"title": "", "categoryorder": "total descending"},
            yaxis={"title": "Win %"}, height=430, margin=dict(l=0, r=0, t=10, b=120),
        )
        fig.update_xaxes(tickangle=-45)
        st.plotly_chart(fig, use_container_width=True)

with right2:
    st.subheader("Highest Scoring Venues")
    df = run(*q.venue_scoring(season))
    st.info("No data for this selection.") if df.empty else st.plotly_chart(
        hbar(df, "avg_runs", "venue_name"), use_container_width=True
    )

st.caption(
    "Economy ≈ total runs conceded ÷ overs bowled (includes byes/legbyes). "
    "Win % over matches played; teams with renamed franchises are merged."
)
