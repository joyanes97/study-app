from __future__ import annotations

import base64
import hashlib
import os
import re
import subprocess
from pathlib import Path

import httpx

from study_app.content_document_validator import DocumentValidator
from study_app.settings import Settings
from study_app.study_store import load_pdf_ingest_index, save_pdf_ingest_index


def ingest_pdf_inbox(root: Path, settings: Settings, state_dir: Path) -> dict:
    media_dir = Path(settings.telegram_media_dir)
    inbox_dir = Path(settings.pdf_inbox_dir)
    raw_dir = root / "data" / "incoming-pdf"
    rendered_root = root / "data" / "ocr-pages"
    raw_dir.mkdir(parents=True, exist_ok=True)
    rendered_root.mkdir(parents=True, exist_ok=True)
    inbox_dir.mkdir(parents=True, exist_ok=True)

    index = load_pdf_ingest_index(state_dir)
    ingested: list[dict] = []
    pending_ocr: list[dict] = []

    if not media_dir.exists():
        return {"ingested": ingested, "pending_ocr": pending_ocr}

    for pdf_path in sorted(media_dir.glob("*.pdf")):
        if pdf_path.name.startswith("._"):
            continue
        try:
            DocumentValidator.validate_file(pdf_path)
        except ValueError as exc:
            index[str(pdf_path)] = {
                "hash": None,
                "mtime": pdf_path.stat().st_mtime,
                "status": "invalid",
                "mode": "validation_failed",
                "markdown_path": "",
                "source_pdf": str(pdf_path),
                "error": str(exc),
            }
            pending_ocr.append(
                {
                    "source_pdf": str(pdf_path),
                    "title": pdf_path.stem,
                    "error": str(exc),
                }
            )
            continue
        file_hash = sha1_file(pdf_path)
        previous = index.get(str(pdf_path))
        stat = pdf_path.stat()
        if (
            previous
            and previous.get("hash") == file_hash
            and previous.get("mtime") == stat.st_mtime
        ):
            continue

        archived_pdf = raw_dir / f"{safe_stem(pdf_path.stem)}-{file_hash[:8]}.pdf"
        if not archived_pdf.exists():
            archived_pdf.write_bytes(pdf_path.read_bytes())

        extracted = extract_pdf_text(pdf_path)
        if looks_like_real_text(extracted, settings.pdf_text_min_chars):
            markdown = text_to_markdown(extracted, pdf_path.stem)
            mode = "direct_text"
            status = "ingested"
        else:
            try:
                markdown = ocr_pdf_to_markdown(
                    pdf_path, rendered_root / file_hash, settings
                )
                mode = "glm_ocr"
                status = "ingested"
            except Exception as exc:
                markdown = ""
                mode = "glm_ocr"
                status = "pending_ocr"
                pending_ocr.append(
                    {
                        "source_pdf": str(pdf_path),
                        "title": pdf_path.stem,
                        "error": str(exc),
                    }
                )

        md_path = inbox_dir / f"{safe_stem(pdf_path.stem)}-{file_hash[:8]}.md"
        if status == "ingested":
            md_path.write_text(wrap_markdown(markdown, pdf_path), encoding="utf-8")
            ingested.append(
                {
                    "source_pdf": str(pdf_path),
                    "markdown_path": str(md_path),
                    "mode": mode,
                    "title": pdf_path.stem,
                }
            )

        index[str(pdf_path)] = {
            "hash": file_hash,
            "mtime": stat.st_mtime,
            "status": status,
            "mode": mode,
            "markdown_path": str(md_path),
            "source_pdf": str(pdf_path),
        }

    save_pdf_ingest_index(state_dir, index)
    return {"ingested": ingested, "pending_ocr": pending_ocr}


def extract_pdf_text(pdf_path: Path) -> str:
    result = subprocess.run(
        ["pdftotext", "-layout", "-nopgbrk", str(pdf_path), "-"],
        capture_output=True,
        text=True,
        check=False,
    )
    return clean_extracted_text(result.stdout)


def looks_like_real_text(text: str, min_chars: int) -> bool:
    stripped = text.strip()
    if len(stripped) < min_chars:
        return False
    alpha = sum(char.isalpha() for char in stripped)
    spaces = sum(char.isspace() for char in stripped)
    return alpha > min_chars // 3 and spaces > min_chars // 10


