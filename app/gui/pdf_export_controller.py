"""Two-action PDF export and remembered FINAL updates, sharing exact-byte verification."""
from __future__ import annotations

from dataclasses import dataclass, replace
from pathlib import Path
import threading
from typing import TYPE_CHECKING

from PySide6.QtCore import QObject, QTimer, Qt
from PySide6.QtWidgets import QFileDialog, QDialog, QProgressDialog
from shiboken6 import isValid

from app.core.artifact_export import (
    EXPORT_CONTEXT_PATHS, ExportedPdf, capture_export_inputs, exported_pdf,
    pdf_export_destination, publish_exact_file, verified_final_pdf,
)
from app.core.compiler import BuildPurpose, CompileResult
from app.core.paths import normalize_path
from app.core.pdf_state import PdfBuildRecord, PdfFreshness
from app.gui.project_checkpoint_dialog import CaptureLease, _Signals, _run

if TYPE_CHECKING:
    from app.gui.main_window import MainWindow


@dataclass(frozen=True)
class PendingExport:
    root_file: Path
    target: Path
    requested_revision: int
    scope: Path
    tab_id: int
    bound_build_id: int | None = None
    ready: bool = False
    previous: ExportedPdf | None = None
    automatic: bool = False


class PdfExportController(QObject):
    """GUI-thread coordination; the publication worker receives immutable evidence only."""

    def __init__(self, window: "MainWindow") -> None:
        super().__init__(window)
        self.window = window
        self._pending: dict[Path, PendingExport] = {}
        self._automatic_results = {}  # Latest accepted FINAL per root, drained by the existing timer.
        self._stopped_roots = set()
        self._publication = None
        self._closed = False
        self._progress = None
        self._signals = _Signals()
        self._signals.finished.connect(self._finished, Qt.ConnectionType.QueuedConnection)
        self._timer = QTimer(self)
        self._timer.setInterval(75)
        self._timer.timeout.connect(self._poll)
        window.destroyed.connect(self.shutdown)

    def pending_for(self, root: str | Path) -> PendingExport | None:
        return self._pending.get(normalize_path(root))

    def choose_destination(self, root: Path) -> bool:
        if self._pending:
            self._report_status("正在导出，请稍候。", 4000)
            return False
        remembered = self.window.app_settings.pdf_export_target(root)
        target = remembered[1].target if remembered else root.with_suffix(".pdf")
        number = 2
        while not remembered and target.exists():
            target = root.with_name(f"{root.stem}-{number}.pdf")
            number += 1
        dialog = QFileDialog(self.window, "导出 PDF · 以后正式编译会更新此文件", str(target), "PDF (*.pdf)")
        dialog.setAcceptMode(QFileDialog.AcceptMode.AcceptSave)
        dialog.setDefaultSuffix("pdf")
        dialog.setLabelText(QFileDialog.DialogLabel.Accept, "更新并导出")
        dialog.setOption(QFileDialog.Option.DontConfirmOverwrite, True)
        try:
            if dialog.exec() != QDialog.DialogCode.Accepted:
                return False
            destination = dialog.selectedFiles()[0]
        finally:
            dialog.deleteLater()
        # Recheck after the file dialog; another window may have changed the project.
        if not self.request_export(root, destination):
            return False
        self._progress = QProgressDialog("正在更新 PDF，完成后自动导出…", "取消", 0, 0, self.window)
        self._progress.setWindowTitle("导出 PDF")
        self._progress.setWindowModality(Qt.WindowModality.ApplicationModal)
        self._progress.canceled.connect(lambda: self.cancel_root(root))
        self._progress.show()
        return True

    def _request(self, root: Path, *, scope: Path | None = None):
        kwargs = {} if scope is None else dict(root=root, scope=scope)
        request = self.window.readiness.capture_request(**kwargs)
        if request.root != root or request.scope is None or request.block is not None:
            raise ValueError("导出目标已切换，请从对应文稿重新导出。")
        tabs = self.window.readiness._context(**kwargs)[3]
        if any(tab.external_conflict for tab in tabs):
            raise ValueError("文件有外部修改冲突，请先处理后再导出。")
        if any(tab.editor.has_preedit() for tab in tabs):
            raise ValueError("请先完成正在输入的文字，再导出 PDF。")
        return request

    def _current(self, request) -> bool:
        record, proof = request.final, request.build_evidence
        return bool(record is not None and proof is not None
                    and record.freshness is PdfFreshness.CURRENT and record.has_valid_pdf
                    and record.last_successful_revision == record.source_revision
                    and proof.build_id == record.latest_build_id
                    and proof.inputs is not None and proof.inputs.stable
                    and proof.job_key.root_file == request.root
                    and proof.job_key.source_revision == record.source_revision
                    and proof.job_key.engine == request.engine
                    and proof.job_key.toolchain == request.tools
                    and not any(buffer.modified for buffer in request.buffers))

    def request_export(self, root: str | Path, target: str | Path) -> bool:
        """Accept the explicit save/update/export intent; no file write on picker cancellation."""
        if self._closed or self._pending or self._publication is not None:
            return False
        root = normalize_path(root)
        target = Path(target).expanduser().absolute()
        try:
            request = self._request(root)
            if target.suffix.lower() != ".pdf":
                raise ValueError("请选择 PDF 文件名。")
            remembered = self.window.app_settings.pdf_export_target(root)
            previous = (remembered[1] if remembered and remembered[0] == request.scope
                        and remembered[1].target == target else None)
            if previous is None and (target.exists() or target.is_symlink()):
                raise ValueError("已有同名文件，请换个名字；原文件不会覆盖。")
            tab = self.window.current_tab()
            if tab is None:
                return False
            self._stopped_roots.discard(root)
            self._pending[root] = PendingExport(root, target, request.source_revision,
                                                request.scope, id(tab.editor), ready=self._current(request),
                                                previous=previous)
            if not self._pending[root].ready and not self._start_final(self._pending[root]):
                self._pending.pop(root, None)
                return False
            self._timer.start()
            self._report_status("正在更新 PDF，完成后自动导出…", 0)
            return True
        except (OSError, ValueError) as exc:
            self._pending.pop(root, None)
            self._report_error(str(exc))
            return False

    def _start_final(self, pending: PendingExport) -> bool:
        return self.window.compile.compile_current(
            immediate=True, show_missing_warning=True, purpose=BuildPurpose.FINAL,
            user_initiated=True, _tab_id=pending.tab_id, _reason="更新并导出 PDF",
        )

    def handle_compile_started(self, root, build_id, purpose) -> bool:
        if BuildPurpose(purpose) is not BuildPurpose.FINAL:
            return False
        root = normalize_path(root)
        pending = self._pending.get(root)
        if pending is not None and pending.automatic:
            self.cancel_root(root)  # Its newer result may enqueue a fresh automatic update.
            return True
        if pending is None or (pending.bound_build_id is not None and build_id <= pending.bound_build_id):
            return False
        self._pending[root] = replace(pending, bound_build_id=build_id, ready=False)
        return True

    def handle_compile_result(self, result: CompileResult, record: PdfBuildRecord | None) -> bool:
        if self._closed or result.purpose is not BuildPurpose.FINAL:
            return False
        root = normalize_path(result.root_file)
        pending = self._pending.get(root)
        if pending is None or pending.automatic:
            if (result.ok and record is not None and record.latest_build_id == result.build_id
                    and record.freshness is PdfFreshness.CURRENT
                    and self.window.app_settings.pdf_export_target(root) is not None):
                self._automatic_results[root] = result.build_id
                self._timer.start()
                return True
            return False
        if pending is None or pending.bound_build_id != result.build_id or record is None:
            return False
        if not result.ok:
            self.cancel_root(root)
            self._report_error("PDF 更新失败，未导出旧版本。请查看编译错误。")
            return True
        try:
            request = self._request(root)
            if self._current(request):
                self._pending[root] = replace(pending, ready=True)
            elif record.source_revision != record.last_successful_revision:
                pending = replace(pending, requested_revision=record.source_revision, bound_build_id=None)
                self._pending[root] = pending
                if not self._start_final(pending):
                    self.cancel_root(root)
            else:
                raise ValueError("PDF 尚未验证为最新版本，未导出。请重新正式编译。")
        except (OSError, ValueError) as exc:
            self.cancel_root(root)
            self._report_error(str(exc))
        return True

    def _poll(self) -> None:
        if not self._closed and not self._pending:
            self._queue_automatic()
        if self._closed or not self._pending:
            self._timer.stop()
            return
        pending = next(iter(self._pending.values()))
        try:
            kwargs = dict(root=pending.root_file, scope=pending.scope) if pending.automatic else {}
            key, scope, root, tabs, _, session = self.window.readiness._context(**kwargs)
            if root != pending.root_file or scope != pending.scope or session is not None:
                raise ValueError("项目已切换，导出已取消。")
            if pending.automatic and pending.tab_id not in self.window.tabs:
                raise ValueError("文稿已关闭，自动更新已取消。")
            if any(tab.external_conflict for tab in tabs):
                raise ValueError("文件有外部修改冲突，请先处理后再导出。")
            if self._publication is not None:
                _, lease, expected = self._publication
                lease.validate()
                if key != expected:
                    lease.cancelled.set()
                return
            if not pending.ready:
                return
            # A queued GUI result can precede the worker's final idle cleanup.
            managers = self.window.compile_managers.values()
            if any(manager.is_busy or manager._scheduled_request is not None or manager._pending_request is not None
                   for manager in managers
                   if manager.root_file.is_relative_to(pending.scope)):
                return
            request = self._request(pending.root_file, scope=pending.scope if pending.automatic else None)
            if not self._current(request):
                raise ValueError("内容已变化，请重新导出；已有文件保持不变。")
            try:
                lease = CaptureLease(self.window, pending.scope)
            except ValueError as exc:
                self.window.append_log(str(exc))
                raise ValueError("同项目还有编译、导入或未保存草稿，请处理后再导出。") from exc
            try:
                if lease.drafts or any(tab.editor.has_preedit() for _, tab, *_ in lease.tabs):
                    raise ValueError("另一个窗口有未保存内容，请先处理后再导出。")
                proof, scope, target, cancel = request.build_evidence, pending.scope, pending.target, lease.cancelled
                self._publication = pending, lease, request.key

                def work(stop):
                    context = capture_export_inputs(scope, EXPORT_CONTEXT_PATHS, cancelled=stop)
                    payload = verified_final_pdf(proof, context, cancelled=stop)
                    destination = pdf_export_destination(target, proof)
                    published = publish_exact_file(destination, payload,
                        check_source=lambda: verified_final_pdf(proof, context, cancelled=stop),
                        cancelled=stop, previous=pending.previous)
                    return exported_pdf(published, payload)

                self._thread = threading.Thread(target=_run, args=(work, cancel, self._signals),
                                                name="icstex-pdf-export", daemon=True)
                self._thread.start()
            except BaseException:
                lease.release()
                self._publication = None
                raise
        except (OSError, ValueError, RuntimeError) as exc:
            if self._publication is not None:
                self._publication[1].cancelled.set()
            else:
                self.cancel_root(pending.root_file)
                self._report_failure(pending, str(exc))

    def _queue_automatic(self):
        """No compile/save request here: only consume a successful, still-current FINAL."""
        while self._automatic_results:
            root = next(iter(self._automatic_results))
            build_id = self._automatic_results.pop(root)
            remembered = self.window.app_settings.pdf_export_target(root)
            tab = self.window.compile._tab_for_compile_root(root)
            record = self.window.pdf_state.record_for(root)
            if (remembered is None or tab is None or record is None
                    or record.latest_build_id != build_id or record.freshness is not PdfFreshness.CURRENT):
                continue
            scope, previous = remembered
            self._stopped_roots.discard(root)  # Another window may have explicitly exported again.
            pending = PendingExport(root, previous.target, record.source_revision, scope,
                                    id(tab.editor), build_id, True, previous, True)
            self._pending[root] = pending
            return

    def stop_automatic(self):
        root = self.window._compile_root_for_tab(self.window.current_tab())
        if root is not None:
            self._stopped_roots.add(root)
            self.window.app_settings.forget_pdf_export(root)
            self.cancel_root(root)
            self.window._update_pdf_action_state()
            self._report_status("已停止自动更新导出 PDF；已有文件保留。", 5000)

    def _report_failure(self, pending, message):
        if pending.automatic:
            self.window.append_log(message)
            self._report_pending_status(pending,
                f"未更新 {pending.target.name}；请检查目标文件，或重新导出到新位置。", 12000)
        else:
            self._report_error(message)

    def _report_pending_status(self, pending, message, duration):
        if (not pending.automatic
                or self.window._compile_root_for_tab(self.window.current_tab()) == pending.root_file):
            self._report_status(message, duration)
        else:
            self.window.append_log(message)  # Do not replace another document's current indicators.

    def _finished(self, value, error) -> None:
        publication, self._publication = self._publication, None
        if publication is None:
            return
        pending, lease, _ = publication
        lease.release()
        cancelled = lease.cancelled.is_set()
        self._pending.pop(pending.root_file, None)
        if not self._automatic_results:
            self._timer.stop()
        self._close_progress()
        if self._closed:
            return
        if value is not None:
            # Publication may win a late cancellation: report the real file. A user
            # stopping updates during a worker must not be silently enrolled again.
            remembered = self.window.app_settings.pdf_export_target(pending.root_file)
            remember = (pending.root_file not in self._stopped_roots
                        and (not pending.automatic or remembered == (pending.scope, pending.previous)))
            if remember:
                self.window.app_settings.remember_pdf_export(pending.root_file, pending.scope, value)
            self.window._update_pdf_action_state()
            hint = "；正式编译后自动更新。" if remember else "；自动更新已停止或目标已更改。"
            self._report_pending_status(pending,
                f"已{'更新' if pending.previous else '导出'} PDF：{value.target}{hint}", 8000)
        elif cancelled:
            self._report_pending_status(pending, "导出已取消，未覆盖已有文件。", 5000)
        else:
            self.window.append_log(error)
            self._report_failure(pending, "导出未完成，已有文件未覆盖。文稿或 PDF 可能已变化，请重试。")

    def _close_progress(self):
        progress, self._progress = self._progress, None
        if progress is not None and isValid(progress):
            progress.close()
            progress.deleteLater()

    def cancel_root(self, root) -> bool:
        root = normalize_path(root)
        self._automatic_results.pop(root, None)
        pending = self._pending.get(root)
        if self._publication is not None and self._publication[0].root_file == root:
            self._publication[1].cancelled.set()
        else:
            self._pending.pop(root, None)
        if not self._pending and not self._automatic_results:
            self._timer.stop()
            self._close_progress()
        if pending is not None and not self._closed:
            self._report_pending_status(pending, "已取消导出；没有覆盖已有文件。", 4000)
        return pending is not None

    def shutdown(self):
        if self._closed:
            return
        self._closed = True
        self._automatic_results.clear()
        if isValid(self._timer):
            self._timer.stop()
        for root in tuple(self._pending):
            self.cancel_root(root)
        if self._publication is not None:
            self._publication[1].cancelled.set()
            self._publication[1].release()

    def _report_status(self, message: str, duration_ms: int) -> None:
        self.window.notify_pdf_export_status(message, duration_ms)

    def _report_error(self, message: str) -> None:
        self.window.notify_pdf_export_error(message)
