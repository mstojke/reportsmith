"""Built-in labels ("Figure", "Contents", "Note", ...) in several languages.

The labels follow the report's ``language``: ``Report("...",
language="pl")`` captions figures "Rysunek 1" and titles the table of
contents "Spis treści". Only the primary language subtag counts (``"de-CH"``
uses German); languages without a translation use English.
``Report(labels={...})`` overrides single labels, e.g. ``{"figure": "Fig."}``.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Mapping, Optional

if TYPE_CHECKING:
    from .elements import Callout, TableOfContents
    from .report import Report

#: Every label key, with its English text.
ENGLISH = {
    "figure": "Figure",
    "table": "Table",
    "equation": "Equation",
    "section": "Section",
    "contents": "Contents",
    "notes": "Notes",
    "author": "Author",
    "date": "Date",
    "note": "Note",
    "tip": "Tip",
    "important": "Important",
    "warning": "Warning",
    "caution": "Caution",
    "image": "Image",
    "logo": "Logo",
    "back_to_reference": "Back to reference",
}

#: Translations, by primary language subtag. Missing keys fall back to English.
TRANSLATIONS: dict[str, dict[str, str]] = {
    "en": ENGLISH,
    "cs": {
        "figure": "Obrázek", "table": "Tabulka", "equation": "Rovnice", "section": "Oddíl",
        "contents": "Obsah", "notes": "Poznámky", "author": "Autor", "date": "Datum",
        "note": "Poznámka", "tip": "Tip", "important": "Důležité", "warning": "Varování",
        "caution": "Upozornění", "image": "Obrázek", "logo": "Logo",
        "back_to_reference": "Zpět na odkaz",
    },
    "de": {
        "figure": "Abbildung", "table": "Tabelle", "equation": "Gleichung", "section": "Abschnitt",
        "contents": "Inhaltsverzeichnis", "notes": "Anmerkungen", "author": "Autor",
        "date": "Datum", "note": "Hinweis", "tip": "Tipp", "important": "Wichtig",
        "warning": "Warnung", "caution": "Vorsicht", "image": "Bild", "logo": "Logo",
        "back_to_reference": "Zurück zum Verweis",
    },
    "es": {
        "figure": "Figura", "table": "Tabla", "equation": "Ecuación", "section": "Sección",
        "contents": "Índice", "notes": "Notas", "author": "Autor", "date": "Fecha",
        "note": "Nota", "tip": "Consejo", "important": "Importante", "warning": "Advertencia",
        "caution": "Precaución", "image": "Imagen", "logo": "Logotipo",
        "back_to_reference": "Volver a la referencia",
    },
    "fr": {
        "figure": "Figure", "table": "Tableau", "equation": "Équation", "section": "Section",
        "contents": "Table des matières", "notes": "Notes", "author": "Auteur", "date": "Date",
        "note": "Remarque", "tip": "Astuce", "important": "Important",
        "warning": "Avertissement", "caution": "Attention", "image": "Image", "logo": "Logo",
        "back_to_reference": "Retour à la référence",
    },
    "it": {
        "figure": "Figura", "table": "Tabella", "equation": "Equazione", "section": "Sezione",
        "contents": "Indice", "notes": "Note", "author": "Autore", "date": "Data",
        "note": "Nota", "tip": "Suggerimento", "important": "Importante",
        "warning": "Avvertenza", "caution": "Attenzione", "image": "Immagine", "logo": "Logo",
        "back_to_reference": "Torna al riferimento",
    },
    "nl": {
        "figure": "Figuur", "table": "Tabel", "equation": "Vergelijking", "section": "Sectie",
        "contents": "Inhoudsopgave", "notes": "Noten", "author": "Auteur", "date": "Datum",
        "note": "Opmerking", "tip": "Tip", "important": "Belangrijk",
        "warning": "Waarschuwing", "caution": "Let op", "image": "Afbeelding", "logo": "Logo",
        "back_to_reference": "Terug naar verwijzing",
    },
    "pl": {
        "figure": "Rysunek", "table": "Tabela", "equation": "Równanie", "section": "Sekcja",
        "contents": "Spis treści", "notes": "Przypisy", "author": "Autor", "date": "Data",
        "note": "Uwaga", "tip": "Wskazówka", "important": "Ważne", "warning": "Ostrzeżenie",
        "caution": "Przestroga", "image": "Obraz", "logo": "Logo",
        "back_to_reference": "Powrót do odwołania",
    },
    "pt": {
        "figure": "Figura", "table": "Tabela", "equation": "Equação", "section": "Seção",
        "contents": "Sumário", "notes": "Notas", "author": "Autor", "date": "Data",
        "note": "Nota", "tip": "Dica", "important": "Importante", "warning": "Aviso",
        "caution": "Cuidado", "image": "Imagem", "logo": "Logotipo",
        "back_to_reference": "Voltar à referência",
    },
    "sv": {
        "figure": "Figur", "table": "Tabell", "equation": "Ekvation", "section": "Avsnitt",
        "contents": "Innehåll", "notes": "Noter", "author": "Författare", "date": "Datum",
        "note": "Obs", "tip": "Tips", "important": "Viktigt", "warning": "Varning",
        "caution": "Försiktighet", "image": "Bild", "logo": "Logotyp",
        "back_to_reference": "Tillbaka till referensen",
    },
}


def check_labels(labels: Optional[Mapping[str, str]]) -> dict[str, str]:
    """Validate ``Report(labels=...)`` overrides."""
    if labels is None:
        return {}
    unknown = sorted(set(labels) - set(ENGLISH))
    if unknown:
        known = ", ".join(sorted(ENGLISH))
        raise ValueError(f"Unknown label {unknown[0]!r}; labels are: {known}")
    for key, value in labels.items():
        if not isinstance(value, str):
            raise TypeError(f"Label {key!r} must be a string, got {type(value).__name__}")
    return dict(labels)


def language_labels(language: str) -> dict[str, str]:
    """The built-in labels for a language tag (``"pl"``, ``"de-CH"``)."""
    primary = language.replace("_", "-").split("-")[0].lower()
    return {**ENGLISH, **TRANSLATIONS.get(primary, {})}


def labels_for(report: "Report") -> dict[str, str]:
    """The labels a report renders with: its language's, then its overrides."""
    return {**language_labels(report.language), **report.labels}


def toc_title(el: "TableOfContents", labels: Mapping[str, str]) -> str:
    """A TOC's title: its own, or the "contents" label (``""`` for none)."""
    return labels["contents"] if el.title is None else el.title


def callout_title(el: "Callout", labels: Mapping[str, str]) -> str:
    """A callout's title: its own, or the label for its kind."""
    return el.title or labels[el.kind]