def ocr_pdf_to_markdown(pdf_path: Path, render_dir: Path, settings: Settings) -> str:
    render_dir.mkdir(parents=True, exist_ok=True)
    prefix = render_dir / "page"
    subprocess.run(
        [
            "pdftoppm",
            "-png",
            "-r",
            "160",
            "-f",
            "1",
            "-l",
            str(settings.pdf_max_pages),
            str(pdf_path),
            str(prefix),
        ],
        check=True,
        capture_output=True,
        text=True,
    )
    pages = sorted(render_dir.glob("page-*.png"))
    if not pages:
        raise RuntimeError("No pages rendered from PDF")

    markdown_pages = []
    for index, image_path in enumerate(pages, start=1):
        page_md = ocr_image_to_markdown(image_path, settings)
        cleaned = strip_code_fences(page_md).strip()
        if cleaned:
            markdown_pages.append(f"## Page {index}\n\n{cleaned}")
    if not markdown_pages:
        raise RuntimeError("GLM-OCR returned empty output")
    return "\n\n".join(markdown_pages)


def ocr_image_to_markdown(image_path: Path, settings: Settings) -> str:
    api_base = os.environ.get("GLM_OCR_API_BASE", settings.glm_ocr_api_base).rstrip("/")
    api_key = os.environ.get("GLM_OCR_API_KEY", "")
    model = settings.glm_ocr_model
    data_url = image_to_data_url(image_path)
    payload = {
        "model": model,
        "messages": [
            {
                "role": "user",
                "content": [
                    {
                        "type": "text",
                        "text": "Text Recognition: return clean markdown only. Preserve headings, lists and tables when possible.",
                    },
                    {
                        "type": "image_url",
                        "image_url": {"url": data_url},
                    },
                ],
            }
        ],
        "temperature": 0.1,
    }
    headers = {"Content-Type": "application/json"}
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"
    with httpx.Client(timeout=180) as client:
        response = client.post(
            f"{api_base}/chat/completions", json=payload, headers=headers
        )
        response.raise_for_status()
        data = response.json()
    return data["choices"][0]["message"]["content"]


def image_to_data_url(image_path: Path) -> str:
    raw = image_path.read_bytes()
    return f"data:image/png;base64,{base64.b64encode(raw).decode()}"


def text_to_markdown(text: str, title: str) -> str:
    cleaned = re.sub(r"\n{3,}", "\n\n", clean_extracted_text(text).strip())
    return f"# {title.strip()}\n\n{cleaned}".strip() + "\n"


def wrap_markdown(markdown: str, pdf_path: Path) -> str:
    title = pdf_path.stem.replace("-", " ").replace("_", " ").strip()
    frontmatter = [
        "---",
        "subject: inbox",
        f"topic: {title}",
        f"subtopic: {title}",
        "priority: medium",
        "estimated_weight: 0.5",
        f"source_pdf: {pdf_path}",
        "---",
        "",
    ]
    return "\n".join(frontmatter) + markdown.strip() + "\n"


def sha1_file(path: Path) -> str:
    digest = hashlib.sha1()
    with path.open("rb") as handle:
        while chunk := handle.read(1024 * 1024):
            digest.update(chunk)
    return digest.hexdigest()


def safe_stem(value: str) -> str:
    value = value.lower().strip()
    value = re.sub(r"[^a-z0-9]+", "-", value)
    return value.strip("-") or "document"


def strip_code_fences(text: str) -> str:
    stripped = text.strip()
    if stripped.startswith("```"):
        stripped = re.sub(r"^```[a-zA-Z0-9_-]*\n", "", stripped)
        stripped = re.sub(r"\n```$", "", stripped)
    return stripped


def clean_extracted_text(text: str) -> str:
    lines = []
    for raw_line in text.splitlines():
        line = raw_line.rstrip()
        if should_drop_line(line):
            continue
        line = re.sub(r"\s{2,}", " ", line).strip()
        if not line:
            lines.append("")
            continue
        lines.append(line)
    cleaned = "\n".join(lines)
    cleaned = re.sub(r"\n{3,}", "\n\n", cleaned)
    return cleaned.strip()


def should_drop_line(line: str) -> bool:
    stripped = line.strip()
    if not stripped:
        return False
    patterns = [
        r"www\.temarioopol\.com",
        r"©\s*Autor:\s*Francisco\s+Javier\s+Bejarano\s+M\.?",
        r"^\d+\s+Bloque\s+\d+.*$",
        r"^Bloque\s+\d+\s+Legislaci[oó]n$",
        r"^Polic[ií]a\s+Local\s+de\s+C[oó]rdoba\.?$",
        r"^P[aá]g\.\s*\d+$",
        r"^-{10,}$",
    ]
    return any(
        re.search(pattern, stripped, flags=re.IGNORECASE) for pattern in patterns
    )
