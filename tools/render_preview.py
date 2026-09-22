"""Render window screenshots without a live scan.

Development aid: builds the audit window, feeds it made-up outcomes and saves a
PNG per language. Lets interface changes be reviewed without waiting for a real
audit, and without a machine that happens to fail the interesting rules.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from PySide6.QtWidgets import QApplication  # noqa: E402

from sentin_harden.audit import AuditResult, Outcome  # noqa: E402
from sentin_harden.ui import MainWindow  # noqa: E402

OUTCOMES = [Outcome.FAIL, Outcome.PASS, Outcome.ERROR, Outcome.FAIL]


def main() -> int:
    app = QApplication([])
    window = MainWindow()

    target = window.target or next(iter(window.base.targets.values()))
    window.target = target
    results = [
        AuditResult(rule, OUTCOMES[index % len(OUTCOMES)], "sample")
        for index, rule in enumerate(target.rules)
    ]

    out = Path(__file__).resolve().parents[1] / "build" / "preview"
    out.mkdir(parents=True, exist_ok=True)

    for code in ("pl", "en"):
        window.switch_language(code)
        window._scan_finished(results)
        window.show()
        app.processEvents()
        window.grab().save(str(out / f"window-{code}.png"))

    # And one frame mid-scan, so the progress bar can be reviewed too.
    window.progress.setRange(0, len(results))
    window.progress.setValue(max(len(results) - 1, 0))
    window.progress.setVisible(True)
    window._scan_progress(max(len(results) - 1, 0), len(results), target.rules[-1])
    app.processEvents()
    window.grab().save(str(out / "window-scanning.png"))

    print(out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
