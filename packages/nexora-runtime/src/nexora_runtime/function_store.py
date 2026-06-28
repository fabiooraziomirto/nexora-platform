"""Function artifact store for nexora-runtime.

Downloads WASM artifacts from artifact_uri, verifies SHA-256 checksum,
and stores them under STORE_DIR/{function_id}/function.wasm.
"""
import hashlib
import logging
import shutil
from pathlib import Path
from typing import Any

import httpx

logger = logging.getLogger("nexora-runtime.store")

STORE_DIR = Path("/var/lib/nexora-runtime/functions")


class FunctionNotFound(Exception):
    pass


class ChecksumMismatch(Exception):
    pass


def function_path(function_id: str) -> Path:
    return STORE_DIR / function_id / "function.wasm"


def is_installed(function_id: str) -> bool:
    return function_path(function_id).exists()


async def install(
    function_id: str,
    artifact_uri: str,
    checksum: str | None,
    runtime_type: str = "wasm",
    memory_mb: int = 64,
    timeout_ms: int = 30000,
) -> dict:
    """Download and verify a function artifact. Returns metadata dict."""
    dest = function_path(function_id)
    dest.parent.mkdir(parents=True, exist_ok=True)

    logger.info("Installing function %s from %s", function_id, artifact_uri)

    # Download
    try:
        async with httpx.AsyncClient(timeout=120.0, follow_redirects=True) as client:
            resp = await client.get(artifact_uri)
            resp.raise_for_status()
            wasm_bytes = resp.content
    except Exception as exc:
        raise RuntimeError(f"Failed to download artifact: {exc}") from exc

    # Verify checksum
    if checksum:
        algo, _, expected = checksum.partition(":")
        if algo == "sha256":
            actual = hashlib.sha256(wasm_bytes).hexdigest()
            if actual != expected:
                raise ChecksumMismatch(
                    f"Checksum mismatch for {function_id}: expected {expected}, got {actual}"
                )
        else:
            logger.warning("Unknown checksum algorithm '%s' — skipping verification", algo)

    # Write atomically
    tmp = dest.with_suffix(".tmp")
    tmp.write_bytes(wasm_bytes)
    tmp.rename(dest)

    # Store metadata alongside the wasm file
    import json
    meta = {
        "function_id": function_id,
        "artifact_uri": artifact_uri,
        "runtime_type": runtime_type,
        "memory_mb": memory_mb,
        "timeout_ms": timeout_ms,
        "size_bytes": len(wasm_bytes),
        "checksum": checksum,
    }
    (dest.parent / "meta.json").write_text(json.dumps(meta, indent=2))

    logger.info("Installed function %s (%d bytes)", function_id, len(wasm_bytes))
    return meta


def get_metadata(function_id: str) -> dict:
    import json
    meta_path = function_path(function_id).parent / "meta.json"
    if not meta_path.exists():
        raise FunctionNotFound(function_id)
    return json.loads(meta_path.read_text())


def uninstall(function_id: str) -> None:
    fn_dir = STORE_DIR / function_id
    if fn_dir.exists():
        shutil.rmtree(fn_dir)
        logger.info("Uninstalled function %s", function_id)


def list_installed() -> list[str]:
    if not STORE_DIR.exists():
        return []
    return [d.name for d in STORE_DIR.iterdir() if d.is_dir() and (d / "function.wasm").exists()]
