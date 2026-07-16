"""Opt-in evidence-pack caption labeler (Phase 4c).

LLM **labels** only — never invents graph nodes, edges, or risk topology.
Default off; never runs on live-buffer overlay audits.
"""

from focus.llm.labeler import apply_llm_captions, label_caption
from focus.llm.pack import CaptionEvidencePack, build_evidence_pack
from focus.llm.settings import LlmSettings, load_llm_settings, resolve_llm_captions
from focus.llm.weak import is_weak_caption

__all__ = [
    "CaptionEvidencePack",
    "LlmSettings",
    "apply_llm_captions",
    "build_evidence_pack",
    "is_weak_caption",
    "label_caption",
    "load_llm_settings",
    "resolve_llm_captions",
]
