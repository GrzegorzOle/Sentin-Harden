"""Language handling.

Every user-facing string in the rule base is a mapping ``{"pl": ..., "en": ...}``.
The interface never hardcodes a translation of rule content, and never displays a
raw identifier - labels for vocabulary values come from ``vocabularies.yaml``.

Only the handful of strings belonging to the interface itself (button captions,
column headers) live here, because they have no place in the rule data.
"""

from __future__ import annotations

from typing import Iterable, Mapping

LANGUAGES = ("pl", "en")
DEFAULT_LANGUAGE = "pl"


class Language:
    """Currently selected language. Switching it requires no restart."""

    def __init__(self, code: str = DEFAULT_LANGUAGE) -> None:
        self.code = code if code in LANGUAGES else DEFAULT_LANGUAGE

    def set(self, code: str) -> None:
        if code in LANGUAGES:
            self.code = code

    def text(self, field: Mapping[str, str] | None, fallback: str = "") -> str:
        """Pick the active language from a bilingual field."""
        if not field:
            return fallback
        value = field.get(self.code)
        if value:
            return str(value).strip()
        # A missing translation is a defect caught by the validator, but the
        # interface must not go blank because of it.
        for other in LANGUAGES:
            if field.get(other):
                return str(field[other]).strip()
        return fallback

    def list(self, field: Mapping[str, Iterable[str]] | None) -> list[str]:
        """Pick the active language from a bilingual list field."""
        if not field:
            return []
        values = field.get(self.code)
        if values:
            return [str(item) for item in values]
        for other in LANGUAGES:
            if field.get(other):
                return [str(item) for item in field[other]]
        return []


# Interface strings. Rule content is never translated here.
UI_TEXT: dict[str, dict[str, str]] = {
    "window_title": {"pl": "Sentin-Harden", "en": "Sentin-Harden"},
    "scan": {"pl": "Skanuj", "en": "Scan"},
    "scanning": {"pl": "Sprawdzanie…", "en": "Scanning…"},
    "scanning_rule": {
        "pl": "Sprawdzanie {done}/{total}: {title}",
        "en": "Checking {done}/{total}: {title}",
    },
    "copy": {"pl": "Kopiuj polecenie", "en": "Copy command"},
    "copied": {"pl": "Skopiowano do schowka", "en": "Copied to clipboard"},
    "filter_risk": {"pl": "Ryzyko", "en": "Risk"},
    "filter_disruption": {"pl": "Uciążliwość", "en": "Disruption"},
    "filter_all": {"pl": "wszystkie", "en": "all"},
    "col_item": {"pl": "Punkt", "en": "Item"},
    "col_risk": {"pl": "Ryzyko", "en": "Risk"},
    "col_disruption": {"pl": "Uciążliwość", "en": "Disruption"},
    "col_result": {"pl": "Wynik", "en": "Result"},
    "detail_protects": {"pl": "Co wnosi", "en": "What it protects against"},
    "detail_breaks": {"pl": "Co przestanie działać", "en": "What stops working"},
    "detail_disruption": {"pl": "Dlaczego taka uciążliwość", "en": "Why this disruption class"},
    "detail_not_when": {"pl": "Kiedy nie stosować", "en": "When not to apply"},
    "detail_command": {"pl": "Polecenie naprawcze", "en": "Remediation command"},
    "detail_notes": {"pl": "Uwagi", "en": "Notes"},
    "detail_interruption": {"pl": "Przerwa w pracy", "en": "Interruption"},
    "detail_reversibility": {"pl": "Odwracalność", "en": "Reversibility"},
    "detail_areas": {"pl": "Obszary wpływu", "en": "Impact areas"},
    "detail_benchmark": {"pl": "Punkt benchmarku", "en": "Benchmark item"},
    "detail_empty": {"pl": "Wybierz punkt z listy.", "en": "Select an item from the list."},
    "run_unavailable": {
        "pl": "Uruchamianie z poziomu aplikacji nie jest jeszcze dostępne. Skopiuj polecenie i wykonaj je we własnej konsoli.",
        "en": "Running from the application is not available yet. Copy the command and run it in your own console.",
    },
    "no_impact_assessed": {
        "pl": "Sprawdzono — nie znaleziono skutków eksploatacyjnych.",
        "en": "Checked - no operational consequences found.",
    },
    "not_assessed": {
        "pl": "Wpływu jeszcze nie oceniono. Brak listy skutków nie oznacza, że ich nie ma.",
        "en": "Impact not assessed yet. An empty list does not mean there are none.",
    },
    "system_unknown": {"pl": "System nierozpoznany", "en": "System not recognised"},
    "summary": {
        "pl": "{total} reguł: {passed} spełnionych, {failed} niespełnionych, {errors} bez rozstrzygnięcia",
        "en": "{total} rules: {passed} compliant, {failed} non-compliant, {errors} undetermined",
    },
    "no_rules": {
        "pl": "Dla wykrytego systemu nie ma jeszcze reguł w bazie.",
        "en": "No rules in the base for the detected system yet.",
    },
}


def ui(key: str, language: Language, **kwargs: object) -> str:
    field = UI_TEXT.get(key)
    value = language.text(field, fallback=key)
    return value.format(**kwargs) if kwargs else value
