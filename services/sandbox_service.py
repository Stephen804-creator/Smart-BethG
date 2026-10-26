"""Restricted Docker sandbox. Arbitrary host shell execution is never exposed."""
import json
import os
import shutil
import subprocess
import tempfile
import time
import uuid
from pathlib import Path

import config
from database import get_connection
from services.workspace_service import WorkspaceService


class SandboxUnavailableError(RuntimeError):
    pass


class SandboxService:
    MAX_SOURCE_BYTES = 64_000
    MAX_OUTPUT_BYTES = 16_000
    TIMEOUT_SECONDS = 15
    MEMORY_LIMIT = "256m"
    CPU_LIMIT = "0.50"

    def execute_python(self, user_id, source, workspace_id=None):
        if not isinstance(source, str) or not source.strip():
            raise ValueError("Python source is required.")
        if len(source.encode("utf-8")) > self.MAX_SOURCE_BYTES:
            raise ValueError("Python source exceeds the 64 KB limit.")
        run_id = str(uuid.uuid4())
        if workspace_id is not None:
            WorkspaceService().require_workspace_access(user_id, workspace_id, "edit")
        image = os.getenv("SMART_BETHG_SANDBOX_PYTHON_IMAGE", "").strip()
        enabled = os.getenv("SMART_BETHG_SANDBOX_ENABLED", "false").strip().lower() == "true"
        docker = shutil.which("docker")
        if not enabled or not image or "@sha256:" not in image or image not in config.DOCKER_ALLOWED_IMAGES or not docker:
            self._record(run_id, user_id, workspace_id, "rejected", image or None,
                         "python_script", None, {}, "sandbox_unavailable")
            raise SandboxUnavailableError(
                "Sandbox execution is disabled or not safely configured. Configure Docker and a trusted digest-pinned image."
            )
        self._record(run_id, user_id, workspace_id, "running", image, "python_script", None, {}, None)
        started = time.monotonic()
        try:
            with tempfile.TemporaryDirectory(prefix="smartbethg-sandbox-") as directory:
                root = Path(directory)
                root.chmod(0o755)
                script = root / "main.py"
                script.write_text(source, encoding="utf-8")
                script.chmod(0o444)
                # Every security-sensitive option is fixed here. No caller-provided
                # image, arguments, mounts, environment, network, or shell is accepted.
                command = [
                    docker, "run", "--rm",
                    "--network=none", "--read-only",
                    "--cap-drop=ALL", "--security-opt=no-new-privileges",
                    "--pids-limit=64", "--memory", self.MEMORY_LIMIT,
                    "--cpus", self.CPU_LIMIT, "--user=65534:65534",
                    "--tmpfs", "/tmp:rw,noexec,nosuid,size=16m",
                    "--mount", f"type=bind,src={root},dst=/workspace,readonly",
                    image, "python", "-I", "-B", "/workspace/main.py",
                ]
                result = subprocess.run(
                    command, shell=False, stdin=subprocess.DEVNULL,
                    stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                    text=True, encoding="utf-8", errors="replace",
                    timeout=self.TIMEOUT_SECONDS,
                    env={"PATH": os.path.dirname(docker), "LANG": "C.UTF-8"},
                    check=False,
                )
            elapsed_ms = int((time.monotonic() - started) * 1000)
            stdout = (result.stdout or "")[:self.MAX_OUTPUT_BYTES]
            stderr = (result.stderr or "")[:self.MAX_OUTPUT_BYTES]
            status = "succeeded" if result.returncode == 0 else "failed"
            payload = {"stdout": stdout, "stderr": stderr, "duration_ms": elapsed_ms,
                       "output_truncated": len(result.stdout or "") > self.MAX_OUTPUT_BYTES or
                                           len(result.stderr or "") > self.MAX_OUTPUT_BYTES}
            self._record(run_id, user_id, workspace_id, status, image, "python_script",
                         result.returncode, payload, None if result.returncode == 0 else "nonzero_exit")
            return {"id": run_id, "status": status, "exit_code": result.returncode, **payload}
        except subprocess.TimeoutExpired:
            self._record(run_id, user_id, workspace_id, "timed_out", image, "python_script",
                         None, {"duration_ms": int((time.monotonic() - started) * 1000)}, "timeout")
            return {"id": run_id, "status": "timed_out", "exit_code": None,
                    "stdout": "", "stderr": "Execution exceeded the 15 second time limit."}
        except Exception:
            self._record(run_id, user_id, workspace_id, "failed", image, "python_script",
                         None, {}, "sandbox_runtime_error")
            raise

    @staticmethod
    def _record(run_id, user_id, workspace_id, status, image, command_name, exit_code, result, error_code):
        conn = get_connection()
        try:
            conn.execute(
                "INSERT INTO sandbox_execution_records(id,user_id,workspace_id,status,image,command_name,exit_code,result_json,error_code,started_at,completed_at) "
                "VALUES (?,?,?,?,?,?,?,?,?,CASE WHEN ?='running' THEN CURRENT_TIMESTAMP ELSE NULL END,"
                "CASE WHEN ? IN ('rejected','succeeded','failed','timed_out') THEN CURRENT_TIMESTAMP ELSE NULL END) "
                "ON CONFLICT(id) DO UPDATE SET status=EXCLUDED.status,exit_code=EXCLUDED.exit_code,"
                "result_json=EXCLUDED.result_json,error_code=EXCLUDED.error_code,completed_at=EXCLUDED.completed_at",
                (run_id, user_id, workspace_id, status, image, command_name, exit_code,
                 json.dumps(result, ensure_ascii=False), error_code, status, status),
            )
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    def list_for_user(self, user_id, limit=50):
        conn = get_connection()
        try:
            rows = conn.execute(
                "SELECT id,workspace_id,status,image,command_name,exit_code,result_json,error_code,started_at,completed_at,created_at "
                "FROM sandbox_execution_records WHERE user_id=? ORDER BY created_at DESC LIMIT ?",
                (user_id, max(1, min(100, int(limit)))),
            ).fetchall()
            result = []
            for row in rows:
                item = dict(row)
                item["result"] = json.loads(item.pop("result_json") or "{}")
                result.append(item)
            return result
        finally:
            conn.close()
