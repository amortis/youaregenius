"""Построчный рендер текста с оффсетами в плоском тексте и привязкой аннотаций."""
from __future__ import annotations

import base64
import json

from markupsafe import Markup, escape


def build_line_map(structure: list[dict]) -> list[dict]:
    """Вернуть [{heading, lines: [{text, start, end, anns: []}]}] с оффсетами.

    Оффсеты считаются по тому же алгоритму, что `structure_to_text`:
    блоки разделены "\\n\\n", заголовок и строки — одной новой строкой.
    """
    blocks: list[dict] = []
    offset = 0
    for seg in structure:
        heading = seg.get("heading") or None
        raw_lines = list(seg.get("lines", []))
        body = "\n".join(raw_lines)
        if heading and body:
            content = f"{heading}\n{body}"
            first_line_offset = len(heading) + 1
        else:
            content = heading or body
            first_line_offset = len(heading) if heading else 0

        lines: list[dict] = []
        cursor = offset + first_line_offset
        for text in raw_lines:
            lines.append({"text": text, "start": cursor, "end": cursor + len(text), "anns": []})
            cursor += len(text) + 1
        blocks.append({"heading": heading, "lines": lines})
        offset += len(content) + 2  # разделитель "\n\n" между блоками
    return blocks


def attach_annotations(line_map: list[dict], annotations) -> list[dict]:
    """Привязать аннотации к строкам, чей диапазон пересекается с оффсетами строки."""
    for block in line_map:
        for line in block["lines"]:
            line["anns"] = [
                a
                for a in annotations
                if a.start_offset < line["end"] and a.end_offset > line["start"]
            ]
    return line_map


def marked_line(line: dict) -> Markup:
    """Строка с <mark> вокруг фрагментов, покрытых аннотациями."""
    parts: list[str] = []
    marks = sorted(
        (max(0, a.start_offset - line["start"]), a.end_offset - line["start"])
        for a in line["anns"]
        if a.end_offset > line["start"]
    )
    marks = [(s, e) for s, e in marks if e > s and s < len(line["text"])]

    cursor = 0
    for start, end in marks:
        if start > cursor:
            parts.append(str(escape(line["text"][cursor:start])))
        parts.append(f"<mark>{escape(line['text'][start:end])}</mark>")
        cursor = max(cursor, end)
    if cursor < len(line["text"]):
        parts.append(str(escape(line["text"][cursor:])))
    return Markup("".join(parts))


def _ann_ids(line: dict | None) -> tuple[int, ...]:
    if not line:
        return ()
    return tuple(sorted(a.id for a in line["anns"]))


def build_view_blocks(blocks: list[dict]) -> list[dict]:
    """Группирует смежные аннотированные строки с одинаковыми аннотациями
    в «регион» — одна непрерывная подсветка (как выделение на Genius).

    Возвращает rows: {kind: heading, text} | {kind: lines|region, anns, lines}.
    """
    rows: list[dict] = []
    pending_lines: list[dict] = []
    pending_anns: list | None = None
    prev_line = None
    prev_ids: tuple[int, ...] = ()

    def flush() -> None:
        nonlocal pending_lines, pending_anns
        if pending_lines:
            rows.append(
                {
                    "kind": "region" if pending_anns else "lines",
                    "anns": pending_anns or [],
                    "lines": pending_lines,
                }
            )
            pending_lines = []
        pending_anns = None

    for block in blocks:
        if block.get("heading"):
            flush()
            rows.append({"kind": "heading", "text": block["heading"]})
        for line in block.get("lines", []):
            ids = _ann_ids(line)
            contiguous = (
                pending_anns is not None
                and ids == prev_ids
                and prev_line is not None
                and line["start"] == prev_line["end"] + 1
            )
            if contiguous:
                pending_lines.append(line)
            else:
                flush()
                pending_lines = [line]
                pending_anns = line["anns"] or None
            prev_line = line
            prev_ids = ids
        flush()
    return rows


def build_view_rows(orig_blocks: list[dict], trans_blocks: list[dict]) -> list[dict]:
    """То же для «Два языка»: пары строк (оригинал/перевод).

    Аннотация, задевающая несколько строк, делится на отдельные строки —
    каждая такая строка становится собственной аннотацией (одинаковые
    карточки), как просил пользователь: аннотация на 3 строки → 3 одинаковые.
    """
    from itertools import zip_longest

    rows: list[dict] = []
    for oseg, tseg in zip_longest(orig_blocks or [], trans_blocks or []):
        o_lines = ((oseg or {}).get("lines") or []) if oseg else []
        t_lines = ((tseg or {}).get("lines") or []) if tseg else []
        if (oseg or {}).get("heading"):
            rows.append(
                {
                    "kind": "heading",
                    "text": (oseg or {}).get("heading"),
                    "ru": (tseg or {}).get("heading") if tseg else None,
                }
            )
        for i, en in enumerate(o_lines):
            ru = t_lines[i] if i < len(t_lines) else None
            seen: set[int] = set()
            anns: list = []
            for ann in (en.get("anns") or []) + ((ru.get("anns") or []) if ru else []):
                if ann.id not in seen:
                    seen.add(ann.id)
                    anns.append(ann)
            pair = {"kind": "pair", "en": en, "ru": ru}
            if anns:
                rows.append({"kind": "region", "anns": anns, "lines": [pair]})
            else:
                rows.append({"kind": "pairs", "anns": [], "lines": [pair]})
    return rows


def annotation_tip(annotations) -> str:
    """Текст всплывающей подсказки: автор и содержимое каждой аннотации."""
    lines = []
    for ann in annotations:
        author = getattr(ann.user, "username", None) or "аноним"
        lines.append(f"{author}: {ann.content}")
    return "\n\n".join(lines)


def annotation_cards(annotations) -> list[dict]:
    """Сериализация аннотаций строки для карточки в стиле Genius."""
    cards = []
    for ann in annotations:
        author = getattr(ann.user, "username", None) or "аноним"
        cards.append(
            {
                "id": ann.id,
                "excerpt": ann.excerpt,
                "content": ann.content,
                "author": author,
                "date": ann.created_at.strftime("%d.%m.%Y"),
            }
        )
    return cards


def annotation_payload(annotations) -> str:
    """Base64 JSON для data-атрибута: безопасно для кавычек/тегов в HTML."""
    payload = json.dumps(annotation_cards(annotations), ensure_ascii=True).encode("utf-8")
    return base64.b64encode(payload).decode("ascii")