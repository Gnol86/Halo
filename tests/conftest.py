"""Home Assistant fixtures for the local custom integration."""

import pytest


@pytest.fixture(autouse=True)
def enable_halo(enable_custom_integrations):
    """Allow Home Assistant's test loader to discover custom_components/halo."""
