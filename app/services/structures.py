from typing import Any


def structure_to_text(structure: list[dict[str, Any]]) -> str:
    parts = []
    for seg in structure:
        lines = "\n".join(seg.get("lines", []))
        heading = seg.get("heading")
        if heading:
            parts.append(f"{heading}\n{lines}" if lines else heading)
        elif lines:
            parts.append(lines)
    return "\n\n".join(parts)


def split_structure(structure: list[dict[str, Any]]) -> list[tuple[str | None, list[str]]]:
    return [(seg.get("heading"), list(seg.get("lines", []))) for seg in structure]