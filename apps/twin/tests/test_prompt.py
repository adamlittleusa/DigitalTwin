from pathlib import Path

from twin import prompt as pm
from twin.knowledge import Knowledge, KnowledgeFile
from twin.prompt import build_system_prompt


def kf(kind: str, title: str, body: str, period: str | None = None) -> KnowledgeFile:
    return KnowledgeFile(path=Path(f"{title}.md"), title=title, kind=kind, body=body, period=period)


SAMPLE = Knowledge(files=(
    kf("identity", "Identity", "Adam is a security leader."),
    kf("role", "Recorded Future", "Four years in CTI.", period="2018-07 to 2022-08"),
    kf("faq", "FAQ", "Q: Are you real? A: I am an AI twin."),
))


def test_prompt_contains_every_title_as_heading() -> None:
    text = build_system_prompt(SAMPLE)
    assert "## Identity (identity)" in text
    assert "## Recorded Future (role, 2018-07 to 2022-08)" in text
    assert "## FAQ (faq)" in text


def test_bodies_are_included_unmodified() -> None:
    text = build_system_prompt(SAMPLE)
    for file in SAMPLE.files:
        assert file.body in text


def test_order_is_preserved() -> None:
    text = build_system_prompt(SAMPLE)
    assert text.index("## Identity") < text.index("## Recorded Future") < text.index("## FAQ")


def test_role_instructions_come_first_and_rules_last() -> None:
    text = build_system_prompt(SAMPLE)
    assert text.startswith(pm.ROLE_INSTRUCTIONS.strip())
    assert text.rstrip().endswith(pm.RULES.strip())
    assert text.index(pm.ROLE_INSTRUCTIONS.strip()) < text.index("## Identity") < text.index(pm.RULES.strip())


def test_rules_mention_all_three_tools() -> None:
    assert "record_unknown_question" in pm.RULES
    assert "record_user_details" in pm.RULES
    assert "record_sensitive_question" in pm.RULES


def test_prompt_names_the_person() -> None:
    assert pm.PERSON_NAME in build_system_prompt(SAMPLE)


def test_empty_knowledge_still_builds() -> None:
    text = build_system_prompt(Knowledge(files=()))
    assert pm.ROLE_INSTRUCTIONS.strip() in text


def test_each_file_is_wrapped_in_a_section_element() -> None:
    text = build_system_prompt(SAMPLE)
    expected = (
        '<section kind="identity" title="Identity">\n'
        "## Identity (identity)\n\n"
        "Adam is a security leader.\n"
        "</section>"
    )
    assert expected in text


def test_role_body_headings_stay_inside_their_section() -> None:
    two = Knowledge(files=(
        kf("role", "New", "## Context\n\nNew co.", period="2023-07 to present"),
        kf("role", "Old", "## Context\n\nOld co.", period="2018-07 to 2022-08"),
    ))
    text = build_system_prompt(two)
    new_start = text.index('<section kind="role" title="New">')
    new_end = text.index("</section>", new_start)
    old_start = text.index('<section kind="role" title="Old">')
    assert new_start < new_end < old_start
    assert "New co." in text[new_start:new_end]
    assert "Old co." not in text[new_start:new_end]


def test_sections_are_separated_by_blank_lines() -> None:
    text = build_system_prompt(SAMPLE)
    assert '\n\n<section kind="identity"' in text
    assert '</section>\n\n<section kind="role"' in text


def test_built_prompt_carries_the_tool_rules() -> None:
    text = build_system_prompt(SAMPLE)
    for tool in ("record_unknown_question", "record_sensitive_question", "record_user_details"):
        assert tool in text


def test_rules_state_tool_precedence_and_voice() -> None:
    assert "boundaries section first" in pm.RULES
    assert "never call both" in pm.RULES
    assert "As an AI language model" in pm.RULES
    assert "Never use code blocks" in pm.RULES


def test_role_instructions_explain_sections_and_periods() -> None:
    assert "<section>" in pm.ROLE_INSTRUCTIONS
    assert "newest first" in pm.ROLE_INSTRUCTIONS
    assert '"present"' in pm.ROLE_INSTRUCTIONS


def test_empty_knowledge_omits_the_knowledge_heading() -> None:
    text = build_system_prompt(Knowledge(files=()))
    assert pm.KNOWLEDGE_HEADING not in text
    assert text.startswith(pm.ROLE_INSTRUCTIONS.strip())
    assert text.rstrip().endswith(pm.RULES.strip())


def test_role_instructions_bridge_third_to_first_person() -> None:
    assert "written about Adam in the third person" in pm.ROLE_INSTRUCTIONS
    assert "answer as Adam in the first person" in pm.ROLE_INSTRUCTIONS


def test_rules_mention_show_project_once_per_reply() -> None:
    assert "show_project" in pm.RULES
    assert "at most once per reply" in pm.RULES


def test_project_sections_carry_a_slug_attribute() -> None:
    files = (
        KnowledgeFile(
            path=Path("projects/digital-twin.md"),
            title="Digital twin",
            kind="project",
            body="Adam built a digital twin.",
            period="2026-09 to present",
        ),
        kf("identity", "Identity", "Adam is a security leader."),
    )
    text = build_system_prompt(Knowledge(files=files))
    assert '<section kind="project" title="Digital twin" slug="digital-twin">' in text
    identity_start = text.index('<section kind="identity"')
    identity_end = text.index(">", identity_start)
    assert "slug=" not in text[identity_start:identity_end]
