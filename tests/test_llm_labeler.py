"""Evidence-pack caption labeler — no live API calls in CI."""

from __future__ import annotations

from focus.config import FocusConfig
from focus.llm.pack import (
    CaptionEvidencePack,
    MeasuredSlots,
    build_evidence_pack,
    pack_contains_secrets,
)
from focus.llm.settings import resolve_llm_captions
from focus.llm.validate import validate_label
from focus.llm.weak import is_weak_caption
from focus.models import ChangedSymbolInfo


def test_is_weak_caption_empty_and_generic():
    assert is_weak_caption("")
    assert is_weak_caption("Other code may call this.")
    assert is_weak_caption("`foo` — see implementation.", symbol_name="foo")
    assert not is_weak_caption("Returns `ok`.")
    assert not is_weak_caption("Added a blank line.")
    assert not is_weak_caption("Calls `enrich_changed_symbols(…)` here.")


def test_build_evidence_pack_caps_edit_lines():
    source = [f"line {i}" for i in range(1, 40)]
    changed = list(range(1, 30))
    symbol = ChangedSymbolInfo(
        path="mod.py",
        name="do_thing",
        kind="function",
        line=1,
        changed_lines=changed,
        detail="",
    )
    pack = build_evidence_pack(
        symbol,
        risk="HIGH",
        implication="🟠 HIGH — callers — a bad change fails auth",
        purpose_hint="does a thing",
        source_lines=source,
    )
    assert isinstance(pack, CaptionEvidencePack)
    assert len(pack.edit_lines) <= 20
    assert pack.implication_who == "callers"
    assert "do_thing" in pack.allowed_tokens
    assert pack.risk_tier == "HIGH"


def test_pack_rejects_secret_bearing_lines():
    symbol = ChangedSymbolInfo(
        path="cfg.py",
        name="load",
        kind="function",
        line=1,
        changed_lines=[1],
    )
    pack = build_evidence_pack(
        symbol,
        risk="LOW",
        source_lines=['api_key = "sk-abcdefghijklmnopqrstuvwxyz012345"'],
    )
    assert pack_contains_secrets(pack) is True


def test_validate_label_caps_and_rejects_hops():
    pack = CaptionEvidencePack(
        path="a.py",
        symbol_name="fn",
        symbol_kind="function",
        risk_tier="MEDIUM",
        allowed_tokens=["fn", "helper"],
        measured=MeasuredSlots(),
    )
    assert validate_label("Calls `helper` after the edit.", pack) == (
        "Calls `helper` after the edit."
    )
    assert validate_label("Touches 3 hops away.", pack) is None
    assert validate_label("This is CRITICAL somehow.", pack) is None
    long = "x" * 200
    clipped = validate_label(long, pack)
    assert clipped is not None
    assert len(clipped) <= 110
    assert clipped.endswith("…")
    # Clip that tears a `code` span open must fail closed (dogfood: dangling backtick).
    torn = "x" * 105 + " `helper` tail"
    assert validate_label(torn, pack) is None


def test_validate_rejects_unknown_backticks():
    """Fail closed: inventing a caller name is rejected, not stripped and kept."""
    pack = CaptionEvidencePack(
        path="a.py",
        symbol_name="fn",
        symbol_kind="function",
        risk_tier="LOW",
        allowed_tokens=["fn"],
    )
    assert validate_label("Mentions `InventedCaller` and `fn`.", pack) is None


def test_validate_rejects_ungrounded_camelcase_and_scope():
    pack = CaptionEvidencePack(
        path="a.py",
        symbol_name="fn",
        symbol_kind="function",
        risk_tier="LOW",
        allowed_tokens=["fn"],
        measured=MeasuredSlots(),
    )
    assert validate_label("Delegates to AuthService here.", pack) is None
    assert validate_label("Handles authentication for callers.", pack) is None
    assert validate_label("Touches 2 hops of downstream files.", pack) is None


def test_validate_allows_scope_when_implication_names_callers():
    pack = CaptionEvidencePack(
        path="a.py",
        symbol_name="fn",
        symbol_kind="function",
        risk_tier="HIGH",
        implication_who="callers",
        implication_what="a bad change fails auth",
        allowed_tokens=["fn"],
        measured=MeasuredSlots(),
    )
    out = validate_label("Risky for callers if auth breaks.", pack)
    assert out == "Risky for callers if auth breaks."


def test_validate_allows_measured_return_restatement():
    pack = CaptionEvidencePack(
        path="mod.py",
        symbol_name="do_thing",
        symbol_kind="function",
        risk_tier="LOW",
        deterministic_caption="",
        allowed_tokens=["do_thing", "helper"],
        measured=MeasuredSlots(return_expr="helper()", callees=["helper"]),
    )
    out = validate_label("Returns `helper`.", pack)
    assert out == "Returns `helper`."


