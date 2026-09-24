"""The simulation, and the only way to a change.

Hard rule 4 asks that nothing be executed before its consequences have been
shown, and this is where that happens. The dialog is built from a
:class:`~sentin_harden.remediation.Plan`, which was worked out without touching
the machine, and the Run button it carries is the only one in the application.

What the window shows, in this order, is deliberate. The commands come last.
Somebody deciding whether to apply a hardening item needs to know what will stop
working before they need to know which registry value carries it, and a preview
that opens on a block of PowerShell invites the reader to skip to the button.

**One rule at a time, always.** There is no list here, no checkbox column and no
"apply the safe ones" path. Several items mean several decisions, each with its
own preview and its own verdict.
"""

from __future__ import annotations

import html

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QLabel,
    QTextBrowser,
    QVBoxLayout,
)

from .i18n import Language, ui
from .inventory import Inventory, Presence
from .remediation import Applied, Blocker, Plan, Stage
from .ruleset import RuleBase

DOCUMENT_STYLE = (
    "<style>"
    "body{font-family:'Segoe UI',sans-serif;font-size:10.5pt;color:#1a1d21;}"
    "h2{margin:0 0 6px 0;font-size:13pt;}"
    "h3{margin:14px 0 4px 0;font-size:10pt;text-transform:uppercase;color:#5a6472;}"
    "pre{background:#f4f5f7;border:1px solid #d8dbe0;padding:8px;white-space:pre-wrap;"
    "font-family:Consolas,'Courier New',monospace;font-size:9.5pt;}"
    "li{margin-bottom:3px;}"
    ".warn{color:#8a3500;}"
    ".quiet{color:#5a6472;}"
    ".here{color:#b3261e;font-weight:bold;}"
    "</style>"
)

PRESENCE_KEY = {
    Presence.IN_USE: "presence_in_use",
    Presence.NO_SIGN: "presence_no_sign",
    Presence.UNDETERMINED: "presence_undetermined",
}

BLOCKER_KEY = {
    Blocker.NO_BACKUP: "blocker_no_backup",
    Blocker.NO_ROLLBACK: "blocker_no_rollback",
    Blocker.NO_CHANGE: "blocker_no_change",
    Blocker.NOT_RUNNABLE: "blocker_not_runnable",
    Blocker.NEEDS_ELEVATION: "blocker_needs_elevation",
}

STAGE_KEY = {
    Stage.BACKUP: "stage_backup",
    Stage.CHANGE: "stage_change",
    Stage.VERIFY: "stage_verify",
}


