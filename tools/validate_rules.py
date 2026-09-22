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
import re
import sys
from pathlib import Path

try:
    import yaml
    from jsonschema import Draft202012Validator
except ImportError as missing:
    sys.exit(f"Missing required package: {missing.name}. Install with: pip install pyyaml jsonschema")

LANGUAGES = ("pl", "en")


class RuleFileError(Exception):
    """A file that cannot be parsed at all, as opposed to one that breaks a rule."""


def load_yaml(path: Path):
    try:
        return yaml.safe_load(path.read_text(encoding="utf-8"))
    except yaml.YAMLError as broken:
        # A malformed file has to come back as a finding like any other. Letting
        # the parser error escape would abort the whole run on the first bad
        # file and hide everything after it - including from the commit hook.
        mark = getattr(broken, "problem_mark", None)
        where = f" at line {mark.line + 1}, column {mark.column + 1}" if mark else ""
        problem = getattr(broken, "problem", None) or str(broken)
        raise RuleFileError(f"not valid YAML{where}: {problem}") from None


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


USER_RIGHT = re.compile(r"Se[A-Za-z]+(?:Privilege|Right)")
NAMED_VALUE = re.compile(r"\$path\s*=\s*'([^']+)'\s*\n\s*\$name\s*=\s*'([^']+)'")
REGISTRY_PATH = re.compile(r"\$path\s*=\s*'([^']+)'")
# A rule that pulls the whole key and then picks properties off it, rather than
# naming one value up front. The dollar sign in the character class is what keeps
# `$item.$name` out: that is the named-value form, already covered above.
PROPERTY_READ = re.compile(r"\$item\.([A-Za-z_][A-Za-z0-9_]*)")


def settings_touched(rule) -> set[str]:
    """Name the settings a rule reads, so two rules cannot silently cover one point.

    Reads the audit command rather than the remediation one: a rule is a duplicate
    of another when it answers the same question, not when it writes the same value.
    """
    command = ((rule.get("audit") or {}).get("test_command")) or ""
    found = set()
    for match in USER_RIGHT.findall(command):
        found.add(f"right {match}")
    for path, name in NAMED_VALUE.findall(command):
        found.add(f"registry {path}!{name}")
    # Several rules read one key and take more than one value out of it, so the
    # value name never appears in a $name assignment. Without this the duplicate
    # check cannot see them at all - and those are exactly the rules where one
    # point quietly covers two settings.
    paths = REGISTRY_PATH.findall(command)
    if len(paths) == 1:
        for name in PROPERTY_READ.findall(command):
            found.add(f"registry {paths[0]}!{name}")
    return found


def check(base: Path) -> list[str]:
    schema_dir = base / "_schema"
    schema = json.loads((schema_dir / "rule.schema.json").read_text(encoding="utf-8"))
    Draft202012Validator.check_schema(schema)
    validator = Draft202012Validator(schema)

    known_areas = {entry["id"] for entry in load_yaml(schema_dir / "impact-areas.yaml")["areas"]}

    findings: list[str] = []
    seen_ids: dict[str, Path] = {}
    seen_settings: dict[tuple[str, str], str] = {}
    rule_count = 0

    targets = sorted(d for d in base.iterdir() if d.is_dir() and not d.name.startswith("_"))
    if not targets:
        return ["The base contains no targets."]

    per_target: dict[str, int] = {}

    for target in targets:
        if not (target / "meta.yaml").exists():
            findings.append(f"{target.name}: meta.yaml is missing")
            continue
        try:
            load_yaml(target / "meta.yaml")
        except RuleFileError as broken:
            findings.append(f"{target.name}/meta.yaml: {broken}")
            continue

        rule_dir = target / "rules"
        per_target[target.name] = 0
        if not rule_dir.exists():
            continue

        for path in sorted(rule_dir.glob("*.yaml")):
            rule_count += 1
            per_target[target.name] += 1
            label = f"{target.name}/{path.name}"
            try:
                rule = load_yaml(path)
            except RuleFileError as broken:
                findings.append(f"{label}: {broken}")
                continue

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

            for setting in sorted(settings_touched(rule)):
                key = (target.name, setting)
                if key in seen_settings:
                    findings.append(
                        f"{label}: reads {setting}, already covered by {seen_settings[key]}"
                    )
                else:
                    seen_settings[key] = path.name

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
