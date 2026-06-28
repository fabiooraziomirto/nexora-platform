from unittest.mock import patch

from common.auth.context import AuthSettings, RequestAuthenticator


def test_internal_key_authenticates_as_internal_service_when_configured():
    authenticator = RequestAuthenticator(AuthSettings(auth_enabled=True))

    with patch.dict("os.environ", {"INTERNAL_SERVICE_KEY": "secret"}):
        user = authenticator.authenticate_internal_key("secret")

    assert user is not None
    assert user.user_id == "internal-service"
    assert user.tenant_id == "system"
    assert "platform-admin" in user.roles


def test_missing_internal_key_does_not_create_dev_bypass():
    authenticator = RequestAuthenticator(AuthSettings(auth_enabled=True))

    with patch.dict("os.environ", {}, clear=True):
        user = authenticator.authenticate_internal_key(None)

    assert user is None


def test_wrong_internal_key_is_rejected():
    authenticator = RequestAuthenticator(AuthSettings(auth_enabled=True))

    with patch.dict("os.environ", {"INTERNAL_SERVICE_KEY": "secret"}):
        user = authenticator.authenticate_internal_key("wrong")

    assert user is None