class PreviewDialog(QDialog):
    """What would happen, shown before anything does."""

    def __init__(
        self,
        base: RuleBase,
        plan: Plan,
        language: Language,
        inventory: Inventory | None = None,
        parent=None,
    ) -> None:
        super().__init__(parent)
        self._base = base
        self._plan = plan
        self._language = language
        self._inventory = inventory

        self.setWindowTitle(ui("preview_title", language))
        self.resize(760, 620)

        view = QTextBrowser()
        view.setStyleSheet(
            "QTextBrowser{background:#ffffff;color:#1a1d21;"
            "border:1px solid #c9ced6;padding:8px;}"
        )
        view.setHtml(self._build_html())

        buttons = QDialogButtonBox(QDialogButtonBox.Cancel)
        cancel = buttons.button(QDialogButtonBox.Cancel)
        cancel.setText(ui("preview_cancel", language))
        # Cancel is the default, so a stray Return closes the window instead of
        # changing the system. The button that changes something is never the
        # one a keypress reaches first.
        cancel.setDefault(True)

        self.run_button = buttons.addButton(
            ui("preview_run", language), QDialogButtonBox.AcceptRole
        )
        self.run_button.setDefault(False)
        self.run_button.setAutoDefault(False)
        self.run_button.setEnabled(plan.runnable)
        if not plan.runnable:
            self.run_button.setToolTip(
                "\n".join(ui(BLOCKER_KEY[b], language) for b in plan.blockers)
            )

        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)

        note = QLabel(ui("preview_single_only", language))
        note.setWordWrap(True)
        note.setStyleSheet("color:#5a6472;")

        layout = QVBoxLayout()
        layout.addWidget(view)
        layout.addWidget(note)
        layout.addWidget(buttons)
        self.setLayout(layout)

    # -- rendering ---------------------------------------------------------

    def _t(self, field, fallback: str = "") -> str:
        return self._language.text(field, fallback)

    def _build_html(self) -> str:
        plan = self._plan
        rule = plan.rule
        lang = self._language
        out = [DOCUMENT_STYLE]

        out.append(f"<h2>{html.escape(self._t(rule.title, rule.identifier))}</h2>")
        out.append(
            "<p class='quiet'>%s</p>" % html.escape(ui("preview_lead", lang))
        )

        out.append(self._areas_section())
        out.append(self._breaks_section())
        out.append(self._facts_section())
        out.append(self._blockers_section())
        out.append(self._commands_section())
        return "".join(out)

    def _areas_section(self) -> str:
        """The summed consequences, narrowed by what the machine shows.

        This is the part hard rule 4 is actually about: not a list of commands
        but a list of what they reach into. Each area carries what the
        inventory found, and the reservation that goes with it - a machine
        showing no sign of something is not a machine where nobody uses it.
        """
        lang = self._language
        areas = self._plan.areas
        out = [f"<h3>{ui('preview_areas', lang)}</h3>"]
        if not areas:
            out.append(f"<p class='warn'>{ui('preview_no_areas', lang)}</p>")
            return "".join(out)

        rows = []
        for area in areas:
            area_id = area.get("id", "")
            name = html.escape(self._t(self._base.area_name(area_id), area_id))
            if self._inventory is None or not self._inventory.collected:
                rows.append(f"<li>{name}</li>")
                continue
            presence = self._inventory.presence(area_id)
            mark = html.escape(ui(PRESENCE_KEY[presence], lang))
            style = " class='here'" if presence is Presence.IN_USE else " class='quiet'"
            rows.append(f"<li>{name} &mdash; <span{style}>{mark}</span></li>")

        out.append("<ul>" + "".join(rows) + "</ul>")
        if self._inventory is not None and self._inventory.collected:
            out.append(f"<p class='quiet'>{ui('presence_caveat', lang)}</p>")
            if self._inventory.partial:
                out.append(f"<p class='quiet'>{ui('presence_partial', lang)}</p>")
        return "".join(out)

    def _breaks_section(self) -> str:
        lang = self._language
        rule = self._plan.rule
        out = [f"<h3>{ui('detail_breaks', lang)}</h3>"]
        breaks = lang.list(rule.consequences.get("what_breaks"))
        if breaks:
            out.append("<ul>" + "".join(f"<li>{html.escape(b)}</li>" for b in breaks) + "</ul>")
        elif rule.assessment_state == "assessed-no-impact":
            out.append(f"<p>{ui('no_impact_assessed', lang)}</p>")
        else:
            out.append(f"<p class='warn'>{ui('not_assessed', lang)}</p>")

        not_when = lang.list(rule.consequences.get("do_not_apply_when"))
        if not_when:
            out.append(f"<h3>{ui('detail_not_when', lang)}</h3>")
            out.append("<ul>" + "".join(f"<li>{html.escape(n)}</li>" for n in not_when) + "</ul>")
        return "".join(out)

    def _facts_section(self) -> str:
        lang = self._language
        plan = self._plan
        facts = []
        if plan.interruption:
            facts.append(
                "%s: %s"
                % (
                    ui("detail_interruption", lang),
                    self._t(self._base.label("interruption", plan.interruption)),
                )
            )
        if plan.reversibility:
            facts.append(
                "%s: %s"
                % (
                    ui("detail_reversibility", lang),
                    self._t(self._base.label("reversibility", plan.reversibility)),
                )
            )
        facts.append(
            "%s: %s"
            % (
                ui("preview_user_visible", lang),
                ui("preview_yes" if plan.user_visible else "preview_no", lang),
            )
        )
        return "<p>" + html.escape(" | ".join(facts)) + "</p>"

    def _blockers_section(self) -> str:
        if self._plan.runnable:
            return ""
        lang = self._language
        out = [f"<h3>{ui('preview_blocked', lang)}</h3><ul>"]
        for blocker in self._plan.blockers:
            out.append(f"<li class='warn'>{html.escape(ui(BLOCKER_KEY[blocker], lang))}</li>")
        out.append("</ul>")
        out.append(f"<p class='quiet'>{ui('preview_copy_instead', lang)}</p>")
        return "".join(out)

    def _commands_section(self) -> str:
        """The three stages, named and in the order they will run.

        Shown even where the Run button is blocked. Whoever is going to paste
        the commands into their own console is owed the same order the
        application would have used, backup first.
        """
        lang = self._language
        plan = self._plan
        out = [f"<h3>{ui('preview_sequence', lang)}</h3>"]
        for index, stage in enumerate((Stage.BACKUP, Stage.CHANGE, Stage.VERIFY), start=1):
            command = plan.command(stage).strip()
            out.append(
                "<p><b>%d. %s</b></p>" % (index, html.escape(ui(STAGE_KEY[stage], lang)))
            )
            if command:
                out.append(f"<pre>{html.escape(command)}</pre>")
            else:
                out.append(f"<p class='warn'>{ui('preview_stage_missing', lang)}</p>")

        rollback = plan.rollback_command.strip()
        if rollback:
            out.append(f"<h3>{ui('detail_rollback', lang)}</h3>")
            out.append(f"<pre>{html.escape(rollback)}</pre>")
            out.append(f"<p class='quiet'>{ui('preview_rollback_hint', lang)}</p>")
        return "".join(out)