def test_resolve_llm_captions_defaults_and_overlay_off(monkeypatch):
    monkeypatch.delenv("FOCUS_LLM_ENABLED", raising=False)
    monkeypatch.delenv("FOCUS_LLM_API_KEY", raising=False)
    monkeypatch.delenv("FOCUS_LLM_BASE_URL", raising=False)
    monkeypatch.setenv("FOCUS_LLM_PROVIDER", "openai")
    assert resolve_llm_captions() is False
    assert resolve_llm_captions(force=True) is False  # openai needs a key
    monkeypatch.setenv("FOCUS_LLM_API_KEY", "test-key")
    monkeypatch.setenv("FOCUS_LLM_ENABLED", "true")
    # ENABLED alone must not turn captions on (IDE autosave safety).
    assert resolve_llm_captions() is False
    assert resolve_llm_captions(force=True) is True
    assert resolve_llm_captions(overlays={"a.py": "x"}) is False
    assert resolve_llm_captions(config=FocusConfig(llm_captions=True)) is True
    assert resolve_llm_captions(force=False) is False


def test_resolve_llm_captions_ollama_key_optional(monkeypatch):
    monkeypatch.delenv("FOCUS_LLM_API_KEY", raising=False)
    monkeypatch.delenv("FOCUS_LLM_ENABLED", raising=False)
    monkeypatch.setenv("FOCUS_LLM_PROVIDER", "ollama")
    assert resolve_llm_captions() is False
    assert resolve_llm_captions(force=True) is True
    monkeypatch.setenv("FOCUS_LLM_ENABLED", "true")
    assert resolve_llm_captions() is False
    assert resolve_llm_captions(overlays={"a.py": "x"}) is False
    assert resolve_llm_captions(force=False) is False


def test_build_client_ollama_uses_local_base_url():
    from focus.llm.clients import DEFAULT_OLLAMA_MODEL, OpenAIClient, build_client
    from focus.llm.settings import DEFAULT_OLLAMA_BASE_URL, LlmSettings

    client = build_client(
        LlmSettings(provider="ollama", enabled=True, api_key=None, model=None, base_url=None)
    )
    assert isinstance(client, OpenAIClient)
    assert client.base_url == DEFAULT_OLLAMA_BASE_URL.rstrip("/")
    assert client.model == DEFAULT_OLLAMA_MODEL
    assert client.api_key == "ollama"

    custom = build_client(
        LlmSettings(
            provider="ollama",
            base_url="http://localhost:11434/v1/",
            model="qwen2.5-coder:7b",
        )
    )
    assert isinstance(custom, OpenAIClient)
    assert custom.base_url == "http://localhost:11434/v1"
    assert custom.model == "qwen2.5-coder:7b"


def test_openai_client_posts_to_base_url(monkeypatch):
    from focus.llm.clients import OpenAIClient

    captured: dict = {}

    class _FakeResp:
        def raise_for_status(self) -> None:
            return None

        def json(self) -> dict:
            return {
                "choices": [
                    {"message": {"content": '{"detail": "Returns `helper`."}'}}
                ]
            }

    class _FakeHttp:
        def __init__(self, *args, **kwargs) -> None:
            pass

        def __enter__(self):
            return self

        def __exit__(self, *args) -> None:
            return None

        def post(self, url, headers=None, json=None):
            captured["url"] = url
            captured["headers"] = headers
            captured["json"] = json
            return _FakeResp()

    monkeypatch.setattr("focus.llm.clients.httpx.Client", _FakeHttp)
    client = OpenAIClient(
        api_key="ollama",
        model="qwen2.5:7b",
        base_url="http://127.0.0.1:11434/v1",
    )
    out = client.label({"symbol_name": "fn"})
    assert out == "Returns `helper`."
    assert captured["url"] == "http://127.0.0.1:11434/v1/chat/completions"
    assert captured["json"]["model"] == "qwen2.5:7b"


class _FakeClient:
    def __init__(self, detail: str) -> None:
        self.detail = detail
        self.calls = 0

    def label(self, pack_json):
        self.calls += 1
        return self.detail


def test_label_caption_validates_mocked_client():
    from focus.llm.labeler import label_caption

    symbol = ChangedSymbolInfo(
        path="a.py",
        name="fn",
        kind="function",
        line=2,
        changed_lines=[2],
        detail="",
    )
    pack = build_evidence_pack(
        symbol,
        risk="LOW",
        source_lines=["", "return helper()", ""],
    )
    pack = pack.model_copy(
        update={"allowed_tokens": sorted({*pack.allowed_tokens, "helper"})},
    )
    client = _FakeClient("Returns result of `helper`.")
    out = label_caption(pack, client=client)
    assert out == "Returns result of `helper`."
    assert client.calls == 1


