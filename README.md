# Sentin-Harden

Graficzne narzędzie do audytu i utwardzania konfiguracji systemów według CIS Benchmarks —
z naciskiem na to, czego sam benchmark nie mówi: **co przestanie działać po wdrożeniu zasady.**

> **Status: wczesny etap prac.** Repozytorium zawiera na razie założenia projektowe.
> Kod aplikacji dopiero powstaje.

## Problem

Listę niezgodności z benchmarkiem wygeneruje dowolny skaner. Trudność zaczyna się później:
setki punktów, płaska lista, brak informacji o tym, który z nich zablokuje ludziom pracę,
a który nikt nie zauważy. W efekcie hardening albo grzęźnie na etapie raportu, albo wdraża się
go hurtem i odkręca po pierwszym zgłoszeniu od użytkowników.

Sentin-Harden ma odpowiadać na pytanie, które faktycznie blokuje decyzję:
**„co się zepsuje, jeśli to włączę?"**

## Jak działa

1. **Audyt** — zebranie stanu systemu i raport zgodności. Etap wyłącznie do odczytu,
   niczego nie zmienia.
2. **Remediacja sterowana przez użytkownika** — dla każdego niespełnionego punktu narzędzie
   pokazuje gotowe polecenie i pozwala je uruchomić albo skopiować do własnej konsoli.

Nic nie dzieje się samo. Aplikacja ma tłumaczyć, a nie wyręczać.

## Czym się różni od zwykłego skanera

**Dwie własne oceny przy każdym punkcie**, niezależne od poziomów L1/L2:

- **kategoria ryzyka** — ile realnie daje wdrożenie, czyli co zyskuje atakujący, gdy punkt
  zostaje niespełniony;
- **klasa uciążliwości** — czy ktokolwiek to zauważy, czy zmiana wymaga okna serwisowego
  i uprzedzenia użytkowników.

Z ich zestawienia wynika kolejność pracy: wysokie ryzyko przy zerowej uciążliwości to szybkie
wygrane, wysokie ryzyko przy dużej uciążliwości to miejsce na świadomą decyzję. Lista sortuje się
według tej macierzy, nie według numeru punktu.

**Konkretne skutki, nie ostrzeżenia ogólne.** Zamiast „może wpłynąć na kompatybilność" —
wskazanie, co dokładnie przestanie działać, czy wymaga restartu i kiedy tej zmiany nie stosować.
Skutki da się czytać w drugą stronę: wskazujesz, z czego korzystasz, a narzędzie pokazuje,
które zasady Cię zabolą.

**Świadome odpuszczenie jest pełnoprawnym wynikiem.** Punkt można zaakceptować jako ryzyko —
z uzasadnieniem, autorem i datą przeglądu. Trafia do raportu jako osobny status, więc po czasie
widać różnicę między decyzją a zaniedbaniem. Akceptacja wygasa i wraca do ponownego rozpatrzenia.

## Bezpieczeństwo pracy

- Kopia zapasowa modyfikowanego zasobu **przed** każdą zmianą.
- Punkt bez zdefiniowanej kopii i procedury wycofania można wyłącznie skopiować — nie uruchomić
  z poziomu aplikacji.
- Podsumowanie konsekwencji przed wykonaniem, także przy zmianach zbiorczych.
- Zbiorczo stosuje się wyłącznie zmiany zaklasyfikowane jako nieuciążliwe.
- Po naprawie punkt jest audytowany ponownie — to jedyny dowód, że zadziałała.

## Platformy docelowe

| System | Powłoka |
|---|---|
| Windows 10, Windows 11 | PowerShell |
| Windows Server (wspierane wersje) | PowerShell |
| IIS | PowerShell |
| Debian, Ubuntu | bash |
| Fedora | bash |

Dystrybucja: instalator dla Windows, samodzielny obraz dla Linuksa. **Python nie jest wymagany
po stronie użytkownika.**

## Raport

Eksport do HTML i PDF, przygotowany **do druku** — jako dokument przekazywany dalej, a nie zrzut
ekranu z aplikacji. Generowany przed remediacją i po niej.

## Stosunek do CIS

Projekt nie jest powiązany z Center for Internet Security ani przez nie firmowany.
CIS Benchmarks są objęte własną licencją i **ich treść nie jest tutaj powielana** — narzędzie
odwołuje się wyłącznie do numeracji punktów oraz wersji benchmarku, żeby dało się zestawić raport
z dokumentem źródłowym. Opisy ryzyka, opisy skutków eksploatacyjnych oraz polecenia audytu
i naprawy są autorskie.

Po dokument benchmarku sięgnij bezpośrednio do CIS.

## Zastrzeżenie

Narzędzie modyfikuje konfigurację systemu operacyjnego. Zmiany wykonujesz na własną
odpowiedzialność — przetestuj je poza produkcją i upewnij się, że rozumiesz opisane skutki,
zanim je wdrożysz.

## Licencja

Apache License 2.0 — zobacz [LICENSE](LICENSE).
