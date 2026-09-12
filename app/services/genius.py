"""Scraping Genius without official API.

Search uses the private JSON endpoint the genius.com site itself calls,
track page is parsed from HTML via BeautifulSoup.
"""

from __future__ import annotations

import logging
import re

import requests
from bs4 import BeautifulSoup
from bs4 import Tag

from app.services.structures import structure_to_text

log = logging.getLogger(__name__)

SEARCH_URL = "https://genius.com/api/search/multi"
SONG_URL_TMPL = "https://genius.com/songs/{genius_id}"
HEADING_RE = re.compile(r"^\[[^\]]+\]$")

DEFAULT_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/124.0 Safari/537.36"
    ),
    "Accept": "application/json, text/plain, */*",
    "Referer": "https://genius.com/",
    "Origin": "https://genius.com",
    "Accept-Language": "en-US,en;q=0.9",
}


class GeniusError(Exception):
    pass


def _http_get(url: str, *, headers: dict[str, str] | None = None, **kwargs) -> requests.Response:
    response = requests.get(
        url, headers={**DEFAULT_HEADERS, **(headers or {})}, timeout=20, **kwargs
    )
    response.raise_for_status()
    return response


def search(query: str, user_agent: str | None = None) -> list[dict]:
    """Поиск треков через внутренний endpoint genius.com (без токена)."""
    if not query.strip():
        raise GeniusError("Пустой поисковый запрос")

    headers = {"User-Agent": user_agent} if user_agent else None
    try:
        response = _http_get(SEARCH_URL, headers=headers, params={"q": query.strip()})
    except requests.RequestException as exc:  # pragma: no cover
        raise GeniusError(f"Не удалось выполнить поиск: {exc}") from exc

    try:
        data = response.json()
    except ValueError as exc:  # pragma: no cover
        raise GeniusError("Genius вернул некорректный ответ") from exc

    results: list[dict] = []
    seen: set[str] = set()
    for section in data.get("response", {}).get("sections", []):
        for hit in section.get("hits", []):
            if hit.get("type") != "song":
                continue
            result = hit.get("result", {})
            genius_id = str(result.get("id"))
            if not genius_id or genius_id in seen:
                continue
            seen.add(genius_id)
            results.append(_song_result(result))
    return results


def _song_result(result: dict) -> dict:
    artist = (result.get("primary_artist") or {}).get("name") or "Unknown Artist"
    return {
        "genius_id": str(result.get("id")),
        "title": result.get("title") or "Untitled",
        "artist": artist,
        "cover_url": result.get("song_art_image_thumbnail_url")
        or result.get("header_image_thumbnail_url"),
        "url": result.get("url") or result.get("path"),
        "full_title": result.get("full_title") or result.get("title"),
    }


def scrape_track(genius_id: str, user_agent: str | None = None) -> dict:
    """Извлечь название/артиста/альбом/обложку/структуру текста со страницы трека."""
    headers = {"User-Agent": user_agent} if user_agent else None
    url = SONG_URL_TMPL.format(genius_id=genius_id)
    try:
        response = _http_get(url, headers=headers)
    except requests.RequestException as exc:  # pragma: no cover
        raise GeniusError(f"Не удалось загрузить трек {genius_id}: {exc}") from exc

    soup = BeautifulSoup(response.text, "html.parser")
    structure = parse_lyrics_structure(soup)
    if not structure:
        raise GeniusError(f"Не удалось извлечь текст трека (genius_id={genius_id})")

    title, artist = _parse_title_artist(soup)
    return {
        "genius_id": genius_id,
        "title": title,
        "artist": artist,
        "album": _parse_album(soup),
        "cover_url": _og_image(soup),
        "source_url": url,
        "structure": structure,
        "lyrics": structure_to_text(structure),
    }


def _parse_title_artist(soup: BeautifulSoup) -> tuple[str, str]:
    title, artist = "Untitled", "Unknown Artist"
    for prop in ("og:title", "twitter:title"):
        tag = soup.find("meta", {"property": prop})
        if tag and tag.get("content"):
            title = tag["content"].strip()
            break
    if " – " in title:
        artist, title = title.split(" – ", 1)
    elif soup.title:
        raw = soup.title.get_text(" ", strip=True)
        raw = raw.removesuffix(" | Genius Lyrics").strip()
        if " – " in raw:
            artist, title = raw.split(" – ", 1)
        else:
            title = raw
    return title.strip(), artist.strip()


def _parse_album(soup: BeautifulSoup) -> str | None:
    link = soup.find("a", href=re.compile(r"/albums/"))
    if link is None:
        return None
    text = link.get_text(" ", strip=True)
    return text or None


def _og_image(soup: BeautifulSoup) -> str | None:
    tag = soup.find("meta", property="og:image")
    return tag.get("content") if tag else None


def parse_lyrics_structure(soup: BeautifulSoup) -> list[dict]:
    """Разобрать div[data-lyrics-container] в секции вида {heading, lines}.

    Единственный надёжный разделитель строк на современном genius.com —
    тег <br/>. Абзацы собраны из inline-фрагментов (<a>/<span>/<i>,
    «ReferentFragment»), которые режут строку даже посреди слова
    («So man» + «y losing…» → «So many losing…»), поэтому новые строки
    между текстовыми узлами НЕ вставляются.
    """
    structure: list[dict] = []
    buf: list[str] = []

    def flush() -> None:
        text = "".join(buf).strip()
        buf.clear()
        if not text:
            return
        if HEADING_RE.fullmatch(text):
            structure.append({"heading": text, "lines": []})
        else:
            if not structure:
                structure.append({"heading": None, "lines": []})
            structure[-1]["lines"].append(text)

    def visit(node) -> None:
        if isinstance(node, Tag):
            if _is_excluded_widget(node) or node.name in ("script", "style"):
                return
            if node.name == "br":
                flush()
                return
            for child in node.children:
                visit(child)
            return

        text = str(node)
        if not text.strip():
            return
        pieces = [text] if "\n" not in text else text.split("\n")
        for piece in pieces:
            stripped = piece.strip()
            if not stripped:
                continue
            if HEADING_RE.fullmatch(stripped):
                flush()
                structure.append({"heading": stripped, "lines": []})
            else:
                buf.append(piece)

    for container in soup.select("div[data-lyrics-container]"):
        for child in container.children:
            visit(child)
    flush()
    return structure


def _is_excluded_widget(child: Tag) -> bool:
    if child.get("data-exclude-from-selection"):
        return True
    cls = " ".join(child.get("class") or [])
    return "LyricsHeader" in cls or "LyricsHeader__Container" in cls