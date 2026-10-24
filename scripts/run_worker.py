"""Run the durable worker separately from the web API: python scripts/run_worker.py."""
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from services.job_queue import JobWorker
from services.mission_executor import MissionExecutor


def main():
    worker = JobWorker(handlers={"mission.execute": MissionExecutor().execute})
    while True:
        try:
            worked = worker.run_once()
        except Exception:
            from logging_setup import get_logger
            get_logger("worker").exception("Worker poll failed")
            worked = False
        if not worked:
            time.sleep(1)


if __name__ == "__main__":
    main()
