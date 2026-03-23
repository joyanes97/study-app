from __future__ import annotations

import json
import os
from pathlib import Path

import httpx

from study_app.pdf_ingest import clean_extracted_text, text_to_markdown


def generate_practical_cases(source_markdown: str, output_path: Path) -> Path:
    prompt = build_prompt(source_markdown)
    content = call_local_qwen(prompt)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(content.strip() + "\n", encoding="utf-8")
    return output_path


def build_prompt(source_markdown: str) -> str:
    sample = clean_extracted_text(source_markdown)[:28000]
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
        "max_tokens": 8192,
    }
    headers = {"Content-Type": "application/json", "Authorization": f"Bearer {api_key}"}
    with httpx.Client(timeout=300) as client:
        response = client.post(
            f"{api_base}/chat/completions", json=payload, headers=headers
        )
        response.raise_for_status()
        data = response.json()
    return data["choices"][0]["message"]["content"]


def build_practical_source_markdown(text: str, title: str) -> str:
    return text_to_markdown(text, title)
