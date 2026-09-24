"""What is actually installed on this machine.

A warning worth reading says "you have this here", not "this may bother
somebody". The audit reads the system anyway, so it collects the installed
software, the services and the optional features while it is there, and the
impact areas of a rule are then narrowed down to the ones this machine shows
signs of using.

One reservation runs through the whole module and is repeated in the interface
rather than left implicit: **an inventory is a premise, not a proof.** Not
finding a program does not mean nobody uses it. A share can be reached from a
machine that has no file server on it; a protocol can be spoken by an
application that installed nothing under its own name. So the three answers this
module gives are kept apart and never collapsed into two:

* **in use** - something on this machine points at it,
* **no sign of it** - nothing points at it, which is weaker than "unused",
* **not determined** - the area has no signals defined, or the collection could
  not read what it needed.

The signals themselves live with the impact area dictionary, not here. This
module knows how to match a service name; it does not know which service means
file sharing.
"""

from __future__ import annotations

import json
import platform
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum

from .executor import Executor

# Collection is deliberately read-only and deliberately survivable: every part
# is wrapped so that one unreadable source leaves a gap rather than an empty
# inventory. Features need elevation on Windows; without it the list comes back
# empty and the area is reported as not determined rather than as unused.
_WINDOWS_COLLECT = r"""
$out = [ordered]@{ services = @(); running = @(); features = @(); packages = @();
                   shares = @(); printers = @(); listening = @(); missing = @() }

try {
  $svc = Get-Service -ErrorAction Stop
  $out.services = @($svc | ForEach-Object { $_.Name })
  $out.running  = @($svc | Where-Object { $_.Status -eq 'Running' } | ForEach-Object { $_.Name })
} catch { $out.missing += 'services' }

try {
  $f = Get-WindowsOptionalFeature -Online -ErrorAction Stop
  $out.features = @($f | Where-Object { $_.State -eq 'Enabled' } | ForEach-Object { $_.FeatureName })
} catch { $out.missing += 'features' }

try {
  $keys = @(
    'HKLM:\SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall\*',
    'HKLM:\SOFTWARE\WOW6432Node\Microsoft\Windows\CurrentVersion\Uninstall\*',
    'HKCU:\SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall\*'
  )
  $names = @()
  foreach ($k in $keys) {
    $names += @(Get-ItemProperty -Path $k -ErrorAction SilentlyContinue |
                Where-Object { $_.DisplayName } | ForEach-Object { $_.DisplayName })
  }
  $out.packages = @($names | Sort-Object -Unique)
} catch { $out.missing += 'packages' }

try {
  # Administrative shares are left out on purpose. They exist on every
  # installation, so counting them would turn the signal into noise - what
  # matters is whether somebody put a share here deliberately.
  $out.shares = @(Get-SmbShare -ErrorAction Stop |
                  Where-Object { $_.Name -notlike '*$' } | ForEach-Object { $_.Name })
} catch { $out.missing += 'shares' }

try {
  $out.printers = @(Get-Printer -ErrorAction Stop | ForEach-Object { $_.Name })
} catch { $out.missing += 'printers' }

try {
  # A listening port is the strongest sign this collection can gather. A service
  # can be installed and idle, and a package can sit unused for years, but
  # something answering on a port is being offered to the network right now.
  $out.listening = @(Get-NetTCPConnection -State Listen -ErrorAction Stop |
                     ForEach-Object { [string]$_.LocalPort } | Sort-Object -Unique)
} catch { $out.missing += 'listening' }

$out | ConvertTo-Json -Compress -Depth 4
"""

_LINUX_COLLECT = r"""
services=""
running=""
packages=""
shares=""
printers=""
listening=""
missing=""

if command -v systemctl >/dev/null 2>&1; then
  services=$(systemctl list-unit-files --type=service --no-legend --no-pager 2>/dev/null | awk '{print $1}')
  running=$(systemctl list-units --type=service --state=running --no-legend --no-pager 2>/dev/null | awk '{print $1}')
else
  missing="services"
fi

if command -v dpkg-query >/dev/null 2>&1; then
  packages=$(dpkg-query -W -f='${Package}\n' 2>/dev/null)
elif command -v rpm >/dev/null 2>&1; then
  packages=$(rpm -qa --qf '%{NAME}\n' 2>/dev/null)
else
  missing="$missing packages"
fi

# Shares other than the administrative ones, and installed printers. Both are
# read through the ordinary tools and both are allowed to come back empty.
if command -v net >/dev/null 2>&1; then
  shares=$(net usershare list 2>/dev/null)
fi
if command -v lpstat >/dev/null 2>&1; then
  printers=$(lpstat -a 2>/dev/null | awk '{print $1}')
fi

# Listening ports. The address is cut away and only the port kept, so that a
# service bound to one interface counts the same as one bound to all.
if command -v ss >/dev/null 2>&1; then
  listening=$(ss -ltnH 2>/dev/null | awk '{print $4}' | sed 's/.*://' | sort -u)
elif command -v netstat >/dev/null 2>&1; then
  listening=$(netstat -ltn 2>/dev/null | awk '/^tcp/ {print $4}' | sed 's/.*://' | sort -u)
else
  missing="$missing listening"
fi

json_list() {
  printf '['
  first=1
  while IFS= read -r line; do
    [ -z "$line" ] && continue
    [ $first -eq 0 ] && printf ','
    printf '"%s"' "$(printf '%s' "$line" | sed 's/\\/\\\\/g; s/"/\\"/g')"
    first=0
  done
  printf ']'
}

printf '{"services":'
printf '%s' "$services" | json_list
printf ',"running":'
printf '%s' "$running" | json_list
printf ',"features":[],"packages":'
printf '%s' "$packages" | json_list
printf ',"shares":'
printf '%s' "$shares" | json_list
printf ',"printers":'
printf '%s' "$printers" | json_list
printf ',"listening":'
printf '%s' "$listening" | json_list
printf ',"missing":'
printf '%s' "$(printf '%s' "$missing" | tr ' ' '\n')" | json_list
printf '}\n'
"""


