# process/modules/story_gpt.py
import os, json
from pathlib import Path
from openai import OpenAI
from paths import REFERENCE_DIR
try:
    from dotenv import load_dotenv
    load_dotenv()
except Exception:
    pass

client = OpenAI()  # uses OPENAI_API_KEY

# (reuse your existing extract_team_lines with the REG-only + final-status filter)


def load_references(names: list[str], max_chars: int = 4000) -> str:
    """Concatenate markdown refs from /reference in the given order."""
    parts = []
    for name in names:
        fname = name if name.endswith(".md") else f"{name}.md"
        p = REFERENCE_DIR / fname
        parts.append(p.read_text(encoding="utf-8") if p.exists() else f"[Missing reference: {fname}]")
    blob = "\n\n".join(parts)
    return blob[:max_chars]

def _score_for(game: dict, team: str):
    for k, v in game.items():
        if isinstance(k, str) and k.endswith(" Score") and k.startswith(team):
            return v

def _score_against(game: dict, team: str):
    for k, v in game.items():
        if isinstance(k, str) and k.endswith(" Score") and not k.startswith(team):
            return v

def extract_team_lines(grouped_json: dict, team: str, *, include_preseason: bool = False) -> list[str]:
    """
    Build compact lines for GPT using only completed regular-season games by default.
    - include_preseason=False: use REG only; True adds PRE.
    - final statuses: {2, 3} (seen in your data). Skip status==1 (scheduled).
    - skip 0–0 games (unplayed placeholders).
    """
    phases = ("pre", "reg") if include_preseason else ("reg",)
    FINAL_STATUSES = {2, 3}

    lines = []
    for phase in phases:
        weeks = grouped_json.get(phase, {})
        if not isinstance(weeks, dict):
            continue
        for week_label, matchups in weeks.items():
            if not isinstance(matchups, dict):
                continue
            for _, game in matchups.items():
                if not isinstance(game, dict):
                    continue

                # Only finished games
                if game.get("status") not in FINAL_STATUSES:
                    continue

                home = game.get("homeTeamName")
                away = game.get("awayTeamName")
                if team not in (home, away):
                    continue

                # Find scores using "<Team Name> Score" keys
                pf = pa = None
                for k, v in game.items():
                    if isinstance(k, str) and k.endswith(" Score"):
                        if k.startswith(team):
                            pf = v
                        else:
                            pa = v if pa is None else pa

                # Require real scores; skip 0–0 placeholders
                if pf is None or pa is None:
                    continue
                if pf == 0 and pa == 0:
                    continue

                res = "W" if pf > pa else "L" if pf < pa else "T"
                lines.append(f"{week_label}: {home} vs {away} — {team} {pf}-{pa} ({res})")
    return lines


def list_teams_from_final(processed_path: Path) -> set[str]:
    """Read your final grouped schedule and return a set of team names present."""
    data = json.loads(Path(processed_path).read_text(encoding="utf-8"))
    teams: set[str] = set()
    for phase in ("pre", "reg"):
        weeks = data.get(phase, {})
        if not isinstance(weeks, dict):
            continue
        for _, matchups in weeks.items():
            if not isinstance(matchups, dict):
                continue
            for _, game in matchups.items():
                if not isinstance(game, dict):
                    continue
                home = game.get("homeTeamName")
                away = game.get("awayTeamName")
                if home: teams.add(home)
                if away: teams.add(away)
    return teams

def generate_story_from_file(
    processed_path: Path,
    team: str,
    model: str = "gpt-4o-mini",
    include_preseason: bool = False,
    references: list[str] | None = None,  # e.g. ["tiebreakers", "tiebreaker_story_template"]
) -> str:
    """Return a free-flow narrative (for GUI) using schedule lines + optional refs as guidance."""
    if not os.getenv("OPENAI_API_KEY"):
        raise RuntimeError("OPENAI_API_KEY not set. Put it in .env or your environment.")

    data = json.loads(Path(processed_path).read_text(encoding="utf-8"))
    lines = extract_team_lines(data, team, include_preseason=include_preseason)
    schedule_block = "\n".join(lines[:150])

    refs_text = load_references(references) if references else ""
    # Split refs so prompt is clear (template = guidance, rulebook = facts)
    # Expecting files named: reference/tiebreakers.md and reference/tiebreaker_story_template.md
    # If you pass in both (recommended), order them as [ "tiebreaker_story_template", "tiebreakers" ].

    system = (
        "You are an NFL analyst. Use only the provided schedule lines plus the reference text. "
        "Write in a natural, human tone. The template (if provided) is guidance for tone/sections, "
        "NOT a strict format to copy. Do not invent games or stats beyond what the lines imply."
    )

    user = (
        f"TEAM: {team}\n\n"
        f"Schedule lines (regular season, completed games only):\n{schedule_block}\n\n"
        "Reference material (first = stylistic template guidance, second = official tiebreak rules if present):\n"
        f"{refs_text}\n\n"
        "Please produce a short free-flow report:\n"
        "- Start with a punchy one-sentence headline.\n"
        "- Then 5–8 concise bullets on key wins/losses, margins, trends.\n"
        "- End with a brief tiebreaker note informed by the rules (head-to-head, division record, common games, conference record, strength of victory/schedule). "
        "If a detail isn’t derivable from the lines, say so briefly.\n"
        "Keep it under ~200 words."
    )

    resp = client.responses.create(
        model=model,
        input=[{"role": "system", "content": system},
               {"role": "user", "content": user}],
        temperature=0.7,
    )
    return resp.output_text
