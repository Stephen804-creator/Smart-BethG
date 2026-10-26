"""Opt-in Python execution in a constrained, no-network Docker container.

Never falls back to executing submitted source code on the application host.
"""
import hashlib
import shutil
import subprocess
import time

import config
from database import get_connection


class SandboxExecutionService:
    MAX_SOURCE_CHARS = 20000
    MAX_OUTPUT_CHARS = 12000
    MAX_TIMEOUT_SECONDS = 10
    MEMORY_LIMIT = "128m"
    CPU_LIMIT = "0.5"
    PYTHON_IMAGE = getattr(config, "SANDBOX_PYTHON_IMAGE", "")

    def execute_python(self, user_id, source, timeout_seconds=5):
        if not isinstance(source, str) or not source.strip():
            raise ValueError("Python source code is required.")
        if len(source) > self.MAX_SOURCE_CHARS:
            raise ValueError(f"Source exceeds the {self.MAX_SOURCE_CHARS}-character limit.")
        try:
            timeout_seconds = max(1, min(int(timeout_seconds), self.MAX_TIMEOUT_SECONDS))
        except (TypeError, ValueError):
            timeout_seconds = 5

        digest = hashlib.sha256(source.encode("utf-8")).hexdigest()
        started = time.monotonic()
        result = {"status": "unavailable", "exit_code": None, "stdout": "",
                  "stderr": "Sandbox is not configured. Host execution fallback is disabled."}
        image = self.PYTHON_IMAGE
        enabled = getattr(config, "SANDBOX_ENABLED", False)
        if enabled and image and image in config.DOCKER_ALLOWED_IMAGES and shutil.which("docker"):
            command = [
                "docker", "run", "--rm", "-i", "--pull=never",
                "--network=none", "--read-only",
                "--tmpfs", "/tmp:rw,noexec,nosuid,size=16m",
                "--memory", self.MEMORY_LIMIT, "--cpus", self.CPU_LIMIT,
                "--pids-limit", "64", "--cap-drop", "ALL",
                "--security-opt", "no-new-privileges",
                "--user", "65534:65534",
                image, "python", "-I", "-c",
                "import sys; exec(compile(sys.stdin.read(), '<user-code>', 'exec'))",
            ]
            try:
                completed = subprocess.run(
                    command, input=source, capture_output=True, text=True,
                    timeout=timeout_seconds + 2, check=False, shell=False,
                    env={"PATH": "/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin",
                         "LANG": "C.UTF-8", "PYTHONNOUSERSITE": "1"},
                )
                result = {
                    "status": "succeeded" if completed.returncode == 0 else "failed",
                    "exit_code": completed.returncode,
                    "stdout": completed.stdout[:self.MAX_OUTPUT_CHARS],
                    "stderr": completed.stderr[:self.MAX_OUTPUT_CHARS],
                }
            except subprocess.TimeoutExpired:
                result = {"status": "timed_out", "exit_code": None, "stdout": "",
                          "stderr": f"Execution exceeded the {timeout_seconds}-second time limit."}
            except OSError:
                result = {"status": "unavailable", "exit_code": None, "stdout": "",
                          "stderr": "The isolated Docker runtime could not be started."}

        duration_ms = max(0, int((time.monotonic() - started) * 1000))
        conn = get_connection()
        try:
            row = conn.execute(
                "INSERT INTO sandbox_executions(user_id,language,source_sha256,status,exit_code,stdout,stderr,duration_ms) "
                "VALUES (?,'python',?,?,?,?,?,?) RETURNING id,created_at",
                (user_id, digest, result["status"], result["exit_code"],
                 result["stdout"], result["stderr"], duration_ms),
            ).fetchone()
            conn.commit()
            result.update({"execution_id": row["id"], "created_at": row["created_at"],
                           "duration_ms": duration_ms, "source_sha256": digest})
            return result
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    def list_for_user(self, user_id, limit=20):
        conn = get_connection()
        try:
            rows = conn.execute(
                "SELECT id,language,source_sha256,status,exit_code,stdout,stderr,duration_ms,created_at "
                "FROM sandbox_executions WHERE user_id=? ORDER BY created_at DESC,id DESC LIMIT ?",
                (user_id, max(1, min(50, int(limit)))),
            ).fetchall()
            return [dict(row) for row in rows]
        finally:
            conn.close()
