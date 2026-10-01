"""
Layer 1: Ingestion
-------------------
This file's ONLY job is talking to the NBA stats API and returning clean
pandas DataFrames. It does not touch a database and does not compute any
features - that happens in later layers. Keeping this file "dumb" (just
fetch + return) is what makes it easy to test and reuse.
"""

import time
import pandas as pd
from nba_api.stats.endpoints import playergamelog
from nba_api.stats.static import players


def get_player_id(full_name: str) -> int:
    """
    Look up a player's numeric NBA ID from their name.
    This uses a small local dataset bundled with nba_api - no network call.
    """
    matches = players.find_players_by_full_name(full_name)
    if not matches:
        raise ValueError(f"No player found matching '{full_name}'")
    if len(matches) > 1:
        # e.g. multiple historical players with similar names
        print(f"Warning: multiple matches for '{full_name}', using the first: {matches[0]}")
    return matches[0]["id"]


def fetch_player_gamelog(player_id: int, season: str) -> pd.DataFrame:
    """
    Fetch one player's full game log for one season.

    season format: '2024-25' (this is how the NBA API expects it -
    not '2024' or '2024-2025')

    Returns a DataFrame with one row per game the player played that season.
    """
    log = playergamelog.PlayerGameLog(player_id=player_id, season=season)
    df = log.get_data_frames()[0]
    return df


def fetch_multiple_players(player_names: list[str], season: str) -> pd.DataFrame:
    """
    Loop over several players, fetching each one's game log, with:
      - a small delay between calls (rate limiting - don't hammer the API)
      - error handling (one failed player shouldn't kill the whole run)

    Returns one combined DataFrame with all players' games stacked together.
    """
    all_logs = []

    for name in player_names:
        try:
            player_id = get_player_id(name)
            print(f"Fetching {name} (id={player_id})...")
            df = fetch_player_gamelog(player_id, season)
            df["PLAYER_NAME"] = name  # tag rows with the player's name
            all_logs.append(df)
        except Exception as e:
            # Real ingestion code must not crash on one bad player.
            # Log it and move on - you can investigate failures later.
            print(f"  FAILED for {name}: {type(e).__name__}: {e}")

        time.sleep(0.6)  # be polite to the API - avoid rate limiting

    if not all_logs:
        raise RuntimeError("No player data was successfully fetched.")

    return pd.concat(all_logs, ignore_index=True)


if __name__ == "__main__":
    # Quick manual test when running this file directly.
    # Run this on YOUR machine (not this sandbox) since it needs live
    # internet access to stats.nba.com.
    test_players = ["LeBron James", "Stephen Curry", "Nikola Jokic"]
    result = fetch_multiple_players(test_players, season="2025-26")
    print("\nFinal combined shape:", result.shape)
    print(result[["PLAYER_NAME", "GAME_DATE", "PTS", "REB", "AST"]].head(10))
    print(result['PLAYER_NAME'].value_counts())