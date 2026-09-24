#!/usr/bin/env python3
"""Build the Linux image.

One AppImage that runs on Debian, Ubuntu and Fedora without any of them having
Python installed. The form was chosen because it is the only one of the three
candidates that meets that condition with a single file: a .deb and an .rpm
would be two packages and two dependency trees for the same binary.

Three constraints shape what this script does, and none of them is optional:

* **Build on the oldest distribution still supported.** glibc is compatible
  forwards and not backwards, so an image built on Fedora will not start on an
  older Debian. The build runs in a container or on a runner old enough for the
  whole range, and this script refuses to guess - it checks and says so.
* **A directory layout inside the image.** PySide6 is under the LGPL and its
  libraries have to stay replaceable. AppImage mounts a directory, so this is
  satisfied by construction as long as the freeze stays a directory build.
* **No elevation at start.** The image runs as an ordinary user. The audit is
  read-only and reports what it could not read; a change asks for root at the
  moment it is made, and not before.

Usage:
    python3 tools/build_appimage.py
    python3 tools/build_appimage.py --build       # freeze first
    python3 tools/build_appimage.py --tool <path to appimagetool>

Exit code 0 means the image was built and checked.
"""

from __future__ import annotations

import argparse
import os
import platform
import re
import shutil
import stat
import subprocess
import sys
import urllib.request
from pathlib import Path

PROJECT = Path(__file__).resolve().parent.parent
DIST = PROJECT / "dist" / "Sentin-Harden"
WORK = PROJECT / "build" / "appimage"
APPDIR = WORK / "Sentin-Harden.AppDir"

APPIMAGETOOL_URL = (
    "https://github.com/AppImage/appimagetool/releases/download/continuous/"
    "appimagetool-x86_64.AppImage"
)

# Newer than this and the image starts refusing to run on distributions the
# rule base still covers. Checked rather than assumed, because the difference
# only shows up on somebody else's machine.
MAX_GLIBC = (2, 36)

DESKTOP_ENTRY = """[Desktop Entry]
Type=Application
Name=Sentin-Harden
GenericName=CIS benchmark audit
Comment=Audit a system against a CIS benchmark and apply fixes one at a time
Exec=Sentin-Harden
Icon=sentin-harden
Categories=System;Security;
Terminal=false
StartupWMClass=Sentin-Harden
"""

# The launcher, and it stays this short on purpose. The frozen runtime already
# carries its own libraries and finds its own Qt plugins relative to the
# executable; setting LD_LIBRARY_PATH or QT_QPA_PLATFORM_PLUGIN_PATH here would
# point at directories this layout does not have, and would override the paths
# that do work. Handing straight over is the whole job.
APPRUN = """#!/bin/sh
HERE=$(dirname "$(readlink -f "$0")")
exec "$HERE/usr/lib/Sentin-Harden/Sentin-Harden" "$@"
"""


def run(command: list[str], description: str, env: dict | None = None) -> None:
    print(f"==> {description}")
    result = subprocess.run(command, cwd=PROJECT, env=env)
    if result.returncode != 0:
        raise SystemExit(f"{description}: failed with code {result.returncode}")


def version() -> str:
    text = (PROJECT / "sentin_harden" / "__init__.py").read_text(encoding="utf-8")
    found = re.search(r'__version__\s*=\s*"([^"]+)"', text)
    if not found:
        raise SystemExit("the version is missing from sentin_harden/__init__.py")
    return found.group(1)


def check_glibc() -> None:
    """Warn where the build host is too new for the distributions covered.

    A warning and not a refusal: somebody building for their own machine has
    every right to. A release build runs on a controlled host, where this
    prints nothing.
    """
    try:
        _, release = platform.libc_ver()
        parts = tuple(int(p) for p in release.split(".")[:2])
    except (ValueError, TypeError):
        print("    could not read the glibc version; not checking it")
        return
    if parts > MAX_GLIBC:
        print(
            f"    warning: built against glibc {release}. The image will not "
            f"start on a distribution older than that, and the rule base "
            f"covers some. Build on an older host for a release."
        )


