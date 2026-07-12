
from focus.audit import orphan_line_explanations
from focus.models import ChangedSymbolInfo, LineExplanation


def test_orphan_line_explanations_flags_uncovered_hunks() -> None:
    symbols = [
        ChangedSymbolInfo(
            path="pkg/mod.py",
            name="foo",
            kind="function",
            line=10,
            changed_lines=[12, 13],
        )
    ]
    ranges = {"pkg/mod.py": [(1, 2), (12, 13)]}

    orphans = orphan_line_explanations(symbols, ranges)

    assert orphans == [
        LineExplanation(
            path="pkg/mod.py",
            line=1,
            changed_lines=[1, 2],
            detail=(
                "Edited outside a changed function — check the HUD map "
                "for file-level blast radius."
            ),
        )
    ]
