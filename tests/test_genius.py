from app.services.genius import parse_lyrics_structure
from app.services.structures import structure_to_text
from bs4 import BeautifulSoup

HTML = """
<div data-lyrics-container="true">
  <div data-exclude-from-selection="true">520 Contributors</div>
  <a>[Verse 1]</a>
  <a>Is this the real life?</a>
  <br>
  <a>Is this just fantasy?</a>
  <br>
  <a>Caught in a landslide</a>
</div>
<div data-lyrics-container="true">
  <a>[Chorus]</a>
  <a>Nothing really matters</a>
</div>
"""


def test_parse_lyrics_structure_ignores_widgets_and_builds_segments():
    structure = parse_lyrics_structure(BeautifulSoup(HTML, "html.parser"))
    assert structure == [
        {"heading": "[Verse 1]", "lines": ["Is this the real life?", "Is this just fantasy?", "Caught in a landslide"]},
        {"heading": "[Chorus]", "lines": ["Nothing really matters"]},
    ]


def test_structure_to_text_roundtrip():
    structure = [
        {"heading": "[Verse 1]", "lines": ["Is this the real life?", "Is this just fantasy?"]},
        {"heading": None, "lines": ["Caught in a landslide"]},
    ]
    text = structure_to_text(structure)
    assert text == (
        "[Verse 1]\nIs this the real life?\nIs this just fantasy?\n\nCaught in a landslide"
    )


HTML_BARE = """
<div data-lyrics-container="true">
  <div data-exclude-from-selection="true">66 Contributors Translations Português</div>
  [Verse 1]
  <a><span><i>Is this the real life</i><i>?</i> (Uh-huh)<br/>Is this just fantasy?</span></a>
  <br>
  <p>Caught in a landslide</p>
  [Chorus]
  <a><span><i>Nothing really matters to me</i></span></a>
</div>
"""


def test_parse_lyrics_structure_handles_bare_text_nodes():
    structure = parse_lyrics_structure(BeautifulSoup(HTML_BARE, "html.parser"))
    assert structure == [
        {
            "heading": "[Verse 1]",
            "lines": ["Is this the real life? (Uh-huh)", "Is this just fantasy?", "Caught in a landslide"],
        },
        {"heading": "[Chorus]", "lines": ["Nothing really matters to me"]},
    ]


def test_parse_does_not_split_fragments_mid_word():
    html = """
    <div data-lyrics-container="true">
      [Chorus]
      <a><span><i>So man</i><i>y losing hope in those dreams that they</i></span></a>
    </div>
    """
    structure = parse_lyrics_structure(BeautifulSoup(html, "html.parser"))
    assert structure == [
        {"heading": "[Chorus]", "lines": ["So many losing hope in those dreams that they"]}
    ]


def test_parse_joins_fragments_of_one_line_but_breaks_on_br():
    html = """
    <div data-lyrics-container="true">
      <a><span>Just got off the stage on the</span></a>
      <a><span>TODAY Show</span></a>
      <br/>
      <a><span>Years go by</span></a>
    </div>
    """
    structure = parse_lyrics_structure(BeautifulSoup(html, "html.parser"))
    assert structure == [
        {
            "heading": None,
            "lines": [
                "Just got off the stage on theTODAY Show",
                "Years go by",
            ],
        }
    ]