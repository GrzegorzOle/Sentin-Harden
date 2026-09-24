"""Printable audit report.

The report is a document meant to leave the machine: printed, signed, handed to
an auditor or a client. It is not a screenshot of the window, so it is built as
its own HTML with a print stylesheet rather than by dumping the table.

Two parts, in this order and for a reason:

* what the state is - the summary and the full list of items, so the reader can
  set the report beside the benchmark they hold;
* what to do about it - for every item found unmet, what it gives, what it
  breaks, and the commands, so the document stands on its own without the
  application.

The whole thing carries a reservation, and carries it twice. A list of commands
in a printed document invites being run straight through, and that is exactly
what must not happen here.
"""

from __future__ import annotations

import html
from datetime import datetime
from typing import Iterable

from . import paths
from .audit import AuditResult, Outcome, Scope, summarise
from .i18n import Language
from .ruleset import Rule, RuleBase

# Kept apart from i18n.py, which holds the short strings of the window. Report
# prose is long enough that mixing the two would bury the interface captions.
TEXT: dict[str, dict[str, str]] = {
    "title": {
        "pl": "Raport zgodności z CIS Benchmark",
        "en": "CIS Benchmark compliance report",
    },
    "generated": {"pl": "Sporządzono", "en": "Prepared"},
    "machine": {"pl": "Maszyna", "en": "Machine"},
    "scope": {"pl": "Zakres", "en": "Scope"},
    "reservation_heading": {
        "pl": "Zestawienie poglądowe — przeczytaj przed wdrożeniem",
        "en": "An indicative summary - read before rolling anything out",
    },
    "reservation_body": {
        "pl": (
            "Ten dokument jest <strong>zestawieniem poglądowym</strong>, a nie "
            "instrukcją do wykonania po kolei. Opisuje stan zastany w chwili "
            "sporządzenia i proponuje kierunek zmian — nie przesądza, że każda "
            "z nich jest w tym środowisku właściwa."
        ),
        "en": (
            "This document is <strong>an indicative summary</strong> and not a "
            "set of instructions to be worked through in order. It describes "
            "the state found at the time of preparation and proposes a "
            "direction - it does not settle that every change is right for "
            "this environment."
        ),
    },
    "reservation_points": {
        "pl": (
            "<li>Każdą zmianę stosuj <strong>pojedynczo</strong> i sprawdzaj "
            "skutek, zanim przejdziesz do następnej. Zbiorczo wolno stosować "
            "wyłącznie punkty opisane jako pozbawione uciążliwości.</li>"
            "<li>Przeczytaj rubrykę <em>Co przestanie działać</em>, zanim "
            "uruchomisz polecenie. Część punktów odcina funkcje, z których "
            "ktoś w tej organizacji korzysta na co dzień.</li>"
            "<li>Przed zmianą wykonaj <strong>kopię zapasową</strong> "
            "modyfikowanego zasobu. Polecenie kopii i polecenie wycofania są "
            "podane przy każdym punkcie, który je ma.</li>"
            "<li>Punkt bez podanego polecenia wycofania zmieniaj wyłącznie "
            "świadomie — powrót do stanu poprzedniego nie jest wtedy "
            "automatyczny.</li>"
            "<li>Świadome odpuszczenie punktu bywa decyzją prawidłową. "
            "Zapisz powód, zamiast zostawiać punkt bez rozstrzygnięcia.</li>"
            "<li>Polecenia napisano dla systemu wykrytego podczas audytu. Na "
            "innym wydaniu mogą zachować się inaczej.</li>"
        ),
        "en": (
            "<li>Apply every change <strong>one at a time</strong> and check "
            "the effect before moving to the next. Only items described as "
            "carrying no disruption may be applied in bulk.</li>"
            "<li>Read the <em>What stops working</em> entry before running a "
            "command. Some items cut off functions somebody in this "
            "organisation uses daily.</li>"
            "<li>Take a <strong>backup</strong> of the resource being modified "
            "first. The backup command and the rollback command are given for "
            "every item that has them.</li>"
            "<li>Change an item with no rollback command only deliberately - "
            "returning to the previous state is then not automatic.</li>"
            "<li>Deliberately letting an item go is sometimes the right "
            "decision. Record the reason rather than leaving the item "
            "unsettled.</li>"
            "<li>The commands were written for the system detected during the "
            "audit. On another release they may behave differently.</li>"
        ),
    },
    "part_one": {"pl": "Część I — stan zgodności", "en": "Part I - state of compliance"},
    "part_two": {
        "pl": "Część II — jak spełnić punkty niezaliczone",
        "en": "Part II - how to meet the items found unmet",
    },
    "summary_heading": {"pl": "Podsumowanie", "en": "Summary"},
    "total": {"pl": "Punktów sprawdzonych", "en": "Items checked"},
    "passed": {"pl": "Spełnionych", "en": "Compliant"},
    "failed": {"pl": "Niespełnionych", "en": "Not compliant"},
    "errors": {"pl": "Bez rozstrzygnięcia", "en": "Undetermined"},
    "errors_note": {
        "pl": (
            "„Bez rozstrzygnięcia” nie znaczy „w porządku”. Punktu nie dało "
            "się sprawdzić — najczęściej z braku uprawnień albo dlatego, że "
            "sprawdzany element nie istnieje w tym wydaniu systemu. Taki punkt "
            "wymaga ręcznego spojrzenia."
        ),
        "en": (
            "\"Undetermined\" does not mean \"in order\". The item could not be "
            "checked - most often for lack of privileges, or because the "
            "checked element does not exist in this release. Such an item "
            "calls for a look by hand."
        ),
    },
    "by_risk": {"pl": "Niespełnione według kategorii ryzyka", "en": "Not compliant by risk category"},
    "listing_heading": {"pl": "Wykaz punktów", "en": "List of items"},
    "listing_note": {
        "pl": (
            "Kolejność wynika z zestawienia ryzyka z uciążliwością, a nie "
            "z numeru punktu w benchmarku. Na górze są rzeczy o dużym znaczeniu "
            "i małym koszcie wdrożenia."
        ),
        "en": (
            "The order follows risk set against disruption rather than the item "
            "number in the benchmark. What carries weight and costs little to "
            "roll out comes first."
        ),
    },
    "col_item": {"pl": "Punkt", "en": "Item"},
    "col_risk": {"pl": "Ryzyko", "en": "Risk"},
    "col_disruption": {"pl": "Uciążliwość", "en": "Disruption"},
    "col_result": {"pl": "Wynik", "en": "Result"},
    "col_found": {"pl": "Wartość zastana", "en": "Value found"},
    "what_it_gives": {"pl": "Co wnosi", "en": "What it gives"},
    "what_breaks": {"pl": "Co przestanie działać", "en": "What stops working"},
    "do_not_apply": {"pl": "Kiedy nie stosować", "en": "When not to apply"},
    "interruption": {"pl": "Przerwa", "en": "Interruption"},
    "reversibility": {"pl": "Cofnięcie", "en": "Reversal"},
    "backup_command": {"pl": "Polecenie kopii zapasowej", "en": "Backup command"},
    "change_command": {"pl": "Polecenie naprawcze", "en": "Remediation command"},
    "rollback_command": {"pl": "Polecenie wycofania", "en": "Rollback command"},
    "no_rollback": {
        "pl": (
            "Ta reguła nie ma zdefiniowanego wycofania, więc aplikacja nie "
            "pozwala jej uruchomić. Polecenie podano wyłącznie do "
            "samodzielnego zastosowania, po rozważeniu skutków."
        ),
        "en": (
            "This rule has no rollback defined, so the application does not "
            "allow it to be run. The command is given for applying by hand "
            "alone, after the consequences have been weighed."
        ),
    },
    "nothing_failed": {
        "pl": (
            "Żaden ze sprawdzonych punktów nie został oceniony jako "
            "niespełniony. Zwróć jednak uwagę na punkty bez rozstrzygnięcia "
            "wymienione w części pierwszej."
        ),
        "en": (
            "None of the checked items was found unmet. Do look, however, at "
            "the undetermined items listed in the first part."
        ),
    },
    "no_impact": {
        "pl": "Sprawdzono — nie znaleziono skutków eksploatacyjnych.",
        "en": "Checked - no operational consequences found.",
    },
    "not_assessed": {
        "pl": (
            "Wpływu tej reguły jeszcze nie oceniono. Brak listy skutków nie "
            "oznacza, że skutków nie ma."
        ),
        "en": (
            "The impact of this rule has not been assessed yet. An empty list "
            "of consequences does not mean there are none."
        ),
    },
    "restore_heading": {
        "pl": "Jak cofnąć tę zmianę z kopii",
        "en": "How to undo this change from the backup",
    },
    "restore_heading_manual": {
        "pl": "Powrót do stanu sprzed zmiany",
        "en": "Getting back to the state before the change",
    },
    "restore_intro": {
        "pl": (
            "Polecenie kopii zapasowej zapisuje stan sprzed zmiany do pliku "
            "JSON, a polecenie wycofania odczytuje ten plik i przywraca z niego "
            "poprzednią wartość. Obydwa odwołują się do tego samego miejsca "
            "przez zapis <code>{{backup_file}}</code> — to nie jest nazwa "
            "pliku, tylko miejsce, w które wpisujesz ścieżkę."
        ),
        "en": (
            "The backup command writes the state from before the change to a "
            "JSON file, and the rollback command reads that file and restores "
            "the previous value from it. Both refer to the same place through "
            "<code>{{backup_file}}</code> - that is not a file name but a slot "
            "where you put a path."
        ),
    },
    "restore_steps": {
        "pl": (
            "<li>Ustal ścieżkę kopii. Uruchamiając polecenia z aplikacji, "
            "dostajesz ją już wpisaną — kopie trafiają do katalogu "
            "<code>%(dir)s</code> pod nazwą <code>%(pattern)s</code>. "
            "Uruchamiając je ręcznie, obowiązuje ścieżka podana "
            "w poleceniu kopii.</li>"
            "<li>W poleceniu wycofania wstaw tę samą ścieżkę w miejsce "
            "<code>{{backup_file}}</code>. Inna ścieżka niż przy kopii oznacza "
            "przywracanie z pliku, którego nie ma, albo z cudzego stanu.</li>"
            "<li>Uruchom polecenie wycofania w konsoli z uprawnieniami "
            "administratora, w tej samej powłoce co polecenie naprawcze.</li>"
            "<li>Sprawdź punkt ponownie. Dopiero powtórzony audyt jest dowodem, "
            "że stan wrócił — sam brak błędu nim nie jest.</li>"
        ),
        "en": (
            "<li>Establish the path of the backup. Running the commands from "
            "the application gives it to you already filled in - backups go to "
            "<code>%(dir)s</code> under the name <code>%(pattern)s</code>. "
            "Running them by hand, the path that counts is the one you gave in "
            "the backup command.</li>"
            "<li>Put that same path into the rollback command in place of "
            "<code>{{backup_file}}</code>. A different path than the backup "
            "used means restoring from a file that is not there, or from "
            "somebody else's state.</li>"
            "<li>Run the rollback command in a console with administrative "
            "rights, in the same shell as the remediation command.</li>"
            "<li>Check the item again. Only a repeated audit is proof that the "
            "state came back - the absence of an error is not.</li>"
        ),
    },
    "restore_no_rollback": {
        "pl": (
            "Ten punkt nie ma polecenia wycofania. Kopia zapisuje stan sprzed "
            "zmiany i pozwala odczytać, co obowiązywało, ale przywrócenie tej "
            "wartości wykonujesz samodzielnie. Zmieniaj ten punkt wyłącznie "
            "świadomie."
        ),
        "en": (
            "This item has no rollback command. The backup records the state "
            "from before the change and lets you read what was in force, but "
            "restoring that value is your own work. Change this item "
            "deliberately or not at all."
        ),
    },
    "restore_no_backup": {
        "pl": (
            "Ten punkt nie ma ani polecenia kopii zapasowej, ani polecenia "
            "wycofania. Przed zmianą zapisz stan zastany we własnym zakresie — "
            "bez tego powrót do poprzedniej konfiguracji opiera się na pamięci."
        ),
        "en": (
            "This item has neither a backup command nor a rollback command. "
            "Record the current state yourself before changing it - without "
            "that, getting back to the previous configuration rests on memory."
        ),
    },
    "page": {"pl": "Strona", "en": "Page"},
}

