import json, os
from pathlib import Path

# ==============================
# Setup paths
# ==============================
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
DATA_DIR = PROJECT_ROOT / "data"
RAW_DIR = DATA_DIR / "raw"
PROC_DIR = DATA_DIR / "processed"

# Make sure folders exist
RAW_DIR.mkdir(parents=True, exist_ok=True)
PROC_DIR.mkdir(parents=True, exist_ok=True)


# ==============================
# Helper functions
# ==============================
def load_json(path):
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)

def make_team_name(team_obj, style="city_display"):
    city = team_obj.get("cityName") or ""
    display = team_obj.get("displayName") or ""
    abbr = team_obj.get("abbrName") or ""
    if style == "abbr":
        return abbr or display or city
    if style == "display":
        return display or abbr or city
    # default: "City Display"
    if city and display:
        return f"{city} {display}"
    return display or city or abbr

def make_player_key(player_obj, used=None):
    first = (player_obj.get("firstName") or "").strip()
    last = (player_obj.get("lastName") or "").strip()
    jersey = player_obj.get("jerseyNum")
    roster_id = player_obj.get("rosterId")

    base = f"{first} {last}".strip() or str(roster_id)

    # Ensure uniqueness
    if used is not None:
        if base not in used:
            used.add(base)
            return base
        # Try jersey number
        if jersey is not None:
            key2 = f"{base} (#{jersey})"
            if key2 not in used:
                used.add(key2)
                return key2
        # Fallback to rosterId
        key3 = f"{base} ({roster_id})"
        used.add(key3)
        return key3

    return base


# ==============================
# Transformation functions
# ==============================
def transform_teams(teams_data, team_name_style="city_display"):
    transformed = {}
    team_id_to_name = {}

    for team_id, team_obj in teams_data.items():
        name = make_team_name(team_obj, style=team_name_style)

        # Ensure unique team keys
        final_name = name
        suffix = 2
        while final_name in transformed:
            final_name = f"{name} [{suffix}]"
            suffix += 1

        # Map teamId -> name
        try:
            team_id_to_name[int(team_id)] = final_name
        except:
            team_id_to_name[team_id] = final_name

        # Transform roster
        roster = team_obj.get("roster") or {}
        used_names = set()
        new_roster = {}
        for pid, player in roster.items():
            pkey = make_player_key(player, used=used_names)
            new_roster[pkey] = player

        new_team_obj = dict(team_obj)
        new_team_obj["roster"] = new_roster
        transformed[final_name] = new_team_obj

    return transformed, team_id_to_name


def transform_schedule(schedule_data, id_to_name):
    def id_to_n(x):
        try:
            return id_to_name.get(int(x), x)
        except Exception:
            return id_to_name.get(x, x)

    out = {}
    for phase, weeks in schedule_data.items():
        if weeks is None:
            out[phase] = weeks
            continue

        new_weeks = []
        for wk in weeks:
            if wk is None:
                new_weeks.append(wk)
                continue

            if isinstance(wk, list):
                new_games = []
                for g in wk:
                    if not isinstance(g, dict):
                        new_games.append(g)
                        continue
                    g2 = dict(g)
                    away_id = g.get("awayTeamId")
                    home_id = g.get("homeTeamId")
                    if away_id is not None:
                        g2["awayTeamName"] = id_to_n(away_id)
                    if home_id is not None:
                        g2["homeTeamName"] = id_to_n(home_id)
                    new_games.append(g2)
                new_weeks.append(new_games)
            else:
                new_weeks.append(wk)

        out[phase] = new_weeks
    return out

# --- NEW: Weekly grouping helpers ---

def _matchup_key(game: dict) -> str:
    """Return 'Home Team vs Away Team' using the provided names."""
    home = game.get("homeTeamName") or "Home"
    away = game.get("awayTeamName") or "Away"
    return f"{home} vs {away}"

def _week_key(week_index: int) -> str:
    """Return 'Week #' string using the weekIndex as-is (0-based per your data)."""
    return f"Week {week_index}"

def group_phase_by_weeks(phase_weeks) -> dict:
    """
    Given the raw structure for one phase (e.g., schedules['pre'] or schedules['reg']),
    return a dict like:
      {
        "Week 0": {
          "New England Patriots vs New York Giants": { ...full game dict... },
          "Baltimore Ravens vs Tennessee Titans": { ... },
          ...
        },
        "Week 1": { ... },
        ...
      }
    The input phase_weeks is typically a list where each element is a list of game dicts.
    """
    out = {}
    if not phase_weeks:
        return out

    for maybe_games in phase_weeks:
        if not maybe_games or not isinstance(maybe_games, list):
            # could be None or something unexpected; skip gracefully
            continue

        for game in maybe_games:
            if not isinstance(game, dict):
                continue

            # Use the weekIndex straight from the game (you asked to use the index in the key)
            widx = game.get("weekIndex")
            if widx is None:
                # If missing, skip or place into a special bucket; here we skip
                continue

            wk_key = _week_key(widx)
            m_key = _matchup_key(game)

            if wk_key not in out:
                out[wk_key] = {}
            out[wk_key][m_key] = game
    return out

