"""RapidOCR Review -> Text Block flow (independent of formula OCR)."""
from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QEventLoop, QTimer
from PySide6.QtWidgets import QApplication, QDialog, QFileDialog, QMessageBox

from app.core.blocks.model import content_for_text
from app.gui.text_ocr.text_ocr_manager import TextOcrManager
from app.gui.text_ocr.text_review_dialog import TextReviewDialog


def get_manager(parent=None) -> TextOcrManager:
    """Return the application-wide TextOcrManager, creating it lazily."""

    app = QApplication.instance()
    manager = getattr(app, "text_ocr_manager", None)
    if manager is None:
        manager = TextOcrManager(app)
        app.text_ocr_manager = manager
    return manager


def wait_text(manager: TextOcrManager, image_path: Path, timeout_ms: int = 90_000):
    """Blocking helper: recognize one image, return (text, payload) or None."""

    box: dict = {}

    def on_ready(request_id, text, payload) -> None:
        box["text"] = text
        box["payload"] = payload

    def on_failed(request_id, code, message) -> None:
        box["error"] = f"{code}: {message}"

    def stop(*_args) -> None:
        loop.quit()

    loop = QEventLoop()
    timer = QTimer()
    timer.setSingleShot(True)
    timer.timeout.connect(stop)
    timer.start(timeout_ms)
    manager.text_ready.connect(on_ready)
    manager.failed.connect(on_failed)
    manager.text_ready.connect(stop)
    manager.failed.connect(stop)
    manager.recognize(image_path)
    loop.exec()
    manager.text_ready.disconnect(on_ready)
    manager.failed.disconnect(on_failed)
    manager.text_ready.disconnect(stop)
    manager.failed.disconnect(stop)
    timer.stop()
    if "text" in box:
        return box["text"], box["payload"]
    return None


def _pick_image(parent) -> Path | None:
    file_name, _ = QFileDialog.getOpenFileName(parent, "选择文字图片", "", "图片 (*.png *.jpg *.jpeg *.webp)")
    if not file_name:
        return None
    return Path(file_name)


def run_text_block_ocr(parent, controller) -> None:
    """Open image -> RapidOCR -> review -> create a Text Block."""

    manager = get_manager(parent)
    if manager.status() == "NOT_INSTALLED":
        QMessageBox.information(parent, "文字识别", "RapidOCR 未安装或运行环境缺失，请先在设置中安装。")
        return
    image_path = _pick_image(parent)
    if image_path is None:
        return
    result = wait_text(manager, image_path)
    if result is None:
        QMessageBox.warning(parent, "文字识别", "识别失败或超时，请检查 RapidOCR 运行环境。")
        return
    text, payload = result
    if not text.strip():
        QMessageBox.information(parent, "文字识别", "未识别到文字内容。")
        return
    dialog = TextReviewDialog(image_path, text, payload, parent)
    if dialog.exec() != QDialog.DialogCode.Accepted:
        return
    final_text = dialog.result_text()
    if not final_text:
        QMessageBox.information(parent, "文字识别", "识别内容为空，未创建 Block。")
        return
    first_line = final_text.splitlines()[0].strip()
    alias = (first_line[:20] + "…") if len(first_line) > 20 else (first_line or "OCR 文本")
    controller.add_block("text", alias=alias, content=content_for_text(final_text))
    QMessageBox.information(parent, "文字识别", "已创建 Text Block。")
