"""
Smart BethG - Result Verifier (T0405)

The existing ExecutionEngine.execute() treats any non-exception return
from a tool as success. That misses real failures a tool can report
without raising - e.g. a shell command that runs and returns a non-zero
exit code is not an exception, but it is not a success either. This is
exactly the "claims success without verification" anti-pattern the
project's own build rules warn against.

Each action has its own idea of what a valid, successful result looks
like. An action with no verification rule fails closed (unverifiable)
rather than being assumed successful.
"""


def verify_result(action: str, raw_result) -> dict:
    if action == "terminal.execute":
        return _verify_command_result(raw_result)
    if action == "filesystem.read":
        return _verify_shape(raw_result, "content")
    if action == "filesystem.write":
        return _verify_shape(raw_result, "path")
    if action == "git.read":
        return _verify_command_result(raw_result)
    if action == "git.write":
        return _verify_command_result(raw_result)
    if action == "network.request":
        return _verify_shape(raw_result, "content")
    if action == "docker.run":
        return _verify_command_result(raw_result)

    return {
        "success": False,
        "status": "unverifiable",
        "reason": f"No verification rule exists for action {action!r}.",
        "result": raw_result,
    }


def _verify_command_result(raw_result) -> dict:
    if not isinstance(raw_result, dict) or "return_code" not in raw_result:
        return {
            "success": False,
            "status": "unverifiable",
            "reason": "Command tool returned an unexpected result shape.",
            "result": raw_result,
        }
    if raw_result["return_code"] != 0:
        return {
            "success": False,
            "status": "command_failed",
            "reason": raw_result.get("stderr") or f"Exited with code {raw_result['return_code']}.",
            "result": raw_result,
        }
    return {"success": True, "status": "executed", "result": raw_result}


def _verify_shape(raw_result, required_key: str) -> dict:
    if not isinstance(raw_result, dict) or required_key not in raw_result:
        return {
            "success": False,
            "status": "unverifiable",
            "reason": f"Tool result did not include expected key {required_key!r}.",
            "result": raw_result,
        }
    return {"success": True, "status": "executed", "result": raw_result}
