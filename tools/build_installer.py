#!/usr/bin/env python3
"""Build the Windows installer from the frozen artifact.

Takes what ``build_artifact.py`` produced under ``dist/Sentin-Harden`` and
packs it into one per-machine MSI. Three steps, in this order:

1. **harvest** - heat.exe walks the built directory and writes a source file
   listing every file in it. The frozen runtime is several hundred files and
   the list changes with every PySide6 release, so it is generated rather than
   kept by hand;
2. **compile** - candle.exe turns the harvest and the product definition into
   object files;
3. **link** - light.exe builds the MSI and embeds the cabinet.

The toolchain is the WiX Toolset, which is free, needs no interactive session
and runs the same way on a developer machine and on a build server. That last
point is what decided it: an installer that can only be produced by hand is an
installer that stops being produced.

Signing is a separate, optional step. An unsigned artifact that runs PowerShell
against the registry is exactly the shape SmartScreen and every antivirus is
built to distrust, so a release build should be signed - but the certificate
belongs to whoever publishes, not to the repository, and the build works
without one.

Usage:
    python tools/build_installer.py
    python tools/build_installer.py --build            # freeze first
    python tools/build_installer.py --sign-with <thumbprint>

Exit code 0 means the MSI was built and its size was checked.
"""

from __future__ import annotations

import argparse
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

PROJECT = Path(__file__).resolve().parent.parent
DIST = PROJECT / "dist" / "Sentin-Harden"
WORK = PROJECT / "build" / "installer"
PRODUCT = PROJECT / "installer" / "sentin-harden.wxs"

MANUFACTURER = "Grzegorz Oleksy"
TIMESTAMP_URL = "http://timestamp.digicert.com"

# Known install locations, newest first. The toolset is not on PATH by default
# and hunting for it here is cheaper than asking every machine to set one up.
WIX_CANDIDATES = [
    Path(os.environ.get("WIX", "")) / "bin",
    Path(r"C:\Program Files (x86)\WiX Toolset v3.14\bin"),
    Path(r"C:\Program Files (x86)\WiX Toolset v3.11\bin"),
    Path(r"C:\Program Files\WiX Toolset v3.14\bin"),
]


def wix_bin() -> Path:
    for candidate in WIX_CANDIDATES:
        if candidate and (candidate / "candle.exe").exists():
            return candidate
    raise SystemExit(
        "the WiX Toolset was not found. Install it, or point the WIX "
        "environment variable at its directory."
    )


def run(command: list[str], description: str) -> None:
    print(f"==> {description}")
    result = subprocess.run(command, cwd=PROJECT)
    if result.returncode != 0:
        raise SystemExit(f"{description}: failed with code {result.returncode}")


def version() -> str:
    """Read the version from the package, so it is stated in one place only.

    Parsed rather than imported: importing the package pulls in PySide6, which
    a build server has no reason to have loaded to answer this question.
    """
    text = (PROJECT / "sentin_harden" / "__init__.py").read_text(encoding="utf-8")
    found = re.search(r'__version__\s*=\s*"([^"]+)"', text)
    if not found:
        raise SystemExit("the version is missing from sentin_harden/__init__.py")
    parts = found.group(1).split(".")
    if not all(part.isdigit() for part in parts[:3]):
        # Windows Installer accepts only numbers here and silently misbehaves
        # on anything else, so a version it cannot carry is refused outright.
        raise SystemExit(f"the version is not usable in an MSI: {found.group(1)}")
    return ".".join(parts[:3])


def license_rtf(target: Path) -> Path:
    """Convert the licence to the RTF the installer window insists on.

    Generated rather than kept in the repository: two copies of a licence drift
    apart, and the one shown to whoever is installing has to be the one that
    actually ships.
    """
    text = (PROJECT / "LICENSE").read_text(encoding="utf-8")
    escaped = text.replace("\\", r"\\").replace("{", r"\{").replace("}", r"\}")
    body = escaped.replace("\n", r"\par" + "\n")
    target.write_text(
        r"{\rtf1\ansi\deff0{\fonttbl{\f0\fnil\fcharset0 Segoe UI;}}"
        r"\fs16" + "\n" + body + "\n}",
        encoding="ascii",
        errors="replace",
    )
    return target


