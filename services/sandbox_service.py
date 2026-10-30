"""Restricted Docker sandbox. Arbitrary host shell execution is never exposed."""
import json
import os
import shutil
import subprocess
import tempfile
import threading
import time
import uuid
from pathlib import Path

import config
from database import get_connection
from services.runtime_registry import (
    RuntimeUnavailableError,
    is_digest_pinned_image,
    resolve_runtime,
)
from services.workspace_service import WorkspaceService


class SandboxUnavailableError(RuntimeError):
    pass


class SandboxService:
    MAX_OUTPUT_BYTES = 16_000

    def execute_python(self, user_id, source, workspace_id=None):
        return self.execute_runtime(user_id, "python", source, workspace_id)

    def execute_runtime(self, user_id, runtime_id, source, workspace_id=None):
        if not isinstance(source, str) or not source.strip():
            raise ValueError("Source code is required.")
        run_id = str(uuid.uuid4())
        if workspace_id is not None:
            WorkspaceService().require_workspace_access(user_id, workspace_id, "edit")
        try:
            runtime, image = resolve_runtime(runtime_id)
        except RuntimeUnavailableError as exc:
            self._record(run_id, user_id, workspace_id, "rejected", None,
                         runtime_id, None, {}, "sandbox_unavailable")
            raise SandboxUnavailableError(str(exc)) from exc
        if len(source.encode("utf-8")) > runtime.max_source_bytes:
            raise ValueError(
                f"Source code exceeds the {runtime.max_source_bytes // 1000} KB limit."
            )
        docker = shutil.which("docker")
        if not docker:
            self._record(run_id, user_id, workspace_id, "rejected", image,
                         runtime_id, None, {}, "sandbox_unavailable")
            raise SandboxUnavailableError("The isolated execution service is unavailable.")
        if config.IS_PRODUCTION and not self._docker_is_rootless(docker):
            self._record(run_id, user_id, workspace_id, "rejected", image,
                         runtime_id, None, {}, "sandbox_host_not_rootless")
            raise SandboxUnavailableError(
                "Production code execution requires a rootless Docker runtime."
            )

        self._record(run_id, user_id, workspace_id, "running", image, runtime_id, None, {}, None)
        started = time.monotonic()
        container_name = "sbx-" + run_id.replace("-", "")[:24]
        try:
            with tempfile.TemporaryDirectory(prefix="smartbethg-sandbox-") as directory:
                root = Path(directory)
                # The parent temporary directory is private to the host process.
                # Docker's fixed non-root UID needs traverse/read access only to
                # this one read-only input directory and file.
                root.chmod(0o755)
                script = root / runtime.source_filename
                script.write_text(source, encoding="utf-8")
                script.chmod(0o444)
                command = self._docker_run_command(
                    docker, container_name, root, image, runtime
                )
                process = subprocess.Popen(
                    command, shell=False, stdin=subprocess.DEVNULL,
                    stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                    env={"PATH": os.path.dirname(docker), "LANG": "C.UTF-8"},
                )
                output = {"stdout": bytearray(), "stderr": bytearray(), "total": 0}
                output_lock = threading.Lock()
                output_limit_reached = threading.Event()

                def drain(stream, key):
                    while True:
                        chunk = stream.read(4096)
                        if not chunk:
                            break
                        with output_lock:
                            remaining = self.MAX_OUTPUT_BYTES - output["total"]
                            if remaining > 0:
                                accepted = chunk[:remaining]
                                output[key].extend(accepted)
                                output["total"] += len(accepted)
                            if len(chunk) > max(0, remaining):
                                output_limit_reached.set()

                readers = [
                    threading.Thread(target=drain, args=(process.stdout, "stdout"), daemon=True),
                    threading.Thread(target=drain, args=(process.stderr, "stderr"), daemon=True),
                ]
                for reader in readers:
                    reader.start()

                deadline = started + runtime.timeout_seconds
                timed_out = False
                while process.poll() is None:
                    if output_limit_reached.is_set():
                        break
                    remaining_time = deadline - time.monotonic()
                    if remaining_time <= 0:
                        timed_out = True
                        break
                    try:
                        process.wait(timeout=min(0.05, remaining_time))
                    except subprocess.TimeoutExpired:
                        continue

                if timed_out or output_limit_reached.is_set():
                    self._cleanup_container(docker, container_name)
                    try:
                        process.wait(timeout=2)
                    except subprocess.TimeoutExpired:
                        process.kill()
                        process.wait(timeout=2)
                else:
                    process.wait(timeout=2)

                for reader in readers:
                    reader.join(timeout=2)

                # --rm is a second cleanup layer; verify the daemon no longer
                # knows this named container, and force-remove if it remains.
                cleanup_verified = self._ensure_container_absent(docker, container_name)
                if not cleanup_verified:
                    raise SandboxUnavailableError(
                        "Execution ended but the isolated container could not be confirmed removed."
                    )

            elapsed_ms = int((time.monotonic() - started) * 1000)
            stdout = output["stdout"].decode("utf-8", "replace")
            stderr = output["stderr"].decode("utf-8", "replace")
            if timed_out:
                payload = {
                    "stdout": stdout,
                    "stderr": f"Execution exceeded the {runtime.timeout_seconds} second time limit.",
                    "duration_ms": elapsed_ms,
                    "output_truncated": True,
                }
                self._record(run_id, user_id, workspace_id, "timed_out", image, runtime_id,
                             None, payload, "timeout")
                return {"id": run_id, "status": "timed_out", "exit_code": None, **payload}
            if output_limit_reached.is_set():
                payload = {
                    "stdout": stdout,
                    "stderr": "Execution exceeded the 16 KB combined output limit.",
                    "duration_ms": elapsed_ms,
                    "output_truncated": True,
                }
                self._record(run_id, user_id, workspace_id, "failed", image, runtime_id,
                             None, payload, "output_limit")
                return {"id": run_id, "status": "failed", "exit_code": None, **payload}

            return_code = process.returncode
            payload = {
                "stdout": stdout,
                "stderr": stderr,
                "duration_ms": elapsed_ms,
                "output_truncated": False,
            }
            status = "succeeded" if return_code == 0 else "failed"
            self._record(run_id, user_id, workspace_id, status, image, runtime_id,
                         return_code, payload, None if return_code == 0 else "nonzero_exit")
            return {"id": run_id, "status": status, "exit_code": return_code, **payload}
        except Exception:
            self._cleanup_container(docker, container_name)
            self._record(run_id, user_id, workspace_id, "failed", image, runtime_id,
                         None, {}, "sandbox_runtime_error")
            raise

    @staticmethod
    def _docker_run_command(docker, container_name, root, image, runtime):
        """Build the fixed, deny-by-default Docker invocation."""
        return [
            docker, "run", "--rm", "--pull=never", "--name", container_name,
            "--network=none", "--ipc=private", "--read-only",
            "--cap-drop=ALL", "--security-opt=no-new-privileges:true",
            "--pids-limit", str(runtime.pids_limit),
            "--memory", runtime.memory_limit,
            # Equal memory and memory-swap limits prevent additional swap use.
            "--memory-swap", runtime.memory_limit,
            "--cpus", runtime.cpu_limit,
            "--shm-size=16m",
            "--ulimit", "nofile=64:64",
            "--ulimit", "fsize=1048576:1048576",
            "--ulimit", "core=0:0",
            "--log-driver=none", "--stop-timeout=1",
            "--user=65534:65534",
            "--tmpfs", f"/tmp:rw,noexec,nosuid,nodev,size={runtime.tmpfs_size},mode=1777",
            "--workdir=/workspace",
            "--mount", f"type=bind,src={root},dst=/workspace,readonly",
            image, runtime.executable, *runtime.arguments,
            f"/workspace/{runtime.source_filename}",
        ]

    @staticmethod
    def _docker_is_rootless(docker):
        """Production execution is blocked unless Docker reports rootless mode."""
        try:
            result = subprocess.run(
                [docker, "info", "--format", "{{json .SecurityOptions}}"],
                shell=False, stdin=subprocess.DEVNULL,
                stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
                text=True, timeout=5, check=False,
                env={"PATH": os.path.dirname(docker), "LANG": "C.UTF-8"},
            )
            if result.returncode != 0:
                return False
            options = json.loads(result.stdout or "[]")
            return any("rootless" in str(option).lower() for option in options)
        except (OSError, subprocess.TimeoutExpired, ValueError, TypeError):
            return False

    @classmethod
    def _ensure_container_absent(cls, docker, container_name):
        try:
            inspect = subprocess.run(
                [docker, "inspect", container_name],
                shell=False, stdin=subprocess.DEVNULL,
                stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                text=True, timeout=3, check=False,
            )
            if inspect.returncode != 0:
                message = (inspect.stderr or "").lower()
                return "no such object" in message or "not found" in message
            return cls._cleanup_container(docker, container_name)
        except (OSError, subprocess.TimeoutExpired):
            return False

    @staticmethod
    def _is_digest_pinned_image(image):
        return is_digest_pinned_image(image)

    @staticmethod
    def _cleanup_container(docker, container_name):
        # Try kill and force-remove independently. A failed kill must never
        # prevent the removal attempt. Only a clear "not found" response proves
        # absence; a daemon/connection error is not treated as successful cleanup.
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
        try:
            inspect = subprocess.run(
                [docker, "inspect", container_name],
                shell=False, stdin=subprocess.DEVNULL,
                stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                text=True, timeout=3, check=False,
            )
            if inspect.returncode == 0:
                return False
            message = (inspect.stderr or "").lower()
            return "no such object" in message or "not found" in message
        except (subprocess.TimeoutExpired, OSError):
            return False

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
