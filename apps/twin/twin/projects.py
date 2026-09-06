"""Project cards the twin can show, built from the knowledge files of kind project."""

from __future__ import annotations

import re
from dataclasses import asdict, dataclass

from twin.knowledge import Knowledge, KnowledgeFile

SUMMARY_LIMIT = 280
_TRUNCATION_MARK = "…"
_SUMMARY_HEADING = "what it is"


@dataclass(frozen=True)
class ProjectCard:
    slug: str
    title: str
    summary: str
    url: str

    def as_dict(self) -> dict[str, str]:
        return asdict(self)


class ProjectCatalog:
    def __init__(self, cards: tuple[ProjectCard, ...]) -> None:
        self._cards = cards
        self._by_slug = {card.slug: card for card in cards}

    @classmethod
    def from_knowledge(cls, knowledge: Knowledge, site_url: str) -> ProjectCatalog:
        base = site_url.rstrip("/")
        return cls(tuple(_card(file, base) for file in knowledge.files if file.kind == "project"))

    @property
    def cards(self) -> tuple[ProjectCard, ...]:
        return self._cards

    @property
    def slugs(self) -> tuple[str, ...]:
        return tuple(card.slug for card in self._cards)

    def get(self, slug: str) -> ProjectCard | None:
        return self._by_slug.get(slug)


def _card(file: KnowledgeFile, base: str) -> ProjectCard:
    slug = file.path.stem
    return ProjectCard(slug=slug, title=file.title, summary=_summary(file.body), url=f"{base}/projects/{slug}")


def _summary(body: str) -> str:
    return _cut(_section_paragraph(body, _SUMMARY_HEADING) or _first_paragraph(body), SUMMARY_LIMIT)


def _paragraphs(text: str) -> list[str]:
    return [p.strip() for p in re.split(r"\n\s*\n", text) if p.strip()]


def _section_paragraph(body: str, heading: str) -> str | None:
    """The first paragraph under a '## <heading>' line, or None when the heading is absent or empty."""
    paragraphs = _paragraphs(body)
    for index, paragraph in enumerate(paragraphs):
        if paragraph.lstrip("#").strip().lower() == heading and index + 1 < len(paragraphs):
            following = paragraphs[index + 1]
            return None if following.startswith("#") else following
    return None


def _first_paragraph(body: str) -> str:
    for paragraph in _paragraphs(body):
        if not paragraph.startswith("#"):
            return paragraph
    return ""


def _cut(text: str, limit: int) -> str:
    text = " ".join(text.split())
    if len(text) <= limit:
        return text
    head = text[: limit - len(_TRUNCATION_MARK)]
    if " " in head:
        head = head.rsplit(" ", 1)[0]
    return head.rstrip(",.;:") + _TRUNCATION_MARK
