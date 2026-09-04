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
