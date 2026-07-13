"""Test FrozenVault backend."""

import frozen_vault_backend


def test_import() -> None:
    """Test that the app can be imported."""
    assert isinstance(frozen_vault_backend.__name__, str)
