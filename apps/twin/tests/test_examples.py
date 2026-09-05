from twin.examples import EXAMPLE_QUESTIONS


def test_example_questions_are_four_complete_sentences() -> None:
    assert isinstance(EXAMPLE_QUESTIONS, tuple)
    assert len(EXAMPLE_QUESTIONS) == 4
    for question in EXAMPLE_QUESTIONS:
        assert question.strip() == question
        assert question[-1] in ".?"


def test_example_questions_are_distinct() -> None:
    assert len(set(EXAMPLE_QUESTIONS)) == len(EXAMPLE_QUESTIONS)
