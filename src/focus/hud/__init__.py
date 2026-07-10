"""Focus HUD — Mermaid map + markdown render from computed blast radius.

This package turns graph facts into the Focus HUD contract in docs/HUD.md.
Topology always comes from the NetworkX graph; wording is template-based
(no LLM). Every Mermaid edge is validated against the graph before emit.
"""

from focus.hud.build import build_hud
from focus.hud.render import render_hud

__all__ = ["build_hud", "render_hud"]
