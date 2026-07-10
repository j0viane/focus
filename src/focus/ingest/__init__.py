"""Focus ingest — git diff and related change detection."""

from focus.ingest.diff import (
    GitDiffError,
    changed_files,
    changed_python_files,
    resolve_base_ref,
)

__all__ = [
    "GitDiffError",
    "changed_files",
    "changed_python_files",
    "resolve_base_ref",
]
