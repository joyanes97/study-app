from __future__ import annotations

import mimetypes
import os
import re
from pathlib import Path
from typing import ClassVar


class DocumentValidator:
    MAX_FILE_SIZE: ClassVar[int] = 100 * 1024 * 1024
    MAX_PDF_SIZE: ClassVar[int] = 50 * 1024 * 1024

    ALLOWED_EXTENSIONS: ClassVar[set[str]] = {
        ".pdf",
        ".txt",
        ".md",
        ".doc",
        ".docx",
        ".rtf",
        ".html",
        ".htm",
        ".xml",
        ".json",
        ".csv",
        ".xlsx",
        ".xls",
        ".pptx",
        ".ppt",
    }

    ALLOWED_MIME_TYPES: ClassVar[set[str]] = {
        "application/pdf",
        "text/plain",
        "text/markdown",
        "application/msword",
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        "application/rtf",
        "text/html",
        "application/xml",
        "text/xml",
        "application/json",
        "text/csv",
        "application/vnd.ms-excel",
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        "application/vnd.ms-powerpoint",
        "application/vnd.openxmlformats-officedocument.presentationml.presentation",
    }

    @staticmethod
    def validate_upload_safety(
        filename: str,
        file_size: int | None,
        allowed_extensions: set[str] | None = None,
    ) -> str:
        if file_size is not None and file_size > DocumentValidator.MAX_FILE_SIZE:
            raise ValueError(
                f"File too large: {file_size} bytes. Maximum allowed: {DocumentValidator.MAX_FILE_SIZE} bytes"
            )

        _, ext = os.path.splitext(filename.lower())
        if (
            ext == ".pdf"
            and file_size is not None
            and file_size > DocumentValidator.MAX_PDF_SIZE
        ):
            raise ValueError(
                f"PDF file too large: {file_size} bytes. Maximum allowed for PDFs: {DocumentValidator.MAX_PDF_SIZE} bytes"
            )

        safe_name = os.path.basename(filename)
        safe_name = re.sub(r"[\x00-\x1f\x7f]", "", safe_name)
        safe_name = re.sub(r'[<>:"/\\|?*]', "_", safe_name)

        if not safe_name or safe_name in (".", "..") or safe_name.strip("_") == "":
            raise ValueError("Invalid filename")

        exts_to_check = allowed_extensions or DocumentValidator.ALLOWED_EXTENSIONS
        if ext not in exts_to_check:
            raise ValueError(
                f"Unsupported file type: {ext}. Allowed types: {', '.join(sorted(exts_to_check))}"
            )

        guessed_mime, _ = mimetypes.guess_type(filename.lower())
        if guessed_mime and guessed_mime not in DocumentValidator.ALLOWED_MIME_TYPES:
            raise ValueError(
                f"MIME type validation failed: {guessed_mime}. File may be malicious or corrupted."
            )

        return safe_name

    @staticmethod
    def validate_file(path: str | Path) -> dict:
        file_path = Path(path)
        if not file_path.exists():
            raise ValueError(f"File not found: {file_path}")
        if not file_path.is_file():
            raise ValueError(f"Not a file: {file_path}")
        if not os.access(file_path, os.R_OK):
            raise ValueError(f"File not readable: {file_path}")

        size = file_path.stat().st_size
        safe_name = DocumentValidator.validate_upload_safety(file_path.name, size)
        _, ext = os.path.splitext(safe_name.lower())
        return {
            "filename": safe_name,
            "extension": ext,
            "size_bytes": size,
            "size_mb": round(size / (1024 * 1024), 2),
            "is_allowed": ext in DocumentValidator.ALLOWED_EXTENSIONS,
        }
