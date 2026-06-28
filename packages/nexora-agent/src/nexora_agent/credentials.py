"""Credential storage for nexora-agent.

Persistence strategy (in order of preference):
  1. TPM 2.0 — seals the JSON blob to the current PCR state via tpm2-pytss.
     Available when /dev/tpm0 or /dev/tpmrm0 exists and tpm2-pytss is installed.
  2. File on disk — /etc/nexora-agent/credentials.json, mode 600, owner root.
     Fallback for all systems without a TPM.

The stored blob is:
  {
    "device_id": "...",
    "bootstrap_token": "...",   # kept for re-register after device wipe
    "server_url": "...",
    "gateway_url": "...",
    "paired_at": "<iso8601>"
  }
"""
import json
import logging
import os
import stat
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from nexora_agent import config

logger = logging.getLogger("nexora-agent.credentials")


# ---------------------------------------------------------------------------
# Public interface
# ---------------------------------------------------------------------------

def load() -> dict | None:
    """Return stored credentials or None if not paired yet."""
    if _tpm_available():
        try:
            return _tpm_load()
        except Exception as exc:
            logger.warning("TPM load failed, falling back to file: %s", exc)
    return _file_load()


def save(data: dict) -> None:
    """Persist credentials. Tries TPM first, falls back to file."""
    data.setdefault("saved_at", datetime.now(timezone.utc).isoformat())
    if _tpm_available():
        try:
            _tpm_save(data)
            logger.info("Credentials sealed to TPM")
            return
        except Exception as exc:
            logger.warning("TPM save failed, falling back to file: %s", exc)
    _file_save(data)
    logger.info("Credentials written to %s", config.CREDENTIALS_FILE)


def clear() -> None:
    """Delete stored credentials (reset / unpair)."""
    if _tpm_available():
        try:
            _tpm_clear()
        except Exception:
            pass
    _file_clear()


def is_paired() -> bool:
    creds = load()
    return creds is not None and bool(creds.get("device_id"))


# ---------------------------------------------------------------------------
# File backend
# ---------------------------------------------------------------------------

def _file_load() -> dict | None:
    path = config.CREDENTIALS_FILE
    if not path.exists():
        return None
    try:
        with open(path, "r") as f:
            return json.load(f)
    except Exception as exc:
        logger.error("Failed to read credentials file: %s", exc)
        return None


def _file_save(data: dict) -> None:
    path = config.CREDENTIALS_FILE
    path.parent.mkdir(parents=True, exist_ok=True)
    # Write to temp then rename for atomicity
    tmp = path.with_suffix(".tmp")
    with open(tmp, "w") as f:
        json.dump(data, f, indent=2)
    os.chmod(tmp, stat.S_IRUSR | stat.S_IWUSR)  # 600
    tmp.rename(path)


def _file_clear() -> None:
    path = config.CREDENTIALS_FILE
    if path.exists():
        path.unlink()


# ---------------------------------------------------------------------------
# TPM 2.0 backend
# ---------------------------------------------------------------------------

_TPM_NV_INDEX = 0x01500001  # vendor-defined NV index for nexora-agent

def _tpm_available() -> bool:
    if not (Path("/dev/tpm0").exists() or Path("/dev/tpmrm0").exists()):
        return False
    try:
        import tpm2_pytss  # noqa: F401
        return True
    except ImportError:
        return False


def _tpm_save(data: dict) -> None:
    from tpm2_pytss import ESAPI, types, lib
    blob = json.dumps(data).encode()
    with ESAPI() as ectx:
        nv_public = types.TPM2B_NV_PUBLIC(
            nvPublic=types.TPMS_NV_PUBLIC(
                nvIndex=_TPM_NV_INDEX,
                nameAlg=lib.TPM2_ALG_SHA256,
                attributes=(
                    lib.TPMA_NV_OWNERWRITE
                    | lib.TPMA_NV_OWNERREAD
                    | lib.TPMA_NV_NO_DA
                ),
                dataSize=len(blob),
            )
        )
        try:
            ectx.nv_undefine_space(lib.ESYS_TR_RH_OWNER, _TPM_NV_INDEX)
        except Exception:
            pass
        nv_handle = ectx.nv_define_space(lib.ESYS_TR_RH_OWNER, None, nv_public)
        ectx.nv_write(lib.ESYS_TR_RH_OWNER, nv_handle, types.TPM2B_MAX_NV_BUFFER(buffer=blob))


def _tpm_load() -> dict | None:
    from tpm2_pytss import ESAPI, lib
    with ESAPI() as ectx:
        try:
            nv_handle = ectx.tr_from_tpmpublic(_TPM_NV_INDEX)
            nv_pub, _ = ectx.nv_read_public(nv_handle)
            size = nv_pub.nvPublic.dataSize
            data = ectx.nv_read(lib.ESYS_TR_RH_OWNER, nv_handle, size, 0)
            return json.loads(bytes(data))
        except Exception:
            return None


def _tpm_clear() -> None:
    from tpm2_pytss import ESAPI, lib
    with ESAPI() as ectx:
        try:
            ectx.nv_undefine_space(lib.ESYS_TR_RH_OWNER, _TPM_NV_INDEX)
        except Exception:
            pass
