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
    "report": {"pl": "Raport do druku", "en": "Printable report"},
    "report_save": {"pl": "Zapisz raport", "en": "Save report"},
    "report_saved": {"pl": "Zapisano raport: {path}", "en": "Report saved: {path}"},
    "report_failed": {
        "pl": "Nie udało się zapisać raportu: {error}",
        "en": "Could not save the report: {error}",
    },
    "copy": {"pl": "Kopiuj polecenie", "en": "Copy command"},
    "copied": {"pl": "Skopiowano do schowka", "en": "Copied to clipboard"},
    "copy_rollback": {
        "pl": "Kopiuj polecenie wycofania",
        "en": "Copy rollback command",
    },
    "copy_rollback_hint": {
        "pl": (
            "Przywraca stan z pliku kopii zapasowej zapisanego przed zmianą. "
            "Ścieżka jest już wpisana w polecenie — uruchom je w konsoli "
            "z uprawnieniami administratora, a potem sprawdź punkt ponownie."
        ),
        "en": (
            "Restores the state from the backup file written before the "
            "change. The path is already filled in - run the command in a "
            "console with administrative rights, then check the item again."
        ),
    },
    "copied_rollback": {
        "pl": "Skopiowano polecenie wycofania. Działa tylko z plikiem kopii, do którego wskazuje.",
        "en": "Rollback command copied. It works only with the backup file it points at.",
    },
    "filter_risk": {"pl": "Ryzyko", "en": "Risk"},
    "filter_disruption": {"pl": "Uciążliwość", "en": "Disruption"},
    "filter_result": {"pl": "Wynik", "en": "Result"},
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
    "detail_rollback": {"pl": "Polecenie wycofania", "en": "Rollback command"},
    "detail_rollback_hint": {
        "pl": (
            "Odczytuje plik kopii zapasowej i przywraca z niego poprzednią "
            "wartość. Ma sens dopiero wtedy, gdy kopia powstała — plik jest ten "
            "sam, który zapisuje polecenie powyżej."
        ),
        "en": (
            "Reads the backup file and restores the previous value from it. It "
            "means something only once the backup exists - the file is the same "
            "one the command above writes."
        ),
    },
    "detail_no_rollback": {
        "pl": (
            "Ta reguła nie ma polecenia wycofania. Powrót do stanu poprzedniego "
            "nie jest automatyczny — zapisz stan zastany, zanim cokolwiek "
            "zmienisz."
        ),
        "en": (
            "This rule has no rollback command. Getting back to the previous "
            "state is not automatic - record the current state before changing "
            "anything."
        ),
    },
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
    "summary_filtered": {
        "pl": "(widocznych: {visible})",
        "en": "(visible: {visible})",
    },
    "no_matches": {
        "pl": "Żaden punkt nie pasuje do ustawionych filtrów.",
        "en": "No item matches the selected filters.",
    },
    "no_rules": {
        "pl": "Dla wykrytego systemu nie ma jeszcze reguł w bazie.",
        "en": "No rules in the base for the detected system yet.",
    },
    "overlay_excluded": {
        "pl": "wykryte, poza zakresem skanowania",
        "en": "detected, outside the scope of the scan",
    },
    "overlay_excluded_hint": {
        "pl": (
            "Na tej maszynie wykryto: %s. Paczka reguł dla tego składnika nie "
            "obejmuje wykrytego systemu, więc jego punkty nie zostaną "
            "sprawdzone. Raport nie mówi o nim nic — ani że jest w porządku, "
            "ani że nie jest."
        ),
        "en": (
            "Found on this machine: %s. The rule pack for that component does "
            "not cover the detected system, so its items will not be checked. "
            "The report says nothing about it - neither that it is in order nor "
            "that it is not."
        ),
    },
}


def ui(key: str, language: Language, **kwargs: object) -> str:
    field = UI_TEXT.get(key)
    value = language.text(field, fallback=key)
    return value.format(**kwargs) if kwargs else value
