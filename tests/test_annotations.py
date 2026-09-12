import pytest

from app.services.annotations import (
    AnnotationError,
    build_excerpt,
    highlight,
    validate_offsets,
)


def test_validate_offsets_ok():
    validate_offsets("hello world", 0, 5)
    validate_offsets("hello", 4, 5)


@pytest.mark.parametrize(
    "start,end", [(0, 0), (-1, 2), (0, 99), (5, 3), (11, 12)]
)
def test_validate_offsets_bad(start, end):
    with pytest.raises(AnnotationError):
        validate_offsets("hello world", start, end)


def test_build_excerpt():
    assert build_excerpt("hello world", 6, 11) == "world"


def test_highlight_single():
    class A:
        start_offset = 0
        end_offset = 5
        on_original = True

    out = highlight("hello <world>", [A()])
    assert "<mark>hello</mark> &lt;world&gt;" == str(out)


def test_highlight_skips_translation_annotations():
    class OnTranslation:
        start_offset = 0
        end_offset = 5
        on_original = False

    out = highlight("hello", [OnTranslation()])
    assert "hello" == str(out)