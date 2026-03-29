from __future__ import annotations

import re
from pathlib import Path

from study_app.models import Topic


def content_type_for_topic(topic: Topic) -> str:
    path = str(topic.source_path).lower()
    if "/practicals/" in path or "supuestos" in topic.title.lower():
        return "practical"
    return "theory"


def normalized_source_path(root: Path, topic: Topic) -> Path:
    content_type = content_type_for_topic(topic)
    subdir = "practicals" if content_type == "practical" else "theory"
    return root / "data" / "content_normalized" / subdir / f"{topic.id}.txt"


def ensure_normalized_source(root: Path, topic: Topic) -> Path:
    path = normalized_source_path(root, topic)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(normalize_topic_for_notebooklm(topic), encoding="utf-8")
    return path


def normalize_topic_for_notebooklm(topic: Topic) -> str:
    content_type = content_type_for_topic(topic)
    body = topic.body
    if content_type == "practical":
        cleaned = _normalize_practical_body(body)
    else:
        cleaned = _normalize_theory_body(body)
    header = [topic.title.strip(), topic.subtopic.strip(), ""]
    return "\n".join([line for line in header if line]) + "\n" + cleaned.strip() + "\n"


def _normalize_theory_body(body: str) -> str:
    lines = []
    for raw in body.splitlines():
        line = raw.strip()
        if not line:
            lines.append("")
            continue
        if line.startswith("#"):
            continue
        line = _strip_markdown_noise(line)
        line = re.sub(r"^[•➢❖✓◦·]\s*", "", line)
        line = re.sub(r"\s{2,}", " ", line).strip()
        if line:
            lines.append(line)
    cleaned = "\n".join(lines)
    cleaned = re.sub(r"\n{3,}", "\n\n", cleaned)
    return cleaned


def _normalize_practical_body(body: str) -> str:
    cleaned = _strip_markdown_noise(body)
    cleaned = re.sub(
        r"^##\s+Supuesto\s+Pr[áa]ctico\s*",
        "Supuesto práctico ",
        cleaned,
        flags=re.MULTILINE,
    )
    cleaned = re.sub(r"^\*\*([^*]+)\*\*:\s*", r"\1: ", cleaned, flags=re.MULTILINE)
    cleaned = re.sub(r"^[•➢❖✓◦·]\s*", "", cleaned, flags=re.MULTILINE)
    cleaned = re.sub(r"\n{3,}", "\n\n", cleaned)
    return cleaned.strip()


def _strip_markdown_noise(text: str) -> str:
    text = re.sub(r"```[\s\S]*?```", "", text)
    text = re.sub(r"^#{1,6}\s*", "", text, flags=re.MULTILINE)
    text = re.sub(r"\*\*(.*?)\*\*", r"\1", text)
    text = re.sub(r"__(.*?)__", r"\1", text)
    text = re.sub(r"`([^`]+)`", r"\1", text)
    text = re.sub(r"^>\s*", "", text, flags=re.MULTILINE)
    text = re.sub(r"\[(.*?)\]\((.*?)\)", r"\1", text)
    return text
