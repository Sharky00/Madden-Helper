# gui/settings_window.py
import os
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
from app_settings import load_settings, save_settings

def open_export_settings(root: tk.Tk):
    s = load_settings()
    win = tk.Toplevel(root)
    win.title("Export Folder")
    win.transient(root); win.grab_set()
    win.resizable(False, False)

    frm = ttk.Frame(win, padding=12)
    frm.grid(row=0, column=0, sticky="nsew")

    ttk.Label(frm, text="Export to:").grid(row=0, column=0, sticky="w")
    path_var = tk.StringVar(value=s.get("export_dir", ""))
    entry = ttk.Entry(frm, textvariable=path_var, width=48)
    entry.grid(row=0, column=1, sticky="we", padx=(6,0))

    def browse():
        initial = path_var.get() or os.getcwd()
        d = filedialog.askdirectory(parent=win, initialdir=initial, title="Choose export folder")
        if d:
            path_var.set(d)

    ttk.Button(frm, text="Browse…", command=browse).grid(row=0, column=2, padx=(6,0))

    btns = ttk.Frame(frm)
    btns.grid(row=1, column=0, columnspan=3, sticky="e", pady=(12,0))
    ttk.Button(btns, text="Cancel", command=lambda:(win.grab_release(), win.destroy())).pack(side="right")
    def save():
        try:
            save_settings({"export_dir": path_var.get().strip()})
            win.grab_release(); win.destroy()
        except Exception as e:
            messagebox.showerror("Error", str(e))
    ttk.Button(btns, text="Save", command=save).pack(side="right", padx=(6,0))
