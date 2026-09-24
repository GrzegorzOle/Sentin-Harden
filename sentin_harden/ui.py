"""The audit window.

First stage only: detect the system, run the rules, show what was found and let
the user copy a remediation command. There is deliberately no Run button - it
belongs with the backup machinery, which is not built yet, and a Run button that
skips the backup would violate the rule the whole project rests on.
"""

from __future__ import annotations

import html

from PySide6.QtCore import QAbstractTableModel, QModelIndex, Qt, QThread, Signal
from PySide6.QtGui import QColor, QFont, QPalette
from PySide6.QtWidgets import (
    QApplication,
    QComboBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QMainWindow,
    QProgressBar,
    QPushButton,
    QSplitter,
    QTableView,
    QTextBrowser,
    QVBoxLayout,
    QWidget,
)

from . import paths
from .audit import AuditResult, AuditRunner, Outcome, Scope, summarise
from .i18n import Language, ui
from .ruleset import DISRUPTION_ORDER, RISK_ORDER, Rule, RuleBase, Target, load

# Two colour sets. The table follows the system theme, so its colours have to
# work on a dark background as well - the dark-red used on paper turns into an
# unreadable smudge there. The detail panel is always a light document, so it
# uses the print set regardless of the system theme.
RISK_COLOURS_ON_LIGHT = {
    "critical": "#b3261e",
    "high": "#b1580f",
    "medium": "#7a5f12",
    "low": "#4d5766",
}

RISK_COLOURS_ON_DARK = {
    "critical": "#ff7a6e",
    "high": "#ffab5c",
    "medium": "#e6c95f",
    "low": "#a5b0c0",
}

OUTCOME_COLOURS_ON_LIGHT = {
    Outcome.PASS: "#2e7d32",
    Outcome.FAIL: "#b3261e",
    Outcome.ERROR: "#7a5f12",
    Outcome.NOT_APPLICABLE: "#4d5766",
}

OUTCOME_COLOURS_ON_DARK = {
    Outcome.PASS: "#6bcf76",
    Outcome.FAIL: "#ff7a6e",
    Outcome.ERROR: "#e6c95f",
    Outcome.NOT_APPLICABLE: "#a5b0c0",
}


def dark_theme() -> bool:
    """True when the system palette is dark."""
    return QApplication.palette().color(QPalette.Window).lightness() < 128


def risk_colour(risk: str) -> str:
    table = RISK_COLOURS_ON_DARK if dark_theme() else RISK_COLOURS_ON_LIGHT
    return table.get(risk, "#a5b0c0" if dark_theme() else "#4d5766")


def outcome_colour(outcome: Outcome) -> str:
    table = OUTCOME_COLOURS_ON_DARK if dark_theme() else OUTCOME_COLOURS_ON_LIGHT
    return table.get(outcome, "#a5b0c0" if dark_theme() else "#4d5766")


class ScanWorker(QThread):
    """Runs the audit off the interface thread so the window stays responsive.

    It walks the rules itself instead of calling ``run_target``, because a single
    test command can take seconds - long enough for a silent window to look
    frozen. Reporting after every rule is what makes the progress bar move.
    """

    # (rules done, rules total, the rule about to be checked)
    progress = Signal(int, int, object)
    finished_with = Signal(object)

    def __init__(self, rules: list[Rule]) -> None:
        super().__init__()
        # A flat list rather than a target, because a scan covers the host pack
        # and every overlay that applies on top of it. One progress bar has to
        # count them together or it restarts halfway through.
        self._rules = list(rules)

    def run(self) -> None:
        runner = AuditRunner()
        rules = self._rules
        total = len(rules)
        results: list[AuditResult] = []
        for index, rule in enumerate(rules):
            # Announced before the command runs, so the name on the status bar
            # is the rule the user is actually waiting for.
            self.progress.emit(index, total, rule)
            results.append(runner.run_rule(rule))
        self.finished_with.emit(results)


