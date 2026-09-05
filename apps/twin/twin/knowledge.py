"""Load, validate, and order the markdown files that make up the twin's knowledge."""

from __future__ import annotations

import datetime as dt
import logging
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import frontmatter

from twin.errors import TwinError

log = logging.getLogger(__name__)

KINDS: tuple[str, ...] = (
    "identity",
    "voice",
    "boundaries",
    "arc",
    "role",
    "topic",
    "project",
    "faq",
)
KIND_ORDER = {kind: index for index, kind in enumerate(KINDS)}
PERIOD_KINDS = frozenset({"role", "project"})
# Only a top-level raw/ is skipped, matching the knowledge/raw/ anchor in .gitignore.
SKIPPED_TOP_LEVEL_DIRS = frozenset({"raw"})
SKIPPED_FILENAMES = frozenset({"readme.md"})  # compared case-insensitively
TOKEN_WARNING_THRESHOLD = 60_000
CHARS_PER_TOKEN = 4

_MONTH = r"(0[1-9]|1[0-2])"
_PERIOD_RE = re.compile(rf"^(\d{{4}})(?:-{_MONTH})? to (?:(\d{{4}})(?:-{_MONTH})?|present)$")
_PERIOD_HELP = "period must be '<start> to <end>' with YYYY or YYYY-MM ends, or 'present'"


class KnowledgeError(TwinError):
    """Raised when the knowledge directory is missing or a file is invalid."""


@dataclass(frozen=True)
class KnowledgeFile:
    """One validated knowledge file. `path` is relative to the knowledge root."""

    path: Path
    title: str
    kind: str
    body: str
    period: str | None = None
    tags: tuple[str, ...] = ()
    reviewed: str | None = None

    @property
    def period_start(self) -> tuple[int, int]:
        """(year, month) the period starts; a bare year sorts as January."""
        if self.period is None:
            return (0, 0)
        match = _PERIOD_RE.match(self.period)
        if match is None:
            raise ValueError(f"unparseable period: {self.period!r}")
        return (int(match.group(1)), int(match.group(2) or 1))


@dataclass(frozen=True)
class Knowledge:
    files: tuple[KnowledgeFile, ...]

    @property
    def estimated_tokens(self) -> int:
        """Rough size of titles and bodies at four characters per token; a lower bound for the prompt."""
        chars = sum(len(f.title) + len(f.body) for f in self.files)
        return chars // CHARS_PER_TOKEN


def load_knowledge(root: Path) -> Knowledge:
    """Read every knowledge file under root, fail on any invalid one, return them ordered."""
    if not root.is_dir():
        raise KnowledgeError(f"Knowledge directory not found: {root}")

    candidates = sorted(p for p in root.rglob("*.md", case_sensitive=True) if _is_candidate(p, root))
    parsed: list[KnowledgeFile] = []
    problems: list[str] = []
    for path in candidates:
        try:
            parsed.append(_parse_file(path, root))
        except KnowledgeError as exc:
            problems.append(str(exc))
    problems.extend(_duplicate_titles(parsed))
    if problems:
        raise KnowledgeError("Invalid knowledge files:\n" + "\n".join(problems))

    knowledge = Knowledge(files=tuple(sorted(parsed, key=_sort_key)))
    if knowledge.estimated_tokens > TOKEN_WARNING_THRESHOLD:
        log.warning(
            "Knowledge is roughly %d tokens, above the %d token threshold; "
            "consider the core-profile-plus-lookup design.",
            knowledge.estimated_tokens,
            TOKEN_WARNING_THRESHOLD,
        )
    return knowledge


def _is_candidate(path: Path, root: Path) -> bool:
    relative = path.relative_to(root)
    if relative.parts[0] in SKIPPED_TOP_LEVEL_DIRS:
        return False
    return relative.name.casefold() not in SKIPPED_FILENAMES


def _sort_key(file: KnowledgeFile) -> tuple[int, int, str]:
    year, month = file.period_start
    recency = -(year * 100 + month) if file.kind == "role" else 0
    return (KIND_ORDER[file.kind], recency, file.path.as_posix())


