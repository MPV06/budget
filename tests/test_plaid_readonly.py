import pytest
from unittest.mock import MagicMock
from services.plaid_client import PlaidReadOnlyClient, ReadOnlyViolation, ALLOWED_METHODS


def test_allowed_methods_exact_set():
    assert ALLOWED_METHODS == frozenset({
        "accounts_get",
        "transactions_sync",
        "transactions_recurring_get",
        "item_get",
    })


def test_allowed_method_proxies_call():
    raw = MagicMock()
    raw.accounts_get.return_value = {"accounts": []}
    client = PlaidReadOnlyClient(raw)
    result = client.accounts_get({"access_token": "x"})
    assert result == {"accounts": []}
    raw.accounts_get.assert_called_once()


def test_forbidden_method_raises():
    raw = MagicMock()
    client = PlaidReadOnlyClient(raw)
    with pytest.raises(ReadOnlyViolation, match="transfer_create"):
        client.transfer_create({"foo": "bar"})


def test_other_forbidden_methods_raise():
    raw = MagicMock()
    client = PlaidReadOnlyClient(raw)
    for name in ["auth_get", "processor_token_create", "sandbox_item_fire_webhook",
                 "item_remove", "payment_initiation_payment_create"]:
        with pytest.raises(ReadOnlyViolation):
            getattr(client, name)({})
