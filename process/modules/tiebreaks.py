# process/modules/tiebreaks.py
from __future__ import annotations
from pathlib import Path
import json
from collections import defaultdict

# helpers (put near your other utilities)
FINAL_STATUSES = {2, 3}

def _scores_by_team(game: dict) -> dict:
    return {k[:-6].strip(): v for k, v in game.items() if isinstance(k, str) and k.endswith(" Score")}

def head_to_head_status(schedule_json: dict, a: str, b: str) -> dict:
    """Return head-to-head record and whether it's clinched."""
    total = final = a_w = a_l = a_t = 0
    for phase in ("reg",):  # only regular season for tiebreakers
        weeks = schedule_json.get(phase, {})
        if not isinstance(weeks, dict): 
            continue
        for matchups in weeks.values():
            if not isinstance(matchups, dict):
                continue
            for g in matchups.values():
                if not isinstance(g, dict):
                    continue
                teams = (g.get("homeTeamName"), g.get("awayTeamName"))
                if a in teams and b in teams:
                    total += 1
                    if g.get("status") in FINAL_STATUSES:
                        final += 1
                        scores = _scores_by_team(g)
                        a_pts, b_pts = scores.get(a), scores.get(b)
                        if a_pts is None or b_pts is None:
                            continue
                        if a_pts > b_pts: a_w += 1
                        elif a_pts < b_pts: a_l += 1
                        else: a_t += 1
    pending = total - final
    # Clinch logic: if the trailing side cannot catch up with remaining games
    # For typical 2-game divisional series:
    #  - 2–0 or 0–2 after finals => clinched
    clinched = (pending == 0) and (a_w != a_l)  # no more games AND not tied
    return {"a_w": a_w, "a_l": a_l, "a_t": a_t, "final_played": final, "pending": pending, "clinched": clinched}

# --- Division map (keep in sync with your data's team names) ---
NFC_WEST = ["Arizona Cardinals", "Los Angeles Rams", "San Francisco 49ers", "Seattle Seahawks"]
NFC_EAST = ["Dallas Cowboys", "New York Giants", "Philadelphia Eagles", "Washington Commanders"]
NFC_NORTH = ["Chicago Bears", "Detroit Lions", "Green Bay Packers", "Minnesota Vikings"]
NFC_SOUTH = ["Atlanta Falcons", "Carolina Panthers", "New Orleans Saints", "Tampa Bay Buccaneers"]

AFC_WEST = ["Denver Broncos", "Kansas City Chiefs", "Las Vegas Raiders", "Los Angeles Chargers"]
AFC_EAST = ["Buffalo Bills", "Miami Dolphins", "New England Patriots", "New York Jets"]
AFC_NORTH = ["Baltimore Ravens", "Cincinnati Bengals", "Cleveland Browns", "Pittsburgh Steelers"]
AFC_SOUTH = ["Houston Texans", "Indianapolis Colts", "Jacksonville Jaguars", "Tennessee Titans"]

CONF_DIV = {}
for t in NFC_WEST:  CONF_DIV[t] = ("NFC", "West")
for t in NFC_EAST:  CONF_DIV[t] = ("NFC", "East")
for t in NFC_NORTH: CONF_DIV[t] = ("NFC", "North")
for t in NFC_SOUTH: CONF_DIV[t] = ("NFC", "South")
for t in AFC_WEST:  CONF_DIV[t] = ("AFC", "West")
for t in AFC_EAST:  CONF_DIV[t] = ("AFC", "East")
for t in AFC_NORTH: CONF_DIV[t] = ("AFC", "North")
for t in AFC_SOUTH: CONF_DIV[t] = ("AFC", "South")


# --- Core parsing helpers ---
def _score_for(game: dict, team: str):
    for k, v in game.items():
        if isinstance(k, str) and k.endswith(" Score") and k.startswith(team):
            return v

def _collect_games_by_team(processed: dict):
    """Return team_games dict: team -> list of dict(opponent, pf, pa) for REG finished games only."""
    team_games = defaultdict(list)
    all_teams = set()
    reg = processed.get("reg", {})
    if not isinstance(reg, dict):
        return team_games, all_teams

    for _, matchups in reg.items():
        if not isinstance(matchups, dict):
            continue
        for _, g in matchups.items():
            if not isinstance(g, dict) or g.get("status") not in FINAL_STATUSES:
                continue
            home, away = g.get("homeTeamName"), g.get("awayTeamName")
            if not home or not away:
                continue
            hs = _score_for(g, home)
            as_ = _score_for(g, away)
            if hs is None or as_ is None:
                continue
            all_teams.update([home, away])
            team_games[home].append(dict(opponent=away, pf=hs, pa=as_))
            team_games[away].append(dict(opponent=home, pf=as_, pa=hs))
    return team_games, all_teams

