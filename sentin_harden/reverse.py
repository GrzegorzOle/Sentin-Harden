"""The question asked the other way round.

The audit answers "which items does this machine fail?". This view answers the
one people actually ask first: **"I use this - what will hurt me?"** Somebody
weighing up a hardening pass does not start from a benchmark item. They start
from the old scanner in the corridor, the application that speaks a protocol
nobody supports any more, the share three departments map a drive to.

It needs no data of its own. The impact areas are already on every rule, so
reading them backwards is a walk over what is there - which is exactly why the
dictionary was made a dictionary rather than a paragraph of prose.

Two decisions worth stating:

* **It is a view, not a filter.** It stands beside the audit rather than inside
  its toolbar, and it works before any scan has been run. The answer to "what
  will hurt me" does not depend on having scanned anything.
* **It is scoped to what would be audited here.** The rules of a system this
  machine is not are noise in this question, however true they are elsewhere.
"""

from __future__ import annotations

from PySide6.QtCore import QAbstractTableModel, QModelIndex, Qt, Signal
from PySide6.QtGui import QColor, QFont
from PySide6.QtWidgets import (
    QHeaderView,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QSizePolicy,
    QSplitter,
    QTableView,
    QVBoxLayout,
    QWidget,
)

from .audit import AuditResult, Outcome
from .i18n import Language, ui
from .inventory import Inventory, Presence
from .ruleset import Rule, RuleBase, touching


class AreaRulesModel(QAbstractTableModel):
    """Rules reaching into one area, with their verdict where there is one."""

    COLUMNS = ("col_item", "col_risk", "col_disruption", "col_result")

    def __init__(self, base: RuleBase, language: Language) -> None:
        super().__init__()
        self._base = base
        self._language = language
        self._rows: list[Rule] = []
        self._outcomes: dict[str, Outcome] = {}

    def set_rules(self, rules: list[Rule], outcomes: dict[str, Outcome]) -> None:
        self.beginResetModel()
        self._rows = list(rules)
        self._outcomes = outcomes
        self.endResetModel()

    def rule_at(self, row: int) -> Rule | None:
        return self._rows[row] if 0 <= row < len(self._rows) else None

    def retranslate(self) -> None:
        self.beginResetModel()
        self.endResetModel()

    def rowCount(self, parent: QModelIndex = QModelIndex()) -> int:
        return 0 if parent.isValid() else len(self._rows)

    def columnCount(self, parent: QModelIndex = QModelIndex()) -> int:
        return 0 if parent.isValid() else len(self.COLUMNS)

    def headerData(self, section: int, orientation: Qt.Orientation, role: int = Qt.DisplayRole):
        if orientation != Qt.Horizontal or role != Qt.DisplayRole:
            return None
        return ui(self.COLUMNS[section], self._language)

    def data(self, index: QModelIndex, role: int = Qt.DisplayRole):
        rule = self.rule_at(index.row())
        if rule is None:
            return None
        column = index.column()
        outcome = self._outcomes.get(rule.identifier)

        if role == Qt.DisplayRole:
            if column == 0:
                return self._language.text(rule.title, fallback=rule.identifier)
            if column == 1:
                return self._language.text(self._base.label("risk_category", rule.risk))
            if column == 2:
                return self._language.text(self._base.label("disruption", rule.disruption))
            if column == 3:
                # A dash rather than a guess. Before a scan nothing is known
                # about this item on this machine, and an empty cell would be
                # read as "fine".
                if outcome is None:
                    return ui("reverse_unchecked", self._language)
                return self._language.text(self._base.label("audit_result", outcome.value))

        if role == Qt.ToolTipRole and column == 0:
            return self._language.text(rule.title, fallback=rule.identifier)

        if role == Qt.ForegroundRole:
            from .ui import outcome_colour, risk_colour

            if column == 1:
                return QColor(risk_colour(rule.risk))
            if column == 3 and outcome is not None:
                return QColor(outcome_colour(outcome))

        if role == Qt.FontRole and column in (1, 3):
            font = QFont()
            font.setBold(True)
            return font
        return None


