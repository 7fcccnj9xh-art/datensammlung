"""
Text-Processor: Bereinigung, Extraktion, Hashing, Duplikatserkennung.
"""

from __future__ import annotations

import hashlib
import re
from typing import Optional

from langdetect import detect, LangDetectException


class TextProcessor:
    """
    Verarbeitet rohen HTML/Text zu sauberem, normalisiertem Inhalt.
    """

    # Mindest-Textlänge für sinnvollen Inhalt
    MIN_CONTENT_LENGTH = 100

    def clean(self, text: str) -> str:
        """Vollständige Text-Bereinigung."""
        if not text:
            return ""

        # Mehrfache Whitespace reduzieren
        text = re.sub(r'[ \t]+', ' ', text)
        text = re.sub(r'\n{3,}', '\n\n', text)

        # Häufige Boilerplate-Phrasen entfernen
        boilerplate = [
            r'Cookie[s]?.*?akzeptieren.*?\n',
            r'Datenschutz.*?Impressum.*?\n',
            r'Newsletter abonnieren.*?\n',
            r'Alle Rechte vorbehalten.*?\n',
        ]
        for pattern in boilerplate:
            text = re.sub(pattern, '', text, flags=re.IGNORECASE)

        return text.strip()

    def compute_hash(self, content: str) -> str:
        """SHA-256 Hash des Inhalts für Duplikatserkennung."""
        normalized = re.sub(r'\s+', ' ', content.lower().strip())
        return hashlib.sha256(normalized.encode('utf-8')).hexdigest()

    def detect_language(self, text: str) -> Optional[str]:
        """Sprache des Textes erkennen."""
        try:
            if len(text) < 50:
                return None
            return detect(text[:2000])
        except LangDetectException:
            return None

    def extract_sentences(self, text: str, max_sentences: int = 10) -> list[str]:
        """Erste N Sätze extrahieren (für Kurzvorschau)."""
        sentences = re.split(r'(?<=[.!?])\s+', text)
        return [s.strip() for s in sentences[:max_sentences] if len(s.strip()) > 20]

    def truncate(self, text: str, max_chars: int = 5000) -> str:
        """Text auf max_chars begrenzen, an Satzgrenze."""
        if len(text) <= max_chars:
            return text
        truncated = text[:max_chars]
        # An letztem Satzende abschneiden
        last_dot = max(
            truncated.rfind('.'),
            truncated.rfind('!'),
            truncated.rfind('?'),
        )
        if last_dot > max_chars * 0.8:
            return truncated[:last_dot + 1]
        return truncated + "..."

    def is_meaningful(self, text: str) -> bool:
        """Prüft ob Text genug Inhalt hat um verarbeitet zu werden."""
        if not text or len(text) < self.MIN_CONTENT_LENGTH:
            return False
        # Mindestens 10 Wörter
        word_count = len(text.split())
        return word_count >= 10

    def extract_numbers(self, text: str) -> list[float]:
        """Alle Zahlen aus einem Text extrahieren."""
        pattern = r'-?\d+(?:[.,]\d+)?'
        matches = re.findall(pattern, text)
        result  = []
        for m in matches:
            try:
                result.append(float(m.replace(',', '.')))
            except ValueError:
                pass
        return result


# Singleton
_processor: Optional[TextProcessor] = None


def get_text_processor() -> TextProcessor:
    global _processor
    if _processor is None:
        _processor = TextProcessor()
    return _processor
