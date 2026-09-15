"""Block display labels and explicit identity copying; never model authority."""
from PySide6.QtCore import Qt
from PySide6.QtGui import QAction, QKeySequence
from PySide6.QtWidgets import QApplication


BLOCK_LABELS = {"text": "正文", "formula": "公式", "image": "图片", "table": "表格",
                "list": "列表", "heading": "标题", "quote": "引文", "rawLatex": "LaTeX 源码"}
LAYOUT_LABELS = {"row": "横排", "grid": "网格", "column": "纵排", "stack": "纵排"}
ALIGNMENT_LABELS = {"top": "顶部", "middle": "居中", "bottom": "底部"}
FALLBACK_LABELS = {"stackVertically": "改为纵排", "error": "报错并停止", "wrapRows": "自动换行",
                   "normalizeWeights": "归一化宽度", "reduceGap": "缩小间距"}


def block_label(block):
    return f"{block.alias or '未命名'} · {BLOCK_LABELS.get(block.type, '未知类型')}"


def add_identity_copy(view, describe):
    """Expose complete IDs in a context action and the standard Copy shortcut."""
    action = QAction("复制技术身份", view)
    action.setShortcut(QKeySequence.StandardKey.Copy)
    action.setShortcutContext(Qt.ShortcutContext.WidgetShortcut)
    action.triggered.connect(lambda: QApplication.clipboard().setText(
        "\n".join(text for item in view.selectedItems() if (text := describe(item)))))
    view.addAction(action)
    view.setContextMenuPolicy(Qt.ContextMenuPolicy.ActionsContextMenu)
    return action
