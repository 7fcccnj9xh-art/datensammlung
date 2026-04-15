"""
Recherche-Prompts: Templates für alle LLM-Aufrufe im Recherche-Workflow.
System-Prompts sind kurz gehalten (< 500 Tokens) für Prompt-Caching-Effizienz.
"""

from __future__ import annotations


# ----------------------------------------------------------
# System-Prompts (werden gecacht bei wiederholten Aufrufen)
# ----------------------------------------------------------

RESEARCH_SYSTEM_PROMPT = """Du bist ein präziser Recherche-Assistent.
Deine Aufgaben: Fakten extrahieren, zusammenfassen, neue Informationen identifizieren.
Antworte immer auf Deutsch. Sei präzise und sachlich. Keine Floskeln."""

SUMMARY_SYSTEM_PROMPT = """Du bist ein Textzusammenfassung-Spezialist.
Erstelle strukturierte, deutschsprachige Zusammenfassungen.
Behalte alle wichtigen Fakten, Zahlen und Quellen."""


# ----------------------------------------------------------
# Prompt-Builder Funktionen
# ----------------------------------------------------------

def build_summary_prompt(content: str, topic_name: str, max_words: int = 300) -> str:
    """Zusammenfassung eines Textes für ein bestimmtes Topic."""
    return f"""Thema: "{topic_name}"

Text zum Zusammenfassen:
---
{content[:8000]}
---

Erstelle eine strukturierte Zusammenfassung (max. {max_words} Wörter):
1. Wichtigste Erkenntnisse (3-5 Punkte)
2. Relevanz für das Thema "{topic_name}"
3. Quellenangaben wenn vorhanden

Format: Markdown mit Überschriften."""


def build_delta_prompt(old_summary: str, new_content: str, topic_name: str) -> str:
    """Was ist neu gegenüber dem letzten Stand?"""
    return f"""Thema: "{topic_name}"

BISHERIGER WISSENSSTAND:
---
{old_summary[:3000]}
---

NEUER CONTENT:
---
{new_content[:5000]}
---

Analysiere: Was ist NEU gegenüber dem bisherigen Stand?
- Neue Informationen, die vorher nicht bekannt waren
- Geänderte Fakten oder aktualisierte Zahlen
- Nicht mehr zutreffende Informationen

Wenn nichts Wesentliches neu ist, antworte: "Keine wesentlichen Neuigkeiten."
Format: Markdown-Aufzählung der Änderungen."""


def build_relevance_prompt(content: str, topic_name: str, keywords: list[str]) -> str:
    """Relevanz eines Textes für ein Topic bewerten (0.0 - 1.0)."""
    kw_str = ", ".join(keywords) if keywords else "keine angegeben"
    return f"""Bewerte die Relevanz dieses Textes für das Thema "{topic_name}".
Suchbegriffe: {kw_str}

Text:
---
{content[:3000]}
---

Antworte NUR mit einer Zahl zwischen 0.0 (völlig irrelevant) und 1.0 (hochrelevant).
Beispiel: 0.75
Zahl:"""


def build_source_rating_prompt(url: str, title: str, snippet: str) -> str:
    """Vertrauenswürdigkeit einer Quelle einschätzen."""
    return f"""Bewerte die Vertrauenswürdigkeit dieser Quelle:
URL: {url}
Titel: {title}
Ausschnitt: {snippet[:500]}

Kriterien: Bekannte seriöse Domain? Qualitäts-Journalismus? Faktenbasiert?
Antworte NUR mit einer Zahl 0.0 (unzuverlässig) bis 1.0 (sehr vertrauenswürdig).
Zahl:"""


def build_keyword_extraction_prompt(content: str) -> str:
    """Schlüsselbegriffe aus einem Text extrahieren."""
    return f"""Extrahiere die 5-10 wichtigsten Schlüsselbegriffe aus diesem Text.

Text:
---
{content[:4000]}
---

Format: JSON-Array, z.B. ["Begriff1", "Begriff2", "Begriff3"]
Nur das JSON, kein weiterer Text:"""


def build_search_queries_prompt(topic_name: str, description: str, existing_keywords: list[str]) -> str:
    """Optimale Suchanfragen für ein Topic generieren."""
    kw_str = ", ".join(existing_keywords) if existing_keywords else "keine"
    return f"""Generiere 5 optimale Suchanfragen für dieses Recherche-Thema:

Thema: {topic_name}
Beschreibung: {description}
Bekannte Keywords: {kw_str}

Erstelle Suchanfragen die:
- Verschiedene Aspekte des Themas abdecken
- Aktuelle Informationen finden
- Sowohl deutsch als auch englisch (wenn sinnvoll)

Format: JSON-Array mit 5 Strings
["Suchanfrage 1", "Suchanfrage 2", ...]
Nur JSON:"""