class Presence(str, Enum):
    """How much this machine has to say about one impact area."""

    IN_USE = "in-use"
    NO_SIGN = "no-sign"
    UNDETERMINED = "undetermined"


@dataclass
class Inventory:
    """Installed software, services and features, as read once.

    Empty by default, and an empty inventory answers ``UNDETERMINED`` to every
    question rather than ``NO_SIGN``. Nothing collected must never read as
    nothing installed.
    """

    services: set[str] = field(default_factory=set)
    running: set[str] = field(default_factory=set)
    features: set[str] = field(default_factory=set)
    packages: set[str] = field(default_factory=set)
    shares: set[str] = field(default_factory=set)
    printers: set[str] = field(default_factory=set)
    listening: set[str] = field(default_factory=set)
    missing: set[str] = field(default_factory=set)
    collected_at: datetime | None = None
    signals: dict[str, dict] = field(default_factory=dict)

    @property
    def collected(self) -> bool:
        return self.collected_at is not None

    @property
    def partial(self) -> bool:
        """Whether something could not be read - usually for want of elevation."""
        return bool(self.missing)

    def presence(self, area_id: str) -> Presence:
        if not self.collected:
            return Presence.UNDETERMINED
        signal = self.signals.get(area_id) or {}
        if not signal:
            # The area carries no signals, so this machine cannot speak for or
            # against it. Saying "no sign" here would be inventing an answer.
            return Presence.UNDETERMINED

        for kind, names in signal.items():
            if kind in self.missing:
                continue
            if self._matches(kind, names):
                return Presence.IN_USE

        # Every source that could have answered was unreadable, so the silence
        # is the collection's and not the machine's.
        if all(kind in self.missing for kind in signal):
            return Presence.UNDETERMINED
        return Presence.NO_SIGN

    def areas_in_use(self, area_ids: list[str]) -> list[str]:
        return [area for area in area_ids if area and self.presence(area) is Presence.IN_USE]

    def _matches(self, kind: str, names: list[str]) -> bool:
        if kind in ("shares", "printers"):
            # A star asks whether there is any at all, which is the useful
            # question for both: one deliberate share, one installed printer.
            found = self.shares if kind == "shares" else self.printers
            if any(name == "*" for name in names):
                return bool(found)
            return any(self._has(found, name) for name in names)
        if kind == "listening":
            # Ports are written in the dictionary as numbers and arrive from the
            # collection as text, so both sides are compared as text.
            return any(str(name) in self.listening for name in names)
        if kind == "services":
            return any(self._has(self.services, name) for name in names)
        if kind == "running":
            return any(self._has(self.running, name) for name in names)
        if kind == "features":
            return any(self._has(self.features, name) for name in names)
        if kind == "packages":
            # Installed software is matched on a fragment of the display name,
            # which is the only thing a vendor is consistent about. Service and
            # feature names are identifiers and are matched whole.
            lowered = [name.lower() for name in names]
            return any(
                any(fragment in entry.lower() for fragment in lowered)
                for entry in self.packages
            )
        return False

    @staticmethod
    def _has(haystack: set[str], name: str) -> bool:
        lowered = name.lower()
        return any(entry.lower() == lowered for entry in haystack)


def collect(signals: dict[str, dict], executor: Executor | None = None) -> Inventory:
    """Read the machine once. Never changes anything.

    A failure to collect returns an inventory that has been collected of
    nothing and says so, rather than raising - the audit must not fall over
    because a side reading did not work out.
    """
    executor = executor or Executor()
    windows = platform.system() == "Windows"
    shell = "powershell" if windows else "bash"
    script = _WINDOWS_COLLECT if windows else _LINUX_COLLECT

    result = executor.run(shell, script)
    payload = _parse(result.stdout)
    if payload is None:
        return Inventory(
            missing={
                "services", "running", "features", "packages",
                "shares", "printers", "listening",
            },
            signals=signals,
        )

    return Inventory(
        services=set(payload.get("services") or []),
        running=set(payload.get("running") or []),
        features=set(payload.get("features") or []),
        packages=set(payload.get("packages") or []),
        shares=set(payload.get("shares") or []),
        printers=set(payload.get("printers") or []),
        listening={str(entry) for entry in (payload.get("listening") or [])},
        missing={entry for entry in (payload.get("missing") or []) if entry},
        collected_at=datetime.now(),
        signals=signals,
    )


def _parse(stdout: str) -> dict | None:
    """Pick the JSON object out of the output.

    The collection prints one object, but a shell profile or a warning can put
    a line in front of it, so the search starts at the first brace rather than
    assuming the whole output is the payload.
    """
    start = stdout.find("{")
    if start < 0:
        return None
    try:
        return json.loads(stdout[start:])
    except (ValueError, TypeError):
        return None
