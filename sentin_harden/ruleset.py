"""Loading the rule base.

Rules are data. This module turns the YAML files into plain objects and knows
nothing about what any particular benchmark says.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

from . import paths

# Order used for the decision matrix. High risk with no disruption comes first:
# those are the quick wins. Low risk with a planned rollout comes last.
RISK_ORDER = {"critical": 0, "high": 1, "medium": 2, "low": 3}
DISRUPTION_ORDER = {"none": 0, "needs-review": 1, "needs-planned-rollout": 2}


def _read(path: Path) -> Any:
    return yaml.safe_load(path.read_text(encoding="utf-8"))


@dataclass(frozen=True)
class Rule:
    identifier: str
    data: dict[str, Any]

    @property
    def title(self) -> dict[str, str]:
        return self.data.get("benchmark", {}).get("title") or {}

    @property
    def risk(self) -> str:
        return self.data.get("risk_category", "low")

    @property
    def disruption(self) -> str:
        return self.data.get("disruption", "needs-planned-rollout")

    @property
    def assessment_state(self) -> str:
        return self.data.get("assessment_state", "not-assessed")

    @property
    def consequences(self) -> dict[str, Any]:
        return self.data.get("implementation_consequences") or {}

    @property
    def audit(self) -> dict[str, Any]:
        return self.data.get("audit") or {}

    @property
    def remediation(self) -> dict[str, Any]:
        return self.data.get("remediation") or {}

    @property
    def runnable(self) -> bool:
        return bool(self.data.get("runnable"))

    @property
    def matrix_key(self) -> tuple[int, int, str]:
        """Sort key for the decision matrix: risk first, disruption second."""
        return (
            RISK_ORDER.get(self.risk, 99),
            DISRUPTION_ORDER.get(self.disruption, 99),
            self.identifier,
        )


@dataclass
class Target:
    """One audited system together with its rules."""

    identifier: str
    meta: dict[str, Any]
    rules: list[Rule] = field(default_factory=list)

    @property
    def name(self) -> dict[str, str]:
        return self.meta.get("name") or {"pl": self.identifier, "en": self.identifier}

    @property
    def shell(self) -> str:
        return self.meta.get("shell", "powershell")

    @property
    def detection(self) -> dict[str, Any]:
        return self.meta.get("detection") or {}

    @property
    def is_overlay(self) -> bool:
        """An overlay is audited on top of a host, never instead of it."""
        return self.meta.get("type") == "overlay"

    @property
    def requires_host(self) -> list[str]:
        return list(self.meta.get("requires_host") or [])

    def applies_to_host(self, host: "Target") -> bool:
        if not self.is_overlay:
            return False
        return not self.requires_host or host.identifier in self.requires_host


@dataclass
class RuleBase:
    targets: dict[str, Target]
    vocabularies: dict[str, Any]
    impact_areas: dict[str, dict[str, Any]]

    def target(self, identifier: str) -> Target | None:
        return self.targets.get(identifier)

    def label(self, vocabulary: str, value: str) -> dict[str, str]:
        """Bilingual label for a vocabulary value.

        The interface must never invent its own translation of these, and must
        never show the raw identifier.
        """
        entry = self.vocabularies.get(vocabulary) or {}
        for item in entry.get("values", []):
            if item.get("id") == value:
                return item.get("label") or {"pl": value, "en": value}
        return {"pl": value, "en": value}

    def area_name(self, area_id: str) -> dict[str, str]:
        area = self.impact_areas.get(area_id)
        if not area:
            return {"pl": area_id, "en": area_id}
        return area.get("name") or {"pl": area_id, "en": area_id}


def load(root: Path | None = None) -> RuleBase:
    root = root or paths.rules_root()
    schema_dir = root / "_schema"

    vocabularies = _read(schema_dir / "vocabularies.yaml") or {}
    areas_file = _read(schema_dir / "impact-areas.yaml") or {}
    impact_areas = {entry["id"]: entry for entry in areas_file.get("areas", [])}

    targets: dict[str, Target] = {}
    for directory in sorted(p for p in root.iterdir() if p.is_dir() and not p.name.startswith("_")):
        meta_file = directory / "meta.yaml"
        if not meta_file.exists():
            continue
        target = Target(identifier=directory.name, meta=_read(meta_file) or {})

        rule_dir = directory / "rules"
        if rule_dir.exists():
            for rule_file in sorted(rule_dir.glob("*.yaml")):
                data = _read(rule_file) or {}
                identifier = data.get("id") or rule_file.stem
                target.rules.append(Rule(identifier=identifier, data=data))

        target.rules.sort(key=lambda r: r.matrix_key)
        targets[target.identifier] = target

    return RuleBase(targets=targets, vocabularies=vocabularies, impact_areas=impact_areas)