class ResultsModel(QAbstractTableModel):
    COLUMNS = ("col_item", "col_risk", "col_disruption", "col_result")

    def __init__(self, base: RuleBase, language: Language) -> None:
        super().__init__()
        self._base = base
        self._language = language
        self._all: list[AuditResult] = []
        self._rows: list[AuditResult] = []
        self._risk_filter = ""
        self._disruption_filter = ""
        self._outcome_filter = ""

    # -- data --------------------------------------------------------------

    def set_results(self, results: list[AuditResult]) -> None:
        self.beginResetModel()
        # Default order is the decision matrix, not the benchmark numbering:
        # high risk with no disruption first, those are the quick wins.
        self._all = sorted(results, key=lambda r: r.rule.matrix_key)
        self._apply_filters()
        self.endResetModel()

    def set_filters(self, risk: str, disruption: str, outcome: str = "") -> None:
        self.beginResetModel()
        self._risk_filter = risk
        self._disruption_filter = disruption
        self._outcome_filter = outcome
        self._apply_filters()
        self.endResetModel()

    def _apply_filters(self) -> None:
        self._rows = [
            item
            for item in self._all
            if (not self._risk_filter or item.rule.risk == self._risk_filter)
            and (not self._disruption_filter or item.rule.disruption == self._disruption_filter)
            and (not self._outcome_filter or item.outcome.value == self._outcome_filter)
        ]

    def has_results(self) -> bool:
        """Whether a scan has produced anything, regardless of the filters."""
        return bool(self._all)

    def result_at(self, row: int) -> AuditResult | None:
        return self._rows[row] if 0 <= row < len(self._rows) else None

    def retranslate(self) -> None:
        self.headerDataChanged.emit(Qt.Horizontal, 0, len(self.COLUMNS) - 1)
        if self._rows:
            self.dataChanged.emit(
                self.index(0, 0), self.index(len(self._rows) - 1, len(self.COLUMNS) - 1)
            )

    # -- Qt model interface ------------------------------------------------

    def rowCount(self, parent: QModelIndex = QModelIndex()) -> int:
        return 0 if parent.isValid() else len(self._rows)

    def columnCount(self, parent: QModelIndex = QModelIndex()) -> int:
        return 0 if parent.isValid() else len(self.COLUMNS)

    def headerData(self, section: int, orientation: Qt.Orientation, role: int = Qt.DisplayRole):
        if orientation != Qt.Horizontal or role != Qt.DisplayRole:
            return None
        return ui(self.COLUMNS[section], self._language)

    def data(self, index: QModelIndex, role: int = Qt.DisplayRole):
        item = self.result_at(index.row())
        if item is None:
            return None
        rule = item.rule
        column = index.column()

        if role == Qt.DisplayRole:
            if column == 0:
                return self._language.text(rule.title, fallback=rule.identifier)
            if column == 1:
                return self._language.text(self._base.label("risk_category", rule.risk))
            if column == 2:
                return self._language.text(self._base.label("disruption", rule.disruption))
            if column == 3:
                return self._language.text(self._base.label("audit_result", item.outcome.value))

        if role == Qt.ToolTipRole and column == 0:
            # Titles are longer in Polish than in English and the column is the
            # first thing a narrow window squeezes; the tooltip keeps the full
            # text reachable instead of ending at an ellipsis.
            return self._language.text(rule.title, fallback=rule.identifier)

        if role == Qt.ForegroundRole:
            if column == 1:
                return QColor(risk_colour(rule.risk))
            if column == 3:
                return QColor(outcome_colour(item.outcome))

        if role == Qt.FontRole and column in (1, 3):
            font = QFont()
            font.setBold(True)
            return font

        return None


