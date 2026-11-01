#!/usr/bin/env python3
"""Build-time smoke test for the exact command configured in runtime_registry."""
import argparse
import os
import subprocess
import tempfile
import uuid
from pathlib import Path

os.environ.setdefault("SMART_BETHG_ENV", "test")
os.environ.setdefault("SMART_BETHG_SECRET_KEY", "runtime-image-ci-only")

from services.runtime_registry import RUNTIME_DEFINITIONS  # noqa: E402
from services.sandbox_service import SandboxService  # noqa: E402


MARKER = "SMARTBETHG_RUNTIME_OK"
SAMPLES = {
    "python": 'print("SMARTBETHG_RUNTIME_OK")\n',
    "javascript": 'console.log("SMARTBETHG_RUNTIME_OK");\n',
    "typescript": 'const message: string = "SMARTBETHG_RUNTIME_OK";\nconsole.log(message);\n',
    "java": 'class Main { public static void main(String[] args) { System.out.println("SMARTBETHG_RUNTIME_OK"); } }\n',
    "c": '#include <stdio.h>\nint main(void) { puts("SMARTBETHG_RUNTIME_OK"); return 0; }\n',
    "cpp": '#include <iostream>\nint main() { std::cout << "SMARTBETHG_RUNTIME_OK\\n"; }\n',
    "go": 'package main\nimport "fmt"\nfunc main() { fmt.Println("SMARTBETHG_RUNTIME_OK") }\n',
    "rust": 'fn main() { println!("SMARTBETHG_RUNTIME_OK"); }\n',
    "csharp": 'Console.WriteLine("SMARTBETHG_RUNTIME_OK");\n',
    "php": '<?php echo "SMARTBETHG_RUNTIME_OK\\n";\n',
    "dart": 'void main() { print("SMARTBETHG_RUNTIME_OK"); }\n',
    "kotlin": 'println("SMARTBETHG_RUNTIME_OK")\n',
    "swift": 'print("SMARTBETHG_RUNTIME_OK")\n',
    "bash": 'printf "%s\\n" "SMARTBETHG_RUNTIME_OK"\n',
    "powershell": 'Write-Output "SMARTBETHG_RUNTIME_OK"\n',
    "ruby": 'puts "SMARTBETHG_RUNTIME_OK"\n',
    "elixir": 'IO.puts("SMARTBETHG_RUNTIME_OK")\n',
    "r": 'cat("SMARTBETHG_RUNTIME_OK\\n")\n',
    "julia": 'println("SMARTBETHG_RUNTIME_OK")\n',
    "lua": 'print("SMARTBETHG_RUNTIME_OK")\n',
    "perl": 'print "SMARTBETHG_RUNTIME_OK\\n";\n',
}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--runtime", required=True, choices=sorted(RUNTIME_DEFINITIONS))
    parser.add_argument("--image", required=True)
    parser.add_argument("--docker", default="docker")
    args = parser.parse_args()

    runtime = RUNTIME_DEFINITIONS[args.runtime]
    run_id = uuid.uuid4().hex[:24]
    container_name = f"sbx-smoke-{run_id}"
    with tempfile.TemporaryDirectory(prefix="smartbethg-runtime-smoke-") as temp:
        root = Path(temp)
        root.chmod(0o755)
        source = root / runtime.source_filename
        source.write_text(SAMPLES[args.runtime], encoding="utf-8")
        source.chmod(0o444)
        command = SandboxService._docker_run_command(
            args.docker, container_name, root, args.image, runtime
        )
        try:
            result = subprocess.run(
                command,
                stdin=subprocess.DEVNULL,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                timeout=runtime.timeout_seconds + 20,
                check=False,
            )
        except subprocess.TimeoutExpired as exc:
            SandboxService._cleanup_container(args.docker, container_name)
            raise SystemExit(f"{args.runtime}: timed out while executing its smoke program") from exc

        if result.returncode != 0:
            SandboxService._cleanup_container(args.docker, container_name)
            raise SystemExit(
                f"{args.runtime}: smoke execution failed (exit {result.returncode})\n"
                f"stdout:\n{result.stdout[-4000:]}\nstderr:\n{result.stderr[-4000:]}"
            )
        if MARKER not in result.stdout:
            raise SystemExit(
                f"{args.runtime}: expected marker not found in stdout\n"
                f"stdout:\n{result.stdout[-4000:]}\nstderr:\n{result.stderr[-4000:]}"
            )
        if not SandboxService._ensure_container_absent(args.docker, container_name):
            raise SystemExit(f"{args.runtime}: Docker did not confirm container cleanup")

    print(f"{args.runtime}: PASS (fixed runtime command, non-root, networkless, read-only rootfs, bounded resources)")


if __name__ == "__main__":
    main()