OUTCOME_LABEL: dict[Outcome, dict[str, str]] = {
    Outcome.PASS: {"pl": "spełniony", "en": "compliant"},
    Outcome.FAIL: {"pl": "niespełniony", "en": "not compliant"},
    Outcome.ERROR: {"pl": "bez rozstrzygnięcia", "en": "undetermined"},
    Outcome.NOT_APPLICABLE: {"pl": "nie dotyczy", "en": "not applicable"},
}

STYLE = """
@page { size: A4; margin: 18mm 16mm 20mm 16mm; }
body { font-family: "Segoe UI", "DejaVu Sans", sans-serif; font-size: 10.5pt;
       line-height: 1.45; color: #111; background: #fff; margin: 0; }
h1 { font-size: 20pt; margin: 0 0 4pt 0; }
h2 { font-size: 14pt; margin: 22pt 0 8pt 0; padding-bottom: 3pt;
     border-bottom: 1.5pt solid #333; page-break-after: avoid; }
h3 { font-size: 11.5pt; margin: 14pt 0 4pt 0; page-break-after: avoid; }
p, li { orphans: 3; widows: 3; }
.meta { color: #444; font-size: 9.5pt; margin: 0 0 14pt 0; }
.meta span { margin-right: 18pt; }
.reservation { border: 1.5pt solid #8a6d00; background: #fff8e1;
               padding: 9pt 12pt; margin: 12pt 0 18pt 0;
               page-break-inside: avoid; }
.reservation h2 { margin-top: 0; border: none; font-size: 12pt; color: #6b5400; }
.reservation ul { margin: 6pt 0 0 0; padding-left: 16pt; }
table { border-collapse: collapse; width: 100%; font-size: 9.5pt;
        margin: 8pt 0 4pt 0; }
th, td { border: 0.5pt solid #bbb; padding: 3pt 5pt; text-align: left;
         vertical-align: top; }
th { background: #eee; font-weight: 600; }
thead { display: table-header-group; }
tr { page-break-inside: avoid; }
.counts td.n { text-align: right; width: 14%; font-weight: 600; }
.note { font-size: 9.5pt; color: #444; font-style: italic; margin: 4pt 0 10pt 0; }
.rule { page-break-inside: avoid; margin: 0 0 16pt 0;
        border-left: 2.5pt solid #555; padding-left: 10pt; }
.rule .ident { font-family: "Consolas", monospace; font-size: 8.5pt;
               color: #555; }
.badges { margin: 3pt 0 6pt 0; font-size: 9pt; }
.badge { display: inline-block; border: 0.5pt solid #888; border-radius: 2pt;
         padding: 0.5pt 5pt; margin-right: 5pt; }
.field { margin: 5pt 0 0 0; }
.field .label { font-weight: 600; }
pre { font-family: "Consolas", monospace; font-size: 8.5pt; background: #f4f4f4;
      border: 0.5pt solid #ccc; padding: 5pt 7pt; margin: 3pt 0 0 0;
      white-space: pre-wrap; word-wrap: break-word; page-break-inside: avoid; }
.warn { color: #8a3500; font-weight: 600; }
.quiet { color: #4d5766; }
.restore { margin-top: 10pt; padding: 6pt 9pt; border-left: 3pt solid #8a8f98;
           background: #f4f5f7; page-break-inside: avoid; }
.restore h4 { margin: 0 0 4pt 0; font-size: 10pt; }
.restore ol { margin: 4pt 0 0 0; padding-left: 16pt; }
.restore code { font-family: Consolas, "DejaVu Sans Mono", monospace; font-size: 9pt; }
.part { page-break-before: always; }
@media print { .reservation { background: #fff; } }
"""