def _duplicate_titles(files: list[KnowledgeFile]) -> list[str]:
    """One problem line per file whose (kind, title) repeats an earlier file's."""
    first_seen: dict[tuple[str, str], Path] = {}
    problems: list[str] = []
    for file in files:
        key = (file.kind, file.title.casefold())
        earlier = first_seen.get(key)
        if earlier is None:
            first_seen[key] = file.path
        else:
            problems.append(
                f"{file.path.as_posix()}: duplicate {file.kind} title {file.title!r} "
                f"(also in {earlier.as_posix()})"
            )
    return problems


def _parse_file(path: Path, root: Path) -> KnowledgeFile:
    """Read one file (BOM tolerated) and hand its frontmatter and body to the validator."""
    relative = path.relative_to(root)
    try:
        post = frontmatter.load(path, encoding="utf-8-sig")
    except Exception as exc:  # frontmatter surfaces YAML errors as several types
        raise KnowledgeError(f"{relative.as_posix()}: cannot parse frontmatter ({exc})") from exc
    return _validate(relative, dict(post.metadata), post.content.strip())


def _validate(relative: Path, meta: dict[str, Any], body: str) -> KnowledgeFile:
    """Pure validation of one file's metadata and body. Raises KnowledgeError naming every problem."""
    errors: list[str] = []

    if meta.get("public") is not True:
        errors.append("public must be exactly true")

    title = meta.get("title")
    if not isinstance(title, str) or not title.strip():
        errors.append("title must be a non-empty string")
    if isinstance(title, str) and any(ch in title for ch in '<>"'):
        errors.append("title must not contain <, >, or double quotes")

    kind = meta.get("kind")
    kind_ok = isinstance(kind, str) and kind in KIND_ORDER
    if not kind_ok:
        errors.append(f"kind must be one of {', '.join(KINDS)}")

    period = meta.get("period")
    if kind_ok and kind in PERIOD_KINDS:
        errors.extend(_period_problems(period))
    elif kind_ok and period is not None:
        errors.append("period is only allowed on roles and projects")

    if not body:
        errors.append("body is empty")
    if "<section" in body or "</section>" in body:
        errors.append("body must not contain section tags")

    tags = meta.get("tags")
    if tags is None:
        tags = []
    if not isinstance(tags, list) or not all(isinstance(t, str) for t in tags):
        errors.append("tags must be a list of strings")
        tags = []

    reviewed: str | None = None
    try:
        reviewed = _normalise_reviewed(meta.get("reviewed"))
    except ValueError as exc:
        errors.append(str(exc))

    if errors:
        raise KnowledgeError(f"{relative.as_posix()}: " + "; ".join(errors))

    return KnowledgeFile(
        path=relative,
        title=str(title).strip(),
        kind=str(kind),
        body=body,
        period=period if isinstance(period, str) else None,
        tags=tuple(tags),
        reviewed=reviewed,
    )


def _period_problems(period: Any) -> list[str]:
    """Problems with a role or project period: missing, malformed, or ending before it starts."""
    if not isinstance(period, str):
        return [f"period is required for roles and projects; {_PERIOD_HELP}"]
    match = _PERIOD_RE.match(period)
    if match is None:
        return [_PERIOD_HELP]
    start = (int(match.group(1)), int(match.group(2) or 1))
    if match.group(3) is None:  # "to present"
        return []
    end = (int(match.group(3)), int(match.group(4) or 12))
    if end < start:
        return [f"period ends before it starts: {period!r}"]
    return []


def _normalise_reviewed(value: Any) -> str | None:
    """The reviewed date as an ISO string, or None when absent. Raises ValueError for anything else."""
    if value is None:
        return None
    if isinstance(value, dt.datetime):
        return value.date().isoformat()
    if isinstance(value, dt.date):
        return value.isoformat()
    if isinstance(value, str) and value.strip():
        return value.strip()
    raise ValueError("reviewed must be a date")
