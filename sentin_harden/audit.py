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
from dataclasses import dataclass
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

    def detect_scope(self, base) -> tuple[Target | None, list[Target]]:
        """Find the host system, then the overlays that apply on top of it.

        An overlay such as IIS must never be chosen as the host, even when it is
        present: its rules extend the host pack rather than replacing it. Picking
        the first matching target would silently audit a web server instead of
        the operating system it runs on.
        """
        host: Target | None = None
        for target in base.targets.values():
            if target.is_overlay:
                continue
            if self.detect(target):
                host = target
                break

        if host is None:
            return None, []

        overlays = [
            target
            for target in base.targets.values()
            if target.applies_to_host(host) and self.detect(target)
        ]
        return host, overlays

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
