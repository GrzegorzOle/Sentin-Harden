#!/usr/bin/env python3
"""Check the consistency of the rule base.

Verifies:
  * every rule against the schema, including the conditional project rules,
  * that referenced impact areas exist in the dictionary,
  * that a rule lives in the directory matching its platform,
  * that rule identifiers are unique across the whole base,
  * that every target carries a meta.yaml,
  * that no bilingual text field is left with an empty language.

Usage:
    python tools/validate_rules.py [base_directory]

Exit code 0 means the base has no findings.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

try:
    import yaml
    from jsonschema import Draft202012Validator
except ImportError as missing:
    sys.exit(f"Missing required package: {missing.name}. Install with: pip install pyyaml jsonschema")

LANGUAGES = ("pl", "en")


def load_yaml(path: Path):
    return yaml.safe_load(path.read_text(encoding="utf-8"))


def find_empty_translations(node, trail: str = "") -> list[str]:
    """Report bilingual fields where one language is filled and the other is not."""
    findings: list[str] = []
    if isinstance(node, dict):
        if set(LANGUAGES).issubset(node.keys()):
            filled = {lang: bool(node.get(lang)) for lang in LANGUAGES}
            if any(filled.values()) and not all(filled.values()):
                empty = ", ".join(lang for lang, ok in filled.items() if not ok)
                findings.append(f"{trail or '(root)'}: empty translation for: {empty}")
        for key, value in node.items():
            if key not in LANGUAGES:
                findings.extend(find_empty_translations(value, f"{trail}/{key}" if trail else str(key)))
    elif isinstance(node, list):
        for index, value in enumerate(node):
            findings.extend(find_empty_translations(value, f"{trail}[{index}]"))
    return findings


def check(base: Path) -> list[str]:
    schema_dir = base / "_schema"
    schema = json.loads((schema_dir / "rule.schema.json").read_text(encoding="utf-8"))
    Draft202012Validator.check_schema(schema)
    validator = Draft202012Validator(schema)

    known_areas = {entry["id"] for entry in load_yaml(schema_dir / "impact-areas.yaml")["areas"]}

    findings: list[str] = []
    seen_ids: dict[str, Path] = {}
    rule_count = 0

    targets = sorted(d for d in base.iterdir() if d.is_dir() and not d.name.startswith("_"))
    if not targets:
        return ["The base contains no targets."]

    per_target: dict[str, int] = {}

    for target in targets:
        if not (target / "meta.yaml").exists():
            findings.append(f"{target.name}: meta.yaml is missing")
            continue
        load_yaml(target / "meta.yaml")

        rule_dir = target / "rules"
        per_target[target.name] = 0
        if not rule_dir.exists():
            continue

        for path in sorted(rule_dir.glob("*.yaml")):
            rule_count += 1
            per_target[target.name] += 1
            label = f"{target.name}/{path.name}"
            rule = load_yaml(path)

            for error in sorted(validator.iter_errors(rule), key=lambda e: list(e.path)):
                field = "/".join(str(part) for part in error.path) or "(root)"
                findings.append(f"{label}: {field} - {error.message}")

            findings.extend(f"{label}: {item}" for item in find_empty_translations(rule))

            identifier = rule.get("id")
            if identifier in seen_ids:
                findings.append(f"{label}: identifier '{identifier}' already used in {seen_ids[identifier]}")
            elif identifier:
                seen_ids[identifier] = path

            system = (rule.get("platform") or {}).get("system")
            if system and system != target.name:
                findings.append(
                    f"{label}: platform.system is '{system}' but the file sits in '{target.name}'"
                )

            used = set((rule.get("implementation_consequences") or {}).get("impact_areas") or [])
            for unknown in sorted(used - known_areas):
                findings.append(f"{label}: impact area '{unknown}' is not in the dictionary")

    print(f"Targets: {len(targets)}. Rules: {rule_count}. Impact areas: {len(known_areas)}.")
    for name in sorted(per_target):
        print(f"  {name:22} {per_target[name]:3} rules")
    return findings


def main() -> int:
    base = Path(sys.argv[1] if len(sys.argv) > 1 else "rules")
    if not base.is_dir():
        print(f"Base directory not found: {base}", file=sys.stderr)
        return 2

    findings = check(base)
    if findings:
        print(f"\n{len(findings)} findings:\n", file=sys.stderr)
        for item in findings:
            print(f"  {item}", file=sys.stderr)
        return 1

    print("Rule base has no findings.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
