from __future__ import annotations

from pathlib import Path

from study_app.models import Topic
from study_app.source_normalizer import ensure_normalized_source


def notebook_name(topic: Topic) -> str:
    return f"{topic.subject} - {topic.topic}".strip()


def build_batch_script(root: Path, topics: list[Topic]) -> str:
    lines = [
        "#!/usr/bin/env bash",
        "set -euo pipefail",
        "",
        "# Generated NotebookLM helper script",
        "# Run notebooklm login before using this batch.",
        "",
    ]
    for topic in topics:
        out_base = root / "data" / "generated" / topic.id
        source = ensure_normalized_source(root, topic)
        lines.extend(
            [
                f"# {topic.title}",
                f'notebooklm create "{notebook_name(topic)}"',
                "# notebooklm use <notebook_id>",
                f'notebooklm source add "{source}"',
                "notebooklm generate flashcards --difficulty medium --quantity more --wait",
                f'notebooklm download flashcards --format json "{out_base}-cards.json"',
                "notebooklm generate quiz --difficulty hard --quantity standard --wait",
                f'notebooklm download quiz --format json "{out_base}-quiz.json"',
                "",
            ]
        )
    return "\n".join(lines).rstrip() + "\n"
