"""D2 widget comparison with synthetic unit evidence; no real PDF/FINAL claim."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import sys

os.environ["QT_QPA_PLATFORM"] = "offscreen"
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from PySide6.QtCore import QEvent
from shiboken6 import isValid
from app.gui.theme import apply_theme
from tests.test_submission_delivery_gui import SubmissionDeliveryGuiTests
from tools.bench_pdf_pipeline import source_digest


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    output = args.output.resolve()
    output.mkdir(parents=True, exist_ok=False)
    case = SubmissionDeliveryGuiTests()
    case.setUpClass()
    apply_theme(case.app)
    case.setUp()
    dialog = case.dialog
    original = case.sample.root.read_bytes()
    evidence = {"app_sha256": source_digest(), "states": [], "completed": False,
                "limits": "Offscreen widget captures; synthetic FINAL evidence, not PDF rendering or native acceptance"}

    def capture(name, buttons):
        for _ in range(6):
            case.app.processEvents()
        visible = {b.text(): b.visibleRegion().contains(b.rect()) for b in buttons}
        image = name + ".png"
        assert dialog.grab().save(str(output / image))
        evidence["states"].append({"name": name, "image": image, "actions_visible": visible,
            "size": [dialog.width(), dialog.height()]})
        if hasattr(dialog, "pages"):
            assert all(visible.values()), (name, visible)

    try:
        dialog.show()
        for scale in (1.0, 1.5):
            case.app.ui_scale_manager.apply_scale(scale)
            dialog.resize(900 if scale == 1 else 760, 640 if scale == 1 else 620)
            dialog.invalidate()
            capture(f"{scale}-prepare", (dialog.review_button, dialog.close_button))
            case.review()
            frozen = dialog.prepared
            evidence.setdefault("payloads", []).append([(p, len(raw), hashlib.sha256(raw).hexdigest())
                                                         for p, raw in dialog.payloads])
            dialog.outputs.setCurrentItem(dialog.outputs.topLevelItem(0))
            dialog.acknowledge.setChecked(True)
            if hasattr(dialog, "pages"):
                capture(f"{scale}-review", (dialog.acknowledge, dialog.continue_button, dialog.back_button, dialog.close_button))
                dialog.technical_button.click()
                capture(f"{scale}-technical", (dialog.continue_button, dialog.back_button, dialog.close_button))
                dialog.technical_button.click()
                dialog.continue_button.click()
            capture(f"{scale}-target", (dialog.action_button, dialog.close_button))
            assert dialog.prepared is frozen
        assert case.sample.root.read_bytes() == original
        assert not case.window.compile_authorized_roots
        assert not (case.home / "delivered").exists()
        evidence["originals_unchanged"] = True
        evidence["no_compile_or_publish"] = True
        evidence["completed"] = True
    finally:
        case.doCleanups()
        case.app.sendPostedEvents(None, QEvent.Type.DeferredDelete)
        evidence["window_destroyed"] = not isValid(dialog)
        evidence["app_sha256_after"] = source_digest()
        evidence["completed"] = (evidence["completed"] and evidence["window_destroyed"]
                                 and evidence["app_sha256_after"] == evidence["app_sha256"])
        (output / "result.json").write_text(json.dumps(evidence, ensure_ascii=False, indent=2) + "\n")
    assert evidence["completed"], evidence
    print(json.dumps(evidence, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
