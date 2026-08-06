"""Coordinate exports that must come from a current, canonical PDF build."""
from __future__ import annotations

from dataclasses import dataclass
import os
from pathlib import Path
import shutil
import tempfile
from typing import TYPE_CHECKING, Any

from app.core.compiler import BuildPurpose, CompileResult
from app.core.paths import normalize_path
from app.core.pdf_state import PdfBuildRecord, PdfFreshness

if TYPE_CHECKING:  # pragma: no cover - typing only
    from app.gui.main_window import MainWindow


@dataclass(frozen=True)
class PendingExport:
    """One requested destination, tied to the latest observed source revision."""

    root_file: Path
    target: Path
    requested_revision: int
    bound_build_id: int | None = None


class PdfExportController:
    """Export only a current PDF produced by a ``FINAL`` build.

    ``MainWindow`` owns destination selection.  This controller owns the
    freshness check and keeps a request pending while a canonical build is in
    flight.  Preview PDFs are never accepted as an export source.
    """

    def __init__(self, window: "MainWindow") -> None:
        self.window = window
        self._pending: dict[Path, PendingExport] = {}

    def pending_for(self, root: str | Path) -> PendingExport | None:
        return self._pending.get(normalize_path(root))

    def handle_compile_started(
        self,
        root: str | Path,
        build_id: int,
        purpose: BuildPurpose | str,
    ) -> bool:
        """Bind a pending export to the newest FINAL started after its request.

        A FINAL that was already running when the user requested export has
        already emitted its started event, so it cannot claim the new request.
        Rebinding to a newer FINAL also makes late results from an older build
        harmless.
        """
        if BuildPurpose(purpose) is not BuildPurpose.FINAL:
            return False
        root_file = normalize_path(root)
        pending = self._pending.get(root_file)
        if pending is None:
            return False
        if pending.bound_build_id is not None and build_id <= pending.bound_build_id:
            return False
        self._pending[root_file] = PendingExport(
            root_file=pending.root_file,
            target=pending.target,
            requested_revision=pending.requested_revision,
            bound_build_id=build_id,
        )
        return True

    def request_export(self, root: str | Path, target: str | Path) -> bool:
        """Export immediately when canonical state is current, or queue FINAL.

        ``True`` means the request was either completed or successfully queued.
        ``False`` means saving, manager lookup, or the atomic copy failed.
        """
        root_file = normalize_path(root)
        destination = Path(target).expanduser().resolve()
        if not self.window.documents.flush_root_documents(root_file):
            self._report_error("无法保存项目中的待写入修改，已取消 PDF 导出。")
            return False

        record = self.window.pdf_state.record_for(root_file)
        if self._is_current_canonical(record):
            assert record.last_successful_pdf is not None
            return self._copy_atomic(record.last_successful_pdf, destination)

        manager = self._manager_for_root(root_file)
        if manager is None:
            self._report_error("无法为当前项目启动正式编译，已取消 PDF 导出。")
            return False

        self._pending[root_file] = PendingExport(
            root_file=root_file,
            target=destination,
            requested_revision=record.source_revision,
        )
        self._start_final(manager)
        self._report_status("正在使用原图生成正式 PDF，完成后将自动导出…", 5000)
        return True

    def handle_compile_result(
        self,
        result: CompileResult,
        record: PdfBuildRecord | None,
    ) -> bool:
        """Advance a pending request after a canonical compile result.

        Returns whether this result belonged to a pending export.  Preview and
        superseded results are ignored without changing the pending request.
        """
        if BuildPurpose(result.purpose) is not BuildPurpose.FINAL:
            return False

        root_file = normalize_path(result.root_file)
        pending = self._pending.get(root_file)
        if pending is None:
            return False
        if pending.bound_build_id != result.build_id:
            return False
        if record is None:
            return False

        if not result.ok:
            self._pending.pop(root_file, None)
            self._report_error("正式 PDF 编译失败，未导出任何预览或旧版本。")
            return True

        if self._is_current_canonical(record):
            self._pending.pop(root_file, None)
            assert record.last_successful_pdf is not None
            self._copy_atomic(record.last_successful_pdf, pending.target)
            return True

        # A successful build can already be stale when the source changed
        # while it was running.  Flush again and require another FINAL build.
        if record.source_revision != record.last_successful_revision:
            if not self.window.documents.flush_root_documents(root_file):
                self._pending.pop(root_file, None)
                self._report_error("无法保存编译期间的新修改，已取消 PDF 导出。")
                return True
            manager = self._manager_for_root(root_file)
            if manager is None:
                self._pending.pop(root_file, None)
                self._report_error("无法重新启动正式编译，已取消 PDF 导出。")
                return True
            self._pending[root_file] = PendingExport(
                root_file=root_file,
                target=pending.target,
                requested_revision=record.source_revision,
                bound_build_id=None,
            )
            self._start_final(manager)
            self._report_status("检测到编译期间有新修改，正在重新生成正式 PDF…", 5000)
            return True

        # A success with matching revisions but non-current/invalid state is
        # an invariant violation; retrying indefinitely would hide it.
        self._pending.pop(root_file, None)
        self._report_error("正式编译结果不可用，已取消 PDF 导出。")
        return True

    def cancel_root(self, root: str | Path) -> bool:
        """Forget any queued destination for ``root``."""
        return self._pending.pop(normalize_path(root), None) is not None

    @staticmethod
    def _is_current_canonical(record: PdfBuildRecord) -> bool:
        return (
            record.freshness is PdfFreshness.CURRENT
            and record.last_successful_revision == record.source_revision
            and record.has_valid_pdf
        )

    def _manager_for_root(self, root_file: Path) -> Any | None:
        managers = getattr(self.window, "compile_managers", None)
        manager = managers.get(root_file) if managers is not None else None
        if manager is not None:
            return manager
        creator = getattr(self.window, "create_compile_manager", None)
        if callable(creator):
            return creator(root_file)
        return None

    @staticmethod
    def _start_final(manager: Any) -> None:
        cancel_pending = getattr(manager, "cancel_pending", None)
        if callable(cancel_pending):
            cancel_pending()
        manager.compile_async(BuildPurpose.FINAL)

    def _copy_atomic(self, source: Path, target: Path) -> bool:
        temp_name: str | None = None
        try:
            handle, temp_name = tempfile.mkstemp(
                dir=str(target.parent),
                prefix=f".{target.name}.",
                suffix=".part",
            )
            os.close(handle)
            shutil.copy2(source, temp_name)
            os.replace(temp_name, target)
            temp_name = None
        except OSError as exc:
            self._report_error(f"PDF 导出失败：{exc}")
            return False
        finally:
            if temp_name is not None:
                try:
                    os.unlink(temp_name)
                except OSError:
                    pass
        self._report_status(f"已导出 PDF：{target}", 5000)
        return True

    def _report_status(self, message: str, duration_ms: int) -> None:
        callback = getattr(self.window, "notify_pdf_export_status", None)
        if callable(callback):
            callback(message, duration_ms)
            return
        status_bar = getattr(self.window, "statusBar", None)
        if callable(status_bar):
            status_bar().showMessage(message, duration_ms)

    def _report_error(self, message: str) -> None:
        callback = getattr(self.window, "notify_pdf_export_error", None)
        if callable(callback):
            callback(message)
            return
        append_log = getattr(self.window, "append_log", None)
        if callable(append_log):
            append_log(message)
        self._report_status(message, 6000)
