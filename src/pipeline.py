import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from dotenv import load_dotenv

load_dotenv()

import collect
import agent


def run() -> None:
    print("=== Stage 1: collect ===")
    collect.run()

    print("=== Stage 2: analyse ===")
    agent.run()

    print("=== Pipeline complete ===")


if __name__ == "__main__":
    run()
