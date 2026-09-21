# Baza reguł

Reguły są **danymi, nie kodem**. Silnik nie zna treści żadnego benchmarku — dodanie nowego
systemu to dodanie katalogu z plikami, nie pisanie Pythona.

## Układ katalogów

```
rules/
  _schema/
    regula.schema.json     walidacja pojedynczej reguły
    slowniki.yaml          dozwolone wartości pól (kategoria, uciążliwość, …)
    obszary-wplywu.yaml    wspólny słownik obszarów wpływu
  <system>/
    meta.yaml              opis celu + polecenie wykrywania systemu
    reguly/*.yaml          po jednym pliku na regułę
```

Cele: `windows-10`, `windows-11`, `windows-server-2016`, `windows-server-2025`, `iis`,
`debian-13`, `ubuntu-24.04`, `fedora-44`.

`iis` jest **nakładką** — audytuje się go zawsze razem z paczką systemu gospodarza,
nie zamiast niej.

## Format pliku reguły

YAML, jedna reguła w pliku. Wybór YAML zamiast JSON wynika z zawartości: każda reguła niesie
cztery polecenia powłoki i kilka akapitów opisu. W JSON-ie byłyby to jednolinijkowe łańcuchy
z ucieczkami, a każdy odwrotny ukośnik w ścieżce rejestru trzeba byłoby podwajać. Blok YAML
trzyma polecenie dokładnie w takiej postaci, w jakiej wpisuje się je w konsolę, pozwala na
komentarze i daje czytelny diff w gitcie.

Strukturę pilnuje `_schema/regula.schema.json`, więc rygor pozostaje taki sam jak przy JSON-ie.

### Dwie części o różnym pochodzeniu

Blok `benchmark` to **jedyna** część przepisywana z dokumentu CIS i ograniczona do identyfikacji:
nazwa, wersja, numer punktu, tytuł pozwalający go odszukać. Ma umożliwić zestawienie raportu
z egzemplarzem benchmarku, który użytkownik ma u siebie.

Wszystko pozostałe — opis ryzyka, opis uciążliwości, konsekwencje, polecenia testu, kopii, zmiany
i wycofania — jest **pisane od zera**. Nie kopiujemy, nie parafrazujemy zdanie po zdaniu i nie
odtwarzamy struktury opisu z dokumentu CIS.

### Pola

| Pole | Znaczenie |
|---|---|
| `id` | nasz stabilny identyfikator; nie zmienia się przy zmianie numeracji benchmarku |
| `benchmark` | identyfikacja punktu w dokumencie źródłowym |
| `platforma.system` | cel z listy powyżej |
| `kategoria_ryzyka` | ile daje wdrożenie: `krytyczne` / `wysokie` / `srednie` / `niskie` |
| `uciazliwosc` | `bez-uciazliwosci` / `wymaga-sprawdzenia` / `wymaga-swiadomego-wdrozenia` |
| `stan_oceny` | odróżnia „sprawdzone, brak wpływu" od „jeszcze nieocenione" |
| `opis` | przed czym broni i co przestaje być możliwe |
| `opis_uciazliwosci` | dlaczego przypisano taką klasę uciążliwości |
| `konsekwencje_wdrozenia` | obszary wpływu, co przestanie działać, przerwa, kiedy nie stosować, odwracalność |
| `audyt` | powłoka, polecenie testu, wartość oczekiwana, sposób porównania |
| `remediacja` | polecenie kopii, polecenie zmiany, polecenie wycofania |
| `uprawnienia` | poziom wymagany do wykonania |
| `uruchamialne` | czy wolno pokazać przycisk „Uruchom" |

Wartości pól słownikowych pochodzą **wyłącznie** z `_schema/slowniki.yaml`, a identyfikatory
obszarów z `_schema/obszary-wplywu.yaml`. Dowolny tekst w tych miejscach psuje filtrowanie,
sortowanie i porównywalność raportów.

## Reguły, których pilnuje schemat

Schemat nie sprawdza samej składni — wymusza zasady projektu:

- `uruchamialne: true` **wymaga** zarówno `polecenie_kopii`, jak i `polecenie_wycofania`.
  Bez nich punkt można wyłącznie skopiować do własnej konsoli.
- `uciazliwosc: bez-uciazliwosci` **nie może** iść w parze ze `stan_oceny: nieocenione`.
  Nieoceniona reguła nie trafia do trybu zbiorczego.
- `stan_oceny: oceniono-wplyw-opisany` **wymaga** niepustych `obszary_wplywu`
  i `co_przestanie_dzialac`.
- Klasy uciążliwe **wymagają** wypełnionego `opis_uciazliwosci`.

## Jak pisać opisy

**Konkret zamiast ostrzeżenia.** „Skanery zapisujące skany prosto na udział przestaną tam
zapisywać" zamiast „może wpłynąć na kompatybilność". Pole `co_przestanie_dzialac` ma wymuszoną
minimalną długość właśnie po to, żeby nie dało się wpisać tam ogólnika.

**Obszary wpływu przed prozą.** To one napędzają widok odwrotny („korzystam z X — co mnie
zaboli?") i podsumowanie przed wykonaniem. Tekst jest uzupełnieniem wpisu ze słownika,
nigdy jego zamiennikiem.

**Brak wpływu to nie to samo co brak oceny.** Jeśli reguły jeszcze nie oceniono, wpisz
`nieocenione` zamiast zostawiać puste listy. Pusta lista czyta się jako gwarancja
bezpieczeństwa, a nią nie jest.

## Zasady dla poleceń

- Polecenie testu **nie zmienia stanu systemu**. Nigdy.
- Kopia obejmuje dokładnie ten zakres, który modyfikuje zmiana. Kopia szersza lub węższa
  od zmiany sprawia, że wycofanie nie przywraca stanu.
- Tam, gdzie to możliwe, zmieniaj przez **plik nakładkowy**, a nie przez edycję pliku
  głównego — wycofanie sprowadza się wtedy do usunięcia jednego pliku.
- Jeśli błędna konfiguracja może odciąć dostęp do maszyny, **sprawdź ją przed przeładowaniem
  usługi** i przeładuj zamiast restartować.
- Brak sprawdzanego elementu w danym wydaniu systemu to `NOT_APPLICABLE`, nie `FAIL`.

## Przykłady

Dwie reguły wzorcowe pokazują komplet pól po obu stronach:

- `windows-11/reguly/przyklad-smb1-wylaczony.yaml`
- `debian-13/reguly/przyklad-ssh-bez-logowania-root.yaml`

Mają `benchmark.punkt: PRZYKLAD`, bo numerów niesprawdzonych w dokumencie nie wpisujemy.
