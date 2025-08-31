# process/process.py
from paths import PROC_DIR
from .modules.generate_names import run as generate_names_run
from .modules.story_gpt import generate_story_from_file, list_teams_from_final
from .modules.tiebreaks import build_tiebreak_appendix

def run(team: str | None = None, all_teams: bool = False, model: str = "gpt-5-mini",
        include_preseason: bool = False) -> str:
    # 1) Ensure latest processed file exists
    generate_names_run()
    final_path = PROC_DIR / "schedulesPS5_final.json"
    refs = ["tiebreaker_story_template", "tiebreakers"]  # soft guidance + rulebook

    # 2) Single team vs all teams
    if all_teams:
        chunks = []
        for t in sorted(list_teams_from_final(final_path)):
            story = generate_story_from_file(final_path, t, model, include_preseason, refs)
            appendix = build_tiebreak_appendix(final_path, t)
            chunks.append(f"{story}\n{appendix}\n")
        return "\n".join(chunks)

    if not team:
        raise ValueError("Provide a team name or set all_teams=True.")

    story = generate_story_from_file(final_path, team, model, include_preseason, refs)
    appendix = build_tiebreak_appendix(
    final_path,
    team,
    include_division=True,     # put division at the top
    include_wildcard=True
)


    return f"{story}\n\n{appendix}" if appendix else story
