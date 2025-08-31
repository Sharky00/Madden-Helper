# Orchestrates your processing pipeline
from process.modules.generate_names import run as generate_names_run

def run():
    # Add any pre/post steps here later (logging, timing, args, etc.)
    generate_names_run()
    print("Hi i am process")