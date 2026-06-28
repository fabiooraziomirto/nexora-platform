"""Tests for matter-bridge commissioning endpoints (mock mode, no hardware)."""
import asyncio
import pytest
from unittest.mock import AsyncMock, patch


# ---------------------------------------------------------------------------
# Commission state machine (unit tests, no HTTP)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_start_commissioning_mock_mode():
    """Commissioning in mock mode completes without a real matter-server."""
    from matter_bridge.core.commission import start_commissioning, get_session, _sessions
    _sessions.clear()

    session = await start_commissioning(
        commissioning_id="test-cid-001",
        setup_code="MT:Y3QT042C00KA0648G00",
        manual_code=None,
        name="Test Bulb",
        description="Living room bulb",
        owner_id="owner-123",
        tenant_id="tenant-abc",
        matter_client=None,   # mock mode
    )

    assert session["status"] == "pending"
    assert session["name"] == "Test Bulb"
    assert session["node_id"] is not None

    # Wait for background task to complete
    await asyncio.sleep(1.0)

    updated = get_session("test-cid-001")
    # In mock mode the _register_device call will fail (no real device-service)
    # so status should be "failed" or "commissioned" depending on env
    assert updated["status"] in ("commissioned", "failed")


@pytest.mark.asyncio
async def test_commissioning_sets_protocol_meta():
    """Mock commissioning populates protocol_meta with Matter cluster info."""
    from matter_bridge.core.commission import _sessions, _run_commissioning

    _sessions.clear()
    session = {
        "commissioning_id": "test-meta-001",
        "status": "pending",
        "node_id": 42,
        "device_id": None,
        "error": None,
        "name": "Sensor",
        "description": None,
        "owner_id": "owner-1",
        "tenant_id": "t1",
        "started_at": 0,
    }
    _sessions["test-meta-001"] = session

    with patch("matter_bridge.core.commission._register_device", new_callable=AsyncMock) as mock_reg:
        mock_reg.return_value = "device-uuid-999"
        await _run_commissioning(session, "MT:XXXXX", None, None)

    assert session["status"] == "commissioned"
    assert session["device_id"] == "device-uuid-999"
    mock_reg.assert_called_once()
    # Check protocol_meta was passed to _register_device
    _, proto_meta = mock_reg.call_args[0]
    assert "node_id" in proto_meta
    assert "endpoints" in proto_meta
    assert proto_meta["node_id"] == 42


@pytest.mark.asyncio
async def test_commissioning_failure_recorded():
    """If _register_device raises, session status becomes 'failed'."""
    from matter_bridge.core.commission import _sessions, _run_commissioning

    _sessions.clear()
    session = {
        "commissioning_id": "test-fail-001",
        "status": "pending",
        "node_id": 99,
        "device_id": None,
        "error": None,
        "name": "Broken",
        "description": None,
        "owner_id": "owner-x",
        "tenant_id": None,
        "started_at": 0,
    }
    _sessions["test-fail-001"] = session

    with patch(
        "matter_bridge.core.commission._register_device",
        new_callable=AsyncMock,
        side_effect=Exception("device-service unreachable"),
    ):
        await _run_commissioning(session, None, "12345678901", None)

    assert session["status"] == "failed"
    assert "device-service unreachable" in session["error"]


# ---------------------------------------------------------------------------
# CLUSTER_METRIC_MAP (unit tests, no external calls)
# ---------------------------------------------------------------------------

def test_cluster_metric_map_temperature():
    from matter_bridge.core.attribute_watcher import CLUSTER_METRIC_MAP
    metric, unit, multiplier = CLUSTER_METRIC_MAP["TemperatureMeasurement.MeasuredValue"]
    assert metric == "temperature_celsius"
    assert unit == "celsius"
    # 2200 (raw) × 0.01 = 22.0 °C
    assert round(2200 * multiplier, 2) == 22.0


def test_cluster_metric_map_onoff():
    from matter_bridge.core.attribute_watcher import CLUSTER_METRIC_MAP
    metric, unit, multiplier = CLUSTER_METRIC_MAP["OnOff.OnOff"]
    assert metric == "power_state"
    assert multiplier == 1.0


# ---------------------------------------------------------------------------
# Command map (unit tests)
# ---------------------------------------------------------------------------

def test_command_map_on():
    from matter_bridge.core.command_handler import COMMAND_MAP
    cluster, cmd, build_args = COMMAND_MAP["OnOff.On"]
    assert cluster == "OnOff"
    assert cmd == "on"
    assert build_args({}) == {}


def test_command_map_move_to_level():
    from matter_bridge.core.command_handler import COMMAND_MAP
    _, _, build_args = COMMAND_MAP["LevelControl.MoveToLevel"]
    result = build_args({"level": 200, "transition_time": 10})
    assert result["level"] == 200
    assert result["transition_time"] == 10