def test_apply_llm_captions_skips_test_paths():
    from focus.hud.explain import ExplainContext
    from focus.llm.labeler import apply_llm_captions
    from focus.models import SymbolExplanation

    symbol = ChangedSymbolInfo(
        path="tests/test_llm_labeler.py",
        name="raise_for_status",
        kind="function",
        line=1,
        changed_lines=[1],
        detail="",
    )

    class _Boom:
        def label(self, pack_json):
            raise AssertionError("LLM must not run on tests/")

    context = ExplainContext(
        symbols=[symbol],
        graph=__import__("networkx").DiGraph(),
        seeds=[],
        danger_paths=set(),
        downstream_count=0,
        risk="LOW",
        facts_by_path={},
    )
    out = apply_llm_captions(
        [SymbolExplanation(symbol=symbol, text="")],
        context=context,
        client=_Boom(),
    )
    assert out[0].symbol.detail == ""


def test_apply_llm_captions_labels_strong_and_weak():
    """Everywhere: strong Returns/blank captions are also LLM candidates."""
    from focus.hud.explain import ExplainContext
    from focus.llm.labeler import apply_llm_captions
    from focus.models import HunkDetail, SymbolExplanation

    blank = ChangedSymbolInfo(
        path="a.py",
        name="fn",
        kind="function",
        line=1,
        changed_lines=[1],
        detail="Added a blank line.",
        hunk_details=[
            HunkDetail(line=1, changed_lines=[1], detail="Added a blank line."),
        ],
    )
    strong = ChangedSymbolInfo(
        path="b.py",
        name="go",
        kind="function",
        line=1,
        changed_lines=[1],
        detail="Returns `helper`.",
        hunk_details=[
            HunkDetail(line=1, changed_lines=[1], detail="Returns `helper`."),
        ],
    )
    weak = ChangedSymbolInfo(
        path="c.py",
        name="helper",
        kind="function",
        line=1,
        changed_lines=[1],
        detail="Other code may call this.",
        hunk_details=[
            HunkDetail(line=1, changed_lines=[1], detail="Other code may call this."),
        ],
    )

    class _Client:
        def __init__(self) -> None:
            self.calls = 0

        def label(self, pack_json):
            self.calls += 1
            name = pack_json.get("symbol_name", "")
            return f"Labeled `{name}`."

    client = _Client()
    context = ExplainContext(
        symbols=[blank, strong, weak],
        graph=__import__("networkx").DiGraph(),
        seeds=[],
        danger_paths=set(),
        downstream_count=0,
        risk="LOW",
        facts_by_path={},
    )
    out = apply_llm_captions(
        [
            SymbolExplanation(symbol=blank, text=""),
            SymbolExplanation(symbol=strong, text=""),
            SymbolExplanation(symbol=weak, text=""),
        ],
        context=context,
        client=client,
    )
    assert client.calls == 3
    assert out[0].symbol.detail == "Labeled `fn`."
    assert out[1].symbol.detail == "Labeled `go`."
    assert out[2].symbol.detail == "Labeled `helper`."
    assert any(e.kind == "llm_label" for e in out[2].symbol.evidence)


_ORPHAN_SOURCE = '''\
"""Stranger repo — retry policy."""

WEAK_PHRASES = (
    "maybe",
    "unclear",
)


def is_weak(text: str) -> bool:
    """True when the text sounds uncertain."""
    return any(p in text for p in WEAK_PHRASES)
'''


def _orphan_line() -> "LineExplanation":
    from focus.models import LineExplanation

    return LineExplanation(
        path="policy/weak.py",
        line=3,
        changed_lines=[3, 4, 5, 6],
        detail="Sets `WEAK_PHRASES` to `( \"maybe\",…` — read by `is_weak` in this file",
    )


def _orphan_facts() -> dict:
    from pathlib import Path

    from focus.models import Definition, ModuleFacts

    return {
        "policy/weak.py": ModuleFacts(
            path=Path("policy/weak.py"),
            language="python",
            definitions=[
                Definition(
                    name="is_weak",
                    kind="function",
                    line=10,
                    docstring="True when the text sounds uncertain.",
                )
            ],
        )
    }


def test_orphan_pack_carries_ledger_facts():
    from focus.llm.pack import build_orphan_evidence_pack

    pack = build_orphan_evidence_pack(
        path="policy/weak.py",
        name="WEAK_PHRASES",
        risk="LOW",
        run_lines=[3, 4, 5, 6],
        source_lines=_ORPHAN_SOURCE.splitlines(),
        deterministic_caption="Sets `WEAK_PHRASES` …",
        readers=["is_weak"],
        importers=["api/moderate.py"],
        reader_doc="True when the text sounds uncertain.",
    )
    assert pack.symbol_kind == "constant"
    assert pack.readers == ["is_weak"]
    assert pack.importers == ["api/moderate.py"]
    assert "is_weak" in pack.allowed_tokens
    assert "moderate.py" in pack.allowed_tokens