def fetch_tool(target: Path) -> Path:
    print(f"==> fetching appimagetool into {target}")
    target.parent.mkdir(parents=True, exist_ok=True)
    urllib.request.urlretrieve(APPIMAGETOOL_URL, target)
    target.chmod(target.stat().st_mode | stat.S_IEXEC)
    return target


def build_appdir() -> None:
    """Lay the frozen directory out the way AppImage expects to find it."""
    shutil.rmtree(APPDIR, ignore_errors=True)
    (APPDIR / "usr" / "lib").mkdir(parents=True)
    (APPDIR / "usr" / "share" / "applications").mkdir(parents=True)
    (APPDIR / "usr" / "share" / "icons" / "hicolor" / "256x256" / "apps").mkdir(parents=True)

    print("==> laying out the image directory")
    shutil.copytree(DIST, APPDIR / "usr" / "lib" / "Sentin-Harden")

    desktop = APPDIR / "sentin-harden.desktop"
    desktop.write_text(DESKTOP_ENTRY, encoding="utf-8")
    shutil.copy(desktop, APPDIR / "usr" / "share" / "applications")

    icon = PROJECT / "assets" / "sentin-harden.png"
    if not icon.exists():
        raise SystemExit(f"the icon is missing: {icon}. Run tools/make_icon.py.")
    shutil.copy(icon, APPDIR / "sentin-harden.png")
    shutil.copy(
        icon,
        APPDIR / "usr" / "share" / "icons" / "hicolor" / "256x256" / "apps" / "sentin-harden.png",
    )

    apprun = APPDIR / "AppRun"
    apprun.write_text(APPRUN, encoding="utf-8")
    apprun.chmod(apprun.stat().st_mode | stat.S_IEXEC | stat.S_IXGRP | stat.S_IXOTH)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--build", action="store_true", help="freeze the application first")
    parser.add_argument("--tool", help="path to appimagetool instead of downloading it")
    args = parser.parse_args()

    if os.name == "nt":
        raise SystemExit("the image is built on Linux, not on Windows")

    if args.build:
        run([sys.executable, str(PROJECT / "tools" / "build_artifact.py")], "building the artifact")

    executable = DIST / "Sentin-Harden"
    if not executable.exists():
        raise SystemExit(
            f"the artifact is missing: {DIST}. Build it first with "
            "tools/build_artifact.py, or pass --build."
        )

    check_glibc()
    WORK.mkdir(parents=True, exist_ok=True)
    build_appdir()

    tool = Path(args.tool) if args.tool else fetch_tool(WORK / "appimagetool")
    image = PROJECT / "dist" / f"Sentin-Harden-{version()}-x86_64.AppImage"
    image.unlink(missing_ok=True)

    env = dict(os.environ)
    # No signing and no update information: both belong to whoever publishes.
    env.setdefault("ARCH", "x86_64")
    run(
        # A runner has no FUSE, so the tool is asked to unpack itself rather
        # than mount. Without this the build fails on every hosted machine.
        [str(tool), "--appimage-extract-and-run", str(APPDIR), str(image)],
        "building the image",
        env=env,
    )

    if not image.exists():
        raise SystemExit("the image was not produced")
    image.chmod(image.stat().st_mode | stat.S_IEXEC)

    packed = image.stat().st_size
    source = sum(f.stat().st_size for f in DIST.rglob("*") if f.is_file())
    print(f"    image: {image}")
    print(f"    size:  {packed / (1024 * 1024):.0f} MB "
          f"(from {source / (1024 * 1024):.0f} MB of files)")
    if packed < source / 10:
        raise SystemExit("the image is too small to hold the artifact")

    print("==> done")
    return 0


if __name__ == "__main__":
    sys.exit(main())
