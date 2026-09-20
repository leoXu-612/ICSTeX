"""Explicit Block save/close choices shared by the console and owned dialogs."""
from pathlib import Path

from PySide6.QtWidgets import QFileDialog, QMessageBox


def confirm_editor_drafts(parent, session, *, compile_after=False) -> bool:
    session.finish_editor_inputs.emit()
    if not session.editor_drafts:
        return True
    revision = session.editor_draft_revision
    action = "正式编译" if compile_after else "保存"
    button = QMessageBox.StandardButton.Apply if compile_after else QMessageBox.StandardButton.Save
    choice = QMessageBox.warning(parent, f"{action}前应用编辑草稿",
        f"将应用全部 {len(session.editor_drafts)} 份编辑草稿，再{action}当前模型。\n"
        "可以取消，回到待应用列表逐项检查；原对象有变化时不会覆盖。",
        button | QMessageBox.StandardButton.Cancel, QMessageBox.StandardButton.Cancel)
    if choice != button:
        return False
    if revision != session.editor_draft_revision:
        QMessageBox.warning(parent, "草稿已变化", "确认期间编辑草稿发生变化，请重新核对；尚未应用。")
        return False
    return True


def apply_editor_drafts(parent, session) -> bool:
    if session.apply_editor_drafts():
        return True
    QMessageBox.warning(parent, "编辑草稿未应用", session.editor_draft_error or "会话已关闭；未写入文件。")
    return False


def compile_block_session(parent, session) -> None:
    if session is None or session._closed:
        return
    if confirm_editor_drafts(parent, session, compile_after=True) and apply_editor_drafts(parent, session):
        session.request_final()


def save_block_session(parent, session, *, drafts_confirmed=False) -> bool:
    if session is None or session._closed:
        return False
    session.finish_editor_inputs.emit()
    draft_revision = session.editor_draft_revision
    if not drafts_confirmed and not confirm_editor_drafts(parent, session):
        return False
    if session.project_dir is None:
        selected, _ = QFileDialog.getSaveFileName(parent, "保存 Block 项目到新目录", str(Path.home() / "Block_Project"))
        if not selected:
            return False
        try:
            session.bind_new_project(Path(selected))
        except (OSError, ValueError) as exc:
            QMessageBox.warning(parent, "项目未保存", str(exc))
            return False
    if draft_revision != session.editor_draft_revision:
        QMessageBox.warning(parent, "草稿已变化", "选择保存位置期间草稿发生变化，请重新核对；尚未应用。")
        return False
    if not apply_editor_drafts(parent, session):
        return False
    if session.editor_drafts:
        QMessageBox.warning(parent, "还有编辑草稿", "应用期间又产生了编辑草稿；所有内容均保留，请重新核对后保存。")
        return False
    session.save_now()
    if not session.last_save_ok:
        QMessageBox.warning(parent, "Block 项目未保存", session.save_error or "项目尚未保存；草稿仍保留在当前窗口。")
        return False
    return True


def confirm_block_close(parent, session) -> bool:
    if session is None or session._closed:
        return True
    session.finish_editor_inputs.emit()
    if not session.has_unsaved_changes:
        return True
    pending = None if session._writes_paused else session.pause_writes()
    try:
        draft_revision = session.editor_draft_revision
        choice = QMessageBox.warning(parent, "Block 项目有未保存草稿",
            "关闭前是否保存当前 Block 模型？\n"
            + (f"保存将应用全部 {len(session.editor_drafts)} 份编辑草稿再写入；取消可继续检查。\n"
               if session.editor_drafts else "") +
            "放弃只丢弃此窗口尚未保存的草稿，不回退已自动保存的内容，也不覆盖外部文件。\n"
            + (session.save_error if session.save_error else "取消将保留项目和草稿，继续编辑。"),
            QMessageBox.StandardButton.Save | QMessageBox.StandardButton.Discard | QMessageBox.StandardButton.Cancel,
            QMessageBox.StandardButton.Cancel)
        if choice == QMessageBox.StandardButton.Save:
            if draft_revision != session.editor_draft_revision:
                return False
            return save_block_session(parent, session, drafts_confirmed=True)
        if choice == QMessageBox.StandardButton.Discard and draft_revision != session.editor_draft_revision:
            return False
        return choice == QMessageBox.StandardButton.Discard
    finally:
        if pending is not None:
            session.resume_writes(pending)
