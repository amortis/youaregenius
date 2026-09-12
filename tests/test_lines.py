from app.services.lines import (
    annotation_tip,
    attach_annotations,
    build_line_map,
    build_view_blocks,
    build_view_rows,
    marked_line,
)
from app.services.structures import structure_to_text


class Annot:
    def __init__(self, start, end, content="тест", user=None):
        self.start_offset = start
        self.end_offset = end
        self.content = content
        self.user = user


class Usr:
    def __init__(self, username):
        self.username = username


STRUCTURE = [
    {"heading": "[Verse 1]", "lines": ["Is this the real life?", "Is this just fantasy?"]},
    {"heading": None, "lines": ["Caught in a landslide"]},
]


def test_line_map_offsets_match_flat_text():
    text = structure_to_text(STRUCTURE)
    line_map = build_line_map(STRUCTURE)

    flat_lines = text.split("\n")
    for block in line_map:
        for line in block["lines"]:
            assert text[line["start"] : line["end"]] == line["text"]

    # полный список строк (включая заголовок) собирается без потерь
    recovered = []
    for block in line_map:
        for line in block["lines"]:
            recovered.append(line["text"])
    lyrics = ",".join(flat_lines)
    for r in recovered:
        assert r in lyrics


def test_attach_annotations_map():
    line_map = attach_annotations(build_line_map(STRUCTURE), [Annot(11, 20)])
    all_lines = [ln for b in line_map for ln in b["lines"]]
    annotated = [ln for ln in all_lines if ln["anns"]]
    assert annotated and annotated[0]["text"] == "Is this the real life?"


def test_marked_line_wraps_only_annotation_range():
    line_map = attach_annotations(build_line_map(STRUCTURE), [Annot(11, 20)])
    line = line_map[0]["lines"][0]
    out = marked_line(line)
    assert "<mark>s this th</mark>" in str(out)
    assert str(out.striptags()) == line["text"]


def test_annotation_tip_joins_author_and_content():
    anns = [Annot(1, 2, content="первая", user=Usr("alice")),
            Annot(3, 4, content="вторая", user=Usr("bob"))]
    tip = annotation_tip(anns)
    assert "alice: первая" in tip and "bob: вторая" in tip


def test_build_view_groups_adjacent_annotated_lines_into_one_region():
    ann = Annot(11, 54, content="охватывает две строки", user=Usr("alice"))
    ann.id = 1
    blocks = attach_annotations(build_line_map(STRUCTURE), [ann])
    rows = build_view_blocks(blocks)
    kinds = [r["kind"] for r in rows]
    assert kinds == ["heading", "region", "lines"]
    assert rows[0] == {"kind": "heading", "text": "[Verse 1]"}
    region = rows[1]
    assert region["kind"] == "region"
    assert len(region["lines"]) == 2  # обе строки одного блока в одном регионе


def test_build_view_keeps_unannotated_lines_separate():
    ann = Annot(11, 20)
    ann.id = 1
    blocks = attach_annotations(build_line_map(STRUCTURE), [ann])
    rows = build_view_blocks(blocks)
    assert [r["kind"] for r in rows] == ["heading", "region", "lines", "lines"]
    assert len(rows[1]["lines"]) == 1


def test_build_view_rows_splits_annotation_per_line():
    ann = Annot(11, 54, content="по двум строкам", user=Usr("alice"))
    ann.id = 1
    orig = attach_annotations(build_line_map(STRUCTURE), [ann])
    trans = attach_annotations(build_line_map(STRUCTURE), [])
    rows = build_view_rows(orig, trans)
    region_rows = [r for r in rows if r["kind"] == "region"]
    # аннотация на 2 строки -> 2 одинаковые аннотации, по одной на строку
    assert len(region_rows) == 2
    assert all(len(r["lines"]) == 1 for r in region_rows)
    assert all(r["anns"] == [ann] for r in region_rows)