class DetailPanel(QTextBrowser):
    """Everything the user needs to decide, in the active language."""

    def __init__(self, base: RuleBase, language: Language) -> None:
        super().__init__()
        self._base = base
        self._language = language
        self._current: AuditResult | None = None
        self.setOpenExternalLinks(True)
        # A fixed light document rather than a themed widget. Under a dark system
        # theme Qt forces light text, which turned the command box - deliberately
        # light so it reads like a console listing - into white on near-white.
        # This pane is also what the printed report will look like, so keeping it
        # paper-coloured in both themes is the consistent choice.
        self.setStyleSheet(
            "QTextBrowser{background:#ffffff;color:#1a1d21;"
            "border:1px solid #c9ced6;padding:6px;}"
        )
        self.show_result(None)

    def show_result(self, item: AuditResult | None) -> None:
        self._current = item
        if item is None:
            self.setHtml(f"<p style='color:#5a6472'>{ui('detail_empty', self._language)}</p>")
            return
        self.setHtml(self._build_html(item))

    def retranslate(self) -> None:
        self.show_result(self._current)

    def command_for_clipboard(self) -> str:
        """Backup and change together.

        Copying only the change would let the manual path skip the backup, which
        is exactly the guarantee the application is supposed to give.
        """
        if self._current is None:
            return ""
        remediation = self._current.rule.remediation
        if not remediation:
            return ""

        stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        backup_file = paths.backup_dir() / f"{self._current.rule.identifier}-{stamp}.json"

        parts: list[str] = []
        backup = remediation.get("backup_command")
        if backup:
            parts.append(backup.strip())
        change = remediation.get("change_command")
        if change:
            parts.append(change.strip())
        return "\n\n".join(parts).replace("{{backup_file}}", str(backup_file))

    # -- rendering ---------------------------------------------------------

    def _t(self, field, fallback: str = "") -> str:
        return self._language.text(field, fallback)

    def _label(self, vocabulary: str, value: str) -> str:
        return self._t(self._base.label(vocabulary, value))

    def _build_html(self, item: AuditResult) -> str:
        rule: Rule = item.rule
        lang = self._language
        out: list[str] = [
            "<style>"
            "body{font-family:'Segoe UI',sans-serif;font-size:10.5pt;"
            "color:#1a1d21;background:#ffffff;}"
            "h2{margin:0 0 4px 0;font-size:13pt;color:#1a1d21;}"
            "h3{margin:14px 0 4px 0;font-size:10pt;text-transform:uppercase;color:#5a6472;}"
            "pre{background:#f4f5f7;color:#1a1d21;border:1px solid #d8dbe0;"
            "padding:8px;white-space:pre-wrap;font-family:Consolas,'Courier New',monospace;"
            "font-size:9.5pt;}"
            "li{margin-bottom:3px;}"
            "</style>"
        ]

        title = html.escape(self._t(rule.title, rule.identifier))
        out.append(f"<h2>{title}</h2>")

        risk = html.escape(self._label("risk_category", rule.risk))
        disruption = html.escape(self._label("disruption", rule.disruption))
        outcome = html.escape(self._label("audit_result", item.outcome.value))
        risk_ink = RISK_COLOURS_ON_LIGHT.get(rule.risk, "#4d5766")
        outcome_ink = OUTCOME_COLOURS_ON_LIGHT.get(item.outcome, "#4d5766")
        out.append(
            f"<p><b style='color:{risk_ink}'>{risk}</b> &nbsp;|&nbsp; {disruption}"
            f" &nbsp;|&nbsp; <b style='color:{outcome_ink}'>{outcome}</b></p>"
        )

        benchmark = rule.data.get("benchmark", {})
        reference = f"{benchmark.get('name', '')} {benchmark.get('version', '')} — {benchmark.get('item', '')}"
        section = benchmark.get("section")
        if section:
            reference += f" ({section})"
        out.append(
            f"<h3>{ui('detail_benchmark', lang)}</h3><p>{html.escape(reference.strip())}</p>"
        )

        out.append(f"<h3>{ui('detail_protects', lang)}</h3>")
        out.append(f"<p>{self._paragraphs(self._t(rule.data.get('description')))}</p>")

        out.append(f"<h3>{ui('detail_breaks', lang)}</h3>")
        breaks = lang.list(rule.consequences.get("what_breaks"))
        if breaks:
            out.append("<ul>" + "".join(f"<li>{html.escape(b)}</li>" for b in breaks) + "</ul>")
        elif rule.assessment_state == "assessed-no-impact":
            out.append(f"<p>{ui('no_impact_assessed', lang)}</p>")
        else:
            out.append(f"<p style='color:#8a6d1f'>{ui('not_assessed', lang)}</p>")

        disruption_text = self._t(rule.data.get("disruption_description"))
        if disruption_text:
            out.append(f"<h3>{ui('detail_disruption', lang)}</h3>")
            out.append(f"<p>{self._paragraphs(disruption_text)}</p>")

        not_when = lang.list(rule.consequences.get("do_not_apply_when"))
        if not_when:
            out.append(f"<h3>{ui('detail_not_when', lang)}</h3>")
            out.append("<ul>" + "".join(f"<li>{html.escape(n)}</li>" for n in not_when) + "</ul>")

        areas = rule.consequences.get("impact_areas") or []
        if areas:
            names = [self._t(self._base.area_name(a)) for a in areas]
            out.append(f"<h3>{ui('detail_areas', lang)}</h3>")
            out.append(f"<p>{html.escape(', '.join(names))}</p>")

        facts = []
        if rule.consequences.get("interruption"):
            facts.append(
                f"{ui('detail_interruption', lang)}: "
                f"{self._label('interruption', rule.consequences['interruption'])}"
            )
        if rule.consequences.get("reversibility"):
            facts.append(
                f"{ui('detail_reversibility', lang)}: "
                f"{self._label('reversibility', rule.consequences['reversibility'])}"
            )
        if facts:
            out.append("<p>" + html.escape(" &nbsp;|&nbsp; ".join(facts)).replace("&amp;nbsp;", "&nbsp;") + "</p>")

        command = self.command_for_clipboard()
        if command:
            out.append(f"<h3>{ui('detail_command', lang)}</h3>")
            out.append(f"<pre>{html.escape(command)}</pre>")
            out.append(f"<p style='color:#5a6472'>{ui('run_unavailable', lang)}</p>")

        notes = self._t(rule.data.get("notes"))
        if notes:
            out.append(f"<h3>{ui('detail_notes', lang)}</h3>")
            out.append(f"<p>{self._paragraphs(notes)}</p>")

        return "".join(out)

    @staticmethod
    def _paragraphs(text: str) -> str:
        chunks = [html.escape(c.strip()) for c in text.split("\n\n") if c.strip()]
        return "</p><p>".join(chunk.replace("\n", " ") for chunk in chunks)


