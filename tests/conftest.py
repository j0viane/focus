"""Shared pytest fixtures."""

from pathlib import Path

import pytest

GLASS_BOX = Path(__file__).parent / "fixtures" / "glass_box"


@pytest.fixture()
def glass_box_path() -> Path:
    """Path to the committed golden fixture repo."""
    return GLASS_BOX
