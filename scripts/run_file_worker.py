"""Run the isolated file-processing worker: python scripts/run_file_worker.py.

Deploy this as a separate, restricted service. Do not combine it with the
public API or the agent/provider worker. It claims only file-processing jobs.
"""
import os

# The file worker does not sign sessions and must not need the web secret.
os.environ["SMART_BETHG_PROCESS_ROLE"] = "file-worker"

import signal
import sys
import threading
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from logging_setup import get_logger, setup_logging
from services.file_extraction_service import FileExtractionService
from services.file_inspection_service import FileInspectionService
from services.job_queue import JobWorker


def main():
    setup_logging()
    logger = get_logger("file_worker")
    stopping = threading.Event()

    def request_shutdown(_signal, _frame):
        logger.info("File worker shutdown requested")
        stopping.set()

    signal.signal(signal.SIGTERM, request_shutdown)
    signal.signal(signal.SIGINT, request_shutdown)

    inspection = FileInspectionService()
    extraction = FileExtractionService()
    worker = JobWorker(handlers={
        "file.inspect": inspection.inspect_job,
        "file.extract_pdf": extraction.extract_pdf_job,
    })

    logger.info("File inspection worker started; registered job types=file.inspect,file.extract_pdf")
    while not stopping.is_set():
        try:
            worked = worker.run_once()
        except Exception:
            logger.exception("File worker poll failed")
            worked = False
        if not worked:
            stopping.wait(1)

    logger.info("File inspection worker stopped")


if __name__ == "__main__":
    main()
