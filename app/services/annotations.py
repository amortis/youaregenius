from markupsafe import Markup, escape


class AnnotationError(ValueError):
    pass


def validate_offsets(text: str, start: int, end: int) -> None:
    length = len(text)
    if start < 0 or end > length or start >= end:
        raise AnnotationError(
            f"Неверный диапазон [start={start}, end={end}] для текста длиной {length}"
        )


def build_excerpt(text: str, start: int, end: int) -> str:
    validate_offsets(text, start, end)
    return text[start:end]


def highlight(text: str, annotations) -> Markup:
    """Обернуть помеченные фрагменты в <mark>. Оффсеты считаются по плоскому тексту."""
    marks = sorted(
        (a.start_offset, a.end_offset)
        for a in annotations
        if a.on_original
        if a.end_offset is not None
    )
    parts = []
    in_mark = False
    for i, char in enumerate(text):
        marked = any(start <= i < end for start, end in marks)
        if marked and not in_mark:
            parts.append("<mark>")
            in_mark = True
        elif not marked and in_mark:
            parts.append("</mark>")
            in_mark = False
        parts.append(escape(char))
    if in_mark:
        parts.append("</mark>")
    return Markup("".join(parts))