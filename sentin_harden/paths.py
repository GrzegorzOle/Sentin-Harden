"""Resource and data locations.

Two rules the rest of the application depends on:

* Resources (rule packs, schema, dictionaries) are read through :func:`resource`.
  Never build a path relative to ``__file__`` - after freezing with PyInstaller
  the files live in a temporary extraction directory, not next to the sources.

* Anything the application writes - backups of modified resources, reports,
  logs, recorded risk acceptances - goes under :func:`data_dir`. The application
  directory is read-only once installed under Program Files, and a backup that
  does not survive an uninstall is not a backup.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

APP_NAME = "Sentin-Harden"


def is_frozen() -> bool:
    """True when running from a PyInstaller artifact rather than from sources."""
    return getattr(sys, "frozen", False)


def resource_root() -> Path:
    """Directory holding bundled, read-only resources."""
    if is_frozen():
        # PyInstaller unpacks bundled data here; in onedir builds it is the
        # application directory itself.
        return Path(getattr(sys, "_MEIPASS", Path(sys.executable).parent))
    return Path(__file__).resolve().parent.parent


def resource(*parts: str) -> Path:
    """Path to a bundled resource, identical from sources and from an artifact."""
    return resource_root().joinpath(*parts)


def rules_root() -> Path:
    """Root of the rule base."""
    return resource("rules")


def data_dir() -> Path:
    """Writable location for backups, reports and recorded decisions.

    Created on demand. Deliberately outside the application directory so that
    its contents survive an upgrade and an uninstall.
    """
    if os.name == "nt":
        base = Path(os.environ.get("ProgramData", r"C:\ProgramData"))
    else:
        base = Path(os.environ.get("XDG_DATA_HOME", "/var/lib"))
    path = base / APP_NAME
    _try_mkdir(path)
    return path


def backup_dir() -> Path:
    """Directory for backups taken before a change."""
    path = data_dir() / "backups"
    _try_mkdir(path)
    return path


def _try_mkdir(path: Path) -> None:
    # On Linux the audit runs as an ordinary user, who cannot create anything
    # under /var/lib. The path is still the right one for commands later run as
    # root, which create it themselves, so failing here must not take down the
    # window that only displays it.
    try:
        path.mkdir(parents=True, exist_ok=True)
    except OSError:
        pass
