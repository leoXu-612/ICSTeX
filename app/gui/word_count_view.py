from __future__ import annotations

from html import escape

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QProgressBar,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QTextBrowser,
    QVBoxLayout,
    QWidget,
)

from app.core.word_count import WordCountResult, WordCountSegment


STATS: tuple[tuple[str, str], ...] = (
    ("effective", "有效正文"),
    ("total", "总字数"),
    ("headers", "标题"),
    ("captions", "说明/脚注"),
    ("formulas", "公式"),
    ("numbers", "数字"),
)

BREAKDOWN: tuple[tuple[str, str], ...] = (
    ("effective", "有效正文"),
    ("headers", "标题"),
    ("captions", "说明/脚注"),
    ("math_inline", "行内公式"),
    ("math_display", "行间公式"),
    ("numbers", "数字"),
)

CATEGORY_STYLES: dict[str, tuple[str, str, str]] = {
    "effective": ("有效正文", "#d9ecff", "#174c79"),
    "headers": ("标题", "#eadfff", "#4d3b7a"),
    "captions": ("说明/脚注", "#d9f0e7", "#235c48"),
    "math_inline": ("行内公式", "#ffe8cc", "#7a4817"),
    "math_display": ("行间公式", "#ffe0e6", "#7a2d3c"),
    "numbers": ("数字", "#dceff4", "#315c68"),
}
MAX_PREVIEW_CHARS = 12000


