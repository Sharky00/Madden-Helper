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


# ==============================
# Main execution
# ==============================
def run():
    # Load raw files
    teams = load_json(RAW_DIR / "teamsPS5.json")
    schedules = load_json(RAW_DIR / "schedulesPS5.json")

    # Transform
    teams_named, id_to_name = transform_teams(teams)
    schedules_named = transform_schedule(schedules, id_to_name)

    # Save processed files
    with open(PROC_DIR / "teamsPS5_named_keys.json", "w", encoding="utf-8") as f:
        json.dump(teams_named, f, ensure_ascii=False, indent=2)

    with open(PROC_DIR / "schedulesPS5_named.json", "w", encoding="utf-8") as f:
        json.dump(schedules_named, f, ensure_ascii=False, indent=2)

    print("Processed files saved in:", PROC_DIR)
