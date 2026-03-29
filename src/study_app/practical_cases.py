from __future__ import annotations

import os
import re
from pathlib import Path

import httpx

from study_app.pdf_ingest import clean_extracted_text, text_to_markdown


SECTION_ALIASES = {
    "titulo": "title",
    "título": "title",
    "contexto": "context",
    "hechos": "facts",
    "actuacion policial": "police_action",
    "actuación policial": "police_action",
    "diligencias o documentacion": "documents",
    "diligencias o documentación": "documents",
    "diligencias": "documents",
    "documentacion": "documents",
    "documentación": "documents",
    "resolucion final": "resolution",
    "resolución final": "resolution",
    "fundamentacion juridica": "legal_basis",
    "fundamentación jurídica": "legal_basis",
}


def generate_practical_cases(source_markdown: str, output_path: Path) -> Path:
    prompt = build_prompt(source_markdown)
    content = call_local_qwen(prompt)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(content.strip() + "\n", encoding="utf-8")
    return output_path


def build_prompt(source_markdown: str) -> str:
    sample = clean_extracted_text(source_markdown)[:14000]
    return (
        "Genera 12 supuestos prácticos nuevos para Policía Local de Jaén, en español, "
        "basados en el estilo del material de referencia. Cada supuesto debe incluir: "
        "titulo, contexto, hechos, actuacion policial paso a paso, fundamentacion juridica, "
        "diligencias o documentacion, y resolucion final. Usa formato Markdown claro. "
        "No copies literalmente los ejemplos; crea casos nuevos, realistas y variados. "
        "Mantén un tono técnico y de preparación de oposición.\n\n"
        "Material de referencia:\n\n"
        f"{sample}"
    )


def call_local_qwen(prompt: str) -> str:
    api_key = os.environ.get("LOCAL_QWEN_API_KEY", "12345")
    api_base = os.environ.get(
        "LOCAL_QWEN_API_BASE", "http://192.168.3.25:8080/v1"
    ).rstrip("/")
    model = os.environ.get("LOCAL_QWEN_MODEL", "qwen2.5-3b-instruct-q4_k_m.gguf")
    payload = {
        "model": model,
        "messages": [
            {
                "role": "system",
                "content": "Eres un preparador experto de oposiciones de Policía Local en España. Respondes con Markdown estructurado y útil para estudio.",
            },
            {"role": "user", "content": prompt},
        ],
        "temperature": 0.5,
        "max_tokens": 4096,
    }
    headers = {"Content-Type": "application/json", "Authorization": f"Bearer {api_key}"}
    with httpx.Client(timeout=600) as client:
        response = client.post(
            f"{api_base}/chat/completions", json=payload, headers=headers
        )
        response.raise_for_status()
        data = response.json()
    return data["choices"][0]["message"]["content"]


def build_practical_source_markdown(text: str, title: str) -> str:
    return text_to_markdown(text, title)


def parse_practical_cases(markdown: str) -> list[dict]:
    cases = []
    chunks = re.split(r"^##\s+Supuesto\s+Pr[áa]ctico.*$", markdown, flags=re.MULTILINE)
    headings = re.findall(
        r"^##\s+Supuesto\s+Pr[áa]ctico.*$", markdown, flags=re.MULTILINE
    )
    if not headings:
        return cases
    for heading, body in zip(headings, chunks[1:]):
        parsed = _parse_single_case(heading, body)
        if parsed:
            cases.append(parsed)
    return cases


def _parse_single_case(heading: str, body: str) -> dict | None:
    case = {
        "heading": heading.replace("##", "").strip(),
        "title": "",
        "context": "",
        "facts": "",
        "police_action": [],
        "legal_basis": "",
        "documents": [],
        "resolution": "",
        "rubric": [],
    }
    current_field = None
    for raw_line in body.splitlines():
        line = raw_line.strip()
        if not line:
            continue
        section_match = re.match(r"^\*\*([^*:]+):\*\*\s*(.*)$", line)
        if section_match:
            label = normalize_section_name(section_match.group(1))
            current_field = SECTION_ALIASES.get(label)
            content = section_match.group(2).strip()
            if current_field in {
                "title",
                "context",
                "facts",
                "legal_basis",
                "resolution",
            }:
                case[current_field] = content
            elif current_field in {"documents", "police_action"} and content:
                case[current_field].append(content)
            continue

        bullet = re.sub(r"^[0-9]+\.\s*", "", line)
        bullet = re.sub(r"^[-•]\s*", "", bullet)
        if current_field in {"documents", "police_action"}:
            case[current_field].append(_strip_bold(bullet))
        elif current_field in {
            "title",
            "context",
            "facts",
            "legal_basis",
            "resolution",
        }:
            existing = case[current_field]
            case[current_field] = (existing + " " + _strip_bold(line)).strip()

    if not case["title"]:
        case["title"] = case["heading"]
    case["rubric"] = build_practical_rubric(case)
    return case


def normalize_section_name(value: str) -> str:
    value = value.strip().lower()
    value = (
        value.replace("á", "a")
        .replace("é", "e")
        .replace("í", "i")
        .replace("ó", "o")
        .replace("ú", "u")
    )
    return value


def _strip_bold(text: str) -> str:
    return re.sub(r"\*\*(.*?)\*\*", r"\1", text).strip()


def build_practical_rubric(case: dict) -> list[dict]:
    rubric = []
    if case.get("facts"):
        rubric.append({"criterion": "Identificación de hechos relevantes", "points": 2})
    if case.get("police_action"):
        rubric.append({"criterion": "Secuencia de actuación policial", "points": 3})
    if case.get("documents"):
        rubric.append({"criterion": "Diligencias y documentación", "points": 2})
    if case.get("legal_basis") or case.get("resolution"):
        rubric.append(
            {"criterion": "Fundamentación jurídica y resolución", "points": 3}
        )
    if not rubric:
        rubric = [
            {"criterion": "Hechos", "points": 2},
            {"criterion": "Actuación", "points": 3},
            {"criterion": "Fundamento", "points": 3},
            {"criterion": "Resolución", "points": 2},
        ]
    return rubric


def practical_case_summary(case: dict) -> str:
    lines = [case.get("title", case.get("heading", "Supuesto"))]
    if case.get("context"):
        lines.append(f"Contexto: {case['context']}")
    if case.get("facts"):
        lines.append(f"Hechos: {case['facts']}")
    return "\n".join(lines)
