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
    "identity", "voice", "boundaries", "arc", "role", "topic", "project", "faq",
)
KIND_ORDER = {kind: index for index, kind in enumerate(KINDS)}
PERIOD_KINDS = frozenset({"role", "project"})
SKIPPED_DIRS = frozenset({"raw"})
SKIPPED_FILES = frozenset({"README.md"})
TOKEN_WARNING_THRESHOLD = 60_000
CHARS_PER_TOKEN = 4

_PERIOD_RE = re.compile(r"^(\d{4})(?:-(\d{2}))? to (?:(\d{4})(?:-(\d{2}))?|present)$")


class KnowledgeError(TwinError):
    """Raised when the knowledge directory is missing or a file is invalid."""


@dataclass(frozen=True)
class KnowledgeFile:
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
            return (0, 0)
        year, month = match.group(1), match.group(2)
        return (int(year), int(month) if month else 1)


@dataclass(frozen=True)
class Knowledge:
    files: tuple[KnowledgeFile, ...]

    @property
    def estimated_tokens(self) -> int:
        chars = sum(len(f.title) + len(f.body) for f in self.files)
        return chars // CHARS_PER_TOKEN


def load_knowledge(root: Path) -> Knowledge:
    """Read every knowledge file under root, fail on any invalid one, return them ordered."""
    if not root.is_dir():
        raise KnowledgeError(f"Knowledge directory not found: {root}")

    candidates = sorted(p for p in root.rglob("*.md") if _is_candidate(p, root))
    parsed: list[KnowledgeFile] = []
    problems: list[str] = []
    for path in candidates:
        try:
            parsed.append(_parse_file(path, root))
        except KnowledgeError as exc:
            problems.append(str(exc))
    if problems:
        raise KnowledgeError("Invalid knowledge files:\n" + "\n".join(problems))

    ordered = tuple(sorted(parsed, key=lambda f: _sort_key(f, root)))
    knowledge = Knowledge(files=ordered)
    if knowledge.estimated_tokens > TOKEN_WARNING_THRESHOLD:
        log.warning(
            "Knowledge is roughly %d tokens, above the %d token threshold; "
            "consider the core-profile-plus-lookup design.",
            knowledge.estimated_tokens, TOKEN_WARNING_THRESHOLD,
        )
    return knowledge


def _is_candidate(path: Path, root: Path) -> bool:
    relative = path.relative_to(root)
    if relative.parts[0] in SKIPPED_DIRS:
        return False
    return relative.name not in SKIPPED_FILES


def _sort_key(file: KnowledgeFile, root: Path) -> tuple[int, int, str]:
    year, month = file.period_start
    recency = -(year * 100 + month) if file.kind == "role" else 0
    return (KIND_ORDER[file.kind], recency, file.path.relative_to(root).as_posix())


def _parse_file(path: Path, root: Path) -> KnowledgeFile:
    label = path.relative_to(root).as_posix()
    try:
        post = frontmatter.load(path, encoding="utf-8")
    except Exception as exc:  # frontmatter surfaces YAML errors as several types
        raise KnowledgeError(f"{label}: cannot parse frontmatter ({exc})") from exc

    meta: dict[str, Any] = dict(post.metadata)
    errors: list[str] = []

    if meta.get("public") is not True:
        errors.append("public must be exactly true")
    title = meta.get("title")
    if not isinstance(title, str) or not title.strip():
        errors.append("title is required")
    kind = meta.get("kind")
    if kind not in KIND_ORDER:
        errors.append(f"kind must be one of {', '.join(KINDS)}")
    period = meta.get("period")
    if kind in PERIOD_KINDS:
        if not isinstance(period, str) or _PERIOD_RE.match(period) is None:
            errors.append("period is required for roles and projects, as '<start> to <end>' "
                          "with YYYY or YYYY-MM ends, or 'present'")
    body = post.content.strip()
    if not body:
        errors.append("body is empty")
    tags = meta.get("tags") or []
    if not isinstance(tags, list) or not all(isinstance(t, str) for t in tags):
        errors.append("tags must be a list of strings")
    reviewed, reviewed_error = _normalise_reviewed(meta.get("reviewed"))
    if reviewed_error:
        errors.append(reviewed_error)

    if errors:
        raise KnowledgeError(f"{label}: " + "; ".join(errors))

    return KnowledgeFile(
        path=path,
        title=str(title).strip(),
        kind=str(kind),
        body=body,
        period=period if isinstance(period, str) else None,
        tags=tuple(tags),
        reviewed=reviewed,
    )


def _normalise_reviewed(value: Any) -> tuple[str | None, str | None]:
    """Return (iso_date, error). Both are None when the field is absent."""
    if value is None:
        return None, None
    if isinstance(value, dt.datetime):
        return value.date().isoformat(), None
    if isinstance(value, dt.date):
        return value.isoformat(), None
    if isinstance(value, str) and value.strip():
        return value.strip(), None
    return None, "reviewed must be a date"
