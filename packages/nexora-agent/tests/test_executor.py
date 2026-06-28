"""Unit tests for command executor."""
import pytest
from unittest.mock import AsyncMock, patch, MagicMock


@pytest.mark.asyncio
async def test_command_success():
    from nexora_agent.executor import execute
    result = await execute({"execution_type": "command", "command": "echo", "args": ["hello"]})
    assert result["status"] == "succeeded"
    assert result["exit_code"] == 0
    assert "hello" in result["stdout"]


@pytest.mark.asyncio
async def test_command_failure():
    from nexora_agent.executor import execute
    result = await execute({"execution_type": "command", "command": "false"})
    assert result["status"] == "failed"
    assert result["exit_code"] != 0


@pytest.mark.asyncio
async def test_command_not_found():
    from nexora_agent.executor import execute
    result = await execute({"execution_type": "command", "command": "nonexistent_cmd_xyz"})
    assert result["status"] == "failed"
    assert result["exit_code"] == 127 or result["exit_code"] == -1


@pytest.mark.asyncio
async def test_command_timeout():
    from nexora_agent.executor import execute
    result = await execute({
        "execution_type": "command",
        "command": "sleep",
        "args": ["10"],
        "timeout_seconds": 0.2,
    })
    assert result["status"] == "failed"
    assert "timed out" in result["stderr"]


@pytest.mark.asyncio
async def test_empty_command():
    from nexora_agent.executor import execute
    result = await execute({"execution_type": "command", "command": ""})
    assert result["status"] == "failed"


@pytest.mark.asyncio
async def test_function_install_runtime_disabled():
    with patch("nexora_agent.config.RUNTIME_ENABLED", False):
        from nexora_agent import executor
        # Reload to pick up config patch
        import importlib; importlib.reload(executor)
        result = await executor.execute({
            "execution_type": "function.install",
            "plugin": {"id": "fn-001", "artifact_uri": "https://example.com/fn.wasm"},
        })
        assert result["status"] == "failed"
        assert "not enabled" in result["stderr"]


@pytest.mark.asyncio
async def test_function_invoke_runtime_disabled():
    with patch("nexora_agent.config.RUNTIME_ENABLED", False):
        from nexora_agent import executor
        import importlib; importlib.reload(executor)
        result = await executor.execute({
            "execution_type": "function.invoke",
            "plugin": {"id": "fn-001"},
            "args": {},
        })
        assert result["status"] == "failed"


@pytest.mark.asyncio
async def test_function_install_delegates_to_runtime():
    with patch("nexora_agent.config.RUNTIME_ENABLED", True):
        from nexora_agent import executor
        import importlib; importlib.reload(executor)

        mock_resp = MagicMock()
        mock_resp.status_code = 201
        mock_resp.text = "installed"
        mock_client = AsyncMock()
        mock_client.post = AsyncMock(return_value=mock_resp)

        with patch("nexora_agent.executor.httpx.AsyncClient") as mock_cls:
            mock_cls.return_value.__aenter__ = AsyncMock(return_value=mock_client)
            mock_cls.return_value.__aexit__ = AsyncMock(return_value=False)

            result = await executor.execute({
                "execution_type": "function.install",
                "plugin": {
                    "id": "fn-001",
                    "artifact_uri": "https://example.com/fn.wasm",
                    "checksum": "sha256:abc",
                },
            })

        assert result["status"] == "succeeded"
        mock_client.post.assert_called_once()
        assert "/runtime/functions/install" in mock_client.post.call_args[0][0]
