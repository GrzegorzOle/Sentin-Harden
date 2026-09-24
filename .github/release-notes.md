## Co jest w tym wydaniu

| Plik | Dla kogo |
|---|---|
| `Sentin-Harden-*-x64.msi` | Windows 64-bit — instalator dla całej maszyny |
| `Sentin-Harden-*-x86_64.AppImage` | Linux 64-bit — jeden plik, bez instalacji |
| `SHA256SUMS.txt` | sumy kontrolne obu powyższych |

Python nie jest potrzebny po stronie użytkownika — runtime jedzie w środku.

## Uruchomienie

**Windows.** Instalator kładzie aplikację w `Program Files` i zakłada skrót w menu
Start. Audyt i naprawy wymagają uprawnień administratora — uruchom aplikację
podniesioną, inaczej znaczna część sprawdzeń powie wprost, że nie ma dostępu.

**Linux.** Pobierz obraz, nadaj mu prawo wykonywania i uruchom:

```bash
chmod +x Sentin-Harden-*-x86_64.AppImage
./Sentin-Harden-*-x86_64.AppImage
```

Obraz jest budowany na Ubuntu 22.04, więc startuje na tej i każdej nowszej
dystrybucji. Na starszej nie — glibc jest zgodne w przód, nie wstecz.

## Sprawdzenie pliku przed uruchomieniem

Artefakty **nie są podpisane cyfrowo**. Windows pokaże ostrzeżenie SmartScreen,
a część programów antywirusowych zareaguje na sam wzorzec: zamrożony interpreter,
który uruchamia polecenia PowerShell zmieniające rejestr i polityki. Porównaj sumę
kontrolną z zawartością `SHA256SUMS.txt`:

```powershell
Get-FileHash .\Sentin-Harden-*-x64.msi -Algorithm SHA256
```

```bash
sha256sum -c SHA256SUMS.txt --ignore-missing
```

## Zanim zaczniesz zmieniać konfigurację

Aplikacja modyfikuje ustawienia systemu operacyjnego. Etap audytu jest wyłącznie
do odczytu i niczego nie rusza. Każda naprawa idzie w stałej kolejności: kopia
zapasowa modyfikowanego zasobu, podgląd skutków, wykonanie, ponowne sprawdzenie
tego samego punktu. Zmiany stosuje się pojedynczo — trybu zbiorczego nie ma.

Przetestuj poza produkcją i przeczytaj opis skutków, zanim klikniesz „Uruchom".
Odpowiedzialność za zmiany wdrożone na własnej maszynie jest po Twojej stronie.

## Stan projektu

Wersja wczesna. Aplikacja audytuje i naprawia, ale nie ma jeszcze rejestru
świadomie odpuszczonych punktów ani testów automatycznych. Baza reguł obejmuje
Windows 10 i 11, Windows Server 2016 i 2025, IIS, Ubuntu 24.04 oraz Fedorę 44.

Projekt nie jest powiązany z Center for Internet Security ani przez nie firmowany.
Z benchmarków CIS pochodzi wyłącznie identyfikacja punktów; opisy ryzyka, opisy
skutków eksploatacyjnych oraz polecenia audytu i naprawy są autorskie.
