from pathlib import Path

from tests.fakes import IDENTITY_META, project_meta, write_md
from twin.knowledge import load_knowledge
from twin.projects import SUMMARY_LIMIT, ProjectCatalog


def test_catalog_builds_cards_from_project_files(tmp_path: Path) -> None:
    write_md(tmp_path, "identity.md", IDENTITY_META, "Adam.")
    write_md(
        tmp_path,
        "projects/digital-twin.md",
        project_meta("Digital twin"),
        "## What it is\n\nA conversational agent that represents Adam.\n\n## Why\n\nBecause.",
    )
    write_md(tmp_path, "projects/other-thing.md", project_meta("Other thing"), "First paragraph here.\n\nSecond.")
    catalog = ProjectCatalog.from_knowledge(load_knowledge(tmp_path), "https://example.test/")
    assert catalog.slugs == ("digital-twin", "other-thing")
    card = catalog.get("digital-twin")
    assert card is not None
    assert card.title == "Digital twin"
    assert card.summary == "A conversational agent that represents Adam."
    assert card.url == "https://example.test/projects/digital-twin"
    other = catalog.get("other-thing")
    assert other is not None
    assert other.summary == "First paragraph here."
    assert catalog.get("nope") is None


def test_summary_is_cut_at_a_word_boundary(tmp_path: Path) -> None:
    long = ("word " * 100).strip()
    write_md(tmp_path, "projects/p.md", project_meta("P"), f"## What it is\n\n{long}")
    card = ProjectCatalog.from_knowledge(load_knowledge(tmp_path), "https://x").get("p")
    assert card is not None
    assert len(card.summary) <= SUMMARY_LIMIT
    assert card.summary.endswith("…")
    assert not card.summary[:-1].endswith(" ")


def test_empty_catalog_when_no_projects(tmp_path: Path) -> None:
    write_md(tmp_path, "identity.md", IDENTITY_META, "Adam.")
    catalog = ProjectCatalog.from_knowledge(load_knowledge(tmp_path), "https://x")
    assert catalog.cards == ()
    assert catalog.slugs == ()


def test_card_as_dict(tmp_path: Path) -> None:
    write_md(tmp_path, "projects/p.md", project_meta("P"), "Body.")
    card = ProjectCatalog.from_knowledge(load_knowledge(tmp_path), "https://x").get("p")
    assert card is not None
    assert card.as_dict() == {"slug": "p", "title": "P", "summary": "Body.", "url": "https://x/projects/p"}
