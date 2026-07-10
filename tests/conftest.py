"""Shared pytest fixtures."""

from pathlib import Path

import pytest

GLASS_BOX = Path(__file__).parent / "fixtures" / "glass_box"
GLASS_BOX_JS = Path(__file__).parent / "fixtures" / "glass_box_js"


@pytest.fixture()
def glass_box_path() -> Path:
    """Path to the committed golden Python fixture repo."""
    return GLASS_BOX


@pytest.fixture()
def glass_box_js_path() -> Path:
    """Path to the committed golden JS/TS fixture repo."""
    return GLASS_BOX_JS
