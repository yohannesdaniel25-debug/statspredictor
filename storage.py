"""
Layer 2: Storage
-----------------
This file's job is: take DataFrames (from ingest.py) and persist them in a
DuckDB database file on disk. Nothing in here calls the NBA API - it only
knows about pandas DataFrames going in, and a .duckdb file on disk.

Why DuckDB: it's just a single file (no server to run), and it speaks SQL,
so we can ask real questions of the data later (e.g. "average points over
a player's last 10 games") instead of writing manual pandas loops every time.
"""

import duckdb
import pandas as pd

DB_PATH = "nba_stats.duckdb"


def get_connection(db_path: str = DB_PATH) -> duckdb.DuckDBPyConnection:
    """
    Open (or create, if it doesn't exist yet) the DuckDB database file.
    """
    return duckdb.connect(db_path)


def create_tables(con: duckdb.DuckDBPyConnection) -> None:
    """
    Create the player_game_stats table if it doesn't already exist.

    One row = one player's stats in one game.
    PRIMARY KEY (player_id, game_id) means: we will never allow two rows
    with the same player+game combo - this is what makes it safe to re-run
    ingestion without creating duplicate rows.
    """
    con.execute("""
        CREATE TABLE IF NOT EXISTS player_game_stats (
            player_id      BIGINT,
            player_name    VARCHAR,
            game_id        VARCHAR,
            game_date      DATE,
            matchup        VARCHAR,
            win_loss       VARCHAR,
            minutes        INTEGER,
            points         INTEGER,
            rebounds       INTEGER,
            assists        INTEGER,
            steals         INTEGER,
            blocks         INTEGER,
            turnovers      INTEGER,
            fg_pct         DOUBLE,
            fg3_pct        DOUBLE,
            ft_pct         DOUBLE,
            PRIMARY KEY (player_id, game_id)
        )
    """)


def _prepare_dataframe(raw_df: pd.DataFrame, player_id_lookup: dict) -> pd.DataFrame:
    """
    Take the raw DataFrame straight from nba_api (messy column names like
    'PTS', 'REB', 'Player_ID') and reshape it to match our table's schema
    (clean lowercase names matching create_tables above).

    player_id_lookup: dict mapping player_name -> player_id, since the raw
    data already has Player_ID from nba_api, but we're being explicit here
    for clarity.
    """
    df = raw_df.copy()

    # Explicit format = faster and safer than letting pandas guess. The NBA
    # API always returns dates like "APR 12, 2026", so we pin that exact
    # format rather than relying on pandas to infer it correctly every time.
    df["game_date"] = pd.to_datetime(df["GAME_DATE"], format="%b %d, %Y").dt.date

    clean = pd.DataFrame({
        "player_id": df["Player_ID"],
        "player_name": df["PLAYER_NAME"],
        "game_id": df["Game_ID"],
        "game_date": df["game_date"],
        "matchup": df["MATCHUP"],
        "win_loss": df["WL"],
        "minutes": df["MIN"],
        "points": df["PTS"],
        "rebounds": df["REB"],
        "assists": df["AST"],
        "steals": df["STL"],
        "blocks": df["BLK"],
        "turnovers": df["TOV"],
        "fg_pct": df["FG_PCT"],
        "fg3_pct": df["FG3_PCT"],
        "ft_pct": df["FT_PCT"],
    })
    return clean


def save_gamelogs(con: duckdb.DuckDBPyConnection, raw_df: pd.DataFrame) -> int:
    """
    Clean a raw ingested DataFrame and insert it into player_game_stats.
    Rows that already exist (same player_id + game_id) are skipped, not
    duplicated - this is what makes it safe to re-run this daily.

    Returns the number of NEW rows actually inserted.
    """
    clean_df = _prepare_dataframe(raw_df, player_id_lookup={})

    before = con.execute("SELECT COUNT(*) FROM player_game_stats").fetchone()[0]

    # INSERT ... ON CONFLICT DO NOTHING = "insert this row, unless a row
    # with the same primary key already exists, in which case skip it"
    con.execute("""
        INSERT INTO player_game_stats
        SELECT * FROM clean_df
        ON CONFLICT (player_id, game_id) DO NOTHING
    """)

    after = con.execute("SELECT COUNT(*) FROM player_game_stats").fetchone()[0]
    return after - before


def query_player_recent_games(con: duckdb.DuckDBPyConnection, player_name: str, n: int = 10) -> pd.DataFrame:
    """
    Example query: a player's N most recent games, newest first.
    This is the kind of thing that would take a manual pandas filter+sort
    before - now it's one readable SQL statement.
    """
    return con.execute("""
        SELECT game_date, matchup, points, rebounds, assists
        FROM player_game_stats
        WHERE player_name = ?
        ORDER BY game_date DESC
        LIMIT ?
    """, [player_name, n]).df()


if __name__ == "__main__":
    # Manual test: build the DB, insert some data, query it back.
    # Uses ingest.py, so this needs live internet access - run on your
    # own machine, not the sandbox.
    from ingest import fetch_multiple_players

    con = get_connection()
    create_tables(con)

    raw = fetch_multiple_players(["LeBron James", "Stephen Curry"], season="2024-25")
    inserted = save_gamelogs(con, raw)
    print(f"Inserted {inserted} new rows.")

    print("\nLeBron's 5 most recent games:")
    print(query_player_recent_games(con, "LeBron James", n=5))

    # Run it again immediately - should insert 0 new rows, proving
    # the duplicate-prevention logic works.
    inserted_again = save_gamelogs(con, raw)
    print(f"\nRunning again: inserted {inserted_again} new rows (should be 0).")

    con.close()