def _t(key: str, language: Language) -> str:
    return language.text(TEXT.get(key), key)


def _label(base: RuleBase, vocabulary: str, value: str, language: Language) -> str:
    """Human label for a vocabulary value, never the raw identifier."""
    for entry in (base.vocabularies.get(vocabulary) or {}).get("values", []):
        if entry.get("id") == value:
            return language.text(entry.get("label"), value)
    return value


def _esc(value: object) -> str:
    return html.escape(str(value or "")).replace("\n", "<br>")


def _bullets(rule: Rule, field: str, language: Language) -> list[str]:
    entries = (rule.consequences.get(field) or {}).get(language.code)
    if not entries:
        for other in ("pl", "en"):
            entries = (rule.consequences.get(field) or {}).get(other)
            if entries:
                break
    return [str(item) for item in (entries or [])]


def _summary_counts(results: list[AuditResult], language: Language) -> str:
    counts = summarise(results)
    rows = "".join(
        f"<tr><td>{_t(key, language)}</td><td class='n'>{counts[key]}</td></tr>"
        for key in ("total", "passed", "failed", "errors")
    )
    return f"<table class='counts'>{rows}</table>"


def _risk_breakdown(
    base: RuleBase, results: list[AuditResult], language: Language
) -> str:
    failed = [r for r in results if r.outcome is Outcome.FAIL]
    if not failed:
        return ""
    order = ["critical", "high", "medium", "low"]
    tally: dict[str, int] = {}
    for item in failed:
        tally[item.rule.risk] = tally.get(item.rule.risk, 0) + 1
    rows = "".join(
        "<tr><td>%s</td><td class='n'>%d</td></tr>"
        % (_esc(_label(base, "risk_category", key, language)), tally[key])
        for key in order
        if key in tally
    )
    return (
        f"<h3>{_t('by_risk', language)}</h3><table class='counts'>{rows}</table>"
    )


