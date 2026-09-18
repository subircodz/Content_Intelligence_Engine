"""Supported output languages for generated content."""

from enum import Enum


class ContentLanguage(str, Enum):
    """Languages supported for generated article/document output."""

    ENGLISH = "english"
    TELUGU = "telugu"
    TAMIL = "tamil"
    KANNADA = "kannada"
    MALAYALAM = "malayalam"

    @property
    def display_name(self) -> str:
        return {
            ContentLanguage.ENGLISH: "English",
            ContentLanguage.TELUGU: "Telugu",
            ContentLanguage.TAMIL: "Tamil",
            ContentLanguage.KANNADA: "Kannada",
            ContentLanguage.MALAYALAM: "Malayalam",
        }[self]

    @classmethod
    def parse(cls, value: str) -> "ContentLanguage":
        normalized = value.strip().lower()
        try:
            return cls(normalized)
        except ValueError as exc:
            choices = ", ".join(language.value for language in cls)
            raise ValueError(f"Unsupported content language {value!r}. Choose one of: {choices}.") from exc
