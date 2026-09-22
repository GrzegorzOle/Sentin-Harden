"""The audit window.

First stage only: detect the system, run the rules, show what was found and let
the user copy a remediation command. There is deliberately no Run button - it
belongs with the backup machinery, which is not built yet, and a Run button that
skips the backup would violate the rule the whole project rests on.
"""

from __future__ import annotations

import html
from datetime import datetime

from PySide6.QtCore import QAbstractTableModel, QModelIndex, Qt, QThread, Signal
from PySide6.QtGui import QAction, QColor, QFont
from PySide6.QtWidgets import (
    QApplication,
    QComboBox,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QPushButton,
    QSplitter,
    QTableView,
    QTextBrowser,
    QVBoxLayout,
    QWidget,
)

from . import paths
from .audit import AuditResult, AuditRunner, Outcome, summarise
from .i18n import Language, ui
from .ruleset import DISRUPTION_ORDER, RISK_ORDER, Rule, RuleBase, Target, load

RISK_COLOURS = {
    "critical": "#b3261e",
    "high": "#c05621",
    "medium": "#8a6d1f",
    "low": "#5a6472",
}

OUTCOME_COLOURS = {
    Outcome.PASS: "#2e7d32",
    Outcome.FAIL: "#b3261e",
    Outcome.ERROR: "#8a6d1f",
    Outcome.NOT_APPLICABLE: "#5a6472",
}


class ScanWorker(QThread):
    """Runs the audit off the interface thread so the window stays responsive."""

    finished_with = Signal(object)

    def __init__(self, target: Target) -> None:
        super().__init__()
        self._target = target

    def run(self) -> None:
        runner = AuditRunner()
        self.finished_with.emit(runner.run_target(self._target))


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

    # -- data --------------------------------------------------------------

    def set_results(self, results: list[AuditResult]) -> None:
        self.beginResetModel()
        # Default order is the decision matrix, not the benchmark numbering:
        # high risk with no disruption first, those are the quick wins.
        self._all = sorted(results, key=lambda r: r.rule.matrix_key)
        self._apply_filters()
        self.endResetModel()

    def set_filters(self, risk: str, disruption: str) -> None:
        self.beginResetModel()
        self._risk_filter = risk
        self._disruption_filter = disruption
        self._apply_filters()
        self.endResetModel()

    def _apply_filters(self) -> None:
        self._rows = [
            item
            for item in self._all
            if (not self._risk_filter or item.rule.risk == self._risk_filter)
            and (not self._disruption_filter or item.rule.disruption == self._disruption_filter)
        ]

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

        if role == Qt.ForegroundRole:
            if column == 1:
                return QColor(RISK_COLOURS.get(rule.risk, "#000000"))
            if column == 3:
                return QColor(OUTCOME_COLOURS.get(item.outcome, "#000000"))

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
            "body{font-family:'Segoe UI',sans-serif;font-size:10.5pt;}"
            "h2{margin:0 0 4px 0;font-size:13pt;}"
            "h3{margin:14px 0 4px 0;font-size:10pt;text-transform:uppercase;color:#5a6472;}"
            "pre{background:#f4f5f7;border:1px solid #d8dbe0;padding:8px;white-space:pre-wrap;}"
            "li{margin-bottom:3px;}"
            "</style>"
        ]

        title = html.escape(self._t(rule.title, rule.identifier))
        out.append(f"<h2>{title}</h2>")

        risk = html.escape(self._label("risk_category", rule.risk))
        disruption = html.escape(self._label("disruption", rule.disruption))
        outcome = html.escape(self._label("audit_result", item.outcome.value))
        risk_colour = RISK_COLOURS.get(rule.risk, "#000000")
        outcome_colour = OUTCOME_COLOURS.get(item.outcome, "#000000")
        out.append(
            f"<p><b style='color:{risk_colour}'>{risk}</b> &nbsp;|&nbsp; {disruption}"
            f" &nbsp;|&nbsp; <b style='color:{outcome_colour}'>{outcome}</b></p>"
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
        self.risk_filter.currentIndexChanged.connect(self._filters_changed)
        self.disruption_filter.currentIndexChanged.connect(self._filters_changed)

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
        self.table.horizontalHeader().setStretchLastSection(True)
        self.table.selectionModel().selectionChanged.connect(self._selection_changed)

        right = QVBoxLayout()
        right.addWidget(self.detail)
        right.addWidget(self.copy_button)
        right_widget = QWidget()
        right_widget.setLayout(right)

        splitter = QSplitter()
        splitter.addWidget(self.table)
        splitter.addWidget(right_widget)
        splitter.setStretchFactor(0, 3)
        splitter.setStretchFactor(1, 4)

        layout = QVBoxLayout()
        layout.addLayout(top)
        layout.addWidget(splitter)
        container = QWidget()
        container.setLayout(layout)
        self.setCentralWidget(container)

        self.statusBar().showMessage("")

    def _detect_system(self) -> None:
        host, overlays = AuditRunner().detect_scope(self.base)
        self.target = host
        self.overlays = overlays

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

        if self.target is None:
            self.system_label.setText(ui("system_unknown", self.language))
        else:
            self.system_label.setText(self.language.text(self.target.name))

        self.model.retranslate()
        self.detail.retranslate()
        self._update_summary()

    def start_scan(self) -> None:
        if self.target is None:
            self.statusBar().showMessage(ui("system_unknown", self.language))
            return
        if not self.target.rules:
            self.statusBar().showMessage(ui("no_rules", self.language))
            return

        self.scan_button.setEnabled(False)
        self.statusBar().showMessage(ui("scanning", self.language))

        self._worker = ScanWorker(self.target)
        self._worker.finished_with.connect(self._scan_finished)
        self._worker.start()

    def _scan_finished(self, results: list[AuditResult]) -> None:
        self.model.set_results(results)
        self.scan_button.setEnabled(True)
        if self.model.rowCount():
            self.table.selectRow(0)
        self._update_summary()

    def _filters_changed(self) -> None:
        self.model.set_filters(
            self.risk_filter.currentData() or "",
            self.disruption_filter.currentData() or "",
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
            return
        counts = summarise(results)
        self.statusBar().showMessage(ui("summary", self.language, **counts))


def main() -> int:
    app = QApplication([])
    window = MainWindow()
    window.show()
    return app.exec()
