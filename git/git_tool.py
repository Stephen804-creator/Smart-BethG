"""
Constrained Git operations.

All commands run without hooks, external diff drivers, system/global config,
or interactive prompts. Repositories defining executable clean/smudge/process
filters are rejected because Git filters can execute arbitrary host commands.
"""
import os
import subprocess
import tempfile


def _run(args, cwd, timeout=30):
    env = os.environ.copy()
    env["GIT_CONFIG_NOSYSTEM"] = "1"
    env["GIT_CONFIG_GLOBAL"] = os.devnull
    env["GIT_TERMINAL_PROMPT"] = "0"
    env["GIT_PAGER"] = "cat"
    for key in list(env):
        if key in {
            "GIT_CONFIG_COUNT", "GIT_CONFIG_PARAMETERS", "GIT_DIR", "GIT_WORK_TREE",
            "GIT_INDEX_FILE", "GIT_OBJECT_DIRECTORY", "GIT_ALTERNATE_OBJECT_DIRECTORIES",
            "GIT_COMMON_DIR",
        } or key.startswith("GIT_CONFIG_KEY_") or key.startswith("GIT_CONFIG_VALUE_"):
            env.pop(key, None)

    # Git filters can execute commands during add/checkout/status. Refuse any
    # repository that configures them instead of attempting to sandbox them.
    try:
        filters = subprocess.run(
            [
                "git", "-c", "core.fsmonitor=false", "config", "--local",
                "--get-regexp", r"^filter\..*\.(clean|smudge|process)$",
            ],
            cwd=cwd, capture_output=True, text=True, timeout=5, check=False, env=env,
        )
        if filters.returncode == 0 and filters.stdout.strip():
            return {
                "return_code": 126,
                "stdout": "",
                "stderr": "Git operation refused: this repository configures custom filters that can execute host commands.",
            }
    except (OSError, subprocess.TimeoutExpired) as exc:
        return {"return_code": 126, "stdout": "", "stderr": f"Git safety preflight failed ({type(exc).__name__})."}

    # A fresh, empty hook directory is outside the user workspace and is
    # applied as a command-line override, so local core.hooksPath cannot win.
    with tempfile.TemporaryDirectory(prefix="smartbethg-empty-git-hooks-") as hooks_dir:
        command = [
            "git", "--no-pager",
            "-c", f"core.hooksPath={hooks_dir}",
            "-c", "core.fsmonitor=false",
            "-c", "commit.gpgSign=false",
            "-c", "diff.external=",
            *args,
        ]
        try:
            completed = subprocess.run(
                command, cwd=cwd, capture_output=True, text=True,
                timeout=timeout, check=False, env=env,
            )
            return {
                "return_code": completed.returncode,
                "stdout": completed.stdout,
                "stderr": completed.stderr,
            }
        except subprocess.TimeoutExpired:
            return {"return_code": 124, "stdout": "", "stderr": "Git operation timed out."}
        except OSError as exc:
            return {"return_code": 127, "stdout": "", "stderr": f"Git executable unavailable ({type(exc).__name__})."}


class GitTool:
    def status(self, permit, cwd):
        if permit.action != "git.read":
            raise PermissionError("Invalid permit.")
        return _run(["status", "--short"], cwd)

    def diff(self, permit, cwd, staged=False):
        if permit.action != "git.read":
            raise PermissionError("Invalid permit.")
        args = ["diff", "--no-ext-diff", "--staged"] if staged else ["diff", "--no-ext-diff"]
        return _run(args, cwd)

    def branches(self, permit, cwd):
        if permit.action != "git.read":
            raise PermissionError("Invalid permit.")
        return _run(["branch", "-a"], cwd)

    def commit(self, permit, cwd, message):
        if permit.action != "git.write":
            raise PermissionError("Invalid permit.")
        if not message or not message.strip():
            raise ValueError("A commit message is required.")

        add = _run(["add", "-A"], cwd)
        if add["return_code"] != 0:
            return add
        return _run(["commit", "-m", message], cwd)

    def checkout(self, permit, cwd, branch, create=False):
        if permit.action != "git.write":
            raise PermissionError("Invalid permit.")
        if not branch or not branch.strip() or branch.startswith("-") or "\\x00" in branch:
            raise ValueError("A valid branch name is required.")
        checked = _run(["check-ref-format", "--branch", branch], cwd)
        if checked["return_code"] != 0:
            raise ValueError("Invalid Git branch name.")
        args = ["checkout", "-b", branch] if create else ["checkout", branch]
        return _run(args, cwd)
