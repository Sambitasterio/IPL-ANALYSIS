"""SQL for the IPL dashboard.

Kept separate from app.py so the queries can be tested headlessly (no Streamlit
runtime needed). Each function returns (sql, params); params feed SQLAlchemy's
bound-parameter binding so the season filter is never string-interpolated.
"""


def _season(alias: str, season) -> str:
    """SQL fragment that filters on a season, or '' for All."""
    return "" if season == "All" else f"AND {alias}.season = :season"


def _params(season) -> dict:
    return {} if season == "All" else {"season": int(season)}


def seasons():
    return (
        "SELECT DISTINCT season FROM dim_match "
        "WHERE season IS NOT NULL ORDER BY season",
        {},
    )


def kpis(season):
    sql = f"""
        SELECT
          (SELECT COUNT(*) FROM dim_match m WHERE 1=1 {_season('m', season)}) AS matches,
          COALESCE(SUM(f.total_runs), 0) AS runs,
          COALESCE(SUM(CASE WHEN f.is_wicket THEN 1 ELSE 0 END), 0) AS wickets,
          COALESCE(SUM(CASE WHEN f.runs_scored = 6 THEN 1 ELSE 0 END), 0) AS sixes
        FROM fact_deliveries f
        JOIN dim_match m ON f.match_id = m.match_id
        WHERE 1=1 {_season('m', season)}
    """
    return sql, _params(season)


def top_run_scorers(season):
    sql = f"""
        SELECT p.player_name, SUM(f.runs_scored) AS runs
        FROM fact_deliveries f
        JOIN dim_player p ON f.batsman_id = p.player_id
        JOIN dim_match m ON f.match_id = m.match_id
        WHERE 1=1 {_season('m', season)}
        GROUP BY p.player_name
        ORDER BY runs DESC
        LIMIT 10
    """
    return sql, _params(season)


def bowling_economy(season):
    # Require a sensible sample of deliveries; lower the bar for a single season.
    min_balls = 500 if season == "All" else 120
    sql = f"""
        SELECT p.player_name,
               ROUND(SUM(f.total_runs)::numeric / (COUNT(*) / 6.0), 2) AS economy,
               COUNT(*) AS balls
        FROM fact_deliveries f
        JOIN dim_player p ON f.bowler_id = p.player_id
        JOIN dim_match m ON f.match_id = m.match_id
        WHERE 1=1 {_season('m', season)}
        GROUP BY p.player_name
        HAVING COUNT(*) >= {min_balls}
        ORDER BY economy ASC
        LIMIT 10
    """
    return sql, _params(season)


def team_win_pct(season):
    sql = f"""
        WITH played AS (
            SELECT team_id, COUNT(*) AS games FROM (
                SELECT team1_id AS team_id, season FROM dim_match
                UNION ALL
                SELECT team2_id AS team_id, season FROM dim_match
            ) sub
            WHERE 1=1 {_season('sub', season)}
            GROUP BY team_id
        ),
        won AS (
            SELECT winner_id AS team_id, COUNT(*) AS wins
            FROM dim_match m
            WHERE winner_id IS NOT NULL {_season('m', season)}
            GROUP BY winner_id
        )
        SELECT t.team_name,
               ROUND(100.0 * COALESCE(w.wins, 0) / NULLIF(p.games, 0), 1) AS win_pct,
               p.games
        FROM played p
        JOIN dim_team t ON p.team_id = t.team_id
        LEFT JOIN won w ON w.team_id = p.team_id
        WHERE p.games >= 5
        ORDER BY win_pct DESC
    """
    return sql, _params(season)


def venue_scoring(season):
    sql = f"""
        SELECT v.venue_name, ROUND(AVG(mr.total), 0) AS avg_runs
        FROM (
            SELECT f.match_id, SUM(f.total_runs) AS total
            FROM fact_deliveries f
            JOIN dim_match m ON f.match_id = m.match_id
            WHERE 1=1 {_season('m', season)}
            GROUP BY f.match_id
        ) mr
        JOIN dim_match m ON mr.match_id = m.match_id
        JOIN dim_venue v ON m.venue_id = v.venue_id
        GROUP BY v.venue_name
        HAVING COUNT(*) >= 5
        ORDER BY avg_runs DESC
        LIMIT 12
    """
    return sql, _params(season)
