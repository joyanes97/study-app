from __future__ import annotations

import re


def estimate_theme_count(title: str, body: str) -> int:
    upper = title.upper()
    if "SUPUESTOS" in upper:
        cases = len(
            re.findall(
                r"^##\s+Supuesto\s+Pr[áa]ctico",
                body,
                flags=re.MULTILINE | re.IGNORECASE,
            )
        )
        return max(1, cases)

    numbers = re.findall(r"\b(\d+)\b", upper)
    if not numbers:
        return 1

    values = [int(value) for value in numbers]
    block_match = re.match(r"^(?:BLOQUE|BLOCK)\s+(\d+)\b", upper)
    if block_match and values and values[0] == int(block_match.group(1)):
        values = values[1:]

    if "DEL" in upper and "AL" in upper:
        ranges = re.findall(r"DEL\s+(\d+)\s+AL\s+(\d+)", upper)
        total = sum((int(end) - int(start) + 1) for start, end in ranges)
        extras = 0
        trailing = re.search(r"Y\s+(\d+)\.?$", upper)
        if trailing:
            trail_value = int(trailing.group(1))
            if not any(int(start) <= trail_value <= int(end) for start, end in ranges):
                extras = 1
        return max(1, total + extras)

    if len(values) >= 2:
        return len(values)
    return 1


def estimate_target_cards(title: str, body: str) -> int:
    count = estimate_theme_count(title, body)
    if "SUPUESTOS" in title.upper():
        return count * 2
    return count * 12


def estimate_target_questions(title: str, body: str) -> int:
    count = estimate_theme_count(title, body)
    if "SUPUESTOS" in title.upper():
        return count * 2
    return count * 6
