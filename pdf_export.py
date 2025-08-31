# pdf_export.py — fpdf2 exporter with ASCII sanitization, hard-wrap, logos, single & all-teams
import os
import re
import json
from pathlib import Path
from typing import Optional
from fpdf import FPDF

# ---------- robust project paths ----------
try:
    from paths import PROJECT_ROOT, PROC_DIR
except Exception:
    _ROOT = Path(__file__).resolve().parent
    PROJECT_ROOT = _ROOT
    PROC_DIR = PROJECT_ROOT / "data" / "processed"

ASSETS_DIR = PROJECT_ROOT / "assets" / "logos"  # images live in assets/logos/<slug>.png|jpg|jpeg
FINAL_STATUSES = {2, 3}  # finished games in your data

# ---------- ASCII sanitizer (avoid Unicode font issues) ----------
ASCII_SUBS = {
    "—": "-", "–": "-", "−": "-",        # dashes
    "“": '"', "”": '"', "„": '"', "‟": '"',
    "‘": "'", "’": "'", "‚": "'",
    "…": "...", "\u00a0": " ",           # ellipsis, nbsp
    "•": "-",                            # bullet
}
_ASCII_TABLE = str.maketrans(ASCII_SUBS)

def _sanitize(text: str) -> str:
    if not text:
        return text
    s = text.translate(_ASCII_TABLE)
    return "".join(ch if ord(ch) < 128 else "?" for ch in s)

# ---------- hard-wrap any super-long tokens (urls/filenames) ----------
def _hard_wrap_tokens(text: str, chunk: int = 40, trigger: int = 60) -> str:
    """
    For any run of non-space chars length >= trigger, insert spaces every `chunk`
    so fpdf2 can wrap instead of raising 'not enough horizontal space...'.
    """
    def repl(m):
        t = m.group(0)
        return " ".join(t[i:i+chunk] for i in range(0, len(t), chunk))
    return re.sub(rf"\S{{{trigger},}}", repl, text)

def _prep(text: str) -> str:
    return _sanitize(_hard_wrap_tokens(text))

# ---------- helpers ----------
def _slug(s: str) -> str:
    s = (s or "").strip().lower()
    s = re.sub(r"[^a-z0-9\- ]+", "", s)
    return (s.replace(" ", "-") or "team").strip("-")

def _find_logo(team: str) -> Optional[Path]:
    if not team:
        return None
    slug = _slug(team)
    for ext in ("png", "jpg", "jpeg"):
        p = ASSETS_DIR / f"{slug}.{ext}"
        if p.exists():
            return p
    return None

def _scores_by_team(game: dict) -> dict:
    # keys look like "<Team Name> Score"
    return {k[:-6].strip(): v for k, v in game.items()
            if isinstance(k, str) and k.endswith(" Score")}

def _compute_record(processed_path: Path, team: str) -> str:
    """Return 'W-L(-T)' from REG-season finished games."""
    if not processed_path.exists():
        return ""
    data = json.loads(processed_path.read_text(encoding="utf-8"))
    w = l = t = 0
    reg = data.get("reg") or {}
    for weeks in reg.values():
        if not isinstance(weeks, dict):
            continue
        for g in weeks.values():
            if not isinstance(g, dict) or g.get("status") not in FINAL_STATUSES:
                continue
            scores = _scores_by_team(g)
            if team not in scores and team not in (g.get("homeTeamName"), g.get("awayTeamName")):
                continue
            pf = scores.get(team)
            pa = None
            if pf is None:
                home, away = g.get("homeTeamName"), g.get("awayTeamName")
                if team == home:
                    pf, pa = scores.get(home), scores.get(away)
                elif team == away:
                    pf, pa = scores.get(away), scores.get(home)
            else:
                for opp, val in scores.items():
                    if opp != team:
                        pa = val
                        break
            if pf is None or pa is None:
                continue
            if pf > pa: w += 1
            elif pf < pa: l += 1
            else: t += 1
    return f"{w}-{l}" + (f"-{t}" if t else "")

# ---------- PDF document ----------
class _ReportPDF(FPDF):
    def __init__(self):
        super().__init__(format="Letter", unit="pt")
        self.left_margin = 54
        self.right_margin = 54
        self.top_margin = 54
        self.bottom_margin = 54
        self.set_margins(self.left_margin, self.top_margin, self.right_margin)
        self.set_auto_page_break(auto=True, margin=self.bottom_margin)
        # dynamic header
        self._hdr_team: Optional[str] = None
        self._hdr_record: Optional[str] = None
        self._hdr_logo: Optional[str] = None  # path string

    @property
    def content_width(self) -> float:
        return self.w - self.left_margin - self.right_margin

    def set_header_info(self, team: Optional[str], record: Optional[str], logo_path: Optional[Path]):
        self._hdr_team = team
        self._hdr_record = record
        self._hdr_logo = str(logo_path) if logo_path else None

    def header(self):
        y = 24
        # logo on right (~80pt wide)
        if self._hdr_logo and os.path.exists(self._hdr_logo):
            self.image(self._hdr_logo, x=self.w - self.right_margin - 80, y=y - 6, w=80)
        # title on left
        title = ""
        if self._hdr_team:
            title = self._hdr_team
        if self._hdr_record:
            title = f"{title} - {self._hdr_record}" if title else self._hdr_record
        title = _prep(title)
        if title:
            self.set_xy(self.left_margin, y)
            self.set_font("Helvetica", "B", 16)
            # Use explicit width to avoid layout edge cases
            self.cell(w=self.content_width, h=18, txt=title, ln=1)
        # divider
        self.set_y(y + 24)
        self.set_draw_color(210, 210, 210)
        self.set_line_width(0.6)
        self.line(self.left_margin, self.get_y(), self.w - self.right_margin, self.get_y())
        self.ln(8)