class WordCountView(QWidget):
    refreshRequested = Signal()

    def __init__(self) -> None:
        super().__init__()
        self.setObjectName("wordPanel")
        self.labels: dict[str, QLabel] = {}
        self.category_bars: dict[str, QProgressBar] = {}
        self.category_values: dict[str, QLabel] = {}
        self.last_mode_label: str | None = None
        self.meta_label = QLabel("未选择文档")
        self.meta_label.setObjectName("wordCountMeta")
        self.meta_label.setWordWrap(True)
        self.refresh_button = QPushButton("刷新")
        self.refresh_button.clicked.connect(self.refreshRequested.emit)
        self.preview_browser = QTextBrowser()
        self.preview_browser.setObjectName("wordHighlightPreview")
        self.preview_browser.setOpenExternalLinks(False)
        self.preview_browser.setMinimumHeight(170)
        self._build()

    def _build(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(18, 14, 18, 14)
        layout.setSpacing(10)

        header = QHBoxLayout()
        header.setContentsMargins(0, 0, 0, 0)
        title = QLabel("字数统计")
        title.setObjectName("panelTitle")
        header.addWidget(title)
        header.addStretch()
        header.addWidget(self.refresh_button)

        grid = QGridLayout()
        grid.setContentsMargins(0, 0, 0, 0)
        grid.setHorizontalSpacing(10)
        grid.setVerticalSpacing(8)
        for column in range(3):
            grid.setColumnStretch(column, 1)
        for row in range(2):
            grid.setRowMinimumHeight(row, 68)
        for index, (key, label_text) in enumerate(STATS):
            grid.addWidget(self._make_stat(key, label_text), index // 3, index % 3)

        layout.addLayout(header)
        layout.addLayout(grid)
        layout.addWidget(self._make_breakdown())
        layout.addWidget(self._make_highlight_preview())
        layout.addWidget(self.meta_label)
        layout.addStretch()

    def _make_stat(self, key: str, label: str) -> QWidget:
        container = QWidget()
        container.setObjectName("wordStat")
        container.setMinimumHeight(68)
        container.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        layout = QVBoxLayout(container)
        layout.setContentsMargins(10, 8, 10, 8)
        layout.setSpacing(3)

        title = QLabel(label)
        title.setObjectName("wordStatLabel")
        title.setMinimumHeight(16)
        value = QLabel("-")
        value.setObjectName("wordStatValue")
        value.setMinimumWidth(72)
        value.setMinimumHeight(28)
        value.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        value.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.labels[key] = value

        layout.addWidget(title)
        layout.addWidget(value)
        return container

    def _make_breakdown(self) -> QWidget:
        container = QWidget()
        container.setObjectName("wordBreakdown")
        layout = QVBoxLayout(container)
        layout.setContentsMargins(0, 8, 0, 4)
        layout.setSpacing(7)

        title = QLabel("分类分布")
        title.setObjectName("wordBreakdownTitle")
        hint = QLabel("条形长度按当前结果中的最大值相对缩放；右侧精确值为准。")
        hint.setObjectName("wordBreakdownHint")
        hint.setWordWrap(True)
        layout.addWidget(title)
        layout.addWidget(hint)

        rows = QGridLayout()
        rows.setContentsMargins(0, 2, 0, 0)
        rows.setHorizontalSpacing(10)
        rows.setVerticalSpacing(6)
        rows.setColumnStretch(1, 1)
        for row, (key, label_text) in enumerate(BREAKDOWN):
            label = QLabel(label_text)
            label.setObjectName("wordCategoryLabel")

            bar = QProgressBar()
            bar.setObjectName("wordCategoryBar")
            bar.setProperty("category", key)
            bar.setRange(0, 1)
            bar.setValue(0)
            bar.setTextVisible(False)
            bar.setFixedHeight(8)

            value = QLabel("-")
            value.setObjectName("wordCategoryValue")
            value.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
            value.setMinimumWidth(54)

            self.category_bars[key] = bar
            self.category_values[key] = value
            rows.addWidget(label, row, 0)
            rows.addWidget(bar, row, 1)
            rows.addWidget(value, row, 2)
        layout.addLayout(rows)
        return container

    def _make_highlight_preview(self) -> QWidget:
        container = QWidget()
        container.setObjectName("wordHighlightPanel")
        layout = QVBoxLayout(container)
        layout.setContentsMargins(0, 8, 0, 4)
        layout.setSpacing(7)

        title = QLabel("文本分层预览")
        title.setObjectName("wordBreakdownTitle")
        hint = QLabel("颜色用于解释当前项目中哪些可见文本被计入正文、标题、说明/脚注、公式或数字；上方数值为准。")
        hint.setObjectName("wordBreakdownHint")
        hint.setWordWrap(True)
        legend = QLabel(self._legend_html())
        legend.setObjectName("wordHighlightLegend")
        legend.setTextFormat(Qt.TextFormat.RichText)
        legend.setWordWrap(True)
        layout.addWidget(title)
        layout.addWidget(hint)
        layout.addWidget(legend)
        layout.addWidget(self.preview_browser)
        return container

    def set_result(self, result: WordCountResult, document_name: str, is_modified: bool) -> None:
        values = {
            "effective": result.effective_words,
            "total": result.total_words,
            "headers": result.header_words,
            "captions": result.caption_words,
            "formulas": result.formulas,
            "numbers": result.numbers,
        }
        for key, value in values.items():
            self.labels[key].setText(f"{value:,}")
        breakdown = {
            "effective": result.effective_words,
            "headers": result.header_words,
            "captions": result.caption_words,
            "math_inline": result.math_inline,
            "math_display": result.math_display,
            "numbers": result.numbers,
        }
        maximum = max(1, *breakdown.values())
        for key, value in breakdown.items():
            self.category_bars[key].setRange(0, maximum)
            self.category_bars[key].setValue(value)
            self.category_values[key].setText(f"{value:,}")
        state = "当前编辑器内容" if is_modified else "已保存内容"
        note = "有效正文不包含标题、图表说明、脚注、公式和数字；具体提交口径仍以课程要求为准。"
        mode = self._mode_label(result)
        self.last_mode_label = mode
        warnings = " ".join(result.warnings)
        warning_text = f" {warnings}" if warnings else ""
        self.meta_label.setText(f"统计模式：{mode} | {state} | {document_name}。{note}{warning_text}")
        self.preview_browser.setHtml(self._preview_html(result.visual_segments))

    def reset(self, message: str) -> None:
        for label in self.labels.values():
            label.setText("-")
        for key, bar in self.category_bars.items():
            bar.setRange(0, 1)
            bar.setValue(0)
            self.category_values[key].setText("-")
        self.last_mode_label = None
        self.meta_label.setText(message)
        self.preview_browser.setHtml(self._empty_preview_html(message))

    @staticmethod
    def _mode_label(result: WordCountResult) -> str:
        if result.source.startswith("texcount"):
            return "TeXcount 兼容统计"
        if result.source == "fallback":
            return "ICSTeX 结构化统计"
        return result.source

    @staticmethod
    def _legend_html() -> str:
        chips: list[str] = []
        for key, (label, background, foreground) in CATEGORY_STYLES.items():
            chips.append(
                (
                    f'<span style="background:{background}; color:{foreground}; '
                    'border-radius:4px; padding:2px 6px; margin-right:5px; '
                    f'font-weight:600;">{escape(label)}</span>'
                )
            )
        return " ".join(chips)

    @staticmethod
    def _preview_html(segments: tuple[WordCountSegment, ...]) -> str:
        if not segments:
            return WordCountView._empty_preview_html("没有可显示的正文片段。")
        pieces: list[str] = []
        used = 0
        truncated = False
        last_source: str | None = None
        for segment in segments:
            if used >= MAX_PREVIEW_CHARS:
                truncated = True
                break
            if segment.source and segment.source != last_source:
                pieces.append(WordCountView._source_divider_html(segment.source))
                last_source = segment.source
            text = segment.text[: MAX_PREVIEW_CHARS - used]
            if len(text) < len(segment.text):
                truncated = True
            pieces.append(WordCountView._segment_html(text, segment.category))
            used += len(text)
        if truncated:
            pieces.append('\n<span style="color:#8d918d;">……预览已截断，完整统计仍然有效。</span>')
        body = "".join(pieces)
        return (
            '<html><body style="margin:0;">'
            '<pre style="white-space:pre-wrap; font-family:Menlo, Consolas, monospace; '
            'font-size:12px; line-height:1.55; margin:0;">'
            f"{body}</pre></body></html>"
        )

    @staticmethod
    def _source_divider_html(source: str) -> str:
        return (
            '\n<span style="padding:4px 7px; '
            'background:#f1f2f0; color:#545955; border-left:3px solid #a63d33; '
            'font-family:sans-serif; '
            f'font-size:11px; font-weight:600;">{escape(source)}</span>\n'
        )

    @staticmethod
    def _segment_html(text: str, category: str) -> str:
        label, background, foreground = CATEGORY_STYLES.get(category, ("其他", "#f0f0ee", "#666b67"))
        escaped = escape(text)
        if not escaped:
            return ""
        return (
            f'<span title="{escape(label)}" '
            f'style="background:{background}; color:{foreground}; '
            'border-radius:3px; padding:1px 1px;">'
            f"{escaped}</span>"
        )

    @staticmethod
    def _empty_preview_html(message: str) -> str:
        return (
            '<html><body style="margin:0; color:#8d918d; font-size:12px;">'
            f"{escape(message)}</body></html>"
        )


def wrap_in_scroll(view: WordCountView) -> QScrollArea:
    scroll = QScrollArea()
    scroll.setObjectName("wordScroll")
    scroll.setWidgetResizable(True)
    scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
    scroll.setWidget(view)
    return scroll