def _listing(base: RuleBase, results: list[AuditResult], language: Language) -> str:
    head = "".join(
        f"<th>{_t(key, language)}</th>"
        for key in ("col_item", "col_risk", "col_disruption", "col_result", "col_found")
    )
    rows = []
    for item in results:
        rule = item.rule
        rows.append(
            "<tr><td>%s<br><span class='ident'>%s</span></td>"
            "<td>%s</td><td>%s</td><td>%s</td><td>%s</td></tr>"
            % (
                _esc(language.text(rule.title, rule.identifier)),
                _esc(rule.identifier),
                _esc(_label(base, "risk_category", rule.risk, language)),
                _esc(_label(base, "disruption", rule.disruption, language)),
                _esc(language.text(OUTCOME_LABEL.get(item.outcome), item.outcome.value)),
                _esc(item.actual),
            )
        )
    return (
        f"<table><thead><tr>{head}</tr></thead><tbody>"
        + "".join(rows)
        + "</tbody></table>"
    )


def _restore_section(rule: Rule, language: Language) -> str:
    """Closing section of every instruction: getting back to where it was.

    Printed even where the rule has no rollback, because that is the case the
    reader most needs to know about before typing the command above. The
    placeholder in the commands is a slot, not a file name, and a document read
    away from the application has nothing else to explain it.
    """
    remediation = rule.remediation

    if not remediation.get("rollback_command"):
        # No copy to restore from means the heading cannot promise one.
        has_backup = bool(remediation.get("backup_command"))
        key = "restore_no_rollback" if has_backup else "restore_no_backup"
        heading = "restore_heading" if has_backup else "restore_heading_manual"
        return "<div class='restore'><h4>%s</h4><p class='warn'>%s</p></div>" % (
            _esc(_t(heading, language)),
            _esc(_t(key, language)),
        )

    body = "<h4>%s</h4>" % _esc(_t("restore_heading", language))

    steps = _t("restore_steps", language) % {
        "dir": _esc(str(paths.backup_dir())),
        "pattern": _esc("%s-RRRRMMDD-GGMMSS.json" % rule.identifier)
        if language.code == "pl"
        else _esc("%s-YYYYMMDD-HHMMSS.json" % rule.identifier),
    }
    return "<div class='restore'>%s<p>%s</p><ol>%s</ol></div>" % (
        body,
        _t("restore_intro", language),
        steps,
    )


