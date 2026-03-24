from __future__ import annotations

import re
from pathlib import Path

from study_app.markdown_loader import parse_frontmatter


def split_block_markdown(path: Path, output_dir: Path) -> list[Path]:
    text = path.read_text(encoding="utf-8")
    meta, body = parse_frontmatter(text)
    title = first_heading(body) or path.stem.replace("-", " ").title()
    topic_numbers = topic_numbers_from_title(title)
    if len(topic_numbers) <= 1:
        return []

    chunks = split_body_into_chunks(body, len(topic_numbers))
    written: list[Path] = []
    output_dir.mkdir(parents=True, exist_ok=True)
    block_slug = slugify(title)
    base_weight = float(meta.get("estimated_weight", 0.5))
    per_topic_weight = max(0.2, round(base_weight / len(topic_numbers), 2))

    for number, chunk in zip(topic_numbers, chunks):
        topic_title = f"Tema {number}"
        frontmatter = [
            "---",
            f"subject: {meta.get('subject', 'temario')}",
            f"topic: {topic_title}",
            f"subtopic: {title}",
            f"priority: {meta.get('priority', 'medium')}",
            f"estimated_weight: {per_topic_weight}",
            f"source_block: {path.name}",
            "---",
            "",
            f"# {topic_title}",
            "",
        ]
        out_path = output_dir / f"{block_slug}-tema-{number:02d}.md"
        out_path.write_text(
            "\n".join(frontmatter) + chunk.strip() + "\n", encoding="utf-8"
        )
        written.append(out_path)

    updated = set_study_enabled_false(text)
    path.write_text(updated, encoding="utf-8")
    return written


def topic_numbers_from_title(title: str) -> list[int]:
    upper = title.upper()
    ranges = re.findall(r"DEL\s+(\d+)\s+AL\s+(\d+)", upper)
    values: list[int] = []
    if ranges:
        for start, end in ranges:
            values.extend(range(int(start), int(end) + 1))
        extras = re.findall(r"\bY\s+(\d+)\b", upper)
        for extra in extras:
            extra_value = int(extra)
            if extra_value not in values:
                values.append(extra_value)
        return values

    pairs = re.findall(r"TEMAS?\s+(\d+)\s+Y\s+(\d+)", upper)
    if pairs:
        start, end = pairs[0]
        return [int(start), int(end)]

    single = re.findall(r"\bTEMA\s+(\d+)\b", upper)
    return [int(item) for item in single]


def split_body_into_chunks(body: str, count: int) -> list[str]:
    content = strip_main_heading(body)
    paragraphs = [
        paragraph.strip()
        for paragraph in re.split(r"\n\s*\n", content)
        if paragraph.strip()
    ]
    if count <= 1 or not paragraphs:
        return [content]

    total_chars = sum(len(p) for p in paragraphs)
    target = max(1, total_chars // count)
    chunks: list[list[str]] = []
    current: list[str] = []
    current_chars = 0
    remaining_paragraphs = len(paragraphs)

    for paragraph in paragraphs:
        remaining_slots = count - len(chunks)
        min_remaining = max(0, remaining_slots - 1)
        if current and current_chars >= target and remaining_paragraphs > min_remaining:
            chunks.append(current)
            current = []
            current_chars = 0
        current.append(paragraph)
        current_chars += len(paragraph)
        remaining_paragraphs -= 1

    if current:
        chunks.append(current)

    while len(chunks) < count:
        chunks.append([""])
    while len(chunks) > count:
        tail = chunks.pop()
        chunks[-1].extend(tail)

    return ["\n\n".join(chunk).strip() for chunk in chunks]


def strip_main_heading(body: str) -> str:
    lines = body.splitlines()
    if lines and lines[0].startswith("# "):
        return "\n".join(lines[1:]).strip()
    return body.strip()


def first_heading(body: str) -> str | None:
    for line in body.splitlines():
        if line.startswith("# "):
            return line[2:].strip()
    return None


def slugify(value: str) -> str:
    value = value.lower().strip()
    value = re.sub(r"[^a-z0-9]+", "-", value)
    return value.strip("-") or "topic"


def set_study_enabled_false(text: str) -> str:
    meta, body = parse_frontmatter(text)
    meta["study_enabled"] = "false"
    lines = ["---"]
    for key, value in meta.items():
        lines.append(f"{key}: {value}")
    lines.extend(["---", "", body.strip(), ""])
    return "\n".join(lines)
