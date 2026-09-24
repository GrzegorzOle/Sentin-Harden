"""Applying a single fix, in a fixed order.

The order is the whole point of this module and it never varies:

1. **backup** - secure the resource about to be modified,
2. **change** - run the remediation command,
3. **verify** - audit that one item again.

Nothing starts without step 1 succeeding, and step 3 is the only evidence that
step 2 worked. A remediation command that exits zero has said nothing about the
state of the system; plenty of them write a value that the system then ignores.

Two things this module deliberately does not do:

* it never applies more than one rule per call. There is no bulk path here at
  all - not a disabled one, not one behind a flag. A caller that wants several
  fixes asks for them one at a time and gets a separate verdict for each;
* it never decides on its own that a rule may run. :func:`plan` answers that,
  and it answers before anything is executed, so the caller can show the
  answer and its reasons to somebody who then decides.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path

from . import paths
from .audit import AuditResult, AuditRunner, Outcome
from .executor import CommandResult, Executor
from .inventory import Inventory
from .ruleset import Rule, RuleBase

PLACEHOLDER = "{{backup_file}}"


class Blocker(str, Enum):
    """Why a rule may not be run from the application.

    Kept as values rather than as prose so the interface can translate them and
    the report can count them. Every one of these leaves the copy path open -
    refusing to run is not refusing to help.
    """

    NO_BACKUP = "no-backup"
    NO_ROLLBACK = "no-rollback"
    NO_CHANGE = "no-change"
    NOT_RUNNABLE = "not-runnable"
    NEEDS_ELEVATION = "needs-elevation"


class Stage(str, Enum):
    BACKUP = "backup"
    CHANGE = "change"
    VERIFY = "verify"


@dataclass
class Step:
    """One executed stage, with what it printed."""

    stage: Stage
    command: str
    result: CommandResult | None = None
    skipped: str = ""

    @property
    def failed(self) -> bool:
        if self.result is None:
            return False
        return self.result.timed_out or self.result.exit_code != 0


@dataclass
class Plan:
    """The simulation: what would happen, worked out without touching anything.

    Hard rule 4 asks for a preview of consequences and not merely of commands,
    so the areas of impact are carried here alongside the command text, already
    narrowed by what the inventory found on this machine. The commands are here
    too - somebody about to change a system is entitled to read them - but they
    are not the substance of the preview.
    """

    rule: Rule
    backup_file: Path
    areas: list[dict] = field(default_factory=list)
    present: list[str] = field(default_factory=list)
    blockers: list[Blocker] = field(default_factory=list)
    interruption: str = ""
    reversibility: str = ""
    user_visible: bool = False

    @property
    def runnable(self) -> bool:
        return not self.blockers

    def command(self, stage: Stage) -> str:
        """Command text for a stage, with the backup path already filled in."""
        key = {
            Stage.BACKUP: "backup_command",
            Stage.CHANGE: "change_command",
            Stage.VERIFY: "",
        }[stage]
        if not key:
            return str(self.rule.audit.get("test_command") or "")
        raw = str(self.rule.remediation.get(key) or "")
        return raw.replace(PLACEHOLDER, str(self.backup_file))

    @property
    def rollback_command(self) -> str:
        raw = str(self.rule.remediation.get("rollback_command") or "")
        return raw.replace(PLACEHOLDER, str(self.backup_file))


@dataclass
class Applied:
    """What actually happened, stage by stage.

    ``verified`` is the only field that says the machine changed. The others say
    what was attempted.
    """

    plan: Plan
    steps: list[Step] = field(default_factory=list)
    audit: AuditResult | None = None
    aborted: str = ""

    @property
    def verified(self) -> bool:
        return self.audit is not None and self.audit.outcome is Outcome.PASS

    @property
    def backup_written(self) -> bool:
        return self.plan.backup_file.exists()

    def step(self, stage: Stage) -> Step | None:
        for item in self.steps:
            if item.stage is stage:
                return item
        return None


def plan(
    rule: Rule,
    base: RuleBase,
    inventory: Inventory | None = None,
    elevated: bool | None = None,
) -> Plan:
    """Work out what applying this rule would involve. Changes nothing."""
    remediation = rule.remediation
    blockers: list[Blocker] = []

    if not remediation.get("change_command"):
        blockers.append(Blocker.NO_CHANGE)
    # Hard rules 1 and 2 together: no backup or no way back means the fix is
    # available to copy and not to run. The two are reported apart because they
    # are different omissions and the reader deserves to know which one it is.
    if not remediation.get("backup_command"):
        blockers.append(Blocker.NO_BACKUP)
    if not remediation.get("rollback_command"):
        blockers.append(Blocker.NO_ROLLBACK)
    if not rule.runnable:
        blockers.append(Blocker.NOT_RUNNABLE)

    if elevated is None:
        elevated = paths.is_elevated()
    if rule.data.get("privileges") in ("administrator", "root") and not elevated:
        blockers.append(Blocker.NEEDS_ELEVATION)

    areas = []
    for area_id in rule.consequences.get("impact_areas") or []:
        entry = base.impact_areas.get(area_id)
        areas.append(entry or {"id": area_id})

    present: list[str] = []
    if inventory is not None:
        present = inventory.areas_in_use([a.get("id", "") for a in areas])

    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    return Plan(
        rule=rule,
        backup_file=paths.backup_dir() / f"{rule.identifier}-{stamp}.json",
        areas=areas,
        present=present,
        blockers=blockers,
        interruption=str(rule.consequences.get("interruption") or ""),
        reversibility=str(rule.consequences.get("reversibility") or ""),
        user_visible=bool(rule.consequences.get("user_visible")),
    )


class Remediator:
    """Runs one plan, in order, stopping at the first thing that goes wrong."""

    def __init__(
        self, executor: Executor | None = None, auditor: AuditRunner | None = None
    ) -> None:
        self.executor = executor or Executor()
        self.auditor = auditor or AuditRunner(self.executor)

    def apply(self, prepared: Plan) -> Applied:
        applied = Applied(plan=prepared)
        if not prepared.runnable:
            # Reached only if a caller ignored the plan. Refusing here as well
            # keeps the guarantee in the engine rather than in the interface,
            # where a future second caller would not inherit it.
            applied.aborted = "blocked"
            return applied

        shell = str(prepared.rule.remediation.get("shell", "powershell"))

        backup = Step(Stage.BACKUP, prepared.command(Stage.BACKUP))
        backup.result = self.executor.run(shell, backup.command)
        applied.steps.append(backup)
        if backup.failed or not prepared.backup_file.exists():
            # The command may exit zero and still not have written the file -
            # a path that could not be created, a value it declined to read.
            # Without that file there is no way back, so the change does not
            # start. This is hard rule 1 and it is enforced here, not trusted.
            applied.aborted = "backup"
            applied.steps.append(
                Step(Stage.CHANGE, prepared.command(Stage.CHANGE), skipped="backup-failed")
            )
            return applied

        change = Step(Stage.CHANGE, prepared.command(Stage.CHANGE))
        change.result = self.executor.run(shell, change.command)
        applied.steps.append(change)

        # The audit runs whether or not the change reported success. A command
        # that failed may still have changed something, and a command that
        # succeeded may have changed nothing that counts.
        verify = Step(Stage.VERIFY, prepared.command(Stage.VERIFY))
        applied.audit = self.auditor.run_rule(prepared.rule)
        verify.result = None
        applied.steps.append(verify)
        return applied