class OutcomeDialog(QDialog):
    """What actually happened, stage by stage, with the re-check as the verdict.

    The window never says a fix worked because a command exited zero. It says
    it worked when the item has been checked again and now passes, and it says
    so in those words.
    """

    def __init__(
        self, base: RuleBase, applied: Applied, language: Language, parent=None
    ) -> None:
        super().__init__(parent)
        self._base = base
        self._applied = applied
        self._language = language

        self.setWindowTitle(ui("outcome_title", language))
        self.resize(760, 560)

        view = QTextBrowser()
        view.setStyleSheet(
            "QTextBrowser{background:#ffffff;color:#1a1d21;"
            "border:1px solid #c9ced6;padding:8px;}"
        )
        view.setHtml(self._build_html())

        buttons = QDialogButtonBox(QDialogButtonBox.Close)
        buttons.button(QDialogButtonBox.Close).setText(ui("outcome_close", language))
        buttons.rejected.connect(self.reject)
        buttons.accepted.connect(self.accept)

        layout = QVBoxLayout()
        layout.addWidget(view)
        layout.addWidget(buttons)
        self.setLayout(layout)

    def _build_html(self) -> str:
        applied = self._applied
        lang = self._language
        rule = applied.plan.rule
        out = [DOCUMENT_STYLE]
        out.append(f"<h2>{html.escape(self._language.text(rule.title, rule.identifier))}</h2>")

        if applied.aborted == "backup":
            out.append(f"<p class='warn'><b>{ui('outcome_backup_failed', lang)}</b></p>")
        elif applied.aborted:
            out.append(f"<p class='warn'><b>{ui('outcome_blocked', lang)}</b></p>")
        elif applied.verified:
            out.append(
                "<p style='color:#2e7d32'><b>%s</b></p>" % html.escape(ui("outcome_verified", lang))
            )
        else:
            out.append(f"<p class='warn'><b>{ui('outcome_not_verified', lang)}</b></p>")

        if applied.backup_written:
            out.append(
                "<p class='quiet'>%s</p>"
                % html.escape(ui("outcome_backup_at", lang, path=str(applied.plan.backup_file)))
            )

        for step in applied.steps:
            out.append(f"<h3>{html.escape(ui(STAGE_KEY[step.stage], lang))}</h3>")
            if step.skipped:
                out.append(f"<p class='warn'>{ui('outcome_skipped', lang)}</p>")
                continue
            if step.stage is Stage.VERIFY:
                if applied.audit is not None:
                    label = self._language.text(
                        self._base.label("audit_result", applied.audit.outcome.value)
                    )
                    out.append(
                        "<p><b>%s</b> &mdash; %s</p>"
                        % (html.escape(label), html.escape(applied.audit.actual or ""))
                    )
                continue
            if step.result is None:
                continue
            out.append(
                "<p class='quiet'>%s</p>"
                % html.escape(ui("outcome_exit", lang, code=step.result.exit_code))
            )
            text = (step.result.stdout or "").strip() or (step.result.stderr or "").strip()
            if text:
                out.append(f"<pre>{html.escape(text)}</pre>")

        rollback = applied.plan.rollback_command.strip()
        if rollback and not applied.aborted:
            out.append(f"<h3>{ui('detail_rollback', lang)}</h3>")
            out.append(f"<pre>{html.escape(rollback)}</pre>")
            out.append(f"<p class='quiet'>{ui('outcome_rollback_hint', lang)}</p>")
        return "".join(out)
