from __future__ import annotations

import logging

import deepl

log = logging.getLogger(__name__)


class TranslationError(Exception):
    pass


class TranslationProvider:
    """Абстракция провайдера перевода: строится построчно, сохраняя структуру."""

    def translate_lines(self, lines: list[str], target_lang: str = "RU") -> list[str]:
        raise NotImplementedError


class DeepLProvider(TranslationProvider):
    def __init__(self, api_key: str) -> None:
        self.translator = deepl.Translator(api_key)

    def translate_lines(self, lines: list[str], target_lang: str = "RU") -> list[str]:
        texts = self.translator.translate_text(lines, target_lang=target_lang)
        return [text.text for text in texts]


def get_provider(api_key: str) -> TranslationProvider | None:
    if not api_key:
        return None
    return DeepLProvider(api_key)