import tkinter as tk
from tkinter import messagebox

# Import the process runner
from process.process import run as process_run

def on_run():
    try:
        process_run()  # calls generate_names.run() under the hood
        messagebox.showinfo("Success", "Processing complete!")
    except Exception as e:
        messagebox.showerror("Error", f"An error occurred:\n{e}")

def main():
    root = tk.Tk()
    root.title("Madden Helper")
    root.geometry("400x300")

    run_button = tk.Button(root, text="Run", command=on_run)
    run_button.pack(side="bottom", anchor="se", padx=20, pady=20)

    root.mainloop()