# ---------- body renderer with tidy spacing ----------
def _write_body(pdf: _ReportPDF, text: str):
    W = pdf.content_width
    pdf.set_font("Helvetica", size=11)
    lines = text.replace("\r\n", "\n").replace("\r", "\n").split("\n")

    def is_hr(s: str) -> bool:
        return s.strip() in ("---", "***", "___")

    def is_h1(s: str) -> bool:
        return s.startswith("# ")

    def is_h2(s: str) -> bool:
        if s.startswith("## "): return True
        if re.match(r"^\s*Part\s+\d+\s*:\s*", s, flags=re.I): return True
        if re.search(r"(Rivalry Breakdown|Tiebreaker.*|Wild-?card comparisons:)\s*$", s, flags=re.I): return True
        return False

    def is_bullet(s: str) -> bool:
        return s.lstrip().startswith("- ")

    i, n = 0, len(lines)
    while i < n:
        s = lines[i].rstrip()

        if not s:
            j = i + 1
            while j < n and not lines[j].strip():
                j += 1
            pdf.ln(6 if (j - i) == 1 else 14)
            i = j
            continue

        if is_hr(s):
            y = pdf.get_y() + 4
            pdf.set_draw_color(200, 200, 200)
            pdf.set_line_width(0.6)
            pdf.line(pdf.left_margin, y, pdf.w - pdf.right_margin, y)
            pdf.ln(10)
            i += 1
            continue

        if is_h1(s):
            pdf.set_font("Helvetica", "B", 16)
            pdf.set_x(pdf.left_margin)
            pdf.multi_cell(W, 18, _prep(s[2:].strip()))
            pdf.ln(4)
            pdf.set_font("Helvetica", size=11)
            i += 1
            continue

        if is_h2(s):
            txt = s[3:].strip() if s.startswith("## ") else s.strip()
            pdf.set_font("Helvetica", "B", 13)
            pdf.set_x(pdf.left_margin)
            pdf.multi_cell(W, 16, _prep(txt))
            pdf.ln(2)
            pdf.set_font("Helvetica", size=11)
            i += 1
            continue

        if is_bullet(s):
            pdf.ln(2)
            while i < n and is_bullet(lines[i]):
                item = lines[i].lstrip()[2:].strip()
                pdf.set_x(pdf.left_margin)
                pdf.multi_cell(W, 14, "- " + _prep(item))
                i += 1
            pdf.ln(4)
            continue

        # normal paragraph
        para = [s]
        i += 1
        while i < n:
            nxt = lines[i].rstrip()
            if (not nxt) or is_bullet(nxt) or is_h1(nxt) or is_h2(nxt) or is_hr(nxt):
                break
            para.append(nxt)
            i += 1
        pdf.set_x(pdf.left_margin)
        pdf.multi_cell(W, 14, _prep(" ".join(para)))
        pdf.ln(2)

# ---------- public APIs ----------
def save_single_team_pdf(text: str, out_path: Path, team: str):
    """
    One-team export: header "Team - Record" on left + team logo on right.
    If the body starts with "# Team", that heading is skipped (we already have a header).
    """
    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    record = _compute_record(PROC_DIR / "schedulesPS5_final.json", team)
    logo = _find_logo(team)

    pdf = _ReportPDF()
    pdf.set_header_info(team, record, logo)
    pdf.add_page()

    # Skip first "# Team" line if present
    lines = text.replace("\r\n", "\n").replace("\r", "\n").split("\n")
    i = 0
    while i < len(lines) and not lines[i].strip():
        i += 1
    if i < len(lines) and lines[i].startswith("# "):
        body_text = "\n".join(lines[i + 1:])
    else:
        body_text = text

    _write_body(pdf, body_text)
    pdf.output(str(out_path))

def save_all_teams_pdf(all_text: str, out_path: Path):
    """
    Multi-team export:
    - Splits on top-level headings '# Team Name'
    - Each team renders on a new page with title + logo
    """
    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    matches = list(re.finditer(r"(?m)^#\s+(.+?)\s*$", all_text))
    pdf = _ReportPDF()

    if not matches:
        # No headings; single page without per-team header
        pdf.set_header_info(None, None, None)
        pdf.add_page()
        _write_body(pdf, all_text)
        pdf.output(str(out_path))
        return

    for idx, m in enumerate(matches):
        team_name = m.group(1).strip()
        start = m.end()
        end = matches[idx + 1].start() if idx + 1 < len(matches) else len(all_text)
        body_text = all_text[start:end].lstrip("\n")

        record = _compute_record(PROC_DIR / "schedulesPS5_final.json", team_name)
        logo = _find_logo(team_name)

        pdf.set_header_info(team_name, record, logo)
        pdf.add_page()
        _write_body(pdf, body_text)

    pdf.output(str(out_path))
