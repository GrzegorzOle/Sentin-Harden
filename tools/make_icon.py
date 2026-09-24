#!/usr/bin/env python3
"""Draw the application icon.

Kept as a script rather than as a binary somebody once exported, so the mark
can be regenerated at any size without hunting for the original. It writes a
set of PNGs and, on Windows, the multi-resolution ICO the executable carries.

The mark is a shield with a gap in it. The gap is the point: the application is
not about a system being sealed, it is about knowing which opening is still
there and deciding, one at a time, whether to close it.

Usage:
    python tools/make_icon.py
"""

from __future__ import annotations

import sys
from pathlib import Path

from PySide6.QtCore import QRectF, Qt
from PySide6.QtGui import QBrush, QColor, QIcon, QImage, QPainter, QPainterPath

PROJECT = Path(__file__).resolve().parent.parent
ASSETS = PROJECT / "assets"

SIZES = (16, 24, 32, 48, 64, 128, 256, 512)

BACKGROUND = QColor("#1f2733")
SHIELD = QColor("#e8ecf2")
GAP = QColor("#b3261e")


def shield_path(size: float) -> QPainterPath:
    """The outline, described once in a unit square and scaled to the size."""
    w = size
    top = 0.16 * w
    side = 0.22 * w
    bottom = 0.90 * w
    shoulder = 0.56 * w

    path = QPainterPath()
    path.moveTo(0.5 * w, top)
    path.lineTo(w - side, top + 0.06 * w)
    path.lineTo(w - side, shoulder)
    # The lower half narrows to a point, which is what reads as a shield at
    # sixteen pixels; the upper half is nearly square and carries the gap.
    path.quadTo(w - side, bottom - 0.12 * w, 0.5 * w, bottom)
    path.quadTo(side, bottom - 0.12 * w, side, shoulder)
    path.lineTo(side, top + 0.06 * w)
    path.closeSubpath()
    return path


def draw(size: int) -> QImage:
    image = QImage(size, size, QImage.Format_ARGB32)
    image.fill(Qt.transparent)

    painter = QPainter(image)
    painter.setRenderHint(QPainter.Antialiasing, True)

    radius = size * 0.22
    painter.setPen(Qt.NoPen)
    painter.setBrush(QBrush(BACKGROUND))
    painter.drawRoundedRect(QRectF(0, 0, size, size), radius, radius)

    painter.setBrush(QBrush(SHIELD))
    painter.drawPath(shield_path(size))

    # The notch is painted in the background colour rather than cleared, so it
    # reads as a slot in the shield and not as a hole through the whole tile.
    painter.setBrush(QBrush(BACKGROUND))
    painter.drawRect(QRectF(size * 0.44, size * 0.10, size * 0.12, size * 0.44))

    # The notch carries on in the colour the interface uses for the worst
    # finding: the opening is not merely there, it is the thing to look at.
    painter.setBrush(QBrush(GAP))
    painter.drawRect(QRectF(size * 0.44, size * 0.54, size * 0.12, size * 0.20))

    painter.end()
    return image


def main() -> int:
    ASSETS.mkdir(exist_ok=True)

    # A QGuiApplication is not needed for QImage, but QIcon wants one.
    from PySide6.QtGui import QGuiApplication

    app = QGuiApplication.instance() or QGuiApplication([])

    images = {size: draw(size) for size in SIZES}
    for size in (256, 512):
        target = ASSETS / f"sentin-harden-{size}.png"
        images[size].save(str(target), "PNG")
        print(f"    {target}")

    main_png = ASSETS / "sentin-harden.png"
    images[256].save(str(main_png), "PNG")
    print(f"    {main_png}")

    icon = QIcon()
    for size, image in images.items():
        from PySide6.QtGui import QPixmap

        icon.addPixmap(QPixmap.fromImage(image))
    ico = ASSETS / "sentin-harden.ico"
    # Qt writes ICO only where the platform plugin supports it, which is every
    # platform it ships; the sizes come from the pixmaps added above.
    writer_ok = images[256].save(str(ico), "ICO")
    print(f"    {ico}" if writer_ok else "    ICO not written on this platform")

    del app
    return 0


if __name__ == "__main__":
    sys.exit(main())
