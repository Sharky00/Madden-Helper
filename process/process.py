# process/process.py
from paths import PROC_DIR
from .modules.generate_names import run as generate_names_run
from .modules.story_gpt import generate_story_from_file, list_teams_from_final

def run(team: str | None = None, all_teams: bool = False, model: str = "gpt-4o-mini",
        include_preseason: bool = False) -> str:
    generate_names_run()
    final_path = PROC_DIR / "schedulesPS5_final.json"
    refs = ["tiebreaker_story_template", "tiebreakers"]  # <— template guidance + rulebook

    if all_teams:
        chunks = []
        for t in sorted(list_teams_from_final(final_path)):
            chunks.append(f"# {t}\n" + generate_story_from_file(final_path, t, model,
                                                                include_preseason, refs) + "\n")
        return "\n".join(chunks)

    if not team:
        raise ValueError("Provide a team name or set all_teams=True.")
    return generate_story_from_file(final_path, team, model, include_preseason, refs)
