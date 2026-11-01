"""Run the durable worker separately from the web API: python scripts/run_worker.py."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from workers.runner import run_worker_loop


def main():
    run_worker_loop()


if __name__ == "__main__":
    main()
