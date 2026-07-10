"""Load optional Focus config from `.focus.toml` at the repo root.

Missing file → defaults. Unknown keys are ignored so older Focus versions
stay compatible when the config grows.
"""

from __future__ import annotations

import tomllib
from dataclasses import dataclass
from pathlib import Path

from focus.hud.classify import DEFAULT_FAN_OUT_THRESHOLD


@dataclass(frozen=True)
class FocusConfig:
    """Runtime knobs that teams can tune without code changes."""

    fan_out_threshold: int = DEFAULT_FAN_OUT_THRESHOLD


def load_config(root: Path) -> FocusConfig:
    """Read `.focus.toml` under `root`, or return defaults."""
    path = root.resolve() / ".focus.toml"
    if not path.is_file():
        return FocusConfig()
    data = tomllib.loads(path.read_text(encoding="utf-8"))
    focus = data.get("focus", data)
    threshold = focus.get("fan_out_threshold", DEFAULT_FAN_OUT_THRESHOLD)
    try:
        value = int(threshold)
    except (TypeError, ValueError):
        value = DEFAULT_FAN_OUT_THRESHOLD
    if value < 1:
        value = DEFAULT_FAN_OUT_THRESHOLD
    return FocusConfig(fan_out_threshold=value)
