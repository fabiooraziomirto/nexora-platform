"""Unit tests for Zigbee bridge message handler — no MQTT broker, no device-service."""
import json
import pytest
from unittest.mock import AsyncMock, patch, MagicMock


@pytest.fixture(autouse=True)
def clear_registry():
    """Reset device registry between tests."""
    from zigbee_bridge.core import device_registry
    device_registry._name_to_id.clear()
    device_registry._ieee_to_id.clear()
    yield
    device_registry._name_to_id.clear()
    device_registry._ieee_to_id.clear()


# ---------------------------------------------------------------------------
# bridge/devices bulk inventory
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_bulk_devices_registers_known_devices():
    devices = [
        {
            "friendly_name": "living-room-bulb",
            "ieee_address": "0x00158d0001aabbcc",
            "definition": {
                "model": "LED2003G10",
                "vendor": "IKEA",
                "exposes": [{"name": "state"}, {"name": "brightness"}],
            },
            "endpoints": {"1": {"clusters": {"input": ["genOnOff"], "output": []}}},
        }
    ]
    payload = json.dumps(devices).encode()

    with patch("zigbee_bridge.core.device_registry.httpx.AsyncClient") as mock_cls:
        mock_client = AsyncMock()
        mock_cls.return_value.__aenter__ = AsyncMock(return_value=mock_client)
        mock_cls.return_value.__aexit__ = AsyncMock(return_value=False)
        mock_resp = MagicMock()
        mock_resp.raise_for_status = MagicMock()
        mock_resp.json = MagicMock(return_value={"device_id": "dev-zigbee-001"})
        mock_client.post = AsyncMock(return_value=mock_resp)

        from zigbee_bridge.core.message_handler import handle_message
        await handle_message("zigbee2mqtt/bridge/devices", payload)

        mock_client.post.assert_called_once()
        call = mock_client.post.call_args
        assert "/agents/register" in call[0][0]
        body = call[1]["json"]
        assert body["connection_protocol"] == "zigbee"
        assert body["name"] == "living-room-bulb"


@pytest.mark.asyncio
async def test_bulk_devices_skips_coordinator():
    devices = [
        {"friendly_name": "Coordinator", "ieee_address": "0xcc", "definition": {}, "endpoints": {}}
    ]
    payload = json.dumps(devices).encode()

    with patch("zigbee_bridge.core.device_registry.httpx.AsyncClient") as mock_cls:
        mock_client = AsyncMock()
        mock_cls.return_value.__aenter__ = AsyncMock(return_value=mock_client)
        mock_cls.return_value.__aexit__ = AsyncMock(return_value=False)
        mock_client.post = AsyncMock()

        from zigbee_bridge.core.message_handler import handle_message
        await handle_message("zigbee2mqtt/bridge/devices", payload)

        mock_client.post.assert_not_called()


# ---------------------------------------------------------------------------
# bridge/event join/leave
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_device_join_event_registers():
    event = {
        "type": "device_joined",
        "data": {
            "friendly_name": "sensor-01",
            "ieee_address": "0xdeadbeef",
            "definition": {"model": "SNZB-02", "vendor": "SONOFF", "exposes": [{"name": "temperature"}]},
            "endpoints": {},
        },
    }
    payload = json.dumps(event).encode()

    with patch("zigbee_bridge.core.device_registry.httpx.AsyncClient") as mock_cls:
        mock_client = AsyncMock()
        mock_cls.return_value.__aenter__ = AsyncMock(return_value=mock_client)
        mock_cls.return_value.__aexit__ = AsyncMock(return_value=False)
        mock_resp = MagicMock()
        mock_resp.raise_for_status = MagicMock()
        mock_resp.json = MagicMock(return_value={"device_id": "dev-zigbee-002"})
        mock_client.post = AsyncMock(return_value=mock_resp)

        from zigbee_bridge.core.message_handler import handle_message
        await handle_message("zigbee2mqtt/bridge/event", payload)

        mock_client.post.assert_called_once()


