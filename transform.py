"""Step 3 — Extract & clean: build the IPL star schema from the raw CSVs.

Reads  data/raw/matches.csv  and  data/raw/deliveries.csv
Writes 5 tables to  data/transformed/  (4 dimensions + 1 fact).

Surrogate keys (team_id, player_id, venue_id) are assigned here in Python from
sorted distinct values, so they are deterministic across re-runs and the load
step (Step 5) stays idempotent.

Column names are specific to the IPL 2008-2024 dataset:
  matches    -> id, season, city, date, team1, team2, toss_winner, winner,
                result, result_margin, venue
  deliveries -> match_id, inning, over, ball, batter, bowler, batting_team,
                bowling_team, batsman_runs, extra_runs, total_runs, is_wicket,
                dismissal_kind
"""
from pathlib import Path

import pandas as pd

RAW = Path("data/raw")
OUT = Path("data/transformed")

# Franchises that were renamed across seasons -> collapse to a single identity
# so a team's full history aggregates as one team.
TEAM_NAME_MAP = {
    "Delhi Daredevils": "Delhi Capitals",
    "Kings XI Punjab": "Punjab Kings",
    "Rising Pune Supergiants": "Rising Pune Supergiant",
    "Royal Challengers Bangalore": "Royal Challengers Bengaluru",
}


def build_lookup(values) -> dict:
    """Return {name: 1-based id} over sorted distinct, non-empty values."""
    names = sorted({str(v).strip() for v in values if pd.notna(v) and str(v).strip()})
    return {name: i + 1 for i, name in enumerate(names)}


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    matches = pd.read_csv(RAW / "matches.csv")
    deliveries = pd.read_csv(RAW / "deliveries.csv")

    # ---------------------------------------------------------------- clean
    matches = matches.drop_duplicates("id")
    deliveries = deliveries.dropna(subset=["match_id", "batter", "bowler"]).drop_duplicates()

    for col in ["team1", "team2", "toss_winner", "winner"]:
        matches[col] = matches[col].replace(TEAM_NAME_MAP)
    for col in ["batting_team", "bowling_team"]:
        deliveries[col] = deliveries[col].replace(TEAM_NAME_MAP)

    # --------------------------------------------------------- dimension keys
    team_lk = build_lookup(
        pd.concat([matches["team1"], matches["team2"],
                   deliveries["batting_team"], deliveries["bowling_team"]])
    )
    player_lk = build_lookup(pd.concat([deliveries["batter"], deliveries["bowler"]]))

    venues = (
        matches[["venue", "city"]]
        .dropna(subset=["venue"])
        .drop_duplicates("venue")
        .sort_values("venue")
        .reset_index(drop=True)
    )
    venue_lk = {v: i + 1 for i, v in enumerate(venues["venue"])}

    # ------------------------------------------------------------ dim tables
    dim_team = pd.DataFrame(
        {"team_id": list(team_lk.values()), "team_name": list(team_lk.keys())}
    )
    dim_player = pd.DataFrame(
        {"player_id": list(player_lk.values()), "player_name": list(player_lk.keys())}
    )
    dim_venue = pd.DataFrame(
        {
            "venue_id": [venue_lk[v] for v in venues["venue"]],
            "venue_name": venues["venue"],
            "city": venues["city"],
        }
    )

    # -------------------------------------------------------------- dim_match
    margin = pd.to_numeric(matches["result_margin"], errors="coerce")
    res = matches["result"].astype("string").str.lower()
    # Season = the calendar year the matches were played. Every IPL edition
    # falls within a single year, so date.year is the unambiguous edition year
    # (the raw 'season' labels like '2020/21' vs '2021' are inconsistent).
    match_dates = pd.to_datetime(matches["date"], errors="coerce")
    dim_match = pd.DataFrame(
        {
            "match_id": matches["id"],
            "season": match_dates.dt.year.astype("Int64"),
            "date": match_dates.dt.date,
            "city": matches["city"],
            "team1_id": matches["team1"].map(team_lk),
            "team2_id": matches["team2"].map(team_lk),
            "toss_winner_id": matches["toss_winner"].map(team_lk),
            "winner_id": matches["winner"].map(team_lk).astype("Int64"),
            "venue_id": matches["venue"].map(venue_lk).astype("Int64"),
            "result": matches["result"],
            "win_by_runs": margin.where(res.eq("runs")).astype("Int64"),
            "win_by_wickets": margin.where(res.eq("wickets")).astype("Int64"),
        }
    )

    # -------------------------------------------------------- fact_deliveries
    fact = pd.DataFrame(
        {
            "match_id": deliveries["match_id"],
            "inning": deliveries["inning"],
            "over": deliveries["over"],
            "ball": deliveries["ball"],
            "batsman_id": deliveries["batter"].map(player_lk),
            "bowler_id": deliveries["bowler"].map(player_lk),
            "batting_team_id": deliveries["batting_team"].map(team_lk),
            "bowling_team_id": deliveries["bowling_team"].map(team_lk),
            "runs_scored": deliveries["batsman_runs"],
            "extra_runs": deliveries["extra_runs"],
            "total_runs": deliveries["total_runs"],
            "is_wicket": deliveries["is_wicket"].astype(bool),
            "wicket_type": deliveries["dismissal_kind"],
        }
    )
    # Keep only deliveries whose match exists in dim_match (FK integrity).
    fact = fact[fact["match_id"].isin(set(dim_match["match_id"]))]

    # ----------------------------------------------------------------- export
    tables = {
        "dim_team": dim_team,
        "dim_venue": dim_venue,
        "dim_player": dim_player,
        "dim_match": dim_match,
        "fact_deliveries": fact,
    }
    for name, df in tables.items():
        df.to_csv(OUT / f"{name}.csv", index=False)
        print(f"{name:16s} {len(df):>7,} rows")


if __name__ == "__main__":
    main()