def _rule_section(
    base: RuleBase, item: AuditResult, language: Language, number: int
) -> str:
    rule = item.rule
    parts: list[str] = ["<div class='rule'>"]
    parts.append(
        "<h3>%d. %s</h3><div class='ident'>%s</div>"
        % (number, _esc(language.text(rule.title, rule.identifier)), _esc(rule.identifier))
    )

    badges = [
        _label(base, "risk_category", rule.risk, language),
        _label(base, "disruption", rule.disruption, language),
    ]
    consequences = rule.consequences
    for key, vocabulary in (
        ("interruption", "interruption"),
        ("reversibility", "reversibility"),
    ):
        value = consequences.get(key)
        if value:
            badges.append(
                "%s: %s" % (_t(key, language), _label(base, vocabulary, value, language))
            )
    parts.append(
        "<div class='badges'>"
        + "".join(f"<span class='badge'>{_esc(b)}</span>" for b in badges)
        + "</div>"
    )

    description = rule.data.get("description") or {}
    if description:
        parts.append(
            "<div class='field'><span class='label'>%s:</span><br>%s</div>"
            % (_t("what_it_gives", language), _esc(language.text(description)))
        )

    for field, key in (("what_breaks", "what_breaks"), ("do_not_apply_when", "do_not_apply")):
        entries = _bullets(rule, field, language)
        if entries:
            parts.append(
                "<div class='field'><span class='label'>%s:</span><ul>%s</ul></div>"
                % (
                    _t(key, language),
                    "".join(f"<li>{_esc(entry)}</li>" for entry in entries),
                )
            )
        elif field == "what_breaks":
            # An empty list must never print as nothing. On paper a missing
            # heading reads as a guarantee that the change is harmless, and the
            # two reasons a list can be empty - assessed and clean, or never
            # assessed at all - have to stay apart.
            note = "not_assessed" if rule.assessment_state == "not-assessed" else "no_impact"
            parts.append(
                "<div class='field'><span class='label'>%s:</span> <span class='%s'>%s</span></div>"
                % (
                    _t(key, language),
                    "warn" if note == "not_assessed" else "quiet",
                    _t(note, language),
                )
            )

    remediation = rule.remediation
    for key, caption in (
        ("backup_command", "backup_command"),
        ("change_command", "change_command"),
        ("rollback_command", "rollback_command"),
    ):
        command = remediation.get(key)
        if command:
            parts.append(
                "<div class='field'><span class='label'>%s:</span><pre>%s</pre></div>"
                % (_t(caption, language), html.escape(str(command).rstrip()))
            )

    if not rule.runnable:
        parts.append(f"<p class='warn'>{_t('no_rollback', language)}</p>")

    parts.append(_restore_section(rule, language))
    parts.append("</div>")
    return "".join(parts)