def test_validate_accepts_grounded_reader_mention():
    from focus.llm.pack import build_orphan_evidence_pack

    pack = build_orphan_evidence_pack(
        path="policy/weak.py",
        name="WEAK_PHRASES",
        risk="LOW",
        run_lines=[3],
        source_lines=_ORPHAN_SOURCE.splitlines(),
        deterministic_caption="",
        readers=["is_weak"],
        importers=[],
        reader_doc="True when the text sounds uncertain.",
    )
    out = validate_label("Adds a phrase so `is_weak` flags more text.", pack)
    assert out == "Adds a phrase so `is_weak` flags more text."
    # Fail closed: reader the ledger never measured.
    assert validate_label("Now `score_toxicity` flags more text.", pack) is None


def test_apply_llm_line_captions_labels_module_assign(monkeypatch, tmp_path):
    from focus.llm.labeler import apply_llm_line_captions

    # Real file on disk so _source_for_pack can read it.
    target = tmp_path / "weak.py"
    target.write_text(_ORPHAN_SOURCE)
    facts = _orphan_facts()
    facts["policy/weak.py"] = facts["policy/weak.py"].model_copy(
        update={"path": target}
    )

    client = _FakeClient("Adds a phrase so `is_weak` flags more text.")
    out = apply_llm_line_captions(
        [_orphan_line()],
        risk="LOW",
        facts_by_path=facts,
        client=client,
    )
    assert out[0].detail == "Adds a phrase so `is_weak` flags more text."
    assert client.calls == 1


def test_apply_llm_line_captions_keeps_deterministic_on_ungrounded(tmp_path):
    from focus.llm.labeler import apply_llm_line_captions

    target = tmp_path / "weak.py"
    target.write_text(_ORPHAN_SOURCE)
    facts = _orphan_facts()
    facts["policy/weak.py"] = facts["policy/weak.py"].model_copy(
        update={"path": target}
    )

    before = _orphan_line()
    client = _FakeClient("Now `InventedHelper` rejects all captions downstream.")
    out = apply_llm_line_captions(
        [before],
        risk="LOW",
        facts_by_path=facts,
        client=client,
    )
    # Fail closed — deterministic ledger caption survives.
    assert out[0].detail == before.detail


def test_apply_llm_line_captions_labels_assign_without_who(tmp_path):
    """Everywhere: module assigns without readers still get a pack + label attempt."""
    from focus.llm.labeler import apply_llm_line_captions
    from focus.models import LineExplanation, ModuleFacts

    source = "UNUSED = 1\n"
    target = tmp_path / "lonely.py"
    target.write_text(source)
    facts = {"pkg/lonely.py": ModuleFacts(path=target, language="python")}

    client = _FakeClient("Sets an unused module constant.")
    item = LineExplanation(
        path="pkg/lonely.py",
        line=1,
        changed_lines=[1],
        detail="Sets `UNUSED` to `1`.",
    )
    out = apply_llm_line_captions(
        [item],
        risk="LOW",
        facts_by_path=facts,
        client=client,
    )
    assert client.calls == 1
    assert out[0].detail == "Sets an unused module constant."


def test_apply_llm_captions_parallel_preserves_order(monkeypatch):
    import threading
    import time

    from focus.hud.explain import ExplainContext
    from focus.llm.labeler import apply_llm_captions
    from focus.models import SymbolExplanation

    monkeypatch.setenv("FOCUS_LLM_CONCURRENCY", "4")

    class _ParallelClient:
        def __init__(self) -> None:
            self._lock = threading.Lock()
            self.active = 0
            self.max_active = 0

        def label(self, pack_json):
            with self._lock:
                self.active += 1
                self.max_active = max(self.max_active, self.active)
            time.sleep(0.05)
            with self._lock:
                self.active -= 1
            name = pack_json.get("symbol_name", "x")
            return f"Labeled {name}."

    symbols = [
        ChangedSymbolInfo(path="a.py", name=f"fn{i}", kind="function", line=1, changed_lines=[1], detail="")
        for i in range(6)
    ]
    client = _ParallelClient()
    context = ExplainContext(
        symbols=symbols,
        graph=__import__("networkx").DiGraph(),
        seeds=[],
        danger_paths=set(),
        downstream_count=0,
        risk="LOW",
        facts_by_path={},
    )
    out = apply_llm_captions(
        [SymbolExplanation(symbol=s, text="") for s in symbols],
        context=context,
        client=client,
    )
    assert [o.symbol.detail for o in out] == [f"Labeled fn{i}." for i in range(6)]
    assert client.max_active >= 2
