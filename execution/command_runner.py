"""Smart BethG controlled command runner.

LV: This is deliberately not an unrestricted shell. It requires an
ExecutionPermit created by the authorization layer and uses shell=False.
Only individually reviewed programs are allowed.

PV: Add programs one at a time after reviewing their argument and resource
controls. Never turn this into subprocess(..., shell=True).
"""
import subprocess
from execution.execution_engine import ExecutionPermit

class CommandRunner:
    ALLOWED_PROGRAMS = {"python", "git"}

    def run(self, permit: ExecutionPermit, program: str, args: list[str],
            cwd: str, timeout: int = 30):
        if permit.action != "terminal.execute":
            raise PermissionError("Invalid execution permit.")
        if program not in self.ALLOWED_PROGRAMS:
            raise PermissionError("Program is not allowed.")
        if not isinstance(args, list) or not all(isinstance(x, str) for x in args):
            raise TypeError("Arguments must be a list of strings.")

        completed = subprocess.run(
            [program, *args],
            cwd=cwd,
            shell=False,
            capture_output=True,
            text=True,
            timeout=timeout,
            check=False,
        )
        return {
            "return_code": completed.returncode,
            "stdout": completed.stdout,
            "stderr": completed.stderr,
        }