class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.language = Language()
        self.base: RuleBase = load()
        self.scope = Scope()
        self.target: Target | None = None
        self.overlays: list[Target] = []
        self._worker: ScanWorker | None = None

        self.model = ResultsModel(self.base, self.language)
        self.detail = DetailPanel(self.base, self.language)

        self._build_ui()
        self._detect_system()
        self.retranslate()

    # -- construction ------------------------------------------------------

    def _build_ui(self) -> None:
        self.resize(1180, 720)

        self.scan_button = QPushButton()
        self.scan_button.clicked.connect(self.start_scan)


        self.risk_filter = QComboBox()
        self.disruption_filter = QComboBox()
        self.outcome_filter = QComboBox()
        for box in (self.risk_filter, self.disruption_filter, self.outcome_filter):
            box.currentIndexChanged.connect(self._filters_changed)

        self.system_label = QLabel()
        self.copy_button = QPushButton()
        self.copy_button.clicked.connect(self.copy_command)
        self.copy_button.setEnabled(False)

        language_box = QComboBox()
        language_box.addItems(["Polski", "English"])
        language_box.currentIndexChanged.connect(
            lambda index: self.switch_language("pl" if index == 0 else "en")
        )

        top = QHBoxLayout()
        top.addWidget(self.scan_button)
        top.addSpacing(12)
        top.addWidget(self.risk_filter)
        top.addWidget(self.disruption_filter)
        top.addWidget(self.outcome_filter)
        top.addStretch(1)
        top.addWidget(self.system_label)
        top.addSpacing(12)
        top.addWidget(language_box)

        self.table = QTableView()
        self.table.setModel(self.model)
        self.table.setSelectionBehavior(QTableView.SelectRows)
        self.table.setSelectionMode(QTableView.SingleSelection)
        self.table.verticalHeader().setVisible(False)
        self.table.setAlternatingRowColors(True)
        # The title column is the only one worth stretching; the three short
        # ones size to their contents. Stretching the last section instead gave
        # all the slack to "Wynik" and cut the titles down to an ellipsis.
        header = self.table.horizontalHeader()
        header.setStretchLastSection(False)
        header.setSectionResizeMode(0, QHeaderView.Stretch)
        for column in range(1, self.model.columnCount()):
            header.setSectionResizeMode(column, QHeaderView.ResizeToContents)
        # A muted highlight instead of the saturated system blue, which the
        # risk colouring disappeared into. It has to be opaque: a translucent
        # one is painted over the text, not under it, and dulls exactly the
        # column the user is reading.
        highlight = "#3a4763" if dark_theme() else "#cfdcf0"
        self.table.setStyleSheet(
            f"QTableView::item:selected{{background:{highlight};}}"
        )
        self.table.selectionModel().selectionChanged.connect(self._selection_changed)

        right = QVBoxLayout()
        right.addWidget(self.detail)
        right.addWidget(self.copy_button)
        right_widget = QWidget()
        right_widget.setLayout(right)

        splitter = QSplitter()
        splitter.addWidget(self.table)
        splitter.addWidget(right_widget)
        splitter.setStretchFactor(0, 4)
        splitter.setStretchFactor(1, 5)
        splitter.setSizes([520, 660])

        layout = QVBoxLayout()
        layout.addLayout(top)
        layout.addWidget(splitter)
        container = QWidget()
        container.setLayout(layout)
        self.setCentralWidget(container)

        # Kept in the status bar next to the message that names the current
        # rule: together they answer "is anything happening?" without stealing
        # space from the table.
        self.progress = QProgressBar()
        self.progress.setFixedWidth(220)
        self.progress.setTextVisible(True)
        self.progress.setVisible(False)
        self.statusBar().addPermanentWidget(self.progress)
        self.statusBar().showMessage("")

    def _detect_system(self) -> None:
        self.scope = AuditRunner().detect_scope(self.base)
        self.target = self.scope.host
        self.overlays = self.scope.overlays

    def _retranslate_system_label(self) -> None:
        """Name what will be audited, and what was found and will not be.

        An overlay detected on the machine but not declared for this host is
        spelled out instead of passed over. A scan that quietly leaves out a
        server it has just recognised reads as a clean result, and that is the
        one thing the report must never say by omission.
        """
        if self.target is None:
            self.system_label.setText(ui("system_unknown", self.language))
            self.system_label.setToolTip("")
            return

        parts = [self.language.text(self.target.name)]
        parts += [self.language.text(item.name) for item in self.overlays]
        text = " + ".join(parts)

        if self.scope.excluded:
            names = ", ".join(
                self.language.text(item.name) for item in self.scope.excluded
            )
            text += "   ⚠ %s: %s" % (names, ui("overlay_excluded", self.language))
            self.system_label.setToolTip(
                ui("overlay_excluded_hint", self.language) % names
            )
        else:
            self.system_label.setToolTip("")
        self.system_label.setText(text)

    # -- behaviour ---------------------------------------------------------

    def switch_language(self, code: str) -> None:
        self.language.set(code)
        self.retranslate()

    def retranslate(self) -> None:
        self.setWindowTitle(ui("window_title", self.language))
        self.scan_button.setText(ui("scan", self.language))
        self.copy_button.setText(ui("copy", self.language))

        for box, key, vocabulary in (
            (self.risk_filter, "filter_risk", "risk_category"),
            (self.disruption_filter, "filter_disruption", "disruption"),
            (self.outcome_filter, "filter_result", "audit_result"),
        ):
            current = box.currentData()
            box.blockSignals(True)
            box.clear()
            box.addItem(f"{ui(key, self.language)}: {ui('filter_all', self.language)}", "")
            for entry in (self.base.vocabularies.get(vocabulary) or {}).get("values", []):
                box.addItem(self.language.text(entry.get("label")), entry.get("id"))
            index = box.findData(current)
            box.setCurrentIndex(index if index >= 0 else 0)
            box.blockSignals(False)

        self._retranslate_system_label()

        self.model.retranslate()
        self.detail.retranslate()
        self._update_summary()

    def start_scan(self) -> None:
        if self.target is None:
            self.statusBar().showMessage(ui("system_unknown", self.language))
            return
        # The host pack and every overlay that applies, counted as one run. An
        # overlay left out here would be a web server detected and then not
        # examined, which the summary would report as nothing to answer for.
        rules = self.scope.rules
        if not rules:
            self.statusBar().showMessage(ui("no_rules", self.language))
            return

        self.scan_button.setEnabled(False)
        self.statusBar().showMessage(ui("scanning", self.language))
        self.progress.setRange(0, len(rules))
        self.progress.setValue(0)
        self.progress.setVisible(True)

        self._worker = ScanWorker(rules)
        self._worker.progress.connect(self._scan_progress)
        self._worker.finished_with.connect(self._scan_finished)
        self._worker.start()

    def _scan_progress(self, done: int, total: int, rule: Rule) -> None:
        self.progress.setValue(done)
        self.statusBar().showMessage(
            ui(
                "scanning_rule",
                self.language,
                done=done + 1,
                total=total,
                title=self.language.text(rule.title, fallback=rule.identifier),
            )
        )

    def _scan_finished(self, results: list[AuditResult]) -> None:
        self.progress.setValue(self.progress.maximum())
        self.progress.setVisible(False)
        self.model.set_results(results)
        self.scan_button.setEnabled(True)
        if self.model.rowCount():
            self.table.selectRow(0)
        self._update_summary()

    def _filters_changed(self) -> None:
        self.model.set_filters(
            self.risk_filter.currentData() or "",
            self.disruption_filter.currentData() or "",
            self.outcome_filter.currentData() or "",
        )
        self._update_summary()

    def _selection_changed(self) -> None:
        rows = self.table.selectionModel().selectedRows()
        item = self.model.result_at(rows[0].row()) if rows else None
        self.detail.show_result(item)
        self.copy_button.setEnabled(bool(self.detail.command_for_clipboard()))

    def copy_command(self) -> None:
        command = self.detail.command_for_clipboard()
        if not command:
            return
        QApplication.clipboard().setText(command)
        self.statusBar().showMessage(ui("copied", self.language), 4000)

    def _update_summary(self) -> None:
        results = [
            self.model.result_at(row) for row in range(self.model.rowCount())
        ]
        results = [item for item in results if item is not None]
        if not results:
            # Only meaningful once something has been scanned; before that the
            # status bar belongs to whatever the scan is saying.
            if self.model.has_results():
                self.statusBar().showMessage(ui("no_matches", self.language))
            return
        counts = summarise(results)
        self.statusBar().showMessage(ui("summary", self.language, **counts))


def main() -> int:
    app = QApplication([])
    window = MainWindow()
    window.show()
    return app.exec()
