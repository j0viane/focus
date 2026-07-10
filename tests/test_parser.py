"""Parser facts are verified two ways: parametrized snippets covering
every Python import shape, and the glass_box fixture where the correct
answers are known by reading the files."""

from pathlib import Path

import pytest

from focus.scan import parse_module, parse_source

FAKE_PATH = Path("snippet.py")


@pytest.mark.parametrize(
    ("source", "module", "symbols", "alias"),
    [
        ("import os", "os", [], None),
        ("import os.path", "os.path", [], None),
        ("import numpy as np", "numpy", [], "np"),
        ("from pathlib import Path", "pathlib", ["Path"], None),
        (
            "from billing.service import charge_user, refund",
            "billing.service",
            ["charge_user", "refund"],
            None,
        ),
        ("from collections import OrderedDict as OD", "collections", ["OrderedDict"], None),
        ("from . import sibling", ".", ["sibling"], None),
        ("from .relative import thing", ".relative", ["thing"], None),
        ("from ..pkg import other", "..pkg", ["other"], None),
        ("from os import *", "os", ["*"], None),
    ],
)
def test_import_shapes(source: str, module: str, symbols: list[str], alias: str | None):
    facts = parse_source(source.encode(), FAKE_PATH)
    assert len(facts.imports) == 1
    imp = facts.imports[0]
    assert imp.module == module
    assert imp.symbols == symbols
    assert imp.alias == alias
    assert imp.line == 1


def test_multiple_imports_on_one_line():
    facts = parse_source(b"import os, sys", FAKE_PATH)
    assert [imp.module for imp in facts.imports] == ["os", "sys"]


def test_imports_inside_functions_are_found():
    source = b"def lazy():\n    import json\n    return json\n"
    facts = parse_source(source, FAKE_PATH)
    assert [imp.module for imp in facts.imports] == ["json"]
    assert facts.imports[0].line == 2


def test_definitions_functions_classes_and_methods():
    source = b"def top(): ...\nclass Greeter:\n    def greet(self): ...\n"
    facts = parse_source(source, FAKE_PATH)
    assert [(d.name, d.kind, d.line) for d in facts.definitions] == [
        ("top", "function", 1),
        ("Greeter", "class", 2),
        ("greet", "function", 3),
    ]


def test_calls_record_callee_as_written():
    source = b"import os\nos.getcwd()\nprint(len('x'))\n"
    facts = parse_source(source, FAKE_PATH)
    assert {(c.callee, c.line) for c in facts.calls} == {
        ("os.getcwd", 2),
        ("print", 3),
        ("len", 3),
    }


def test_glass_box_billing_service(glass_box_path: Path):
    facts = parse_module(glass_box_path / "billing" / "service.py")

    assert len(facts.imports) == 1
    assert facts.imports[0].module == "auth_utils"
    assert facts.imports[0].symbols == ["validate_token"]

    assert [(d.name, d.kind) for d in facts.definitions] == [("charge_user", "function")]

    callees = {c.callee for c in facts.calls}
    assert "validate_token" in callees


def test_glass_box_routes_import_billing(glass_box_path: Path):
    facts = parse_module(glass_box_path / "api" / "routes.py")

    assert [(i.module, i.symbols) for i in facts.imports] == [("billing.service", ["charge_user"])]
    assert "charge_user" in {c.callee for c in facts.calls}
    assert ("_Router", "class") in {(d.name, d.kind) for d in facts.definitions}


def test_glass_box_auth_utils_has_no_imports(glass_box_path: Path):
    facts = parse_module(glass_box_path / "auth_utils.py")
    assert facts.imports == []
    assert [d.name for d in facts.definitions] == ["validate_token", "hash_password"]


def test_syntactically_broken_file_does_not_crash():
    facts = parse_source(b"def broken(:\n    import os\n", FAKE_PATH)
    assert isinstance(facts.imports, list)
