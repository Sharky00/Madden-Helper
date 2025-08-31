# main.py (top-level)
import os, sys
# ensure project root is importable
sys.path.insert(0, os.path.dirname(__file__))

from gui.launcher import main as launcher_main

if __name__ == "__main__":
    launcher_main()
