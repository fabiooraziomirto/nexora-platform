"""Unit tests for MQTT message handler — no broker, no Kafka, no device-service."""
import json
import pytest
from unittest.mock import AsyncMock, patch, MagicMock


# ---------------------------------------------------------------------------
# handle_message routing
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_register_message_calls_device_service():
    payload = json.dumps({
        "name": "Living Room Sensor",
        "device_type": "temperature-sensor",
    }).encode()

    with patch("mqtt_bridge.core.message_handler.httpx.AsyncClient") as mock_cls:
        mock_client = AsyncMock()
        mock_cls.return_value.__aenter__ = AsyncMock(return_value=mock_client)
        mock_cls.return_value.__aexit__ = AsyncMock(return_value=False)
        mock_resp = MagicMock()
        mock_resp.raise_for_status = MagicMock()
        mock_client.post = AsyncMock(return_value=mock_resp)

        from mqtt_bridge.core.message_handler import handle_message
        await handle_message("nexora/devices/dev-abc/register", payload)

        mock_client.post.assert_called_once()
        call_args = mock_client.post.call_args
        assert "/agents/register" in call_args[0][0]
        body = call_args[1]["json"]
        assert body["connection_protocol"] == "mqtt"
        assert body["name"] == "Living Room Sensor"


@pytest.mark.asyncio
async def test_telemetry_single_sample():
    payload = json.dumps({"metric": "temperature", "value": 22.5, "unit": "celsius"}).encode()

    with patch("mqtt_bridge.core.message_handler.ensure_registered", new_callable=AsyncMock, return_value=True), \
         patch("mqtt_bridge.core.message_handler.httpx.AsyncClient") as mock_cls:

        mock_client = AsyncMock()
        mock_cls.return_value.__aenter__ = AsyncMock(return_value=mock_client)
        mock_cls.return_value.__aexit__ = AsyncMock(return_value=False)
        mock_resp = MagicMock()
        mock_resp.status_code = 202
        mock_client.post = AsyncMock(return_value=mock_resp)

        from mqtt_bridge.core.message_handler import handle_message
        await handle_message("nexora/devices/dev-abc/telemetry", payload)

        mock_client.post.assert_called_once()
        body = mock_client.post.call_args[1]["json"]
        assert body["samples"][0]["metric"] == "temperature"
        assert body["samples"][0]["value"] == 22.5
        assert body["samples"][0]["unit"] == "celsius"


@pytest.mark.asyncio
async def test_telemetry_batch_samples():
    samples = [
        {"metric": "temperature", "value": 21.0},
        {"metric": "humidity", "value": 55.0, "unit": "percent"},
    ]
    payload = json.dumps(samples).encode()

    with patch("mqtt_bridge.core.message_handler.ensure_registered", new_callable=AsyncMock, return_value=True), \
         patch("mqtt_bridge.core.message_handler.httpx.AsyncClient") as mock_cls:

        mock_client = AsyncMock()
        mock_cls.return_value.__aenter__ = AsyncMock(return_value=mock_client)
        mock_cls.return_value.__aexit__ = AsyncMock(return_value=False)
        mock_resp = MagicMock()
        mock_resp.status_code = 202
        mock_client.post = AsyncMock(return_value=mock_resp)

        from mqtt_bridge.core.message_handler import handle_message
        await handle_message("nexora/devices/dev-abc/telemetry", payload)

        body = mock_client.post.call_args[1]["json"]
        assert len(body["samples"]) == 2


@pytest.mark.asyncio
async def test_state_update():
    state = {"relay": True, "brightness": 80}
    payload = json.dumps(state).encode()

    with patch("mqtt_bridge.core.message_handler.ensure_registered", new_callable=AsyncMock, return_value=True), \
         patch("mqtt_bridge.core.message_handler.httpx.AsyncClient") as mock_cls:

        mock_client = AsyncMock()
        mock_cls.return_value.__aenter__ = AsyncMock(return_value=mock_client)
        mock_cls.return_value.__aexit__ = AsyncMock(return_value=False)
        mock_client.post = AsyncMock(return_value=MagicMock())

        from mqtt_bridge.core.message_handler import handle_message
        await handle_message("nexora/devices/dev-abc/state", payload)

        mock_client.post.assert_called_once()
        call_url = mock_client.post.call_args[0][0]
        assert "/shadow/reported" in call_url
        body = mock_client.post.call_args[1]["json"]
        assert body["state"]["relay"] is True


@pytest.mark.asyncio
async def test_unknown_action_ignored():
    from mqtt_bridge.core.message_handler import handle_message
    # Should not raise and should do nothing for unknown action
    await handle_message("nexora/devices/dev-abc/unknown_action", b"{}")


@pytest.mark.asyncio
async def test_wrong_prefix_ignored():
    from mqtt_bridge.core.message_handler import handle_message
    await handle_message("other/devices/dev-abc/telemetry", b"{}")


@pytest.mark.asyncio
async def test_invalid_json_ignored():
    from mqtt_bridge.core.message_handler import handle_message
    await handle_message("nexora/devices/dev-abc/telemetry", b"not-json")


# ---------------------------------------------------------------------------
# Topic parsing edge cases
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_topic_too_short_ignored():
    """Topics with fewer than 4 segments don't reach the handler."""
    from mqtt_bridge.core.message_handler import handle_message
    await handle_message("nexora/devices", b"{}")
