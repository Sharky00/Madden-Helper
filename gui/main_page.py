# gui/main_page.py
import os
import tkinter as tk
from tkinter import messagebox
from tkinter import ttk
try:
    from dotenv import load_dotenv
    load_dotenv()
except Exception:
    pass

from paths import PROC_DIR
from process.process import run as process_run
from process.modules.story_gpt import list_teams_from_final
from process.modules.generate_names import run as generate_names_run  # to ensure final exists at startup

def fetch_team_list() -> list[str]:
    """Ensure final file exists, then list all teams from it."""
    try:
        # Build final if missing
        final_path = PROC_DIR / "schedulesPS5_final.json"
        if not final_path.exists():
            generate_names_run()
        teams = sorted(list(list_teams_from_final(final_path)))
        return teams
    except Exception:
        return []

def on_run(btn, output_box, mode_var, team_var):
    btn.config(state="disabled", text="Running…")
    output_box.delete("1.0", tk.END)
    output_box.insert(tk.END, "Generating… please wait.\n")

    try:
        if not os.getenv("OPENAI_API_KEY"):
            raise RuntimeError("OPENAI_API_KEY not set. Put it in .env or your environment.")

        mode = mode_var.get()  # "single" or "all"
        if mode == "single":
            team = team_var.get().strip()
            if not team:
                raise RuntimeError("Please select a team.")
            result = process_run(team=team, all_teams=False)
        else:
            result = process_run(team=None, all_teams=True)

        output_box.delete("1.0", tk.END)
        output_box.insert(tk.END, result.strip() or "(No output)")
    except Exception as e:
        messagebox.showerror("Error", f"{e}")
    finally:
        btn.config(state="normal", text="Run")

def main():
    root = tk.Tk()
    root.title("Madden Helper")
    root.geometry("800x600")

    # Top controls
    ctl = tk.Frame(root)
    ctl.pack(fill="x", padx=12, pady=10)

    mode_var = tk.StringVar(value="single")
    tk.Radiobutton(ctl, text="Single team", variable=mode_var, value="single").pack(side="left")
    tk.Radiobutton(ctl, text="All teams", variable=mode_var, value="all").pack(side="left", padx=(12, 0))

    # Team picker (enabled only for single)
    tk.Label(ctl, text="Team:").pack(side="left", padx=(20, 6))
    team_var = tk.StringVar()
    team_combo = ttk.Combobox(ctl, textvariable=team_var, width=40, state="readonly")
    team_combo.pack(side="left")

    def on_mode_change(*_):
        if mode_var.get() == "single":
            team_combo.configure(state="readonly")
        else:
            team_combo.configure(state="disabled")
    mode_var.trace_add("write", on_mode_change)

    # Populate team list
    teams = fetch_team_list()
    team_combo["values"] = teams
    if teams:
        team_combo.current(0)

    # Output text area with scrollbar
    frame = tk.Frame(root)
    frame.pack(fill="both", expand=True, padx=12, pady=(0, 12))
    output = tk.Text(frame, wrap="word")
    scroll = tk.Scrollbar(frame, command=output.yview)
    output.configure(yscrollcommand=scroll.set)
    output.pack(side="left", fill="both", expand=True)
    scroll.pack(side="right", fill="y")

    run_btn = tk.Button(root, text="Run", command=lambda: on_run(run_btn, output, mode_var, team_var))
    run_btn.pack(side="bottom", anchor="se", padx=20, pady=20)

    on_mode_change()
    root.mainloop()

if __name__ == "__main__":
    main()
