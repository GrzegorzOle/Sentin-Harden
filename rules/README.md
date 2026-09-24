# Baza reguł

Reguły są **danymi, nie kodem**. Silnik nie zna treści żadnego benchmarku — dodanie systemu to
dodanie katalogu z plikami, nie pisanie Pythona.

Nazwy katalogów, plików, kluczy i wartości słownikowych są **angielskie**. Treść widoczna dla
użytkownika jest **dwujęzyczna**: każde pole tekstowe ma wersję `pl` i `en`, więc przełączenie
języka interfejsu przełącza wszystkie komunikaty, a nie tylko etykiety przycisków.

## Układ katalogów

```
rules/
  _schema/
    rule.schema.json       walidacja pojedynczej reguły
    vocabularies.yaml      dozwolone wartości pól wraz z etykietami pl/en
    impact-areas.yaml      wspólny słownik obszarów wpływu
  <system>/
    meta.yaml              opis celu + polecenie wykrywania systemu
    rules/*.yaml           po jednym pliku na regułę
```

Cele: `windows-10`, `windows-11`, `windows-server-2016`, `windows-server-2025`, `iis`,
`ubuntu-24.04`, `fedora-44`.

`iis` jest **nakładką** — audytuje się go zawsze razem z paczką systemu gospodarza.

## Dlaczego YAML, a nie JSON

Każda reguła niesie cztery polecenia powłoki i kilka akapitów opisu w dwóch językach. W JSON-ie
byłyby to jednolinijkowe łańcuchy z ucieczkami, a każdy odwrotny ukośnik w ścieżce rejestru
trzeba byłoby podwajać. Blok YAML trzyma polecenie dokładnie w postaci, w jakiej wpisuje się je
w konsolę, pozwala na komentarze i daje czytelny diff.

Rygor zapewnia `_schema/rule.schema.json`, więc struktura jest wymuszona tak samo twardo jak
w JSON-ie.

## Dwie części o różnym pochodzeniu

Blok `benchmark` to **jedyna** część przepisywana z dokumentu CIS, ograniczona do identyfikacji:
nazwa, wersja, numer punktu, sekcja, krótki tytuł. Ma pozwolić zestawić raport z egzemplarzem
benchmarku, który użytkownik ma u siebie. Wartość `TBD` oznacza numer jeszcze niepotwierdzony —
**nie zgadujemy numerów**.

Wszystko pozostałe jest pisane od zera: opis ochrony, opis uciążliwości, konsekwencje i wszystkie
polecenia.

## Reguły, których pilnuje schemat

Schemat nie sprawdza samej składni — wymusza zasady projektu:

- `runnable: true` **wymaga** `backup_command` i `rollback_command`. Bez nich punkt można
  wyłącznie skopiować do własnej konsoli.
- `disruption: none` **nie może** iść w parze z `assessment_state: not-assessed`.
- `assessment_state: assessed-impact-described` **wymaga** niepustych `impact_areas`
  i `what_breaks` w obu językach.
- Klasy uciążliwe **wymagają** wypełnionego `disruption_description`.
- Każde pole tekstowe **wymaga obu języków** — brak tłumaczenia nie przejdzie walidacji.

Sprawdzenie:

```bash
pip install -r requirements.txt     # PyYAML + jsonschema, raz
python tools/validate_rules.py
```

Walidacja jest też wpięta w hooka `pre-commit` i uruchamia się automatycznie, gdy commit dotyka
katalogu `rules/`. Reguła niezgodna ze schematem zatrzymuje się przed wypchnięciem, nie po.

## Polecenia — zasady

**Polecenie testu nie zmienia stanu systemu.** Nigdy.

**Zastrzeżone wartości wyjścia.** Test może zwrócić `CHECK_ERROR`, gdy sprawdzenia nie dało się
wykonać (brak uprawnień, niedostępny podsystem), albo `NOT_APPLICABLE`, gdy element nie istnieje
w tym wydaniu systemu. Żadna z nich nie może pasować do `expected`.

To nie jest formalność. `Get-WindowsOptionalFeature` wymaga podniesienia uprawnień, a wywołane
z `-ErrorAction SilentlyContinue` zwraca `$null` — nie do odróżnienia od „funkcja nieobecna".
Reguła napisana naiwnie raportuje wtedy **zgodność, której nie sprawdziła**. Zawsze oddzielaj
„nie ustawione" od „nie dało się odczytać".

**Podstawienie `{{backup_file}}`.** Silnik wypełnia je tą samą ścieżką w poleceniu kopii
i w poleceniu wycofania — dzięki temu wycofanie wie, co przywrócić.

**Kopia obejmuje dokładnie ten zakres, który modyfikuje zmiana.** Przy rejestrze zapisuj pojedynczą
wartość **wraz z informacją, czy w ogóle istniała** — `reg import` nie umie poprawnie cofnąć
sytuacji „tej wartości wcześniej nie było", a wtedy wycofanie zostawia po sobie wartość, której
nikt nie ustawiał.

**Zmieniaj przez plik nakładkowy**, gdzie to możliwe — wycofanie sprowadza się wtedy do usunięcia
jednego pliku.

**Jeśli błąd konfiguracji może odciąć dostęp do maszyny**, sprawdź ją przed przeładowaniem usługi
i przeładuj zamiast restartować.

## Jak pisać opisy

**Konkret zamiast ostrzeżenia.** „Skanery zapisujące skany prosto na udział przestaną tam
zapisywać" zamiast „może wpłynąć na kompatybilność". Pole `what_breaks` ma wymuszoną minimalną
długość właśnie po to, żeby nie dało się wpisać tam ogólnika.

**Obszary wpływu przed prozą.** To one napędzają widok odwrotny („korzystam z X — co mnie
zaboli?") i podsumowanie przed wykonaniem. Tekst uzupełnia wpis ze słownika, nie zastępuje go.

**Brak wpływu to nie brak oceny.** Jeśli reguły jeszcze nie oceniono, wpisz `not-assessed`
zamiast zostawiać puste listy. Pusta lista czyta się jako gwarancja bezpieczeństwa.
