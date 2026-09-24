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
    "no_impact_assessed": {
        "pl": "Sprawdzono — nie znaleziono skutków eksploatacyjnych.",
        "en": "Checked - no operational consequences found.",
    },
    "not_assessed": {
        "pl": "Wpływu jeszcze nie oceniono. Brak listy skutków nie oznacza, że ich nie ma.",
        "en": "Impact not assessed yet. An empty list does not mean there are none.",
    },
    # -- simulation and execution -----------------------------------------
    "run": {"pl": "Zastosuj…", "en": "Apply…"},
    "run_hint": {
        "pl": (
            "Pokazuje, co dokładnie się zmieni i czego to dotknie na tej "
            "maszynie. Nic nie zostanie wykonane przed potwierdzeniem."
        ),
        "en": (
            "Shows exactly what will change and what it reaches into on this "
            "machine. Nothing runs before it is confirmed."
        ),
    },
    "preview_title": {"pl": "Co się wydarzy", "en": "What will happen"},
    "preview_lead": {
        "pl": (
            "Nic jeszcze nie zostało wykonane. Poniżej jest wykaz skutków, "
            "a dopiero pod nim polecenia, które je wywołają."
        ),
        "en": (
            "Nothing has been done yet. Below is the list of consequences, and "
            "only under it the commands that bring them about."
        ),
    },
    "preview_areas": {"pl": "Co zostanie dotknięte", "en": "What will be touched"},
    "preview_no_areas": {
        "pl": (
            "Reguła nie wskazuje żadnego obszaru wpływu. To nie znaczy, że "
            "zmiana jest niegroźna — znaczy, że nikt jeszcze tego nie ocenił."
        ),
        "en": (
            "The rule points at no impact area. That does not mean the change "
            "is harmless - it means nobody has assessed it yet."
        ),
    },
    "preview_sequence": {"pl": "Kolejność wykonania", "en": "Order of execution"},
    "preview_stage_missing": {
        "pl": "Reguła nie definiuje tego kroku.",
        "en": "The rule does not define this step.",
    },
    "preview_rollback_hint": {
        "pl": (
            "Zostanie zapisane razem z kopią. Nie wykonuje się samo — jest do "
            "użycia wtedy, gdy zmiana okaże się błędem."
        ),
        "en": (
            "Recorded together with the backup. It does not run by itself - it "
            "is there for when the change turns out to be a mistake."
        ),
    },
    "preview_user_visible": {
        "pl": "Użytkownik to zauważy",
        "en": "The user will notice",
    },
    "preview_yes": {"pl": "tak", "en": "yes"},
    "preview_no": {"pl": "nie", "en": "no"},
    "preview_blocked": {
        "pl": "Dlaczego nie można tego uruchomić",
        "en": "Why this cannot be run",
    },
    "preview_copy_instead": {
        "pl": (
            "Polecenie pozostaje do skopiowania i wykonania we własnej konsoli. "
            "Blokada dotyczy uruchamiania z aplikacji, nie samej zmiany."
        ),
        "en": (
            "The command remains available to copy and run in your own console. "
            "The block concerns running it from the application, not the change "
            "itself."
        ),
    },
    "preview_single_only": {
        "pl": (
            "Jeden punkt, jedna decyzja. Aplikacja nie stosuje zmian zbiorczo — "
            "każdy punkt ma własny podgląd i własny wynik sprawdzenia."
        ),
        "en": (
            "One item, one decision. The application applies nothing in bulk - "
            "every item gets its own preview and its own re-check."
        ),
    },
    "preview_run": {"pl": "Wykonaj", "en": "Run"},
    "preview_cancel": {"pl": "Nie zmieniaj niczego", "en": "Change nothing"},
    "stage_backup": {"pl": "Kopia zapasowa", "en": "Backup"},
    "stage_change": {"pl": "Zmiana", "en": "Change"},
    "stage_verify": {"pl": "Ponowne sprawdzenie", "en": "Re-check"},
    "blocker_no_backup": {
        "pl": "Reguła nie ma polecenia kopii zapasowej.",
        "en": "The rule has no backup command.",
    },
    "blocker_no_rollback": {
        "pl": "Reguła nie ma polecenia wycofania.",
        "en": "The rule has no rollback command.",
    },
    "blocker_no_change": {
        "pl": "Reguła nie ma polecenia naprawczego.",
        "en": "The rule has no remediation command.",
    },
    "blocker_not_runnable": {
        "pl": "Reguła nie jest oznaczona jako gotowa do uruchomienia.",
        "en": "The rule is not marked as ready to run.",
    },
    "blocker_needs_elevation": {
        "pl": (
            "Aplikacja nie ma uprawnień administratora. Uruchom ją jako "
            "administrator albo skopiuj polecenie do konsoli z uprawnieniami."
        ),
        "en": (
            "The application has no administrative rights. Start it as an "
            "administrator or copy the command into an elevated console."
        ),
    },
    "presence_in_use": {
        "pl": "wykryto na tej maszynie",
        "en": "found on this machine",
    },
    "presence_no_sign": {
        "pl": "nie znaleziono śladu",
        "en": "no sign of it found",
    },
    "presence_undetermined": {
        "pl": "nie ustalono",
        "en": "not determined",
    },
    "presence_caveat": {
        "pl": (
            "Inwentaryzacja jest przesłanką, nie dowodem. Brak śladu na tej "
            "maszynie nie znaczy, że nikt z tego nie korzysta."
        ),
        "en": (
            "The inventory is a premise, not a proof. No sign on this machine "
            "does not mean nobody uses it."
        ),
    },
    "presence_partial": {
        "pl": (
            "Części informacji nie dało się odczytać bez uprawnień "
            "administratora — stąd pozycje bez rozstrzygnięcia."
        ),
        "en": (
            "Some of the information could not be read without administrative "
            "rights - hence the undetermined entries."
        ),
    },
    "applying": {"pl": "Wykonywanie zmiany…", "en": "Applying the change…"},
    "outcome_title": {"pl": "Wynik", "en": "Outcome"},
    "outcome_close": {"pl": "Zamknij", "en": "Close"},
    "outcome_verified": {
        "pl": "Zmiana wykonana i potwierdzona ponownym sprawdzeniem.",
        "en": "The change was applied and confirmed by a re-check.",
    },
    "outcome_not_verified": {
        "pl": (
            "Polecenie się wykonało, ale ponowne sprawdzenie nadal nie wykazuje "
            "zgodności. Stan systemu mógł się nie zmienić."
        ),
        "en": (
            "The command ran, but the re-check still does not show compliance. "
            "The state of the system may not have changed."
        ),
    },
    "outcome_backup_failed": {
        "pl": (
            "Kopia zapasowa się nie powiodła, więc zmiana nie została "
            "wykonana. System pozostał nietknięty."
        ),
        "en": (
            "The backup failed, so the change was not applied. The system was "
            "left untouched."
        ),
    },
    "outcome_blocked": {
        "pl": "Wykonanie zostało wstrzymane. System pozostał nietknięty.",
        "en": "Execution was withheld. The system was left untouched.",
    },
    "outcome_backup_at": {
        "pl": "Kopia zapasowa: {path}",
        "en": "Backup: {path}",
    },
    "outcome_skipped": {
        "pl": "Krok pominięty, bo poprzedni się nie powiódł.",
        "en": "Step skipped because the previous one failed.",
    },
    "outcome_exit": {"pl": "Kod wyjścia: {code}", "en": "Exit code: {code}"},
    "outcome_rollback_hint": {
        "pl": (
            "Skopiuj i uruchom w konsoli z uprawnieniami administratora, żeby "
            "wrócić do stanu sprzed zmiany."
        ),
        "en": (
            "Copy and run it in an elevated console to get back to the state "
            "from before the change."
        ),
    },
    # -- reverse view ------------------------------------------------------
    "tab_audit": {"pl": "Audyt", "en": "Audit"},
    "tab_reverse": {"pl": "Z czego korzystam", "en": "What I use"},
    "reverse_lead": {
        "pl": (
            "Pytanie odwrotne: zamiast zaczynać od punktu benchmarku, zacznij "
            "od tego, z czego korzystasz. Wskaż obszar po lewej, a po prawej "
            "zobaczysz punkty, które w niego uderzają. Pogrubione obszary to "
            "te, po których ta maszyna pokazuje ślad użycia — ale brak śladu "
            "nie jest dowodem, że nikt z nich nie korzysta. "
            "Dwuklik otwiera punkt w widoku audytu."
        ),
        "en": (
            "The question the other way round: instead of starting from a "
            "benchmark item, start from what you use. Pick an area on the left "
            "and the items that reach into it appear on the right. The areas in "
            "bold are those this machine shows signs of using - but no sign is "
            "not proof that nobody uses them. "
            "A double click opens the item in the audit view."
        ),
    },
    "reverse_caption": {
        "pl": "{area}: {total} punktów, z tego {failing} niespełnionych na tej maszynie.",
        "en": "{area}: {total} items, {failing} of them unmet on this machine.",
    },
    "reverse_caption_unscanned": {
        "pl": "{area}: {total} punktów w zakresie. Uruchom skanowanie, żeby zobaczyć, które są niespełnione.",
        "en": "{area}: {total} items in scope. Run a scan to see which of them are unmet.",
    },
    "reverse_unchecked": {"pl": "—", "en": "-"},
    "reverse_scan_first": {
        "pl": "Najpierw uruchom skanowanie — bez niego nie ma czego otworzyć w widoku audytu.",
        "en": "Run a scan first - without one there is nothing to open in the audit view.",
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
