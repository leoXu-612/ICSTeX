"""Render the real source-build update entry without loading an updater or a project."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
from tempfile import TemporaryDirectory

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from PySide6.QtCore import QSettings
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication

from app.core.settings import AppSettings
from app.gui.app_update_controller import AppUpdateController
from app.gui.main_window import MainWindow
from app.gui.theme import apply_theme


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    app = QApplication([])
    apply_theme(app)
    with TemporaryDirectory(prefix="icstex-update-ui-") as temporary:
        settings = QSettings(str(Path(temporary) / "settings.ini"), QSettings.Format.IniFormat)
        window = MainWindow(settings_store=AppSettings(settings))
        app._icstex_windows = [window]
        controller = AppUpdateController(app, settings=settings)
        app._icstex_updates = controller
        window.show()
        main_exposed = QTest.qWaitForWindowExposed(window, 2000)
        window.app_update_action.trigger()
        dialog = controller._dialog
        assert dialog is not None
        dialog_exposed = QTest.qWaitForWindowExposed(dialog, 2000)
        app.processEvents()
        records = []
        for scale in (1.0, 1.5):
            window.set_ui_scale(scale)
            dialog.adjustSize()
            app.processEvents()
            image_path = args.output / f"update-source-{int(scale * 100)}.png"
            assert dialog.grab().save(str(image_path))
            records.append({"scale": scale, "size": [dialog.width(), dialog.height()],
                            "image": image_path.name,
                            "check_enabled": dialog.check_button.isEnabled(),
                            "auto_checked": dialog.automatic.isChecked()})
        assert controller._backend is None
        assert not controller.availability.available
        assert not controller.automatic
        report = {"platform": app.platformName(), "main_exposed": bool(main_exposed),
                  "dialog_exposed": bool(dialog_exposed), "reason": controller.availability.reason,
                  "native_backend_loaded": False, "student_projects_opened": 0, "renders": records}
        (args.output / "report.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
        controller.close()
        window.close()
        app.processEvents()
    print(json.dumps(report, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
