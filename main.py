from gui.main_page import main as gui_main
import os
from dotenv import load_dotenv
load_dotenv()  # loads .env from project root

if not os.getenv("OPENAI_API_KEY"):
    raise SystemExit("OPENAI_API_KEY is not set (check your .env).")

if __name__ == "__main__":
    gui_main()
