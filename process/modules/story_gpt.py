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

def compute_basic_stats(grouped_json: dict, team: str) -> dict:
    """W-L(-T) and point differential from REG games marked final (status 2 or 3)."""
    FINAL_STATUSES = {2, 3}
    w = l = t = diff = 0
    reg = grouped_json.get("reg", {})
    if isinstance(reg, dict):
        for matchups in reg.values():
            if not isinstance(matchups, dict):
                continue
            for game in matchups.values():
                if not isinstance(game, dict) or game.get("status") not in FINAL_STATUSES:
                    continue
                if team not in (game.get("homeTeamName"), game.get("awayTeamName")):
                    continue
                pf = _score_for(game, team)
                pa = _score_against(game, team)
                if pf is None or pa is None:
                    continue
                diff += (pf - pa)
                if pf > pa: w += 1
                elif pf < pa: l += 1
                else: t += 1
    return {"REG_W": w, "REG_L": l, "REG_T": t, "POINT_DIFF": diff}

def _format_record(stats: dict) -> str:
    return f"{stats['REG_W']}-{stats['REG_L']}" + (f"-{stats['REG_T']}" if stats['REG_T'] else "")

def generate_story_from_file(
    processed_path: Path,
    team: str,
    model: str = "gpt-4o-mini",
    include_preseason: bool = False,
    references: list[str] | None = None,
) -> str:
    if not os.getenv("OPENAI_API_KEY"):
        raise RuntimeError("OPENAI_API_KEY not set. Put it in .env or your environment.")

    data = json.loads(Path(processed_path).read_text(encoding="utf-8"))

    # 1) Build schedule lines (REG only, final games)
    lines = extract_team_lines(data, team, include_preseason=include_preseason)
    schedule_block = "\n".join(lines[:150])

    # 2) Compute stats for the prompt
    stats = compute_basic_stats(data, team)
    record = _format_record(stats)
    point_diff = f"{stats['POINT_DIFF']:+d}"
    record = f"{stats['REG_W']}-{stats['REG_L']}" + (f"-{stats['REG_T']}" if stats['REG_T'] else "")
    point_diff = f"{stats['POINT_DIFF']:+d}"

    # 3) Load soft guidance (template first) + rulebook
    refs = references or ["tiebreaker_story_template", "tiebreakers"]
    refs_text = load_references(refs)

    # 4) Free-flow prompt (no bullets, no cap)
    system = (
        "You are an NFL analyst. Use only the provided schedule lines and reference text. "
        "Treat the template (if present) as stylistic guidance—do not follow it rigidly. "
        "Write in a cohesive, free-flow, human tone. Do not invent games or stats beyond the lines."
    )
    user = (
        f"TEAM: {team}\n"
        f"Regular-season record (from provided lines): {record}\n"
        f"Point differential: {point_diff}\n\n"
        f"Schedule lines (regular season, completed games only):\n{schedule_block}\n\n"
        "Reference (template guidance first, then official tie-break rules):\n"
        f"{refs_text}\n\n"
        "Write a natural, paragraph-style season recap (no bullet points). Aim for 2–4 short paragraphs:\n"
        "• A punchy lede summarizing the arc.\n"
        "• Narrative body weaving in key wins/losses, notable margins, and trends grounded in the lines.\n"
        "• A concise tie-breaker outlook using the rulebook order (head-to-head, division record, common games, "
        "conference record, strength of victory/schedule). If something isn’t derivable from the lines, say so briefly.\n"
        "Keep it cohesive and grounded in the lines; if something isn’t explicit, phrase it neutrally without claiming missing data. "
        "Close with a concise tie-breaker outlook consistent with the rulebook (head-to-head, division record, common games, conference record, strength of victory/schedule)."
    )

    resp = client.responses.create(
        model=model,
        input=[{"role": "system", "content": system},
            {"role": "user", "content": user}],
    )

    body = resp.output_text.strip()
    title = f"{team} — {record}"        # ← Title line you wanted
    return f"{title}\n\n{body}"