def _wlt(records):
    w = l = t = 0
    for r in records:
        if r["pf"] > r["pa"]: w += 1
        elif r["pf"] < r["pa"]: l += 1
        else: t += 1
    return (w, l, t)

def _head_to_head(team_games, A, B):
    recs = [r for r in team_games[A] if r["opponent"] == B]
    w, l, t = _wlt(recs)
    if w > l: return "A", (w, l, t)
    if l > w: return "B", (w, l, t)
    if w == l == t == 0: return "None", (0, 0, 0)  # no games
    return "Tie", (w, l, t)

def _record_vs_filter(team_games, team, predicate):
    return _wlt([r for r in team_games[team] if predicate(r["opponent"])])

def _winpct(wlt):
    w, l, t = wlt
    gp = w + l + t
    return (w + 0.5 * t) / gp if gp else 0.0

def describe_division_tiebreak(schedule_json: dict, team: str, opp: str) -> str:
    h2h = head_to_head_status(schedule_json, team, opp)
    h2h_str = f"{h2h['a_w']}-{h2h['a_l']}" + (f"-{h2h['a_t']}" if h2h['a_t'] else "")
    if h2h["clinched"]:
        leader = team if h2h["a_w"] > h2h["a_l"] else opp
        return f"{leader} clinches the head-to-head ({h2h_str})."
    # not clinched -> 'current edge' language
    if h2h["a_w"] > h2h["a_l"]:
        return (f"Current edge: {team} via head-to-head ({h2h_str}). "
                f"{h2h['pending']} head-to-head game(s) pending; a split would move to division record next.")
    elif h2h["a_l"] > h2h["a_w"]:
        return (f"Current edge: {opp} via head-to-head ({h2h_str}). "
                f"{h2h['pending']} head-to-head game(s) pending; a split would move to division record next.")
    else:
        return (f"Head-to-head even ({h2h_str}). "
                "Proceed to division record, then common games (≥4), then conference record.")


# --- Compare functions per NFL procedures ---
def _common_games_records(team_games, A, B):
    oppsA = {r["opponent"] for r in team_games[A]} - {B}
    oppsB = {r["opponent"] for r in team_games[B]} - {A}
    common = oppsA & oppsB
    recA = _wlt([r for r in team_games[A] if r["opponent"] in common])
    recB = _wlt([r for r in team_games[B] if r["opponent"] in common])
    return recA, recB, len(common)

def compare_division_tiebreak(processed: dict, A: str, B: str):
    team_games, _ = _collect_games_by_team(processed)
    steps = []

    # 1) Head-to-head
    h2h_res, h2h_wlt = _head_to_head(team_games, A, B)
    steps.append(("Head-to-head", h2h_res, h2h_wlt))
    if h2h_res in ("A", "B"): return steps

    # 2) Division record
    A_div = _record_vs_filter(team_games, A, lambda opp: CONF_DIV.get(opp) == CONF_DIV.get(A))
    B_div = _record_vs_filter(team_games, B, lambda opp: CONF_DIV.get(opp) == CONF_DIV.get(B))
    cmp_div = "A" if _winpct(A_div) > _winpct(B_div) else "B" if _winpct(B_div) > _winpct(A_div) else "Tie"
    steps.append(("Division record", cmp_div, A_div, B_div))
    if cmp_div in ("A", "B"): return steps

    # 3) Common games (min 4)
    A_c, B_c, n = _common_games_records(team_games, A, B)
    if n >= 4:
        cmp_c = "A" if _winpct(A_c) > _winpct(B_c) else "B" if _winpct(B_c) > _winpct(A_c) else "Tie"
        steps.append((f"Common games (n={n})", cmp_c, A_c, B_c))
        if cmp_c in ("A", "B"): return steps
    else:
        steps.append((f"Common games (n={n})", "N/A", A_c, B_c))

    # 4) Conference record
    A_conf = _record_vs_filter(team_games, A, lambda opp: CONF_DIV.get(opp, ("",""))[0] == "NFC")
    B_conf = _record_vs_filter(team_games, B, lambda opp: CONF_DIV.get(opp, ("",""))[0] == "NFC")
    cmp_conf = "A" if _winpct(A_conf) > _winpct(B_conf) else "B" if _winpct(B_conf) > _winpct(A_conf) else "Tie"
    steps.append(("Conference record", cmp_conf, A_conf, B_conf))
    return steps

