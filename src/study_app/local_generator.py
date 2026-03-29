from __future__ import annotations

import json
import os
from pathlib import Path
import re
from itertools import cycle

import httpx

from study_app.models import Topic
from study_app.practical_cases import parse_practical_cases
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
    if topic.content_type == "practical":
        return _generate_practical_cards(topic, target)
    if os.environ.get("LOCAL_QWEN_DISABLE") == "1":
        return _fallback_cards(topic, target)
    try:
        raw = _call_local_qwen(
            _cards_prompt(topic, target), temperature=0.3, max_tokens=900
        )
        parsed = _parse_cards(raw, topic.title)
        if len(parsed["cards"]) >= max(3, target // 2):
            return _top_up_cards(topic, parsed, target)
    except Exception:
        pass
    return _fallback_cards(topic, target)


def _generate_quiz(topic: Topic, target: int) -> dict:
    if topic.content_type == "practical":
        return _generate_practical_quiz(topic, target)
    if os.environ.get("LOCAL_QWEN_DISABLE") == "1":
        return _fallback_quiz(topic, target)
    try:
        raw = _call_local_qwen(
            _quiz_prompt(topic, target), temperature=0.3, max_tokens=900
        )
        parsed = _parse_quiz(raw, topic.title)
        if len(parsed["questions"]) >= max(2, target // 2):
            return _top_up_quiz(topic, parsed, target)
    except Exception:
        pass
    return _fallback_quiz(topic, target)


def _cards_prompt(topic: Topic, target: int) -> str:
    source = topic.body[:1800]
    return (
        f"Genera exactamente {target} flashcards para el tema '{topic.title}'. "
        "Devuelve solo texto con este formato repetido:\n"
        "Q: pregunta breve\nA: respuesta exacta\n---\n"
        "Prioriza leyes, artículos, órganos, principios y definiciones.\n\n"
        f"Contenido fuente:\n\n{source}"
    )


def _quiz_prompt(topic: Topic, target: int) -> str:
    source = topic.body[:1600]
    return (
        f"Genera exactamente {target} preguntas tipo test para el tema '{topic.title}'. "
        "Cada pregunta debe tener 4 opciones: 1 correcta y 3 distractores plausibles. "
        "Devuelve solo texto con este formato repetido:\n"
        "Q: pregunta\nA: correcta\nB: distractor\nC: distractor\nD: distractor\nEXPL: explicacion breve\n---\n"
        "Prioriza datos normativos y conceptos nucleares.\n\n"
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
                "content": "Eres un generador de material didáctico preciso. Devuelves solo el formato solicitado.",
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
        wrong3 = _field(block, "D")
        expl = _field(block, "EXPL")
        if question and correct and wrong1 and wrong2 and wrong3:
            questions.append(
                {
                    "question": question,
                    "hint": expl,
                    "explanation": expl,
                    "answerOptions": [
                        {"text": correct, "isCorrect": True},
                        {"text": wrong1, "isCorrect": False},
                        {"text": wrong2, "isCorrect": False},
                        {"text": wrong3, "isCorrect": False},
                    ],
                }
            )
    return {"title": title, "questions": questions}


def _top_up_cards(topic: Topic, parsed: dict, target: int) -> dict:
    existing = parsed["cards"]
    if len(existing) >= target:
        parsed["cards"] = existing[:target]
        return parsed
    fallback = _fallback_cards(topic, target)["cards"]
    seen = {(item["front"], item["back"]) for item in existing}
    for item in fallback:
        key = (item["front"], item["back"])
        if key in seen:
            continue
        existing.append(item)
        seen.add(key)
        if len(existing) >= target:
            break
    parsed["cards"] = existing[:target]
    return parsed


def _top_up_quiz(topic: Topic, parsed: dict, target: int) -> dict:
    existing = parsed["questions"]
    if len(existing) >= target:
        parsed["questions"] = existing[:target]
        return parsed
    fallback = _fallback_quiz(topic, target)["questions"]
    seen = {item["question"] for item in existing}
    for item in fallback:
        if item["question"] in seen:
            continue
        existing.append(item)
        seen.add(item["question"])
        if len(existing) >= target:
            break
    parsed["questions"] = existing[:target]
    return parsed


def _split_blocks(raw: str) -> list[str]:
    return [block.strip() for block in raw.split("---") if block.strip()]


def _field(block: str, label: str) -> str:
    match = re.search(
        rf"(?:^|\n){label}:\s*(.+?)(?=\n[A-Z]+:|\Z)", block, flags=re.DOTALL
    )
    return match.group(1).strip() if match else ""


def _fallback_cards(topic: Topic, target: int) -> dict:
    facts = _build_facts(topic)
    if not facts:
        facts = [{"kind": "generic", "text": f"Contenido clave del {topic.title}."}]
    cards = []
    for fact in _repeat_to_target(facts, target):
        cards.append(_card_from_fact(topic.title, fact))
    return {"title": topic.title, "cards": cards}


def _fallback_quiz(topic: Topic, target: int) -> dict:
    facts = _build_facts(topic)
    if not facts:
        facts = [{"kind": "generic", "text": f"Contenido relevante del {topic.title}."}]
    pools = _build_distractor_pools(facts)
    questions = []
    for fact in _repeat_to_target(facts, target):
        questions.append(_quiz_from_fact(topic.title, fact, pools))
    return {"title": topic.title, "questions": questions}


def _generate_practical_cards(topic: Topic, target: int) -> dict:
    cases = parse_practical_cases(topic.body)
    cards = []
    for case in cases:
        if case.get("facts"):
            cards.append(
                {
                    "front": f"En el supuesto '{case['title']}', ¿qué hechos relevantes justifican la intervención policial?",
                    "back": case["facts"],
                }
            )
        if case.get("police_action"):
            cards.append(
                {
                    "front": f"¿Cuál es la actuación policial prioritaria en el supuesto '{case['title']}'?",
                    "back": case["police_action"][0],
                }
            )
        if case.get("documents"):
            cards.append(
                {
                    "front": f"¿Qué diligencia o documento debe tramitarse en el supuesto '{case['title']}'?",
                    "back": case["documents"][0],
                }
            )
        if case.get("resolution"):
            cards.append(
                {
                    "front": f"¿Cuál es la resolución final esperable en el supuesto '{case['title']}'?",
                    "back": case["resolution"],
                }
            )
    if not cards:
        return _fallback_cards(topic, target)
    return {"title": topic.title, "cards": cards[:target]}


def _generate_practical_quiz(topic: Topic, target: int) -> dict:
    cases = parse_practical_cases(topic.body)
    questions = []
    for case in cases:
        if case.get("police_action"):
            correct = case["police_action"][0]
            wrongs = _practical_distractors(case, correct)
            questions.append(
                {
                    "question": f"En el supuesto '{case['title']}', ¿cuál debería ser la primera actuación policial prioritaria?",
                    "hint": case.get("facts")
                    or case.get("context")
                    or case.get("resolution", ""),
                    "explanation": f"La prioridad operativa correcta es: {correct}",
                    "answerOptions": [
                        {"text": correct, "isCorrect": True},
                        {"text": wrongs[0], "isCorrect": False},
                        {"text": wrongs[1], "isCorrect": False},
                        {"text": wrongs[2], "isCorrect": False},
                    ],
                    "optionExplanations": _build_option_explanations(
                        correct,
                        wrongs,
                        f"La primera actuación correcta es '{correct}'.",
                    ),
                }
            )
        if case.get("documents"):
            correct = case["documents"][0]
            wrongs = _practical_distractors(case, correct)
            questions.append(
                {
                    "question": f"En el supuesto '{case['title']}', ¿qué diligencia o documentación es más adecuada?",
                    "hint": case.get("facts")
                    or case.get("context")
                    or case.get("resolution", ""),
                    "explanation": f"La diligencia más adecuada es: {correct}",
                    "answerOptions": [
                        {"text": correct, "isCorrect": True},
                        {"text": wrongs[0], "isCorrect": False},
                        {"text": wrongs[1], "isCorrect": False},
                        {"text": wrongs[2], "isCorrect": False},
                    ],
                    "optionExplanations": _build_option_explanations(
                        correct, wrongs, f"La diligencia correcta es '{correct}'."
                    ),
                }
            )
    if not questions:
        return _fallback_quiz(topic, target)
    return {"title": topic.title, "questions": questions[:target]}


def _practical_distractors(case: dict, correct: str) -> list[str]:
    pool = []
    for item in case.get("documents", []) + case.get("police_action", []):
        if item != correct and item not in pool:
            pool.append(item)
    generic = [
        "Abandonar la intervención sin documentar los hechos.",
        "Resolver verbalmente el problema sin practicar diligencias.",
        "Esperar instrucciones sin asegurar la situación inicial.",
    ]
    for item in generic:
        if item != correct and item not in pool:
            pool.append(item)
    while len(pool) < 3:
        pool.append("Actuación no ajustada al supuesto práctico.")
    return pool[:3]


def _build_facts(topic: Topic) -> list[dict]:
    lines = _normalize_theory_lines(topic.body)
    facts = []
    for line in lines:
        if line.startswith("#"):
            continue
        cleaned = line.lstrip("•➢❖✓-⎯▪o ").strip()
        cleaned = re.sub(r"\s+", " ", cleaned)
        if len(cleaned) < 8:
            continue

        if _is_heading_noise(cleaned):
            continue

        paired_laws = re.match(
            r"((?:DECRETO|ORDEN|LEY|LO|RD|RDL)\s+[0-9/]+[^.]*?)\s+Y\s+((?:ORDEN|DECRETO|LEY|LO|RD|RDL)\s+[0-9/]+[^.]*?)\.\s*(.+)",
            cleaned,
            flags=re.IGNORECASE,
        )
        if paired_laws:
            facts.append(
                {
                    "kind": "law_pair",
                    "law": paired_laws.group(1).strip(" ."),
                    "support_law": paired_laws.group(2).strip(" ."),
                    "concept": paired_laws.group(3).strip(" ."),
                    "text": cleaned,
                }
            )
            continue

        article_match = re.search(
            r"\bART[ÍI]?C?U?L?O?\s*([0-9]+(?:\.[0-9]+)?)", cleaned, flags=re.IGNORECASE
        )
        short_article_match = re.search(
            r"\bART\s*([0-9]+(?:\.[0-9]+)?)", cleaned, flags=re.IGNORECASE
        )
        article = None
        if article_match:
            article = article_match.group(1)
        elif short_article_match:
            article = short_article_match.group(1)

        law_match = re.match(
            r"((?:LO|LEY|RDL|RD|DECRETO|ORDEN|INSTRUCCI[ÓO]N)\s+[0-9/]+(?:\s+de\s+[0-9]+\s+[A-ZÁÉÍÓÚÑ]+)?)",
            cleaned,
            flags=re.IGNORECASE,
        )
        if law_match:
            law = law_match.group(1).strip(" .")
            concept = cleaned[len(law_match.group(0)) :].strip(" .,-")
            if concept:
                facts.append(
                    {
                        "kind": "law",
                        "law": law,
                        "concept": concept,
                        "article": article,
                        "text": cleaned,
                    }
                )
                continue

        title_match = re.match(
            r"ART[ÍI]?C?U?L?O?\s*([0-9]+(?:\.[0-9]+)?)\.\s*(.+)",
            cleaned,
            flags=re.IGNORECASE,
        )
        if title_match:
            facts.append(
                {
                    "kind": "article_title",
                    "article": title_match.group(1),
                    "concept": title_match.group(2).strip(),
                    "text": cleaned,
                }
            )
            continue

        enum_match = re.match(r"([0-9]+º?)\s+(.+)", cleaned)
        if enum_match:
            facts.append(
                {
                    "kind": "enumeration",
                    "label": enum_match.group(1),
                    "concept": enum_match.group(2).strip(),
                    "text": cleaned,
                }
            )
            continue

        split_match = re.match(r"([A-ZÁÉÍÓÚÑ][A-ZÁÉÍÓÚÑ\s]+)\.\s+(.+)", cleaned)
        if split_match and len(split_match.group(1).split()) <= 8:
            facts.append(
                {
                    "kind": "headline_fact",
                    "headline": split_match.group(1).title(),
                    "concept": split_match.group(2).strip(),
                    "text": cleaned,
                }
            )
            continue

        if len(cleaned) >= 20:
            facts.append({"kind": "generic", "text": cleaned})

    dedup = []
    seen = set()
    for fact in facts:
        key = fact.get("text", "")
        if key in seen:
            continue
        seen.add(key)
        dedup.append(fact)
    return dedup[:120]


def _card_from_fact(topic_title: str, fact: dict) -> dict:
    kind = fact.get("kind")
    if kind == "law_pair":
        return {
            "front": f"En el {topic_title}, ¿qué regulan conjuntamente {fact['law']} y {fact['support_law']}?",
            "back": fact["concept"],
        }
    if kind == "law":
        if fact.get("article"):
            return {
                "front": f"En el {topic_title}, ¿qué norma se asocia al artículo {fact['article']}?",
                "back": f"{fact['law']}. {fact['concept']}.",
            }
        return {
            "front": f"En el {topic_title}, ¿qué regula la norma {fact['law']}?",
            "back": fact["concept"],
        }
    if kind == "article_title":
        return {
            "front": f"¿Qué regula el artículo {fact['article']} en el {topic_title}?",
            "back": fact["concept"],
        }
    if kind == "enumeration":
        return {
            "front": f"¿Qué dato clave corresponde al punto {fact['label']} del {topic_title}?",
            "back": fact["concept"],
        }
    if kind == "headline_fact":
        return {
            "front": f"En el {topic_title}, ¿qué establece el apartado '{fact['headline']}'?",
            "back": fact["concept"],
        }
    return {
        "front": f"En el {topic_title}, ¿qué establece el temario sobre '{_generic_focus(fact['text'])}'?",
        "back": fact["text"],
    }


def _build_distractor_pools(facts: list[dict]) -> dict:
    pools = {
        "law": [],
        "law_pair": [],
        "article_title": [],
        "enumeration": [],
        "headline_fact": [],
        "generic": [],
    }
    for fact in facts:
        pools.setdefault(fact["kind"], []).append(fact)
    return pools


def _quiz_from_fact(topic_title: str, fact: dict, pools: dict) -> dict:
    kind = fact.get("kind")
    if kind == "law_pair":
        return _quiz_from_law_pair(topic_title, fact, pools)
    if kind == "law":
        return _quiz_from_law(topic_title, fact, pools)
    if kind == "article_title":
        return _quiz_from_article_title(topic_title, fact, pools)
    if kind == "enumeration":
        return _quiz_from_enumeration(topic_title, fact, pools)
    return _quiz_from_generic(topic_title, fact, pools)


def _quiz_from_law_pair(topic_title: str, fact: dict, pools: dict) -> dict:
    correct = fact["concept"]
    wrongs = []
    for kind in ("law_pair", "law", "headline_fact", "generic"):
        for candidate in pools.get(kind, []):
            text = candidate.get("concept") or _short_answer_text(
                candidate.get("text", "")
            )
            if text and text != correct and text not in wrongs:
                wrongs.append(text)
            if len(wrongs) == 3:
                break
        if len(wrongs) == 3:
            break
    while len(wrongs) < 3:
        wrongs.append(f"Materia distinta del {topic_title}")
    return {
        "question": f"En el {topic_title}, ¿qué regulan conjuntamente {fact['law']} y {fact['support_law']}?",
        "hint": fact["text"],
        "explanation": f"La respuesta correcta es '{correct}' porque es la materia atribuida en el temario a esas dos normas.",
        "answerOptions": [
            {"text": correct, "isCorrect": True},
            {"text": wrongs[0], "isCorrect": False},
            {"text": wrongs[1], "isCorrect": False},
            {"text": wrongs[2], "isCorrect": False},
        ],
        "optionExplanations": _build_option_explanations(
            correct, wrongs, f"El temario vincula estas normas con '{correct}'."
        ),
    }


def _quiz_from_law(topic_title: str, fact: dict, pools: dict) -> dict:
    correct = fact["concept"]
    wrongs = []
    for kind in ("law", "law_pair", "headline_fact", "generic"):
        for candidate in pools.get(kind, []):
            text = candidate.get("concept") or _short_answer_text(
                candidate.get("text", "")
            )
            if text != correct and text not in wrongs:
                wrongs.append(text)
            if len(wrongs) == 3:
                break
        if len(wrongs) == 3:
            break
    while len(wrongs) < 3:
        wrongs.append(f"Materia distinta del {topic_title}")
    stem = f"En el {topic_title}, ¿qué regula la norma {fact['law']}" + (
        f" en relación con el artículo {fact['article']}?"
        if fact.get("article")
        else "?"
    )
    return {
        "question": stem,
        "hint": fact["text"],
        "explanation": f"La norma {fact['law']} se asocia en el temario con '{correct}'.",
        "answerOptions": [
            {"text": correct, "isCorrect": True},
            {"text": wrongs[0], "isCorrect": False},
            {"text": wrongs[1], "isCorrect": False},
            {"text": wrongs[2], "isCorrect": False},
        ],
        "optionExplanations": _build_option_explanations(
            correct, wrongs, f"La norma {fact['law']} regula '{correct}'."
        ),
    }


def _quiz_from_article_title(topic_title: str, fact: dict, pools: dict) -> dict:
    correct = fact["concept"]
    wrongs = []
    for candidate in pools.get("article_title", []):
        text = candidate["concept"]
        if text != correct and text not in wrongs:
            wrongs.append(text)
        if len(wrongs) == 3:
            break
    while len(wrongs) < 3:
        wrongs.append(f"Contenido distinto del {topic_title}")
    return {
        "question": f"¿Qué regula el artículo {fact['article']} según el {topic_title}?",
        "hint": fact["text"],
        "explanation": f"El artículo {fact['article']} regula '{correct}' en el temario.",
        "answerOptions": [
            {"text": correct, "isCorrect": True},
            {"text": wrongs[0], "isCorrect": False},
            {"text": wrongs[1], "isCorrect": False},
            {"text": wrongs[2], "isCorrect": False},
        ],
        "optionExplanations": _build_option_explanations(
            correct, wrongs, f"El artículo {fact['article']} se refiere a '{correct}'."
        ),
    }


def _quiz_from_enumeration(topic_title: str, fact: dict, pools: dict) -> dict:
    correct = fact["concept"]
    wrongs = []
    for candidate in pools.get("enumeration", []):
        text = candidate["concept"]
        if text != correct and text not in wrongs:
            wrongs.append(text)
        if len(wrongs) == 3:
            break
    while len(wrongs) < 3:
        wrongs.append(f"Dato distinto del {topic_title}")
    return {
        "question": f"¿Qué afirmación corresponde al punto {fact['label']} del {topic_title}?",
        "hint": fact["text"],
        "explanation": f"El punto {fact['label']} del temario contiene '{correct}'.",
        "answerOptions": [
            {"text": correct, "isCorrect": True},
            {"text": wrongs[0], "isCorrect": False},
            {"text": wrongs[1], "isCorrect": False},
            {"text": wrongs[2], "isCorrect": False},
        ],
        "optionExplanations": _build_option_explanations(
            correct, wrongs, f"El punto {fact['label']} recoge '{correct}'."
        ),
    }


def _quiz_from_generic(topic_title: str, fact: dict, pools: dict) -> dict:
    correct = _short_answer_text(fact["text"])
    wrongs = []
    for kind in (
        "headline_fact",
        "generic",
        "enumeration",
        "article_title",
        "law",
        "law_pair",
    ):
        for candidate in pools.get(kind, []):
            text = _short_answer_text(
                candidate.get("concept") or candidate.get("text", "")
            )
            if text and text != correct and text not in wrongs:
                wrongs.append(text)
            if len(wrongs) == 3:
                break
        if len(wrongs) == 3:
            break
    while len(wrongs) < 3:
        wrongs.append(f"Contenido no ajustado al {topic_title}")
    return {
        "question": f"En el {topic_title}, ¿qué establece el temario sobre '{_generic_focus(fact['text'])}'?",
        "hint": fact["text"],
        "explanation": f"La formulación correcta reproduce la idea central del temario sobre '{_generic_focus(fact['text'])}'.",
        "answerOptions": [
            {"text": correct, "isCorrect": True},
            {"text": wrongs[0], "isCorrect": False},
            {"text": wrongs[1], "isCorrect": False},
            {"text": wrongs[2], "isCorrect": False},
        ],
        "optionExplanations": _build_option_explanations(
            correct,
            wrongs,
            "Solo una opción refleja la idea central del tema; las demás pertenecen a otros apartados.",
        ),
    }


def _repeat_to_target(items: list[dict], target: int) -> list[dict]:
    seq = list(items)
    out = []
    iterator = cycle(seq)
    for _ in range(target):
        out.append(next(iterator))
    return out


def _short_answer_text(text: str) -> str:
    value = text.strip()
    value = re.sub(r"^[A-ZÁÉÍÓÚÑ ]+:\s*", "", value)
    value = value.replace("  ", " ")
    if len(value) > 140:
        value = value[:137].rstrip() + "..."
    return value


def _generic_focus(text: str) -> str:
    cleaned = _short_answer_text(text)
    cleaned = cleaned.split(".")[0].strip()
    words = cleaned.split()
    if len(words) > 10:
        cleaned = " ".join(words[:10]) + "..."
    return cleaned


def _build_option_explanations(
    correct: str, wrongs: list[str], correct_reason: str
) -> dict[str, str]:
    explanations = {correct: correct_reason}
    for wrong in wrongs:
        explanations[wrong] = (
            f"'{wrong}' no corresponde a esta pregunta; pertenece a otro apartado o a otra norma del mismo bloque."
        )
    return explanations


def _normalize_theory_lines(body: str) -> list[str]:
    raw_lines = [line.strip() for line in body.splitlines() if line.strip()]
    merged: list[str] = []
    for line in raw_lines:
        if _should_attach_to_previous(line, merged[-1] if merged else ""):
            merged[-1] = f"{merged[-1].rstrip()} {line.lstrip()}"
        else:
            merged.append(line)
    return merged


def _should_attach_to_previous(line: str, previous: str) -> bool:
    if not previous:
        return False
    if re.match(
        r"^(ART[ÍI]?C?U?L?O?|CAP[IÍ]TULO|T[IÍ]TULO|[A-ZÁÉÍÓÚÑ0-9].*:)",
        line,
        flags=re.IGNORECASE,
    ):
        return False
    if line.startswith(("•", "-", "⎯", "✓", "❖", "➢")):
        return False
    if line[:1].islower() or line[:1].isdigit():
        return True
    if previous.endswith((",", ";", ":")):
        return True
    return False


def _is_heading_noise(text: str) -> bool:
    upper = text.upper().strip(" .")
    if re.match(r"^BLOQUE\s+\d+", upper):
        return True
    if re.match(r"^TEMA\s+[0-9\sYALDEL.]+$", upper):
        return True
    if upper in {
        "FUERZAS Y CUERPOS",
        "DE SEGURIDAD.",
        "FUERZAS Y CUERPOS DE SEGURIDAD.",
        "TÍTULO 5.",
        "TÍTULO 4. RÉGIMEN ESTATUTARIO.",
    }:
        return True
    if text.isupper() and len(text.split()) <= 8 and not re.search(r"\d", text):
        return True
    return False
