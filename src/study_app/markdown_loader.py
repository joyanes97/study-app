from __future__ import annotations

import hashlib
import re
from pathlib import Path

from study_app.models import Topic


FRONTMATTER_RE = re.compile(r"\A---\n(.*?)\n---\n(.*)\Z", re.DOTALL)
HEADING_RE = re.compile(r"^#\s+(.*)$", re.MULTILINE)


def parse_frontmatter(text: str) -> tuple[dict[str, str], str]:
    match = FRONTMATTER_RE.match(text.strip())
    if not match:
        return {}, text.strip()
    raw_meta, body = match.groups()
    meta: dict[str, str] = {}
    for line in raw_meta.splitlines():
        if ":" not in line:
            continue
        key, value = line.split(":", 1)
        meta[key.strip()] = value.strip()
    return meta, body.strip()


def title_from_body(body: str, fallback: str) -> str:
    match = HEADING_RE.search(body)
    return match.group(1).strip() if match else fallback


def load_topics(
    content_dir: Path, default_priority: str, default_weight: float
) -> list[Topic]:
    topics: list[Topic] = []
    for path in sorted(content_dir.rglob("*.md")):
        if path.name.startswith("._"):
            continue
        text = path.read_text(encoding="utf-8")
        meta, body = parse_frontmatter(text)
        if meta.get("study_enabled", "true").lower() == "false":
            continue
        fallback = path.stem.replace("-", " ").replace("_", " ").strip().title()
        title = title_from_body(body, fallback)
        rel_parts = path.relative_to(content_dir).parts
        subject = meta.get("subject") or (
            rel_parts[0] if len(rel_parts) > 1 else "general"
        )
        topic_name = meta.get("topic") or (
            rel_parts[-2] if len(rel_parts) > 1 else path.stem
        )
        subtopic = meta.get("subtopic") or path.stem
        digest = hashlib.sha1(str(path).encode("utf-8")).hexdigest()[:12]
        topics.append(
            Topic(
                id=digest,
                subject=subject,
                topic=topic_name,
                subtopic=subtopic,
                source_path=path,
                priority=meta.get("priority", default_priority).lower(),
                estimated_weight=float(meta.get("estimated_weight", default_weight)),
                title=title,
                body=body,
            )
        )
    return topics
