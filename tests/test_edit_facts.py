"""Portable edit-fact ledger — synthetic stranger-repo fixtures (no Focus lore)."""

from __future__ import annotations

from pathlib import Path

from focus.hud.edit_facts import (
    caption_for_overlapping_module_assign,
    importers_of_name,
    module_level_assignments,
    same_file_readers,
    scope_caption_for_module_assign,
)
from focus.hud.explain import caption_for_orphan_edit
from focus.models import Import, ModuleFacts
from focus.scan.parser import parse_source


_STRANGER = '''\
"""Tiny billing helper — not Focus."""

RETRY_LIMIT = 3

MAX_FEE = 100


def charge(amount: int) -> bool:
    if amount > MAX_FEE:
        return False
    return amount < RETRY_LIMIT * 10


def describe() -> str:
    return f"limit={RETRY_LIMIT}"
'''


def test_module_level_assignments_finds_constants() -> None:
    facts = module_level_assignments(_STRANGER)
    by_name = {a.name: a for a in facts}
    assert "RETRY_LIMIT" in by_name
    assert by_name["RETRY_LIMIT"].rhs == "3"
    assert by_name["RETRY_LIMIT"].line == 3
    assert "MAX_FEE" in by_name
    assert by_name["MAX_FEE"].rhs == "100"


def test_same_file_readers_def_use_chain() -> None:
    readers = same_file_readers("RETRY_LIMIT", _STRANGER)
    names = [r.name for r in readers]
    assert "charge" in names
    assert "describe" in names


def test_same_file_readers_single_use() -> None:
    readers = same_file_readers("MAX_FEE", _STRANGER)
    assert [r.name for r in readers] == ["charge"]


def test_importers_of_name_from_facts() -> None:
    changed = "billing/limits.py"
    facts_by_path = {
        changed: ModuleFacts(path=Path(changed), language="python"),
        "api/checkout.py": ModuleFacts(
            path=Path("api/checkout.py"),
            language="python",
            imports=[
                Import(module="billing.limits", symbols=["RETRY_LIMIT"], line=1),
            ],
        ),
        "jobs/retry.py": ModuleFacts(
            path=Path("jobs/retry.py"),
            language="python",
            imports=[
                Import(module="billing.limits", symbols=["*"], line=1),
            ],
        ),
        "unrelated.py": ModuleFacts(
            path=Path("unrelated.py"),
            language="python",
            imports=[
                Import(module="billing.limits", symbols=["MAX_FEE"], line=1),
            ],
        ),
    }
    importers = importers_of_name("RETRY_LIMIT", changed, facts_by_path)
    assert "api/checkout.py" in importers
    assert "jobs/retry.py" in importers
    assert "unrelated.py" not in importers


def test_scope_caption_readers_win() -> None:
    assigns = module_level_assignments(_STRANGER)
    retry = next(a for a in assigns if a.name == "RETRY_LIMIT")
    readers = same_file_readers("RETRY_LIMIT", _STRANGER)
    caption = scope_caption_for_module_assign(
        retry,
        readers=readers,
        importers=["api/checkout.py"],
    )
    assert caption is not None
    assert "Sets `RETRY_LIMIT` to `3`" in caption
    assert "read by `" in caption
    assert "in this file" in caption


def test_scope_caption_importers_only() -> None:
    assigns = module_level_assignments(_STRANGER)
    retry = next(a for a in assigns if a.name == "RETRY_LIMIT")
    caption = scope_caption_for_module_assign(
        retry,
        readers=[],
        importers=["api/checkout.py"],
    )
    assert caption == "Sets `RETRY_LIMIT` to `3` — imported by `api/checkout.py`"


def test_scope_caption_none_without_who() -> None:
    assigns = module_level_assignments(_STRANGER)
    retry = next(a for a in assigns if a.name == "RETRY_LIMIT")
    assert scope_caption_for_module_assign(retry, readers=[], importers=[]) is None


def test_clipped_long_rhs() -> None:
    source = (
        "BIG = (" + ", ".join(f"'{c}'" for c in "abcdefghijklmnopqrstuvwxyz") + ")\n"
        "\n"
        "def use():\n"
        "    return BIG[0]\n"
    )
    assigns = module_level_assignments(source)
    assert len(assigns) == 1
    caption = scope_caption_for_module_assign(
        assigns[0],
        readers=same_file_readers("BIG", source),
        importers=[],
    )
    assert caption is not None
    assert "Sets `BIG` to `" in caption
    assert "…" in caption
    assert "read by `use`" in caption


def test_orphan_caption_uses_reader_clause() -> None:
    """Constant edit yields reader clause — never the orphan fallback."""
    caption = caption_for_orphan_edit(
        ["RETRY_LIMIT = 5"],
        hunk_lines=[3],
        source_text=_STRANGER.replace("RETRY_LIMIT = 3", "RETRY_LIMIT = 5"),
        changed_path="billing/limits.py",
    )
    assert "Edited outside a changed function" not in caption
    assert "Sets `RETRY_LIMIT`" in caption
    assert "read by `" in caption


def test_overlapping_helper_on_stranger_fixture() -> None:
    edited = _STRANGER.replace("MAX_FEE = 100", "MAX_FEE = 250")
    caption = caption_for_overlapping_module_assign(
        source_text=edited,
        hunk_lines=[5],
        changed_path="billing/limits.py",
        facts_by_path=None,
    )
    assert caption is not None
    assert "Sets `MAX_FEE` to `250`" in caption
    assert "read by `charge`" in caption


def test_ann_assign_supported() -> None:
    source = "LIMIT: int = 7\n\ndef check():\n    return LIMIT\n"
    assigns = module_level_assignments(source)
    assert len(assigns) == 1
    assert assigns[0].name == "LIMIT"
    assert assigns[0].rhs == "7"


def test_parse_source_still_lean() -> None:
    """ModuleFacts stays lean — edit facts are on-demand, not in the full-repo scan."""
    facts = parse_source(_STRANGER.encode(), Path("billing/limits.py"))
    assert facts.definitions
    assert not hasattr(facts, "assignments")