def compare_wildcard_tiebreak(processed: dict, A: str, B: str):
    team_games, _ = _collect_games_by_team(processed)
    steps = []

    # 1) Head-to-head (if any)
    h2h_res, h2h_wlt = _head_to_head(team_games, A, B)
    steps.append(("Head-to-head", h2h_res, h2h_wlt))
    if h2h_res in ("A", "B"): return steps

    # 2) Conference record
    A_conf = _record_vs_filter(team_games, A, lambda opp: CONF_DIV.get(opp, ("",""))[0] == CONF_DIV.get(A, ("",""))[0])
    B_conf = _record_vs_filter(team_games, B, lambda opp: CONF_DIV.get(opp, ("",""))[0] == CONF_DIV.get(B, ("",""))[0])
    cmp_conf = "A" if _winpct(A_conf) > _winpct(B_conf) else "B" if _winpct(B_conf) > _winpct(A_conf) else "Tie"
    steps.append(("Conference record", cmp_conf, A_conf, B_conf))
    if cmp_conf in ("A", "B"): return steps

    # 3) Common games (min 4)
    A_c, B_c, n = _common_games_records(team_games, A, B)
    if n >= 4:
        cmp_c = "A" if _winpct(A_c) > _winpct(B_c) else "B" if _winpct(B_c) > _winpct(A_c) else "Tie"
        steps.append((f"Common games (n={n})", cmp_c, A_c, B_c))
    else:
        steps.append((f"Common games (n={n})", "N/A", A_c, B_c))
    return steps


