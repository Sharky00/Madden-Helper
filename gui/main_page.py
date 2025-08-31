# gui/main_page.py
import os
import re
import tkinter as tk
from tkinter import ttk, messagebox
from pathlib import Path
from datetime import datetime
import threading
import traceback
from pdf_export import save_all_teams_pdf, save_single_team_pdf


# Optional: load .env for OPENAI_API_KEY
try:
    from dotenv import load_dotenv
    load_dotenv()
except Exception:
    pass

# --------------- Helpers (no external deps) ---------------
def _project_root() -> Path:
    # gui/ is one level below project root
    return Path(__file__).resolve().parents[1]

def _exports_dir() -> Path:
    # Use app_settings.get_export_dir() if available; else default to ./exports
    try:
        from app_settings import get_export_dir
        d = get_export_dir()
        d.mkdir(parents=True, exist_ok=True)
        return d
    except Exception:
        d = _project_root() / "exports"
        d.mkdir(parents=True, exist_ok=True)
        return d

def _slug(s: str) -> str:
    return re.sub(r"[^a-zA-Z0-9\- ]+", "", s or "").strip().lower().replace(" ", "-") or "report"

# --------------- Imports that may vary by layout ---------------
# paths
try:
    from paths import PROC_DIR
except Exception:
    PROC_DIR = _project_root() / "data" / "processed"

# pipeline entry
try:
    from process.process import run as process_run
except Exception:
    from process import run as process_run  # flat layout fallback

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

# PDF export (optional)
_pdf_multi = _pdf_single = None
try:
    # ReportLab version with multi-team support
    from pdf_export import save_all_teams_pdf as _pdf_multi
    from pdf_export import save_single_team_pdf as _pdf_single
except Exception:
    try:
        # Fallback: single-team helper or generic saver
        from pdf_export import save_text_as_pdf as _pdf_single_generic
        _pdf_single = _pdf_single_generic  # will miss logos/header, but still works
    except Exception:
        _pdf_single = None  # no PDF support available


# --------------- Data helpers ---------------
def _fetch_team_list() -> list[str]:
    """Return sorted team names from processed file, generating it if missing."""
    try:
        final_path = PROC_DIR / "schedulesPS5_final.json"
        if not final_path.exists():
            generate_names_run()
        return sorted(list(list_teams_from_final(final_path)))
    except Exception:
        return []


# --------------- UI ---------------
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

    _run_thread = None  # keep a ref so it isn't GC'd

    def _start_busy():
        run_btn.config(state="disabled", text="Running…")
        progress_lbl.config(text="")
        progress.pack(side="right", padx=6)
        progress_lbl.pack(side="right", padx=(6, 0))
        progress.start(12)

    def _stop_busy():
        progress.stop()
        progress.pack_forget()
        progress_lbl.pack_forget()
        run_btn.config(state="normal", text="Run")

    def on_run():
        nonlocal _run_thread
        if _run_thread and _run_thread.is_alive():
            return  # already running

        output.delete("1.0", tk.END)
        output.insert(tk.END, "Generating… please wait.\n")
        _start_busy()

        def worker():
            try:
                if not os.getenv("OPENAI_API_KEY"):
                    raise RuntimeError("OPENAI_API_KEY not set. Check your .env or environment.")

                if mode_var.get() == "single":
                    team = team_var.get().strip()
                    if not team:
                        raise RuntimeError("Please select a team.")
                    text = process_run(team=team, all_teams=False, include_preseason=False)

                    def done_ok():
                        output.delete("1.0", tk.END)
                        output.insert(tk.END, (text or "").strip() or "(No output)")
                        _stop_busy()
                    root.after(0, done_ok)

                else:
                    # === ALL TEAMS with PROGRESS ===
                    # Get the list once so we can show i/total.
                    try:
                        final_path = PROC_DIR / "schedulesPS5_final.json"
                        if not final_path.exists():
                            generate_names_run()
                        teams = sorted(list(list_teams_from_final(final_path)))
                    except Exception:
                        # Fallback: let process_run handle it, but we won't get per-team progress.
                        teams = []

                    if not teams:
                        # Use old single-shot path if we couldn't enumerate teams
                        text = process_run(team=None, all_teams=True, include_preseason=False)
                        def done_all():
                            output.delete("1.0", tk.END)
                            output.insert(tk.END, (text or "").strip() or "(No output)")
                            _stop_busy()
                        root.after(0, done_all)
                        return

                    total = len(teams)
                    chunks = []

                    for i, tname in enumerate(teams, 1):
                        # update counter label in the UI
                        def upd(i=i, tname=tname):
                            progress_lbl.config(text=f"{i}/{total} • {tname}")
                        root.after(0, upd)

                        # generate one team at a time so UI can show progress
                        try:
                            part = process_run(team=tname, all_teams=False, include_preseason=False)
                        except Exception as e:
                            part = f"# {tname}\nError generating: {e}\n"
                        else:
                            # Ensure each team starts with a heading (helps PDF exporter split pages)
                            if not (part or "").lstrip().startswith("#"):
                                part = f"# {tname}\n{part}"
                        chunks.append((part or "").rstrip() + "\n")

                    final_text = "\n".join(chunks)

                    def done_all():
                        output.delete("1.0", tk.END)
                        output.insert(tk.END, final_text.strip() or "(No output)")
                        _stop_busy()
                    root.after(0, done_all)

            except Exception as e:
                err = "".join(traceback.format_exception_only(type(e), e)).strip()
                def done_err():
                    _stop_busy()
                    messagebox.showerror("Error", err)
                root.after(0, done_err)

        _run_thread = threading.Thread(target=worker, daemon=True)
        _run_thread.start()

    def on_save():
        text = output.get("1.0", "end-1c")
        if not text.strip():
            messagebox.showinfo("Nothing to save", "No output to save yet.")
            return
        export_dir = _exports_dir()
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

        export_dir = _exports_dir()
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")

        try:
            if mode_var.get() == "single":
                team = (team_var.get() or "").strip() or "team"
                out_path = export_dir / f"{_slug(team)}_{ts}.pdf"
                # Header with Team — Record and logo on right
                save_single_team_pdf(text, out_path, team=team)
            else:
                out_path = export_dir / f"all-teams_{ts}.pdf"
                # Splits by "# Team Name" headings; logo+header per page
                save_all_teams_pdf(text, out_path)

            messagebox.showinfo("Saved", f"PDF saved to:\n{out_path}")
        except Exception as e:
            messagebox.showerror("Error", f"Could not save PDF:\n{e}")


    # Bottom button bar (Save as PDF, Save, Progress text + spinner, Run)
    btn_bar = tk.Frame(root)
    btn_bar.pack(fill="x", side="bottom", padx=12, pady=12)

    tk.Button(btn_bar, text="Save as PDF", command=on_save_pdf).pack(side="left", padx=(0, 6))
    tk.Button(btn_bar, text="Save",        command=on_save).pack(side="left")

    # progress widgets (hidden until running)
    progress_lbl = tk.Label(btn_bar, text="", fg="gray")
    progress = ttk.Progressbar(btn_bar, mode="indeterminate", length=120)
    # both are packed/unpacked in _start_busy/_stop_busy

    run_btn = tk.Button(btn_bar, text="Run", command=on_run)
    run_btn.pack(side="right")


# Allow standalone run for testing
def main():
    root = tk.Tk()
    build_main_page(root)
    root.mainloop()


if __name__ == "__main__":
    main()