def group_schedule_by_weeks(schedules_named: dict) -> dict:
    """
    Transform the full schedules dict (which includes 'pre', 'reg', maybe 'post')
    into:
      {
        "pre": { "Week 0": { "Home vs Away": game, ... }, "Week 1": { ... }, ... },
        "reg": { "Week 0": { ... }, "Week 1": { ... }, ... }
      }
    Only 'pre' and 'reg' are re-keyed per your request; other phases are passed through untouched.
    """
    out = {}

    # Re-key the 'pre' and 'reg' phases
    for phase in ("pre", "reg"):
        phase_weeks = schedules_named.get(phase)
        out[phase] = group_phase_by_weeks(phase_weeks)

    # Preserve anything else (e.g., 'post') as-is if present
    for k, v in schedules_named.items():
        if k not in out:
            out[k] = v
    return out

def rename_score_keys_in_game(
    game: dict,
    *,
    keep_original: bool = False
) -> dict:
    """
    Rename 'homeScore' and 'awayScore' to '<Home Team Name> Score' and
    '<Away Team Name> Score', using existing homeTeamName/awayTeamName.
    If keep_original=False, the original 'homeScore'/'awayScore' keys are removed.
    """
    if not isinstance(game, dict):
        return game

    g = dict(game)  # work on a copy

    home_name = g.get("homeTeamName") or "Home"
    away_name = g.get("awayTeamName") or "Away"

    # Build new key names
    home_key = f"{home_name} Score"
    away_key = f"{away_name} Score"

    # Copy scores under new keys (if present)
    if "homeScore" in g:
        g[home_key] = g["homeScore"]
        if not keep_original:
            del g["homeScore"]

    if "awayScore" in g:
        g[away_key] = g["awayScore"]
        if not keep_original:
            del g["awayScore"]

    return g


def rename_score_keys_in_phase_lists(phase_weeks, **opts):
    """
    Apply rename_score_keys_in_game across a raw phase structure:
      [ [game, game, ...], [game, ...], ... ]
    Returns a new structure with renamed score keys.
    """
    if not phase_weeks:
        return phase_weeks
    out = []
    for week in phase_weeks:
        if not isinstance(week, list):
            out.append(week)
            continue
        games_out = []
        for game in week:
            games_out.append(rename_score_keys_in_game(game, **opts) if isinstance(game, dict) else game)
        out.append(games_out)
    return out


def rename_score_keys_in_grouped(grouped: dict, **opts) -> dict:
    """
    Apply rename_score_keys_in_game across your grouped-by-week schedule:
      { "pre": { "Week #": { "Home vs Away": game, ... }, ... }, "reg": {...}, ... }
    """
    out = {}
    for phase, weeks in grouped.items():
        if not isinstance(weeks, dict):
            out[phase] = weeks
            continue
        phase_out = {}
        for wk_key, matchups in weeks.items():
            if not isinstance(matchups, dict):
                phase_out[wk_key] = matchups
                continue
            matchups_out = {}
            for matchup_key, game in matchups.items():
                matchups_out[matchup_key] = (
                    rename_score_keys_in_game(game, **opts) if isinstance(game, dict) else game
                )
            phase_out[wk_key] = matchups_out
        out[phase] = phase_out
    return out

# ==============================
# Main execution
# ==============================

def run():
    # 1) Load raw inputs
    with open(RAW_DIR / "teamsPS5.json", "r", encoding="utf-8") as f:
        teams = json.load(f)
    with open(RAW_DIR / "schedulesPS5.json", "r", encoding="utf-8") as f:
        schedules = json.load(f)

    # 2) Build named structures
    teams_named, id_to_name = transform_teams(teams)
    schedules_named = transform_schedule(schedules, id_to_name)

    # 3) Group schedule by week and matchup ("Home vs Away")
    schedules_grouped = group_schedule_by_weeks(schedules_named)

    # 4) Rename score keys to "<Team Name> Score"
    final_struct = rename_score_keys_in_grouped(schedules_grouped, keep_original=False)

    # 5) Save ONLY the final output
    out_path = PROC_DIR / "schedulesPS5_final.json"
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(final_struct, f, ensure_ascii=False, indent=2)

    print(f"Saved final schedule to: {out_path}")