# --- Public: build a readable appendix for one team ---
# add a parameter so we can hide the header when the story already has “Part 2”
# replace the signature
def build_tiebreak_appendix(processed_path: Path, team: str,
                            *, include_division: bool = True,
                            include_wildcard: bool = True) -> str:
    processed = json.loads(Path(processed_path).read_text(encoding="utf-8"))
    team_games, all_teams = _collect_games_by_team(processed)

    if team not in CONF_DIV:
        return ""

    conf, div = CONF_DIV[team]
    division_rivals = [t for t in all_teams if t != team and CONF_DIV.get(t) == (conf, div)]
    wildcard_opps   = [t for t in all_teams if t != team and CONF_DIV.get(t, ("",""))[0] == conf and t not in division_rivals]

    def fmt_wlt(wlt):
        w,l,t = wlt
        return f"{w}-{l}-{t}" if t else f"{w}-{l}"

    def h2h_line(subject: str, opp: str) -> tuple[str, tuple]:
        # gather head-to-head W/L list + record
        recs = [r for r in team_games[subject] if r["opponent"] == opp]
        wlt = _wlt(recs)
        results = []
        for r in recs:
            tag = "W" if r["pf"] > r["pa"] else ("L" if r["pf"] < r["pa"] else "T")
            results.append(f"{tag} {r['pf']}-{r['pa']}")
        if results:
            return f"{fmt_wlt(wlt)} ({', '.join(results)})", wlt
        return f"{fmt_wlt(wlt)}", wlt

    def division_record(team_name: str) -> tuple[str, tuple]:
        rec = _record_vs_filter(team_games, team_name,
                                lambda opp: CONF_DIV.get(opp) == CONF_DIV.get(team_name))
        return fmt_wlt(rec), rec

    def common_records(subject: str, opp: str) -> tuple[str, tuple, tuple, int]:
        A_c, B_c, n = _common_games_records(team_games, subject, opp)
        if n >= 4:
            return f"Common games (n={n})", A_c, B_c, n
        return f"Common opponents insufficient (n={n})", A_c, B_c, n

    def first_decisive(steps):
        for name, res, *rest in steps:
            if res in ("A", "B"):
                return name, res
        return None, None

    lines = []
    lines.append("Part 2 — Tiebreaker Scenarios\n")

    # ---------------------- DIVISION FIRST ----------------------
    if include_division and division_rivals:
        lines.append("Division Rivalry Breakdown\n")
        for opp in sorted(division_rivals):
            # basics
            h2h_text, _ = h2h_line(team, opp)
            team_div_txt, team_div_rec = division_record(team)
            opp_div_txt,  opp_div_rec  = division_record(opp)
            common_label, A_c, B_c, ncommon = common_records(team, opp)

            # tiebreak winner (first decisive only)
            steps = compare_division_tiebreak(processed, team, opp)
            crit, res = first_decisive(steps)
            if res == "A":
                winner = team
            elif res == "B":
                winner = opp
            else:
                winner = None

            # can pass by overall record?
            can_pass = _pass_by_record_possible(processed, team_games, team, opp)
            yesno = "Yes" if can_pass else "No"
            reason = (f"{team} can still finish with a better overall record."
                      if can_pass else
                      f"{team} cannot mathematically finish above {opp}—would need later-criterion help (Strength of Victory/Schedule).")

            # compose block (keep your detailed bullets, then append the two new ones)
            block = [
                f"vs {opp}",
                f"- Head-to-head record: {h2h_text}.",
                f"- Division record comparison: {team} {team_div_txt} vs {opp} {opp_div_txt}.",
                (f"- {common_label}: {team} {fmt_wlt(A_c)} vs {opp} {fmt_wlt(B_c)}."
                 if ncommon >= 1 else "- Common opponents: none."),
            ]
            # current edge & remaining path (light, based on crit)
            if winner and crit:
                block.append(f"- Current edge: {winner} (via {crit}).")
                if winner == team:
                    block.append(f"- Remaining path: Maintain edge; later rules not needed if tied head-to-head remains favorable.")
                else:
                    block.append(f"- Remaining path: {team} must outperform {opp} on remaining criteria or finish with a better overall record.")
            else:
                block.append("- Current edge: Even/Undecided on early criteria.")
                block.append("- Remaining path: Next rules would be common games (if ≥4) then conference record.")

            # NEW: append the two short bullets
            if winner and crit:
                block.append(f"  - Tiebreaker: {winner} wins via {crit}.")
            else:
                block.append("  - Tiebreaker: No decisive rule yet.")

            block.append(f"  - Can still win by record? {yesno}. {reason}")

            lines.append("\n".join(block) + "\n")

    # ---------------------- WILD CARD NEXT ----------------------
    if include_wildcard and wildcard_opps:
        lines.append("Wild Card Scenarios")
        for opp in sorted(wildcard_opps):
            # head-to-head + conference + common
            h2h_text, _ = h2h_line(team, opp)
            A_conf = _record_vs_filter(team_games, team,
                                       lambda o: CONF_DIV.get(o, ("",""))[0] == conf)
            B_conf = _record_vs_filter(team_games, opp,
                                       lambda o: CONF_DIV.get(o, ("",""))[0] == conf)
            common_label, A_c, B_c, ncommon = common_records(team, opp)

            # tiebreak winner
            steps = compare_wildcard_tiebreak(processed, team, opp)
            crit, res = first_decisive(steps)
            winner = team if res == "A" else (opp if res == "B" else None)

            # can pass by overall record?
            can_pass = _pass_by_record_possible(processed, team_games, team, opp)
            yesno = "Yes" if can_pass else "No"
            reason = (f"{team} can still finish with a better overall record."
                      if can_pass else
                      f"{team} cannot mathematically finish above {opp}—would need later-criterion help (Strength of Victory/Schedule).")

            block = [
                f"- vs {opp}",
                f"  - Head-to-head: {h2h_text}.",
                f"  - Conference record: {team} {fmt_wlt(A_conf)} vs {opp} {fmt_wlt(B_conf)}.",
                (f"  - {common_label}: {team} {fmt_wlt(A_c)} vs {opp} {fmt_wlt(B_c)}."
                 if ncommon >= 1 else "  - Common opponents: none."),
            ]
            if winner and crit:
                block.append(f"  - Tiebreaker: {winner} wins via {crit}.")
            else:
                block.append("  - Tiebreaker: No decisive rule yet.")
            block.append(f"  - Can still win by record? {yesno}. {reason}")
            lines.append("\n".join(block))

    return ("\n\n".join(lines)).strip()





def _current_wins(team_games, team: str) -> int:
    w, l, t = _wlt(team_games[team])
    return w

def _remaining_games(processed: dict, team: str) -> int:
    rem = 0
    reg = processed.get("reg", {})
    for weeks in reg.values():
        if not isinstance(weeks, dict):
            continue
        for g in weeks.values():
            if not isinstance(g, dict):
                continue
            if team in (g.get("homeTeamName"), g.get("awayTeamName")) and g.get("status") not in FINAL_STATUSES:
                rem += 1
    return rem

def _pass_by_record_possible(processed: dict, team_games, subject: str, opp: str) -> bool:
    """Can 'subject' still finish with a strictly better overall record than 'opp'?"""
    subject_max_wins = _current_wins(team_games, subject) + _remaining_games(processed, subject)
    opp_min_wins = _current_wins(team_games, opp)  # assume opponent loses out
    return subject_max_wins > opp_min_wins
