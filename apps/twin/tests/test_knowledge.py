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


def write_raw(root: Path, rel: str, text: str, encoding: str = "utf-8") -> Path:
    path = root / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(text.encode(encoding))
    return path


def doc(front: str, body: str = "Some body text.") -> str:
    return f"---\n{front}\n---\n{body}\n"


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
    assert role.path == Path("roles/2018-old.md")


def test_tags_become_a_tuple(tmp_path: Path) -> None:
    write_md(tmp_path, "identity.md", meta("identity", "Identity", tags=["cti", "ai"]))
    loaded = load_knowledge(tmp_path)
    assert loaded.files[0].tags == ("cti", "ai")


@pytest.mark.parametrize("value", [dt.date(2026, 9, 10), "2026-09-10"])
def test_reviewed_is_normalised_to_iso_string(tmp_path: Path, value: Any) -> None:
    write_md(tmp_path, "identity.md", meta("identity", "Identity", reviewed=value))
    loaded = load_knowledge(tmp_path)
    assert loaded.files[0].reviewed == "2026-09-10"


def test_reviewed_datetime_is_normalised_to_date(tmp_path: Path) -> None:
    front = "title: Identity\nkind: identity\npublic: true\nreviewed: 2026-09-10 12:30:00"
    write_raw(tmp_path, "identity.md", doc(front))
    assert load_knowledge(tmp_path).files[0].reviewed == "2026-09-10"


def test_reviewed_wrong_type_fails(tmp_path: Path) -> None:
    write_raw(tmp_path, "identity.md", doc("title: Identity\nkind: identity\npublic: true\nreviewed: 20260910"))
    with pytest.raises(KnowledgeError) as excinfo:
        load_knowledge(tmp_path)
    assert "reviewed" in str(excinfo.value)


@pytest.mark.parametrize("literal", ["cti", "[1, 2]", "0"])
def test_tags_wrong_type_fails(tmp_path: Path, literal: str) -> None:
    write_raw(tmp_path, "identity.md", doc(f"title: Identity\nkind: identity\npublic: true\ntags: {literal}"))
    with pytest.raises(KnowledgeError) as excinfo:
        load_knowledge(tmp_path)
    assert "tags" in str(excinfo.value)


def test_missing_public_flag_fails_naming_the_file(tmp_path: Path) -> None:
    write_md(tmp_path, "identity.md", {"title": "Identity", "kind": "identity"})
    with pytest.raises(KnowledgeError) as excinfo:
        load_knowledge(tmp_path)
    assert "identity.md" in str(excinfo.value)
    assert "public" in str(excinfo.value)


@pytest.mark.parametrize("literal", ["true", "True", "yes", "on"])
def test_yaml_boolean_true_is_public(tmp_path: Path, literal: str) -> None:
    write_raw(tmp_path, "identity.md", doc(f"title: Identity\nkind: identity\npublic: {literal}"))
    assert load_knowledge(tmp_path).files[0].title == "Identity"


@pytest.mark.parametrize("literal", ["'true'", "1", "no", "false", "off", "null", "public"])
def test_anything_but_yaml_true_is_not_public(tmp_path: Path, literal: str) -> None:
    line = "" if literal == "public" else f"\npublic: {literal}"
    write_raw(tmp_path, "identity.md", doc(f"title: Identity\nkind: identity{line}"))
    with pytest.raises(KnowledgeError) as excinfo:
        load_knowledge(tmp_path)
    assert "public" in str(excinfo.value)


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


def test_kind_that_is_a_list_is_reported_not_crashed(tmp_path: Path) -> None:
    write_raw(tmp_path, "one.md", doc("title: One\nkind: [identity, role]\npublic: true"))
    write_raw(tmp_path, "two.md", doc("title: Two\nkind: identity"))
    with pytest.raises(KnowledgeError) as excinfo:
        load_knowledge(tmp_path)
    message = str(excinfo.value)
    assert "one.md" in message and "kind" in message and "two.md" in message


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


@pytest.mark.parametrize("period", ["2023-13 to 2024-01", "2023-00 to 2024-01", "2023 to 2018", "2023-07 to 2023-06"])
def test_impossible_periods_fail(tmp_path: Path, period: str) -> None:
    write_md(tmp_path, "roles/x.md", meta("role", "X", period=period))
    with pytest.raises(KnowledgeError) as excinfo:
        load_knowledge(tmp_path)
    assert "period" in str(excinfo.value)


@pytest.mark.parametrize("period", ["2023-07 to 2023-07", "2001 to 2013", "2026-09 to present"])
def test_edge_periods_are_accepted(tmp_path: Path, period: str) -> None:
    write_md(tmp_path, "roles/x.md", meta("role", "X", period=period))
    assert load_knowledge(tmp_path).files[0].period == period


