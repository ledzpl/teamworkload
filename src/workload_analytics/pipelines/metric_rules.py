from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import PurePosixPath


LOCKFILE_NAMES = frozenset(
    {
        "package-lock.json",
        "pnpm-lock.yaml",
        "yarn.lock",
        "poetry.lock",
        "Cargo.lock",
    }
)
VENDORED_DIRECTORIES = frozenset({"vendor", "vendors", "third_party", "node_modules"})
GENERATED_DIRECTORIES = frozenset({"dist", "build", ".next", "coverage"})
GENERATED_SUFFIXES = (".generated.ts", ".generated.js", ".gen.ts", ".pb.go")


@dataclass(frozen=True, slots=True)
class FileChange:
    path: str
    lines_added: int
    lines_deleted: int


@dataclass(frozen=True, slots=True)
class GithubChangeSummary:
    lines_added: int
    lines_deleted: int
    included_paths: tuple[str, ...]
    excluded_paths: tuple[str, ...]


def summarize_github_changes(
    file_changes: Iterable[FileChange],
    *,
    is_merge_commit: bool,
) -> GithubChangeSummary:
    changes = tuple(file_changes)
    if is_merge_commit:
        return GithubChangeSummary(
            lines_added=0,
            lines_deleted=0,
            included_paths=(),
            excluded_paths=tuple(change.path for change in changes),
        )

    lines_added = 0
    lines_deleted = 0
    included_paths: list[str] = []
    excluded_paths: list[str] = []

    for change in changes:
        if should_exclude_file_path(change.path):
            excluded_paths.append(change.path)
            continue

        lines_added += change.lines_added
        lines_deleted += change.lines_deleted
        included_paths.append(change.path)

    return GithubChangeSummary(
        lines_added=lines_added,
        lines_deleted=lines_deleted,
        included_paths=tuple(included_paths),
        excluded_paths=tuple(excluded_paths),
    )


def should_exclude_commit(*, parent_count: int) -> bool:
    return parent_count > 1


def should_exclude_file_path(path: str) -> bool:
    normalized = PurePosixPath(path.strip())
    if not normalized.parts:
        return True

    if normalized.name in LOCKFILE_NAMES:
        return True

    if normalized.name.endswith(GENERATED_SUFFIXES):
        return True

    top_level = normalized.parts[0]
    if top_level in VENDORED_DIRECTORIES:
        return True
    if top_level in GENERATED_DIRECTORIES:
        return True

    return False
