#!/usr/bin/env python3
"""Sprawdza spójność bazy reguł.

Weryfikuje:
  * zgodność każdej reguły ze schematem (wraz z zasadami warunkowymi),
  * czy użyte obszary wpływu istnieją w słowniku,
  * czy reguła leży w katalogu odpowiadającym jej platformie,
  * czy identyfikatory reguł są niepowtarzalne,
  * czy każdy cel ma plik meta.yaml.

Użycie:
    python narzedzia/waliduj_reguly.py [katalog_bazy]

Kod wyjścia 0 oznacza bazę bez zastrzeżeń.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

try:
    import yaml
    from jsonschema import Draft202012Validator
except ImportError as brak:
    sys.exit(f"Brak wymaganego pakietu: {brak.name}. Zainstaluj: pip install pyyaml jsonschema")


def wczytaj_yaml(sciezka: Path) -> dict:
    return yaml.safe_load(sciezka.read_text(encoding="utf-8"))


def sprawdz(baza: Path) -> list[str]:
    katalog_schematu = baza / "_schema"
    schemat = json.loads((katalog_schematu / "regula.schema.json").read_text(encoding="utf-8"))
    Draft202012Validator.check_schema(schemat)
    walidator = Draft202012Validator(schemat)

    obszary = {
        pozycja["id"]
        for pozycja in wczytaj_yaml(katalog_schematu / "obszary-wplywu.yaml")["obszary"]
    }

    zastrzezenia: list[str] = []
    widziane_id: dict[str, Path] = {}
    liczba_regul = 0

    cele = sorted(k for k in baza.iterdir() if k.is_dir() and not k.name.startswith("_"))
    if not cele:
        return ["Baza nie zawiera żadnego celu."]

    for cel in cele:
        if not (cel / "meta.yaml").exists():
            zastrzezenia.append(f"{cel.name}: brak pliku meta.yaml")
            continue
        wczytaj_yaml(cel / "meta.yaml")

        katalog_regul = cel / "reguly"
        if not katalog_regul.exists():
            continue

        for plik in sorted(katalog_regul.glob("*.yaml")):
            liczba_regul += 1
            etykieta = f"{cel.name}/{plik.name}"
            regula = wczytaj_yaml(plik)

            for blad in sorted(walidator.iter_errors(regula), key=lambda b: list(b.path)):
                sciezka_pola = "/".join(str(element) for element in blad.path) or "(korzeń)"
                zastrzezenia.append(f"{etykieta}: {sciezka_pola} — {blad.message}")

            identyfikator = regula.get("id")
            if identyfikator in widziane_id:
                zastrzezenia.append(
                    f"{etykieta}: identyfikator '{identyfikator}' już użyty "
                    f"w {widziane_id[identyfikator]}"
                )
            elif identyfikator:
                widziane_id[identyfikator] = plik

            system = (regula.get("platforma") or {}).get("system")
            if system and system != cel.name:
                zastrzezenia.append(
                    f"{etykieta}: platforma.system to '{system}', "
                    f"a plik leży w katalogu '{cel.name}'"
                )

            uzyte = set((regula.get("konsekwencje_wdrozenia") or {}).get("obszary_wplywu") or [])
            for nieznany in sorted(uzyte - obszary):
                zastrzezenia.append(f"{etykieta}: obszar wpływu '{nieznany}' spoza słownika")

    print(f"Celów: {len(cele)}. Reguł: {liczba_regul}. Obszarów wpływu w słowniku: {len(obszary)}.")
    return zastrzezenia


def main() -> int:
    baza = Path(sys.argv[1] if len(sys.argv) > 1 else "rules")
    if not baza.is_dir():
        print(f"Nie znaleziono katalogu bazy: {baza}", file=sys.stderr)
        return 2

    zastrzezenia = sprawdz(baza)
    if zastrzezenia:
        print(f"\nZnaleziono {len(zastrzezenia)} zastrzeżeń:\n", file=sys.stderr)
        for pozycja in zastrzezenia:
            print(f"  {pozycja}", file=sys.stderr)
        return 1

    print("Baza reguł bez zastrzeżeń.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
