"""Caption cache by pack fingerprint — no live LLM calls."""

from __future__ import annotations

from focus.llm.cache import (
    clear_caption_cache,
    get_cached_caption,
    pack_fingerprint,
    put_cached_caption,
)
from focus.llm.pack import CaptionEvidencePack, MeasuredSlots


def _pack(*, name: str = "fn") -> CaptionEvidencePack:
    return CaptionEvidencePack(
        path="a.py",
        symbol_name=name,
        symbol_kind="function",
        risk_tier="LOW",
        allowed_tokens=[name],
        measured=MeasuredSlots(),
    )


def test_pack_fingerprint_stable_and_model_sensitive():
    pack = _pack()
    a = pack_fingerprint(pack, model="qwen2.5-coder:3b")
    b = pack_fingerprint(pack, model="qwen2.5-coder:3b")
    c = pack_fingerprint(pack, model="qwen2.5-coder:7b")
    assert a == b
    assert a != c
    assert pack_fingerprint(_pack(name="other"), model="qwen2.5-coder:3b") != a


def test_memory_cache_round_trip():
    clear_caption_cache(disk=True)
    pack = _pack()
    key = pack_fingerprint(pack, model="test-model-unique")
    assert get_cached_caption(key) is None
    put_cached_caption(key, "Returns `ok`.")
    assert get_cached_caption(key) == "Returns `ok`."
    clear_caption_cache()
    # Disk may still hit after memory wipe.
    assert get_cached_caption(key) == "Returns `ok`."
    clear_caption_cache(disk=True)
    assert get_cached_caption(key) is None
