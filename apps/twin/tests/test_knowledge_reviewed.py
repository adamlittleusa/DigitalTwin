"""Every knowledge file that ships must carry a reviewed date; this gate runs in CI."""

from twin.config import DEFAULT_KNOWLEDGE_DIR
from twin.knowledge import load_knowledge


def test_every_committed_knowledge_file_is_reviewed() -> None:
    knowledge = load_knowledge(DEFAULT_KNOWLEDGE_DIR)
    unreviewed = sorted(str(file.path) for file in knowledge.files if not file.reviewed)
    assert not unreviewed, f"Set a reviewed date on: {unreviewed}"
