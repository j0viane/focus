"""Focus Scan — repository file discovery and AST fact extraction."""

from focus.scan.parser import parse_module, parse_source
from focus.scan.walker import discover_python_files

__all__ = ["discover_python_files", "parse_module", "parse_source"]