def build_html(
    base: RuleBase,
    scope: Scope,
    results: list[AuditResult],
    language: Language,
    machine: str = "",
    generated_at: datetime | None = None,
) -> str:
    """Whole report as one self-contained HTML document."""
    # Sorted here rather than taken as given, so the document reads the same
    # whoever builds it: the decision matrix first, benchmark numbering never.
    results = sorted(results, key=lambda item: item.rule.matrix_key)
    moment = (generated_at or datetime.now()).strftime("%Y-%m-%d %H:%M")
    targets = ", ".join(
        language.text(target.name, target.identifier) for target in scope.targets
    )

    head = [
        "<!DOCTYPE html><html lang='%s'><head><meta charset='utf-8'>" % language.code,
        "<title>%s</title><style>%s</style></head><body>" % (
            _esc(_t("title", language)), STYLE),
        "<h1>%s</h1>" % _esc(_t("title", language)),
        # The separators are characters rather than margins on purpose: the
        # PDF path renders through a text engine that ignores part of the
        # stylesheet, and without them the three entries run into one word.
        "<p class='meta'><span><strong>%s:</strong> %s</span> &middot; "
        "<span><strong>%s:</strong> %s</span> &middot; "
        "<span><strong>%s:</strong> %s</span></p>"
        % (
            _t("generated", language), _esc(moment),
            _t("machine", language), _esc(machine or "-"),
            _t("scope", language), _esc(targets or "-"),
        ),
    ]

    reservation = (
        "<div class='reservation'><h2>%s</h2><p>%s</p><ul>%s</ul></div>"
        % (
            _esc(_t("reservation_heading", language)),
            _t("reservation_body", language),
            _t("reservation_points", language),
        )
    )
    head.append(reservation)

    body = [
        "<h2>%s</h2>" % _esc(_t("part_one", language)),
        "<h3>%s</h3>" % _esc(_t("summary_heading", language)),
        _summary_counts(results, language),
        "<p class='note'>%s</p>" % _esc(_t("errors_note", language)),
        _risk_breakdown(base, results, language),
        "<h3>%s</h3>" % _esc(_t("listing_heading", language)),
        "<p class='note'>%s</p>" % _esc(_t("listing_note", language)),
        _listing(base, results, language),
    ]

    failed = [item for item in results if item.outcome is Outcome.FAIL]
    body.append("<div class='part'><h2>%s</h2>" % _esc(_t("part_two", language)))
    # The reservation is repeated here on purpose. Part two is what gets read
    # on its own, and a page of commands without it invites being worked
    # straight through.
    body.append(reservation)
    if not failed:
        body.append("<p>%s</p>" % _esc(_t("nothing_failed", language)))
    else:
        for number, item in enumerate(failed, start=1):
            body.append(_rule_section(base, item, language, number))
    body.append("</div>")

    return "".join(head) + "".join(body) + "</body></html>"