def harvest(bin_dir: Path, files_wxs: Path) -> None:
    run(
        [
            str(bin_dir / "heat.exe"),
            "dir", str(DIST),
            "-cg", "AppFiles",
            "-dr", "INSTALLFOLDER",
            "-var", "var.SourceDir",
            # -srd keeps the harvested directory itself out of the tree, so the
            # contents land directly in the install folder. -gg settles the
            # component GUIDs now; -sfrag and -sreg keep the output to one
            # fragment and out of the registry.
            "-srd", "-gg", "-sfrag", "-sreg", "-suid",
            "-out", str(files_wxs),
        ],
        "harvesting the artifact",
    )


def compile_and_link(bin_dir: Path, files_wxs: Path, rtf: Path, msi: Path) -> None:
    objects = [WORK / "sentin-harden.wixobj", WORK / "files.wixobj"]
    run(
        [
            str(bin_dir / "candle.exe"),
            "-nologo",
            "-arch", "x64",
            f"-dVersion={version()}",
            f"-dManufacturer={MANUFACTURER}",
            f"-dSourceDir={DIST}",
            f"-dLicenseRtf={rtf}",
            "-ext", "WixUIExtension",
            "-out", str(WORK) + os.sep,
            str(PRODUCT),
            str(files_wxs),
        ],
        "compiling the installer sources",
    )
    run(
        [
            str(bin_dir / "light.exe"),
            "-nologo",
            "-ext", "WixUIExtension",
            # The harvest puts hundreds of unversioned files in one component
            # group, which ICE60 flags on principle; nothing here is a shared
            # versioned library, so the check does not apply. No other check is
            # suppressed - the rest were fixed in the source instead.
            "-sw1076", "-sice:ICE60",
            f"-dSourceDir={DIST}",
            "-out", str(msi),
            *[str(o) for o in objects],
        ],
        "linking the installer",
    )


def sign(bin_dir: Path, thumbprint: str, targets: list[Path]) -> None:
    """Sign the artifact and the package, in that order.

    The executable is signed before the MSI is built in a release flow; here it
    is done afterwards for whoever signs an already-built pair. Either way the
    MSI must be signed last, since signing a file inside it would invalidate
    the package.
    """
    signtool = shutil.which("signtool") or str(bin_dir / "signtool.exe")
    for target in targets:
        run(
            [
                signtool, "sign",
                "/sha1", thumbprint,
                "/fd", "sha256",
                "/tr", TIMESTAMP_URL,
                "/td", "sha256",
                str(target),
            ],
            f"signing {target.name}",
        )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--build",
        action="store_true",
        help="freeze the application first instead of using what is in dist",
    )
    parser.add_argument(
        "--sign-with",
        metavar="THUMBPRINT",
        help="sign the executable and the package with this certificate",
    )
    args = parser.parse_args()

    if args.build:
        run(
            [sys.executable, str(PROJECT / "tools" / "build_artifact.py")],
            "building the artifact",
        )

    if not (DIST / "Sentin-Harden.exe").exists():
        raise SystemExit(
            f"the artifact is missing: {DIST}. Build it first with "
            "tools/build_artifact.py, or pass --build."
        )

    bin_dir = wix_bin()
    print(f"==> using the toolset at {bin_dir}")

    shutil.rmtree(WORK, ignore_errors=True)
    WORK.mkdir(parents=True, exist_ok=True)

    files_wxs = WORK / "files.wxs"
    msi = PROJECT / "dist" / f"Sentin-Harden-{version()}-x64.msi"

    harvest(bin_dir, files_wxs)
    compile_and_link(bin_dir, files_wxs, license_rtf(WORK / "license.rtf"), msi)

    if args.sign_with:
        sign(bin_dir, args.sign_with, [DIST / "Sentin-Harden.exe", msi])

    if not msi.exists():
        raise SystemExit("the installer was not produced")

    # A package far smaller than the artifact it carries means the harvest
    # picked up nothing, which the linker reports as success.
    packed = msi.stat().st_size
    source = sum(f.stat().st_size for f in DIST.rglob("*") if f.is_file())
    print(f"    installer: {msi}")
    print(f"    size:      {packed / (1024 * 1024):.0f} MB "
          f"(from {source / (1024 * 1024):.0f} MB of files)")
    if packed < source / 10:
        raise SystemExit("the installer is too small to hold the artifact")
    if not args.sign_with:
        print("    not signed. A release build should be.")

    print("==> done")
    return 0


if __name__ == "__main__":
    sys.exit(main())