@pytest.mark.asyncio
async def test_device_leave_event_removes():
    from zigbee_bridge.core import device_registry
    device_registry._name_to_id["sensor-01"] = "dev-zigbee-002"
    device_registry._ieee_to_id["0xdeadbeef"] = "dev-zigbee-002"

    event = {"type": "device_leave", "data": {"friendly_name": "sensor-01"}}
    payload = json.dumps(event).encode()

    from zigbee_bridge.core.message_handler import handle_message
    await handle_message("zigbee2mqtt/bridge/event", payload)

    assert "sensor-01" not in device_registry._name_to_id


# ---------------------------------------------------------------------------
# Device state → telemetry + shadow
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_device_state_sends_telemetry_and_shadow():
    from zigbee_bridge.core import device_registry
    device_registry._name_to_id["temp-sensor"] = "dev-zigbee-003"

    state = {"temperature": 22.5, "humidity": 55.0, "battery": 85}
    payload = json.dumps(state).encode()

    with patch("zigbee_bridge.core.message_handler.httpx.AsyncClient") as mock_cls:
        mock_client = AsyncMock()
        mock_cls.return_value.__aenter__ = AsyncMock(return_value=mock_client)
        mock_cls.return_value.__aexit__ = AsyncMock(return_value=False)
        mock_resp = MagicMock()
        mock_resp.status_code = 202
        mock_client.post = AsyncMock(return_value=mock_resp)

        from zigbee_bridge.core.message_handler import handle_message
        await handle_message("zigbee2mqtt/temp-sensor", payload)

        assert mock_client.post.call_count == 2
        urls = [c[0][0] for c in mock_client.post.call_args_list]
        assert any("/telemetry" in u for u in urls)
        assert any("/shadow/reported" in u for u in urls)


@pytest.mark.asyncio
async def test_device_state_unknown_device_skipped():
    state = {"temperature": 20.0}
    payload = json.dumps(state).encode()

    with patch("zigbee_bridge.core.message_handler.httpx.AsyncClient") as mock_cls:
        mock_client = AsyncMock()
        mock_cls.return_value.__aenter__ = AsyncMock(return_value=mock_client)
        mock_cls.return_value.__aexit__ = AsyncMock(return_value=False)
        mock_client.post = AsyncMock()

        from zigbee_bridge.core.message_handler import handle_message
        await handle_message("zigbee2mqtt/unknown-device", payload)

        mock_client.post.assert_not_called()


@pytest.mark.asyncio
async def test_subtopics_ignored():
    """zigbee2mqtt/device/set and similar subtopics should be ignored."""
    from zigbee_bridge.core.message_handler import handle_message
    with patch("zigbee_bridge.core.message_handler._process_device_state") as mock_fn:
        await handle_message("zigbee2mqtt/some-device/set", b"{}")
        mock_fn.assert_not_called()


# ---------------------------------------------------------------------------
# ZIGBEE_METRIC_MAP correctness
# ---------------------------------------------------------------------------

def test_metric_map_coverage():
    from zigbee_bridge.core.message_handler import ZIGBEE_METRIC_MAP
    assert "temperature" in ZIGBEE_METRIC_MAP
    assert ZIGBEE_METRIC_MAP["temperature"] == ("temperature_celsius", "celsius")
    assert "occupancy" in ZIGBEE_METRIC_MAP
    assert "linkquality" in ZIGBEE_METRIC_MAP
    assert "power" in ZIGBEE_METRIC_MAP


# ---------------------------------------------------------------------------
# _infer_device_type
# ---------------------------------------------------------------------------

def test_infer_temperature_sensor():
    from zigbee_bridge.core.message_handler import _infer_device_type
    assert _infer_device_type({"exposes": [{"name": "temperature"}]}) == "temperature-sensor"


def test_infer_dimmable_light():
    from zigbee_bridge.core.message_handler import _infer_device_type
    assert _infer_device_type({"exposes": [{"name": "state"}, {"name": "brightness"}]}) == "dimmable-light"


def test_infer_fallback():
    from zigbee_bridge.core.message_handler import _infer_device_type
    assert _infer_device_type({}) == "zigbee"
