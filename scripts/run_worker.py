"""Run the durable worker separately from the web API: python scripts/run_worker.py."""
import os
import socket
import sys
import threading
import time
import uuid
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from services.job_queue import JobWorker
from services.mission_executor import MissionExecutor
from services.workflow_executor import WorkflowExecutor
from services.specialist_coordinator import SpecialistCoordinator
from services.operations_service import OperationsService
from services.sandbox_service import SandboxService


def main():
    logger = None
    from logging_setup import get_logger
    logger = get_logger("worker")
    operations = OperationsService()
    worker_id = os.getenv(
        "SMART_BETHG_WORKER_ID",
        f"{socket.gethostname()}:{os.getpid()}:{uuid.uuid4().hex[:8]}",
    )[:200]
    stop_heartbeat = threading.Event()

    def heartbeat_loop():
        last_prune = time.monotonic()
        while not stop_heartbeat.wait(15):
            try:
                operations.heartbeat_worker(worker_id, "healthy", {"process_id": os.getpid()})
                if time.monotonic() - last_prune >= 3600:
                    operations.prune_request_traces()
                    last_prune = time.monotonic()
            except Exception:
                logger.exception("Worker heartbeat or retention maintenance failed")

    try:
        operations.heartbeat_worker(worker_id, "starting", {"process_id": os.getpid()})
        heartbeat_thread = threading.Thread(target=heartbeat_loop, name="worker-heartbeat", daemon=True)
        heartbeat_thread.start()
        worker = JobWorker(handlers={
            "mission.execute": MissionExecutor().execute,
            "workflow.execute": WorkflowExecutor().execute,
            "agent.team.execute": SpecialistCoordinator().execute,
        })
        while True:
            try:
                worked = worker.run_once()
            except Exception:
                logger.exception("Worker poll failed")
                worked = False
            if not worked:
                time.sleep(1)
    except KeyboardInterrupt:
        logger.info("Worker shutdown requested")
    finally:
        stop_heartbeat.set()
        try:
            operations.heartbeat_worker(worker_id, "stopping", {"process_id": os.getpid()})
        except Exception:
            logger.exception("Could not persist worker shutdown state")


if __name__ == "__main__":
    main()
