"""
Smart BethG git tool.

status()/diff()/branches() are git.read (LOW risk, no approval needed
for a user who holds the permission). commit()/checkout() are git.write
(HIGH risk, always requires approval regardless of role) - both are
narrow, specific operations, not an arbitrary git command passthrough,
so what's being approved is always concrete and reviewable ("commit
everything with this message" / "switch to this exact branch").

Every method returns the full result (return code, stdout, stderr) so a
caller can actually verify success rather than assuming it (see this
file's own history: status() used to return only stdout, which made a
failure indistinguishable from an empty successful result).
"""
import subprocess


def _run(args, cwd, timeout=30):
    completed = subprocess.run(args, cwd=cwd, capture_output=True, text=True, timeout=timeout, check=False)
    return {"return_code": completed.returncode, "stdout": completed.stdout, "stderr": completed.stderr}


class GitTool:
    def status(self, permit, cwd):
        if permit.action != "git.read":
            raise PermissionError("Invalid permit.")
        return _run(["git", "status", "--short"], cwd)

    def diff(self, permit, cwd, staged=False):
        if permit.action != "git.read":
            raise PermissionError("Invalid permit.")
        args = ["git", "diff", "--staged"] if staged else ["git", "diff"]
        return _run(args, cwd)

    def branches(self, permit, cwd):
        if permit.action != "git.read":
            raise PermissionError("Invalid permit.")
        return _run(["git", "branch", "-a"], cwd)

    def commit(self, permit, cwd, message):
        if permit.action != "git.write":
            raise PermissionError("Invalid permit.")
        if not message or not message.strip():
            raise ValueError("A commit message is required.")

        add = _run(["git", "add", "-A"], cwd)
        if add["return_code"] != 0:
            return add
        return _run(["git", "commit", "-m", message], cwd)

    def checkout(self, permit, cwd, branch, create=False):
        if permit.action != "git.write":
            raise PermissionError("Invalid permit.")
        if not branch or not branch.strip():
            raise ValueError("A branch name is required.")
        args = ["git", "checkout", "-b", branch] if create else ["git", "checkout", branch]
        return _run(args, cwd)
