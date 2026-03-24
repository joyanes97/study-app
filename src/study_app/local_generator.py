from __future__ import annotations

import json
import os
from pathlib import Path
import re
from itertools import cycle

import httpx

from study_app.models import Topic
from study_app.targets import estimate_target_cards, estimate_target_questions


def generate_topic_artifacts(root: Path, topic: Topic) -> tuple[Path, Path]:
    cards_target = estimate_target_cards(topic.title, topic.body)
    questions_target = estimate_target_questions(topic.title, topic.body)

    cards = _generate_cards(topic, cards_target)
    quiz = _generate_quiz(topic, questions_target)

    generated_dir = root / "data" / "generated"
    generated_dir.mkdir(parents=True, exist_ok=True)
    cards_path = generated_dir / f"{topic.id}-cards.json"
    quiz_path = generated_dir / f"{topic.id}-quiz.json"
    cards_path.write_text(
        json.dumps(cards, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    quiz_path.write_text(
        json.dumps(quiz, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    return cards_path, quiz_path


def _generate_cards(topic: Topic, target: int) -> dict:
    if os.environ.get("LOCAL_QWEN_DISABLE") == "1":
        return _fallback_cards(topic, target)
    try:
        raw = _call_local_qwen(
            _cards_prompt(topic, target),
            temperature=0.3,
            max_tokens=900,
        )
        parsed = _parse_cards(raw, topic.title)
        if parsed["cards"]:
            return parsed
    except Exception:
        pass
    return _fallback_cards(topic, target)


def _generate_quiz(topic: Topic, target: int) -> dict:
    if os.environ.get("LOCAL_QWEN_DISABLE") == "1":
        return _fallback_quiz(topic, target)
    try:
        raw = _call_local_qwen(
            _quiz_prompt(topic, target),
            temperature=0.3,
            max_tokens=900,
        )
        parsed = _parse_quiz(raw, topic.title)
        if parsed["questions"]:
            return parsed
    except Exception:
        pass
    return _fallback_quiz(topic, target)


def _cards_prompt(topic: Topic, target: int) -> str:
    source = topic.body[:1800]
    return (
        f"Genera exactamente {target} flashcards para el tema '{topic.title}'. "
        "Devuelve solo texto con este formato repetido, sin JSON:\n"
        "Q: pregunta\nA: respuesta\n---\n"
        "Las respuestas deben ser claras, breves y útiles para oposiciones.\n\n"
        f"Contenido fuente:\n\n{source}"
    )


def _quiz_prompt(topic: Topic, target: int) -> str:
    source = topic.body[:1600]
    return (
        f"Genera exactamente {target} preguntas tipo test para el tema '{topic.title}'. "
        "Cada pregunta debe tener 3 opciones: 1 correcta y 2 distractores plausibles. "
        "Devuelve solo texto con este formato repetido, sin JSON:\n"
        "Q: pregunta\nA: opcion correcta\nB: distractor plausible\nC: distractor plausible\nEXPL: explicacion breve\n---\n"
        "Las preguntas deben ser claras, sin negaciones innecesarias.\n\n"
        f"Contenido fuente:\n\n{source}"
    )


def _call_local_qwen(prompt: str, temperature: float, max_tokens: int) -> str:
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
                "content": "Eres un generador de material didactico preciso. Devuelves solo el formato solicitado, sin introducciones.",
            },
            {"role": "user", "content": prompt},
        ],
        "temperature": temperature,
        "max_tokens": max_tokens,
    }
    headers = {"Content-Type": "application/json", "Authorization": f"Bearer {api_key}"}
    with httpx.Client(timeout=60) as client:
        response = client.post(
            f"{api_base}/chat/completions", json=payload, headers=headers
        )
        response.raise_for_status()
        data = response.json()
    return data["choices"][0]["message"]["content"]


def _parse_cards(raw: str, title: str) -> dict:
    cards = []
    for block in _split_blocks(raw):
        front = _field(block, "Q")
        back = _field(block, "A")
        if front and back:
            cards.append({"front": front, "back": back})
    return {"title": title, "cards": cards}


def _parse_quiz(raw: str, title: str) -> dict:
    questions = []
    for block in _split_blocks(raw):
        question = _field(block, "Q")
        correct = _field(block, "A")
        wrong1 = _field(block, "B")
        wrong2 = _field(block, "C")
        expl = _field(block, "EXPL")
        if question and correct and wrong1 and wrong2:
            questions.append(
                {
                    "question": question,
                    "hint": expl,
                    "answerOptions": [
                        {"text": correct, "isCorrect": True},
                        {"text": wrong1, "isCorrect": False},
                        {"text": wrong2, "isCorrect": False},
                    ],
                }
            )
    return {"title": title, "questions": questions}


def _split_blocks(raw: str) -> list[str]:
    return [block.strip() for block in raw.split("---") if block.strip()]


def _field(block: str, label: str) -> str:
    match = re.search(
        rf"(?:^|\n){label}:\s*(.+?)(?=\n[A-Z]+:|\Z)", block, flags=re.DOTALL
    )
    return match.group(1).strip() if match else ""


def _fallback_cards(topic: Topic, target: int) -> dict:
    facts = _extract_fact_lines(topic.body)
    if not facts:
        facts = [f"Contenido clave del {topic.title}."]
    cards = []
    prompts = cycle(
        [
            f"Resume la idea clave de este punto del {topic.title}.",
            f"Que debes recordar del {topic.title} para el examen?",
            f"Cual es el dato normativo o conceptual esencial de {topic.title}?",
        ]
    )
    for line in _repeat_to_target(facts, target):
        cards.append(
            {
                "front": next(prompts),
                "back": line,
            }
        )
    return {"title": topic.title, "cards": cards}


def _fallback_quiz(topic: Topic, target: int) -> dict:
    facts = _extract_fact_lines(topic.body)
    if not facts:
        facts = [f"Contenido relevante del {topic.title}."]
    distractor_pool = [
        _short_answer_text(line) for line in facts if _short_answer_text(line)
    ] or [topic.title]
    distractor_iter = cycle(distractor_pool)
    questions = []
    for line in _repeat_to_target(facts, target):
        correct = _short_answer_text(line) or line[:120]
        wrong_1 = next(distractor_iter)
        wrong_2 = next(distractor_iter)
        if wrong_1 == correct:
            wrong_1 = f"Interpretacion secundaria de {topic.title}"
        if wrong_2 in {correct, wrong_1}:
            wrong_2 = f"Aplicacion accesoria de {topic.title}"
        questions.append(
            {
                "question": f"Segun el {topic.title}, cual de las siguientes afirmaciones se ajusta mejor al temario?",
                "hint": line,
                "answerOptions": [
                    {"text": correct, "isCorrect": True},
                    {"text": wrong_1, "isCorrect": False},
                    {"text": wrong_2, "isCorrect": False},
                ],
            }
        )
    return {"title": topic.title, "questions": questions}


def _repeat_to_target(items: list[str], target: int) -> list[str]:
    seq = list(items)
    out = []
    iterator = cycle(seq)
    for _ in range(target):
        out.append(next(iterator))
    return out


def _extract_fact_lines(body: str) -> list[str]:
    cleaned = re.sub(r"\s+", " ", body)
    chunks = re.split(r"(?<=[\.!?])\s+", cleaned)
    facts = []
    for chunk in chunks:
        text = chunk.strip(" -\n\t")
        if len(text) < 40:
            continue
        if text.startswith("#"):
            continue
        facts.append(text)
    return facts[:80]


def _short_answer_text(text: str) -> str:
    value = text.strip()
    value = re.sub(r"^[A-ZÁÉÍÓÚÑ ]+:\s*", "", value)
    if len(value) > 140:
        value = value[:137].rstrip() + "..."
    return value
