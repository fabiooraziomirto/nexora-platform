"""Command executor for nexora-agent.

Handles two execution types received over the WebSocket tunnel:
  - "command"          → shell command with timeout + output capture
  - "function.install" → delegate to nexora-runtime via HTTP
  - "function.invoke"  → delegate to nexora-runtime via HTTP

All results are returned as a dict ready for the execution-service callback:
  {"status": "succeeded"|"failed", "exit_code": int, "stdout": str, "stderr": str}
"""
import asyncio
import logging
import os
import signal

import httpx

from nexora_agent import config

logger = logging.getLogger("nexora-agent.executor")


async def execute(dispatch: dict) -> dict:
    """Dispatch a control message to the appropriate handler."""
    execution_type: str = dispatch.get("execution_type", "command")
    payload: dict = dispatch.get("payload", dispatch)

    if execution_type == "function.install":
        return await _function_install(payload)
    elif execution_type == "function.invoke":
        return await _function_invoke(payload)
    else:
        return await _run_command(payload)


# ---------------------------------------------------------------------------
# Shell command execution
# ---------------------------------------------------------------------------

async def _run_command(payload: dict) -> dict:
    command: str = payload.get("command", "")
    args: list = payload.get("args", [])
    env_extra: dict = payload.get("env", {})
    timeout: float = float(payload.get("timeout_seconds", config.COMMAND_TIMEOUT))

    if not command:
        return _result("failed", 1, "", "No command specified")

    # Build argv — if command contains shell metacharacters use shell=True
    use_shell = any(c in command for c in ("|", "&", ";", ">", "<", "$", "`", "\\"))
    if use_shell:
        argv = command + (" " + " ".join(str(a) for a in args) if args else "")
    else:
        argv = [command] + [str(a) for a in args]

    env = {**os.environ, **env_extra}

    logger.info("Executing command: %s (timeout=%.1fs)", command, timeout)
    try:
        proc = await asyncio.create_subprocess_shell(
            argv if use_shell else None,  # type: ignore[arg-type]
            args=None if use_shell else argv,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            env=env,
            # Run as unprivileged user when possible
            preexec_fn=_drop_privileges if os.getuid() == 0 else None,
        ) if use_shell else await asyncio.create_subprocess_exec(
            *argv,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            env=env,
            preexec_fn=_drop_privileges if os.getuid() == 0 else None,
        )

        try:
            stdout_bytes, stderr_bytes = await asyncio.wait_for(
                proc.communicate(), timeout=timeout
            )
        except asyncio.TimeoutError:
            try:
                proc.send_signal(signal.SIGTERM)
                await asyncio.sleep(2)
                proc.kill()
            except ProcessLookupError:
                pass
            return _result("failed", -1, "", f"Command timed out after {timeout}s")

        stdout = _truncate(stdout_bytes.decode("utf-8", errors="replace"))
        stderr = _truncate(stderr_bytes.decode("utf-8", errors="replace"))
        exit_code = proc.returncode or 0
        status = "succeeded" if exit_code == 0 else "failed"

        logger.info("Command finished exit_code=%d", exit_code)
        return _result(status, exit_code, stdout, stderr)

    except (FileNotFoundError, PermissionError) as exc:
        return _result("failed", 127, "", f"Command not found or not executable: {command}: {exc}")
    except Exception as exc:
        logger.error("Command execution error: %s", exc)
        return _result("failed", -1, "", str(exc))


def _drop_privileges():
    """Called in child process (fork) to drop root privileges."""
    try:
        import pwd
        nobody = pwd.getpwnam("nobody")
        os.setgid(nobody.pw_gid)
        os.setuid(nobody.pw_uid)
    except Exception:
        pass


# ---------------------------------------------------------------------------
# nexora-runtime delegation (WASM functions)
# ---------------------------------------------------------------------------

async def _function_install(payload: dict) -> dict:
    if not config.RUNTIME_ENABLED:
        return _result("failed", 1, "", "nexora-runtime not enabled on this device")
    plugin = payload.get("plugin", {})
    try:
        async with httpx.AsyncClient(base_url=config.RUNTIME_URL, timeout=120.0) as client:
            resp = await client.post("/runtime/functions/install", json={
                "function_id": plugin.get("id"),
                "artifact_uri": plugin.get("artifact_uri"),
                "checksum": plugin.get("checksum"),
                "runtime_type": plugin.get("runtime_type", "wasm"),
                "memory_mb": plugin.get("memory_mb", 64),
                "timeout_ms": plugin.get("timeout_ms", 30000),
            })
            if resp.status_code in (200, 201):
                return _result("succeeded", 0, resp.text, "")
            else:
                return _result("failed", 1, "", f"Runtime returned {resp.status_code}: {resp.text}")
    except Exception as exc:
        logger.error("function.install failed: %s", exc)
        return _result("failed", 1, "", str(exc))


async def _function_invoke(payload: dict) -> dict:
    if not config.RUNTIME_ENABLED:
        return _result("failed", 1, "", "nexora-runtime not enabled on this device")
    plugin = payload.get("plugin", {})
    function_id = plugin.get("id") or payload.get("function_id")
    args = payload.get("args", {})
    try:
        async with httpx.AsyncClient(base_url=config.RUNTIME_URL, timeout=60.0) as client:
            resp = await client.post(f"/runtime/functions/{function_id}/invoke", json={"args": args})
            if resp.status_code == 200:
                data = resp.json()
                return _result("succeeded", 0, str(data.get("output", "")), "")
            else:
                return _result("failed", 1, "", f"Runtime returned {resp.status_code}: {resp.text}")
    except Exception as exc:
        logger.error("function.invoke failed function_id=%s: %s", function_id, exc)
        return _result("failed", 1, "", str(exc))


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _result(status: str, exit_code: int, stdout: str, stderr: str) -> dict:
    return {"status": status, "exit_code": exit_code, "stdout": stdout, "stderr": stderr}


def _truncate(text: str) -> str:
    limit = config.COMMAND_MAX_OUTPUT
    if len(text) > limit:
        return text[:limit] + f"\n... [truncated at {limit} bytes]"
    return text