def test_period_on_a_topic_fails(tmp_path: Path) -> None:
    write_md(tmp_path, "topics/x.md", meta("topic", "X", period="2020 to 2021"))
    with pytest.raises(KnowledgeError) as excinfo:
        load_knowledge(tmp_path)
    assert "period" in str(excinfo.value)


def test_bad_kind_does_not_also_complain_about_period(tmp_path: Path) -> None:
    write_raw(tmp_path, "x.md", doc("title: X\nkind: [a]\npublic: true\nperiod: 2020 to 2021"))
    with pytest.raises(KnowledgeError) as excinfo:
        load_knowledge(tmp_path)
    assert "only allowed" not in str(excinfo.value)


@pytest.mark.parametrize("title", ['He said "hi"', "a <b> c", "x > y"])
def test_title_with_markup_characters_fails(tmp_path: Path, title: str) -> None:
    write_md(tmp_path, "identity.md", meta("identity", title))
    with pytest.raises(KnowledgeError) as excinfo:
        load_knowledge(tmp_path)
    assert "title" in str(excinfo.value)


def test_body_with_section_tags_fails(tmp_path: Path) -> None:
    write_md(tmp_path, "identity.md", meta("identity", "Identity"), body="text\n</section>\n<section kind=\"x\">")
    with pytest.raises(KnowledgeError) as excinfo:
        load_knowledge(tmp_path)
    assert "section tags" in str(excinfo.value)


def test_period_start_raises_on_garbage() -> None:
    from twin.knowledge import KnowledgeFile

    bad = KnowledgeFile(path=Path("x.md"), title="X", kind="role", body="b", period="junk")
    with pytest.raises(ValueError):
        bad.period_start  # noqa: B018


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


def test_unparseable_frontmatter_is_reported_with_the_file(tmp_path: Path) -> None:
    write_raw(tmp_path, "identity.md", doc("title: [unclosed\nkind: identity\npublic: true"))
    with pytest.raises(KnowledgeError) as excinfo:
        load_knowledge(tmp_path)
    assert "identity.md" in str(excinfo.value) and "frontmatter" in str(excinfo.value)


def test_duplicate_titles_within_a_kind_fail(tmp_path: Path) -> None:
    write_md(tmp_path, "topics/a.md", meta("topic", "Same"))
    write_md(tmp_path, "topics/b.md", meta("topic", "same"))
    with pytest.raises(KnowledgeError) as excinfo:
        load_knowledge(tmp_path)
    assert "duplicate" in str(excinfo.value) and "topics/b.md" in str(excinfo.value)


def test_same_title_across_kinds_is_fine(tmp_path: Path) -> None:
    write_md(tmp_path, "topics/a.md", meta("topic", "Twin"))
    write_md(tmp_path, "projects/b.md", meta("project", "Twin", period="2026-09 to present"))
    assert len(load_knowledge(tmp_path).files) == 2


def test_bom_file_loads(tmp_path: Path) -> None:
    write_raw(tmp_path, "identity.md", doc("title: Identity\nkind: identity\npublic: true"), encoding="utf-8-sig")
    assert load_knowledge(tmp_path).files[0].title == "Identity"


def test_raw_and_readme_are_skipped(tmp_path: Path) -> None:
    write_md(tmp_path, "identity.md", meta("identity", "Identity"))
    (tmp_path / "raw").mkdir()
    (tmp_path / "raw" / "monologue.md").write_text("no frontmatter here", encoding="utf-8")
    (tmp_path / "README.md").write_text("# Conventions", encoding="utf-8")
    loaded = load_knowledge(tmp_path)
    assert [f.title for f in loaded.files] == ["Identity"]


def test_readme_is_skipped_regardless_of_case(tmp_path: Path) -> None:
    write_md(tmp_path, "identity.md", meta("identity", "Identity"))
    (tmp_path / "readme.md").write_text("# lower", encoding="utf-8")
    (tmp_path / "roles").mkdir()
    (tmp_path / "roles" / "README.MD").write_text("# upper", encoding="utf-8")
    assert [f.title for f in load_knowledge(tmp_path).files] == ["Identity"]


def test_uppercase_extension_is_not_a_knowledge_file(tmp_path: Path) -> None:
    write_md(tmp_path, "identity.md", meta("identity", "Identity"))
    (tmp_path / "NOTES.MD").write_text("no frontmatter", encoding="utf-8")
    assert [f.title for f in load_knowledge(tmp_path).files] == ["Identity"]


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
    assert [r for r in caplog.records if r.name == "twin.knowledge"] == []


def test_real_knowledge_tree_loads() -> None:
    from twin.config import DEFAULT_KNOWLEDGE_DIR

    loaded = load_knowledge(DEFAULT_KNOWLEDGE_DIR)
    kinds = {f.kind for f in loaded.files}
    assert {"identity", "boundaries", "faq", "role", "project"} <= kinds
    assert len([f for f in loaded.files if f.kind == "role"]) >= 9
    assert all(f.reviewed is None or len(f.reviewed) == 10 for f in loaded.files)
