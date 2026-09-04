import datetime as dt
import logging
from pathlib import Path
from typing import Any

import pytest
import yaml

from twin import knowledge as kn
from twin.knowledge import KnowledgeError, load_knowledge


def write_md(root: Path, rel: str, meta: dict[str, Any], body: str = "Some body text.") -> Path:
    path = root / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    text = "---\n" + yaml.safe_dump(meta, sort_keys=False) + "---\n" + body + "\n"
    path.write_text(text, encoding="utf-8")
    return path


def meta(kind: str, title: str, **extra: Any) -> dict[str, Any]:
    return {"title": title, "kind": kind, "public": True, **extra}


@pytest.fixture
def tree(tmp_path: Path) -> Path:
    write_md(tmp_path, "faq.md", meta("faq", "FAQ"))
    write_md(tmp_path, "identity.md", meta("identity", "Identity"))
    write_md(tmp_path, "voice.md", meta("voice", "Voice"))
    write_md(tmp_path, "boundaries.md", meta("boundaries", "Boundaries"))
    write_md(tmp_path, "career-arc.md", meta("arc", "Career arc"))
    write_md(tmp_path, "roles/2018-old.md", meta("role", "Old role", period="2018-07 to 2022-08"))
    write_md(tmp_path, "roles/2023-new.md", meta("role", "New role", period="2023-07 to present"))
    write_md(tmp_path, "roles/2001-army.md", meta("role", "Army", period="2001 to 2013"))
    write_md(tmp_path, "topics/b-topic.md", meta("topic", "Topic B"))
    write_md(tmp_path, "topics/a-topic.md", meta("topic", "Topic A"))
    write_md(tmp_path, "projects/twin.md", meta("project", "Twin", period="2026-09 to present"))
    return tmp_path


def test_valid_tree_loads_in_documented_order(tree: Path) -> None:
    loaded = load_knowledge(tree)
    assert [f.kind for f in loaded.files] == [
        "identity", "voice", "boundaries", "arc",
        "role", "role", "role",
        "topic", "topic",
        "project",
        "faq",
    ]


def test_roles_are_newest_first(tree: Path) -> None:
    loaded = load_knowledge(tree)
    roles = [f.title for f in loaded.files if f.kind == "role"]
    assert roles == ["New role", "Old role", "Army"]


def test_topics_sort_by_filename(tree: Path) -> None:
    loaded = load_knowledge(tree)
    topics = [f.title for f in loaded.files if f.kind == "topic"]
    assert topics == ["Topic A", "Topic B"]


def test_file_fields_are_parsed(tree: Path) -> None:
    loaded = load_knowledge(tree)
    role = next(f for f in loaded.files if f.title == "Old role")
    assert role.period == "2018-07 to 2022-08"
    assert role.body == "Some body text."
    assert role.tags == ()
    assert role.reviewed is None


def test_tags_become_a_tuple(tmp_path: Path) -> None:
    write_md(tmp_path, "identity.md", meta("identity", "Identity", tags=["cti", "ai"]))
    loaded = load_knowledge(tmp_path)
    assert loaded.files[0].tags == ("cti", "ai")


@pytest.mark.parametrize("value", [dt.date(2026, 9, 10), "2026-09-10"])
def test_reviewed_is_normalised_to_iso_string(tmp_path: Path, value: Any) -> None:
    write_md(tmp_path, "identity.md", meta("identity", "Identity", reviewed=value))
    loaded = load_knowledge(tmp_path)
    assert loaded.files[0].reviewed == "2026-09-10"


def test_missing_public_flag_fails_naming_the_file(tmp_path: Path) -> None:
    write_md(tmp_path, "identity.md", {"title": "Identity", "kind": "identity"})
    with pytest.raises(KnowledgeError) as excinfo:
        load_knowledge(tmp_path)
    assert "identity.md" in str(excinfo.value)
    assert "public" in str(excinfo.value)


def test_public_must_be_exactly_true(tmp_path: Path) -> None:
    write_md(tmp_path, "identity.md", {"title": "Identity", "kind": "identity", "public": "yes"})
    with pytest.raises(KnowledgeError):
        load_knowledge(tmp_path)


def test_missing_title_fails(tmp_path: Path) -> None:
    write_md(tmp_path, "identity.md", {"kind": "identity", "public": True})
    with pytest.raises(KnowledgeError) as excinfo:
        load_knowledge(tmp_path)
    assert "title" in str(excinfo.value)


def test_bad_kind_fails(tmp_path: Path) -> None:
    write_md(tmp_path, "x.md", meta("biography", "X"))
    with pytest.raises(KnowledgeError) as excinfo:
        load_knowledge(tmp_path)
    assert "kind" in str(excinfo.value)


def test_role_without_period_fails(tmp_path: Path) -> None:
    write_md(tmp_path, "roles/x.md", meta("role", "X"))
    with pytest.raises(KnowledgeError) as excinfo:
        load_knowledge(tmp_path)
    assert "period" in str(excinfo.value)


@pytest.mark.parametrize("period", ["2018 - 2022", "July 2018 to now", "2018-7 to 2022-08"])
def test_malformed_period_fails(tmp_path: Path, period: str) -> None:
    write_md(tmp_path, "roles/x.md", meta("role", "X", period=period))
    with pytest.raises(KnowledgeError):
        load_knowledge(tmp_path)


def test_empty_body_fails(tmp_path: Path) -> None:
    write_md(tmp_path, "identity.md", meta("identity", "Identity"), body="")
    with pytest.raises(KnowledgeError) as excinfo:
        load_knowledge(tmp_path)
    assert "empty" in str(excinfo.value).lower()


def test_all_invalid_files_are_reported_together(tmp_path: Path) -> None:
    write_md(tmp_path, "one.md", {"title": "One", "kind": "identity"})
    write_md(tmp_path, "two.md", {"title": "Two", "kind": "nope", "public": True})
    with pytest.raises(KnowledgeError) as excinfo:
        load_knowledge(tmp_path)
    assert "one.md" in str(excinfo.value) and "two.md" in str(excinfo.value)


def test_raw_and_readme_are_skipped(tmp_path: Path) -> None:
    write_md(tmp_path, "identity.md", meta("identity", "Identity"))
    (tmp_path / "raw").mkdir()
    (tmp_path / "raw" / "monologue.md").write_text("no frontmatter here", encoding="utf-8")
    (tmp_path / "README.md").write_text("# Conventions", encoding="utf-8")
    loaded = load_knowledge(tmp_path)
    assert [f.title for f in loaded.files] == ["Identity"]


def test_missing_directory_fails(tmp_path: Path) -> None:
    with pytest.raises(KnowledgeError):
        load_knowledge(tmp_path / "nope")


def test_token_estimate_and_warning(
    tmp_path: Path, caplog: pytest.LogCaptureFixture, monkeypatch: pytest.MonkeyPatch
) -> None:
    write_md(tmp_path, "identity.md", meta("identity", "Identity"), body="x" * 400)
    monkeypatch.setattr(kn, "TOKEN_WARNING_THRESHOLD", 50)
    with caplog.at_level(logging.WARNING, logger="twin.knowledge"):
        loaded = load_knowledge(tmp_path)
    assert loaded.estimated_tokens >= 100
    assert any("token" in record.message.lower() for record in caplog.records)


def test_no_warning_under_threshold(tmp_path: Path, caplog: pytest.LogCaptureFixture) -> None:
    write_md(tmp_path, "identity.md", meta("identity", "Identity"))
    with caplog.at_level(logging.WARNING, logger="twin.knowledge"):
        load_knowledge(tmp_path)
    assert not caplog.records
