"""Restricted Docker sandbox. Arbitrary host shell execution is never exposed."""
import json
import os
import re
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
        if (not enabled or not self._is_digest_pinned_image(image)
                or image not in config.DOCKER_ALLOWED_IMAGES or not docker):
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
                container_name = "sbx-" + run_id.replace("-", "")[:24]
                command = [
                    docker, "run", "--rm", "--name", container_name,
                    "--network=none", "--read-only",
                    "--cap-drop=ALL", "--security-opt=no-new-privileges",
                    "--pids-limit=64", "--memory", self.MEMORY_LIMIT,
                    "--cpus", self.CPU_LIMIT, "--user=65534:65534",
                    "--tmpfs", "/tmp:rw,noexec,nosuid,size=16m",
                    "--mount", f"type=bind,src={root},dst=/workspace,readonly",
                    image, "python", "-I", "-B", "/workspace/main.py",
                ]
                process = subprocess.Popen(
                    command, shell=False, stdin=subprocess.DEVNULL,
                    stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                    env={"PATH": os.path.dirname(docker), "LANG": "C.UTF-8"},
                )
                output = {"stdout": bytearray(), "stderr": bytearray(),
                          "stdout_total": 0, "stderr_total": 0}
                def drain(stream, key):
                    total_key = key + "_total"
                    while True:
                        chunk = stream.read(4096)
                        if not chunk:
                            break
                        output[total_key] += len(chunk)
                        remaining = self.MAX_OUTPUT_BYTES - len(output[key])
                        if remaining > 0:
                            output[key].extend(chunk[:remaining])
                import threading
                readers = [
                    threading.Thread(target=drain, args=(process.stdout, "stdout"), daemon=True),
                    threading.Thread(target=drain, args=(process.stderr, "stderr"), daemon=True),
                ]
                for reader in readers:
                    reader.start()
                try:
                    return_code = process.wait(timeout=self.TIMEOUT_SECONDS)
                except subprocess.TimeoutExpired:
                    # Killing the Docker CLI alone can leave the daemon container alive.
                    self._cleanup_container(docker, container_name)
                    try:
                        process.wait(timeout=3)
                    except subprocess.TimeoutExpired:
                        process.kill()
                        process.wait(timeout=2)
                    for reader in readers:
                        reader.join(timeout=2)
                    self._record(run_id, user_id, workspace_id, "timed_out", image, "python_script",
                                 None, {"duration_ms": int((time.monotonic() - started) * 1000),
                                        "output_truncated": True}, "timeout")
                    return {"id": run_id, "status": "timed_out", "exit_code": None,
                            "stdout": output["stdout"].decode("utf-8", "replace"),
                            "stderr": "Execution exceeded the 15 second time limit."}
                for reader in readers:
                    reader.join(timeout=2)
            elapsed_ms = int((time.monotonic() - started) * 1000)
            stdout = output["stdout"].decode("utf-8", "replace")
            stderr = output["stderr"].decode("utf-8", "replace")
            truncated = (output["stdout_total"] > self.MAX_OUTPUT_BYTES or
                         output["stderr_total"] > self.MAX_OUTPUT_BYTES)
            status = "succeeded" if return_code == 0 else "failed"
            payload = {"stdout": stdout, "stderr": stderr, "duration_ms": elapsed_ms,
                       "output_truncated": truncated}
            self._record(run_id, user_id, workspace_id, status, image, "python_script",
                         return_code, payload, None if return_code == 0 else "nonzero_exit")
            return {"id": run_id, "status": status, "exit_code": return_code, **payload}
        except Exception:
            if "container_name" in locals() and "docker" in locals() and container_name:
                self._cleanup_container(docker, container_name)
            self._record(run_id, user_id, workspace_id, "failed", image, "python_script",
                         None, {}, "sandbox_runtime_error")
            raise

    @staticmethod
    def _is_digest_pinned_image(image):
        return bool(re.fullmatch(r"[^@\s]+@sha256:[0-9a-f]{64}", image or ""))

    @staticmethod
    def _cleanup_container(docker, container_name):
        # Try both kill and forced removal. A timed-out Docker CLI can leave the
        # daemon-side container alive, so cleanup must not stop after one failure.
        for action in ("kill", "rm"):
            command = [docker, action]
            if action == "rm":
                command.append("--force")
            command.append(container_name)
            try:
                subprocess.run(command, shell=False, stdin=subprocess.DEVNULL,
                               stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                               timeout=3, check=False)
            except (subprocess.TimeoutExpired, OSError):
                continue

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
