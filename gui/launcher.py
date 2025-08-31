# gui/launcher.py
import tkinter as tk

def _open_main(root: tk.Tk):
    from gui.main_page import build_main_page
    build_main_page(root)

def _open_settings(root: tk.Tk):
    from gui.settings_window import open_export_settings
    open_export_settings(root)

def build_splash(root: tk.Tk):
    for w in root.winfo_children():
        w.destroy()

    root.title("Madden Helper — Home")
    root.geometry("500x360")

    container = tk.Frame(root)
    container.pack(fill="both", expand=True, padx=20, pady=20)

    title = tk.Label(container, text="Madden Helper", font=("Segoe UI", 22, "bold"))
    subtitle = tk.Label(container, text="Franchise Reports & Tiebreakers", font=("Segoe UI", 11))
    title.pack(pady=(30, 6))
    subtitle.pack(pady=(0, 26))

    go_btn = tk.Button(container, text="Open Main Page ▶", width=24, height=2,
                       command=lambda: _open_main(root))
    go_btn.pack(pady=6)

    settings_btn = tk.Button(container, text="Export Folder…", width=24,
                         command=lambda: _open_settings(root))
    settings_btn.pack(pady=6)

    quit_btn = tk.Button(container, text="Quit", command=root.destroy)
    quit_btn.pack(pady=6)

def main():
    root = tk.Tk()
    build_splash(root)
    root.mainloop()

if __name__ == "__main__":
    main()