class ReverseView(QWidget):
    """Pick what you use on the left, read what it will cost on the right."""

    rule_chosen = Signal(str)

    def __init__(self, base: RuleBase, language: Language) -> None:
        super().__init__()
        self._base = base
        self._language = language
        self._rules: list[Rule] = []
        self._outcomes: dict[str, Outcome] = {}
        self._inventory: Inventory | None = None

        self.lead = QLabel()
        self.lead.setWordWrap(True)
        self.lead.setStyleSheet("color:#5a6472;")
        # The paragraph takes the height its text needs and no more. Left to
        # the defaults it keeps whatever the layout hands it and centres the
        # text inside, which on a wide window is a band of empty space between
        # the toolbar and the areas.
        self.lead.setAlignment(Qt.AlignLeft | Qt.AlignTop)
        lead_policy = self.lead.sizePolicy()
        lead_policy.setVerticalPolicy(QSizePolicy.Minimum)
        self.lead.setSizePolicy(lead_policy)

        self.areas = QListWidget()
        self.areas.currentRowChanged.connect(self._area_changed)

        self.model = AreaRulesModel(base, language)
        self.table = QTableView()
        self.table.setModel(self.model)
        self.table.setSelectionBehavior(QTableView.SelectRows)
        self.table.setSelectionMode(QTableView.SingleSelection)
        self.table.verticalHeader().setVisible(False)
        self.table.setAlternatingRowColors(True)
        header = self.table.horizontalHeader()
        header.setStretchLastSection(False)
        header.setSectionResizeMode(0, QHeaderView.Stretch)
        for column in range(1, self.model.columnCount()):
            header.setSectionResizeMode(column, QHeaderView.ResizeToContents)
        # Double-click takes the item back to the audit, where the full
        # description and the remediation live. This view answers which items
        # matter; it deliberately does not duplicate what they say.
        self.table.doubleClicked.connect(self._open_in_audit)

        self.caption = QLabel()
        self.caption.setWordWrap(True)

        right = QVBoxLayout()
        right.addWidget(self.caption)
        right.addWidget(self.table)
        right_widget = QWidget()
        right_widget.setLayout(right)

        splitter = QSplitter()
        splitter.addWidget(self.areas)
        splitter.addWidget(right_widget)
        splitter.setStretchFactor(0, 2)
        splitter.setStretchFactor(1, 5)
        splitter.setSizes([360, 820])

        layout = QVBoxLayout()
        layout.addWidget(self.lead)
        # All the spare height belongs to the splitter. A splitter asks for no
        # more than it needs by default, so without this the surplus is shared
        # out evenly and half the window goes to a two-line paragraph.
        layout.addWidget(splitter, 1)
        self.setLayout(layout)

        self.set_rules([], {})

    # -- data --------------------------------------------------------------

    def set_rules(self, rules: list[Rule], outcomes: dict[str, Outcome]) -> None:
        """The rules in scope, and their verdicts if a scan has been run."""
        self._rules = list(rules)
        self._outcomes = dict(outcomes)
        self._fill_areas()

    def set_results(self, results: list[AuditResult]) -> None:
        self._outcomes = {item.rule.identifier: item.outcome for item in results}
        self._fill_areas()

    def set_inventory(self, inventory: Inventory | None) -> None:
        self._inventory = inventory
        self._fill_areas()

    def retranslate(self) -> None:
        self.lead.setText(ui("reverse_lead", self._language))
        self.model.retranslate()
        self._fill_areas()

    # -- rendering ---------------------------------------------------------

    def _fill_areas(self) -> None:
        """One row per area, carrying its count and what the machine showed.

        Areas with no rule in scope are kept in the list rather than dropped.
        An absent entry reads as "nothing to worry about here", and the truth
        is "no rule in this pack reaches into it", which is a different thing.
        """
        current = self.areas.currentRow()
        self.areas.blockSignals(True)
        self.areas.clear()

        self._per_area: dict[str, list[Rule]] = {}
        for area_id in self._base.impact_areas:
            found = touching(self._rules, area_id)
            self._per_area[area_id] = found

            name = self._language.text(self._base.area_name(area_id), area_id)
            label = f"{name}  ({len(found)})"
            item = QListWidgetItem(label)
            item.setData(Qt.UserRole, area_id)

            if self._inventory is not None and self._inventory.collected:
                presence = self._inventory.presence(area_id)
                if presence is Presence.IN_USE:
                    item.setText(f"{label}  • {ui('presence_in_use', self._language)}")
                    font = item.font()
                    font.setBold(True)
                    item.setFont(font)
                item.setToolTip(
                    "%s\n\n%s"
                    % (
                        self._language.text(
                            (self._base.impact_areas.get(area_id) or {}).get("description")
                        ),
                        ui("presence_caveat", self._language),
                    )
                )
            self.areas.addItem(item)

        self.areas.blockSignals(False)
        if self.areas.count():
            self.areas.setCurrentRow(current if 0 <= current < self.areas.count() else 0)

    def _area_changed(self, row: int) -> None:
        item = self.areas.item(row)
        if item is None:
            self.model.set_rules([], {})
            self.caption.setText("")
            return
        area_id = item.data(Qt.UserRole)
        found = self._per_area.get(area_id, [])
        self.model.set_rules(found, self._outcomes)

        name = self._language.text(self._base.area_name(area_id), area_id)
        failing = sum(
            1
            for rule in found
            if self._outcomes.get(rule.identifier) is Outcome.FAIL
        )
        if self._outcomes:
            self.caption.setText(
                ui("reverse_caption", self._language, area=name, total=len(found), failing=failing)
            )
        else:
            self.caption.setText(
                ui("reverse_caption_unscanned", self._language, area=name, total=len(found))
            )

    def _open_in_audit(self, index: QModelIndex) -> None:
        rule = self.model.rule_at(index.row())
        if rule is not None:
            self.rule_chosen.emit(rule.identifier)
