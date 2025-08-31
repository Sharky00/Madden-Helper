# gui/main_page.py
import os
import re
import tkinter as tk
from tkinter import ttk, messagebox
from pathlib import Path
from datetime import datetime

# Optional: load .env for OPENAI_API_KEY
try:
    from dotenv import load_dotenv
    load_dotenv()
except Exception:
    pass

from paths import PROC_DIR

# Optional export folder integration
try:
    from app_settings import get_export_dir  # returns a Path
except Exception:
    get_export_dir = None  # fallback later

# Optional PDF export helper (requires: pip install reportlab; file: pdf_export.py at project root)
try:
    from pdf_export import save_text_as_pdf
except Exception:
    save_text_as_pdf = None

# --- Robust imports to handle either package or flat-module layouts ---
# pipeline entry
try:
    from process.process import run as process_run
except Exception:
    from process import run as process_run

# team list helper
try:
    from process.modules.story_gpt import list_teams_from_final
except Exception:
    from story_gpt import list_teams_from_final

# ensure processed file exists
try:
    from process.modules.generate_names import run as generate_names_run
except Exception:
    from generate_names import run as generate_names_run


def _fetch_team_list() -> list[str]:
    """Return sorted team names from processed file, generating it if missing."""
    try:
        final_path = PROC_DIR / "schedulesPS5_final.json"
        if not final_path.exists():
            generate_names_run()
        return sorted(list(list_teams_from_final(final_path)))
    except Exception:
        return []


def _slug(s: str) -> str:
    return re.sub(r"[^a-zA-Z0-9\- ]+", "", s).strip().lower().replace(" ", "-") or "report"


def build_main_page(root: tk.Tk):
    """Build the main UI inside the existing root window (no new Tk)."""
    # Clear any prior content (e.g., splash)
    for w in root.winfo_children():
        w.destroy()

    root.title("Madden Helper — Main")
    root.geometry("900x650")

    # --- Top controls row ---
    ctl = tk.Frame(root)
    ctl.pack(fill="x", padx=12, pady=10)

    # Home button (swap back to splash if available)
    def go_home():
        try:
            from gui.launcher import build_splash
            build_splash(root)
        except Exception:
            pass  # if launched standalone, ignore

    tk.Button(ctl, text="◀ Home", command=go_home).pack(side="left")

    # Mode selection
    mode_var = tk.StringVar(value="single")
    tk.Radiobutton(ctl, text="Single team", variable=mode_var, value="single").pack(side="left", padx=(12, 0))
    tk.Radiobutton(ctl, text="All teams",   variable=mode_var, value="all").pack(side="left", padx=(8, 0))

    # Team picker (enabled for single-team mode)
    tk.Label(ctl, text="Team:").pack(side="left", padx=(20, 6))
    team_var = tk.StringVar()
    team_combo = ttk.Combobox(ctl, textvariable=team_var, width=40, state="readonly")
    team_combo.pack(side="left")

    def on_mode_change(*_):
        team_combo.configure(state="readonly" if mode_var.get() == "single" else "disabled")

    mode_var.trace_add("write", on_mode_change)

    # Populate teams
    teams = _fetch_team_list()
    team_combo["values"] = teams
    if teams:
        team_combo.current(0)
    on_mode_change()

    # --- Output area ---
    frame = tk.Frame(root)
    frame.pack(fill="both", expand=True, padx=12, pady=(0, 12))

    output = tk.Text(frame, wrap="word")
    scroll = tk.Scrollbar(frame, command=output.yview)
    output.configure(yscrollcommand=scroll.set)
    output.pack(side="left", fill="both", expand=True)
    scroll.pack(side="right", fill="y")

    # --- Actions ---

    def on_run():
        run_btn.config(state="disabled", text="Running…")
        output.delete("1.0", tk.END)
        output.insert(tk.END, "Generating… please wait.\n")
        try:
            # If your pipeline calls OpenAI, this helps catch a missing key early:
            if not os.getenv("OPENAI_API_KEY"):
                raise RuntimeError("OPENAI_API_KEY not set. Check your .env or environment.")

            if mode_var.get() == "single":
                team = team_var.get().strip()
                if not team:
                    raise RuntimeError("Please select a team.")
                # Only pass supported args
                text = process_run(team=team, all_teams=False, include_preseason=False)
            else:
                text = process_run(team=None, all_teams=True, include_preseason=False)

            output.delete("1.0", tk.END)
            output.insert(tk.END, (text or "").strip() or "(No output)")
        except Exception as e:
            messagebox.showerror("Error", f"{e}")
        finally:
            run_btn.config(state="normal", text="Run")

    def _get_export_dir() -> Path:
        if callable(get_export_dir):
            return get_export_dir()
        # default to ./exports if app_settings not present
        proj_root = Path(os.path.dirname(__file__)).resolve().parents[1]
        default_dir = proj_root / "exports"
        default_dir.mkdir(parents=True, exist_ok=True)
        return default_dir

    def on_save():
        text = output.get("1.0", "end-1c")
        if not text.strip():
            messagebox.showinfo("Nothing to save", "No output to save yet.")
            return
        export_dir = _get_export_dir()
        name = team_var.get().strip() if mode_var.get() == "single" else "all-teams"
        fname = f"{_slug(name)}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.md"
        path = export_dir / fname
        try:
            path.write_text(text, encoding="utf-8")
            messagebox.showinfo("Saved", f"Saved to:\n{path}")
        except Exception as e:
            messagebox.showerror("Error", f"Could not save file:\n{e}")

    def on_save_pdf():
        text = output.get("1.0", "end-1c")
        if not text.strip():
            messagebox.showinfo("Nothing to save", "No output to save yet.")
            return
        if save_text_as_pdf is None:
            messagebox.showerror(
                "PDF export unavailable",
                "Missing dependency or helper.\n\nInstall:\n  pip install reportlab\n\n"
                "And ensure pdf_export.py is at the project root."
            )
            return
        export_dir = _get_export_dir()
        name = team_var.get().strip() if mode_var.get() == "single" else "all-teams"
        fname = f"{_slug(name)}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf"
        out_path = export_dir / fname
        try:
            save_text_as_pdf(text, out_path)
            messagebox.showinfo("Saved", f"PDF saved to:\n{out_path}")
        except Exception as e:
            messagebox.showerror("Error", f"Could not save PDF:\n{e}")

    # Bottom button bar (Save as PDF, Save, Run)
    btn_bar = tk.Frame(root)
    btn_bar.pack(fill="x", side="bottom", padx=12, pady=12)

    tk.Button(btn_bar, text="Save as PDF", command=on_save_pdf).pack(side="left", padx=(0, 6))
    tk.Button(btn_bar, text="Save",        command=on_save).pack(side="left")
    run_btn = tk.Button(btn_bar, text="Run", command=on_run)
    run_btn.pack(side="right")


# Allow standalone run for testing
def main():
    root = tk.Tk()
    build_main_page(root)
    root.mainloop()


if __name__ == "__main__":
    main()
