"""Unit tests for pairing flow — no real device-service required."""
import json
import pytest
from unittest.mock import AsyncMock, MagicMock, patch


@pytest.fixture(autouse=True)
def no_credentials_save():
    """Prevent tests from writing to disk."""
    with patch("nexora_agent.credentials.save") as mock_save:
        yield mock_save


# ---------------------------------------------------------------------------
# Pairing happy path
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_pair_happy_path(no_credentials_save):
    announce_resp = MagicMock()
    announce_resp.raise_for_status = MagicMock()
    announce_resp.json = MagicMock(return_value={
        "device_code": "dev-code-abc123",
        "user_code": "ABCD-1234",
        "expires_in": 60,
        "interval": 0.01,
        "verification_uri": "http://localhost:8000/pair",
    })

    poll_pending = MagicMock()
    poll_pending.status_code = 200
    poll_pending.json = MagicMock(return_value={"status": "pending"})

    poll_approved = MagicMock()
    poll_approved.status_code = 200
    poll_approved.json = MagicMock(return_value={
        "status": "approved",
        "device_id": "dev-001",
        "bootstrap_token": "pair-aabb:secret123",
    })

    register_resp = MagicMock()
    register_resp.raise_for_status = MagicMock()
    register_resp.json = MagicMock(return_value={"device_id": "dev-001"})

    mock_client = AsyncMock()
    mock_client.post = AsyncMock(side_effect=[announce_resp, register_resp])
    mock_client.get = AsyncMock(side_effect=[poll_pending, poll_approved])

    with patch("nexora_agent.pairing.httpx.AsyncClient") as mock_cls:
        mock_cls.return_value.__aenter__ = AsyncMock(return_value=mock_client)
        mock_cls.return_value.__aexit__ = AsyncMock(return_value=False)

        from nexora_agent.pairing import run_pairing
        creds = await run_pairing(
            server_url="http://device-service:8000",
            gateway_url="http://gateway:8007",
            device_name="test-device",
            on_user_code=lambda code, uri: None,
        )

    assert creds["device_id"] == "dev-001"
    assert creds["server_url"] == "http://device-service:8000"
    no_credentials_save.assert_called_once()


@pytest.mark.asyncio
async def test_pair_denied_raises(no_credentials_save):
    announce_resp = MagicMock()
    announce_resp.raise_for_status = MagicMock()
    announce_resp.json = MagicMock(return_value={
        "device_code": "dev-code",
        "user_code": "XXXX-0000",
        "expires_in": 10,
        "interval": 0.01,
        "verification_uri": "http://localhost/pair",
    })

    denied_resp = MagicMock()
    denied_resp.status_code = 200
    denied_resp.json = MagicMock(return_value={"status": "denied"})

    mock_client = AsyncMock()
    mock_client.post = AsyncMock(return_value=announce_resp)
    mock_client.get = AsyncMock(return_value=denied_resp)

    with patch("nexora_agent.pairing.httpx.AsyncClient") as mock_cls:
        mock_cls.return_value.__aenter__ = AsyncMock(return_value=mock_client)
        mock_cls.return_value.__aexit__ = AsyncMock(return_value=False)

        from nexora_agent.pairing import run_pairing, PairingDenied
        with pytest.raises(PairingDenied):
            await run_pairing(
                server_url="http://device-service:8000",
                gateway_url="http://gateway:8007",
                device_name="denied-device",
                on_user_code=lambda c, u: None,
            )


@pytest.mark.asyncio
async def test_pair_expired_on_404(no_credentials_save):
    announce_resp = MagicMock()
    announce_resp.raise_for_status = MagicMock()
    announce_resp.json = MagicMock(return_value={
        "device_code": "dev-code",
        "user_code": "YYYY-9999",
        "expires_in": 10,
        "interval": 0.01,
        "verification_uri": "http://localhost/pair",
    })

    expired_resp = MagicMock()
    expired_resp.status_code = 404

    mock_client = AsyncMock()
    mock_client.post = AsyncMock(return_value=announce_resp)
    mock_client.get = AsyncMock(return_value=expired_resp)

    with patch("nexora_agent.pairing.httpx.AsyncClient") as mock_cls:
        mock_cls.return_value.__aenter__ = AsyncMock(return_value=mock_client)
        mock_cls.return_value.__aexit__ = AsyncMock(return_value=False)

        from nexora_agent.pairing import run_pairing, PairingExpired
        with pytest.raises(PairingExpired):
            await run_pairing(
                server_url="http://device-service:8000",
                gateway_url="http://gateway:8007",
                device_name="expired-device",
                on_user_code=lambda c, u: None,
            )
