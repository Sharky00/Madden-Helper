import os
import sys
import tkinter as tk
from tkinter import messagebox

# Ensure top-level directory (one up from /GUI) is on sys.path BEFORE imports
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), os.pardir))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

import process.generate_names as generate_names  # top-level generate_names.py

def on_run():
    try:
        generate_names.run()
        messagebox.showinfo("Success", "Processing complete!")
    except Exception as e:
        messagebox.showerror("Error", f"An error occurred:\n{e}")

def main():
    root = tk.Tk()
    root.title("Madden Helper")
    root.geometry("400x300")

    # Bottom-right Run button
    run_button = tk.Button(root, text="Run", command=on_run)
    run_button.pack(side="bottom", anchor="se", padx=20, pady=20)

    root.mainloop()

if __name__ == "__main__":
    main()
