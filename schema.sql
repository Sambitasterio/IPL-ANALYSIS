-- IPL Analytics Pipeline — star schema (run in Supabase SQL Editor).
--
-- Surrogate keys (team_id, player_id, venue_id) are assigned in transform.py,
-- so dimension PKs are plain INTEGER, NOT SERIAL. Using SERIAL here would
-- desync the auto-increment sequence against the Python-assigned IDs and cause
-- duplicate-key errors on load.
--
-- Safe to re-run: the DROPs rebuild the schema from scratch.

DROP TABLE IF EXISTS fact_deliveries CASCADE;
DROP TABLE IF EXISTS dim_match CASCADE;
DROP TABLE IF EXISTS dim_player CASCADE;
DROP TABLE IF EXISTS dim_venue CASCADE;
DROP TABLE IF EXISTS dim_team CASCADE;

CREATE TABLE dim_team (
    team_id   INTEGER PRIMARY KEY,
    team_name TEXT NOT NULL
);

CREATE TABLE dim_venue (
    venue_id   INTEGER PRIMARY KEY,
    venue_name TEXT NOT NULL,
    city       TEXT
);

CREATE TABLE dim_player (
    player_id   INTEGER PRIMARY KEY,
    player_name TEXT NOT NULL
);

CREATE TABLE dim_match (
    match_id       INTEGER PRIMARY KEY,
    season         INT,
    date           DATE,
    city           TEXT,
    team1_id       INT REFERENCES dim_team(team_id),
    team2_id       INT REFERENCES dim_team(team_id),
    toss_winner_id INT REFERENCES dim_team(team_id),
    winner_id      INT REFERENCES dim_team(team_id),
    venue_id       INT REFERENCES dim_venue(venue_id),
    result         TEXT,
    win_by_runs    INT,
    win_by_wickets INT
);

CREATE TABLE fact_deliveries (
    id              BIGSERIAL PRIMARY KEY,   -- DB-generated row id (not in the CSV)
    match_id        INT REFERENCES dim_match(match_id),
    inning          INT,
    over            INT,
    ball            INT,
    batsman_id      INT REFERENCES dim_player(player_id),
    bowler_id       INT REFERENCES dim_player(player_id),
    batting_team_id INT REFERENCES dim_team(team_id),
    bowling_team_id INT REFERENCES dim_team(team_id),
    runs_scored     INT,
    extra_runs      INT,
    total_runs      INT,
    is_wicket       BOOLEAN,
    wicket_type     TEXT
);

-- Speed up the dashboard's GROUP BY aggregations over 260k rows.
CREATE INDEX idx_fact_batsman ON fact_deliveries(batsman_id);
CREATE INDEX idx_fact_bowler  ON fact_deliveries(bowler_id);
CREATE INDEX idx_fact_match   ON fact_deliveries(match_id);
