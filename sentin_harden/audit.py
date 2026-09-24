"""The audit engine.

Read-only stage. Nothing here changes system configuration - it runs a rule's
test command, compares the output against the expected value and classifies the
outcome.

The classification matters more than it looks. Being unable to check something
is a separate outcome from finding it misconfigured. A check that fails for lack
of privileges and reports compliance is the worst defect this application could
have, so the reserved output tokens are handled before any comparison.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from enum import Enum

from .executor import CommandResult, Executor
from .ruleset import Rule, Target

# Reserved tokens a test command may print instead of a value.
TOKEN_CHECK_ERROR = "CHECK_ERROR"
TOKEN_NOT_APPLICABLE = "NOT_APPLICABLE"


class Outcome(str, Enum):
    PASS = "PASS"
    FAIL = "FAIL"
    ERROR = "ERROR"
    NOT_APPLICABLE = "NOT_APPLICABLE"


@dataclass
class AuditResult:
    rule: Rule
    outcome: Outcome
    actual: str
    detail: str = ""

    @property
    def is_finding(self) -> bool:
        return self.outcome is Outcome.FAIL


@dataclass
class Scope:
    """What this machine turned out to be, and what is to be checked on it.

    ``excluded`` holds overlays found on the machine that the host pack does not
    declare - a web server on a system the pack was not written for, say. They
    are carried here rather than discarded so the interface can say what it
    saw and left out, instead of showing a scan that merely looks complete.
    """

    host: Target | None = None
    overlays: list[Target] = field(default_factory=list)
    excluded: list[Target] = field(default_factory=list)

    @property
    def targets(self) -> list[Target]:
        """Everything to be audited, host first."""
        return ([self.host] if self.host else []) + list(self.overlays)

    @property
    def rules(self) -> list[Rule]:
        return [rule for target in self.targets for rule in target.rules]


def compare(actual: str, expected: str, method: str) -> bool:
    actual = actual.strip()
    expected = expected.strip()

    if method == "regex":
        return re.search(expected, actual) is not None
    if method == "contains":
        return expected in actual
    if method in ("not-less-than", "not-greater-than"):
        try:
            left, right = float(actual), float(expected)
        except ValueError:
            return False
        return left >= right if method == "not-less-than" else left <= right
    return actual == expected


def classify(rule: Rule, result: CommandResult) -> AuditResult:
    """Turn raw command output into an outcome."""
    value = result.last_line

    if result.timed_out:
        return AuditResult(rule, Outcome.ERROR, value, "timeout")

    # Reserved tokens win over everything, including the exit code: a rule that
    # reports it could not check must never be read as compliant.
    if value == TOKEN_CHECK_ERROR:
        return AuditResult(rule, Outcome.ERROR, value, result.stderr.strip())
    if value == TOKEN_NOT_APPLICABLE:
        return AuditResult(rule, Outcome.NOT_APPLICABLE, value)

    if not value:
        # No output at all is not evidence of compliance either.
        return AuditResult(rule, Outcome.ERROR, value, result.stderr.strip() or "no output")

    audit = rule.audit
    matched = compare(value, str(audit.get("expected", "")), audit.get("comparison", "equals"))
    return AuditResult(rule, Outcome.PASS if matched else Outcome.FAIL, value)


class AuditRunner:
    """Runs the test command of every rule in a target."""

    def __init__(self, executor: Executor | None = None) -> None:
        self.executor = executor or Executor()

    def detect(self, target: Target) -> bool:
        """Check whether the current machine matches this target."""
        detection = target.detection
        command = detection.get("command")
        pattern = detection.get("match")
        if not command or not pattern:
            return False
        result = self.executor.run(target.shell, command)
        return re.search(pattern, result.last_line) is not None

    def detect_scope(self, base) -> Scope:
        """Find the host system, then the overlays that apply on top of it.

        An overlay such as IIS must never be chosen as the host, even when it is
        present: its rules extend the host pack rather than replacing it. Picking
        the first matching target would silently audit a web server instead of
        the operating system it runs on.

        An overlay found on the machine but not declared for this host is kept
        apart rather than dropped. Dropping it would leave the interface showing
        a scan that looks complete while a server it just detected went
        unexamined, and silence there reads as a clean result.
        """
        host: Target | None = None
        for target in base.targets.values():
            if target.is_overlay:
                continue
            if self.detect(target):
                host = target
                break

        if host is None:
            return Scope(host=None)

        overlays: list[Target] = []
        excluded: list[Target] = []
        for target in base.targets.values():
            if not target.is_overlay or not self.detect(target):
                continue
            if target.applies_to_host(host):
                overlays.append(target)
            else:
                excluded.append(target)
        return Scope(host=host, overlays=overlays, excluded=excluded)

    def run_rule(self, rule: Rule) -> AuditResult:
        audit = rule.audit
        shell = audit.get("shell", "powershell")
        command = audit.get("test_command", "")
        if not command:
            return AuditResult(rule, Outcome.ERROR, "", "rule has no test command")
        return classify(rule, self.executor.run(shell, command))

    def run_target(self, target: Target) -> list[AuditResult]:
        return [self.run_rule(rule) for rule in target.rules]


def summarise(results: list[AuditResult]) -> dict[str, int]:
    counts = {"total": len(results), "passed": 0, "failed": 0, "errors": 0}
    for item in results:
        if item.outcome is Outcome.PASS:
            counts["passed"] += 1
        elif item.outcome is Outcome.FAIL:
            counts["failed"] += 1
        else:
            # Errors and not-applicable share a bucket in the summary line, but
            # stay distinct in the table - neither is a pass.
            counts["errors"] += 1
    return counts
