"""Desmos/GeoGebra-style math keyboard for the formula composer.

A calculator-like keypad with large rounded buttons that display real math
structures (fractions, roots, scripts, operators, integrals) instead of LaTeX
source. Every button maps to a structured model action handled by the formula
editor widget; the keyboard never inserts raw LaTeX strings by itself.
"""
from __future__ import annotations

from PySide6.QtCore import QPointF, QRectF, Qt, Signal
from PySide6.QtGui import QColor, QFont, QFontMetricsF, QPainter, QPainterPath, QPen
from PySide6.QtWidgets import (
    QAbstractButton,
    QButtonGroup,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)


_BG = QColor(252, 252, 252)
_BG_NUM = QColor(244, 244, 244)
_BG_ACTIVE = QColor(210, 228, 250)
_BORDER = QColor(216, 219, 223)
_TEXT = QColor(38, 38, 38)
_PLACEHOLDER = QColor(135, 143, 153)
_FONT_MAIN = QFont("Menlo", 22)
_FONT_MAIN.setStyleHint(QFont.StyleHint.Monospace)


def _button_specs(label: str, kind: str, action: str, numeric: bool = False) -> tuple[str, str, str, bool]:
    return (label, kind, action, numeric)


class MathKeyButton(QAbstractButton):
    """A large rounded key that paints a real math preview instead of source."""

    def __init__(
        self,
        label: str,
        kind: str,
        action: str,
        numeric: bool = False,
        checkable: bool = False,
        emphasized: bool = False,
        parent=None,
    ) -> None:
        super().__init__(parent)
        self._label = label
        self._kind = kind
        self.action = action
        self._numeric = numeric
        self._emphasized = emphasized
        self.setCheckable(checkable)
        self.setMinimumSize(42, 40)
        self.setAccessibleName(label)
        self.setToolTip(label)
        self.setCursor(Qt.CursorShape.PointingHandCursor)

    def paintEvent(self, _event) -> None:  # type: ignore[no-untyped-def]
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        rect = self.rect().adjusted(2, 2, -2, -2)

        background = (
            _BG_ACTIVE
            if (self.isChecked() or self._emphasized)
            else (_BG_NUM if self._numeric else _BG)
        )
        if self.isDown():
            background = background.darker(106)
        elif self.underMouse():
            background = background.darker(102)
        painter.setPen(QPen(_BORDER, 1))
        painter.setBrush(background)
        painter.drawRoundedRect(rect, 8, 8)

        painter.setPen(QPen(_TEXT))
        self._draw_preview(painter)

    def _draw_preview(self, painter: QPainter) -> None:
        if self._kind in ("text", "big"):
            font = QFont(_FONT_MAIN)
            if self._kind == "big":
                font.setPointSizeF(27)
            metrics = QFontMetricsF(font)
            fit = min(1.0, (self.width() - 14) / max(1.0, metrics.horizontalAdvance(self._label)),
                      (self.height() - 10) / max(1.0, metrics.height()))
            font.setPointSizeF(font.pointSizeF() * fit)
            painter.setFont(font)
            painter.drawText(self.rect(), Qt.AlignmentFlag.AlignCenter, self._label)
            return

        # One logical canvas keeps every structure centered and inside a compact
        # key. Slots are outlines, not filled blocks that resemble drop shadows.
        painter.save()
        painter.translate(self.width() / 2, self.height() / 2)
        scale = min(1.0, (self.width() - 14) / 60, (self.height() - 10) / 34)
        painter.scale(scale, scale)
        painter.setPen(QPen(_TEXT, 1.5, Qt.PenStyle.SolidLine,
                            Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin))
        painter.setBrush(Qt.BrushStyle.NoBrush)
        self._draw_structure(painter)
        painter.restore()

    @staticmethod
    def _draw_slot(painter: QPainter, x: float, y: float, width: float, height: float) -> None:
        painter.save()
        painter.setPen(QPen(_PLACEHOLDER, 1.2))
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawRoundedRect(QRectF(x, y, width, height), 1.5, 1.5)
        painter.restore()

    @staticmethod
    def _draw_label(painter: QPainter, rect: QRectF, text: str, size: float) -> None:
        painter.save()
        font = QFont(_FONT_MAIN)
        # The structure canvas is in logical pixels, independent of font DPI.
        font.setPixelSize(round(size))
        painter.setFont(font)
        painter.drawText(rect, Qt.AlignmentFlag.AlignCenter, text)
        painter.restore()

    def _draw_structure(self, painter: QPainter) -> None:
        if self._kind == "frac":
            self._draw_slot(painter, -10, -14, 20, 9)
            self._draw_slot(painter, -10, 5, 20, 9)
            painter.drawLine(QPointF(-15, 0), QPointF(15, 0))
            return
        if self._kind in ("sqrt", "nroot"):
            root = QPainterPath(QPointF(-23, 1))
            root.lineTo(-18, -1)
            root.lineTo(-12, 12)
            root.lineTo(-5, -12)
            root.lineTo(24, -12)
            painter.drawPath(root)
            self._draw_slot(painter, 1, -5, 17, 13)
            if self._kind == "nroot":
                self._draw_label(painter, QRectF(-26, -16, 12, 13), "n", 11)
            return
        if self._kind in ("script", "sub"):
            base = {"structure:exp": "e", "structure:exp10": "10"}.get(self.action, "x")
            base_width = 27 if base == "10" else 18
            self._draw_label(painter, QRectF(-base_width, -11, base_width, 28), base, 22)
            self._draw_slot(painter, 3, -13 if self._kind == "script" else 6, 9, 9)
            return
        if self._kind == "abs":
            painter.drawLine(QPointF(-13, -12), QPointF(-13, 12))
            painter.drawLine(QPointF(13, -12), QPointF(13, 12))
            self._draw_slot(painter, -7, -7, 14, 14)
            return
        if self._kind == "doverdx":
            self._draw_label(painter, QRectF(-14, -17, 28, 15), "d", 13)
            self._draw_label(painter, QRectF(-14, 2, 28, 15), "dx", 13)
            painter.drawLine(QPointF(-14, 0), QPointF(14, 0))
            return
        if self._kind == "matrix":
            brackets = QPainterPath(QPointF(-14, -14))
            for point in ((-19, -14), (-19, 14), (-14, 14)):
                brackets.lineTo(*point)
            brackets.moveTo(14, -14)
            for point in ((19, -14), (19, 14), (14, 14)):
                brackets.lineTo(*point)
            painter.drawPath(brackets)
            for row in range(2):
                for column in range(2):
                    self._draw_slot(painter, -11 + column * 14, -11 + row * 14, 8, 8)
            return
        if self._kind == "cases":
            brace = QPainterPath(QPointF(-11, -14))
            brace.cubicTo(-20, -14, -14, -3, -22, 0)
            brace.cubicTo(-14, 3, -20, 14, -11, 14)
            painter.drawPath(brace)
            self._draw_slot(painter, -5, -12, 24, 9)
            self._draw_slot(painter, -5, 3, 24, 9)
            return
        if self._kind == "log10":
            self._draw_label(painter, QRectF(-26, -14, 38, 28), "log", 20)
            if self.action == "structure:logab":
                self._draw_slot(painter, 14, 5, 9, 9)
            else:
                self._draw_label(painter, QRectF(11, 3, 18, 16), "10", 11)
            return
        if self._kind == "invsin":
            self._draw_label(painter, QRectF(-27, -9, 38, 28), self._label.replace("⁻¹", ""), 20)
            self._draw_label(painter, QRectF(10, -16, 20, 14), "−1", 11)
            return

        self._draw_label(painter, QRectF(-30, -17, 60, 34), self._label, 20)


CATEGORY_LABELS = {
    "base": "基础",
    "functions": "函数",
    "greek": "希腊字母",
    "calculus": "微积分",
    "matrix": "矩阵",
}

BASE_BUTTONS = [
    ("x", "text", "text:x"),
    ("y", "text", "text:y"),
    ("上标", "script", "structure:superscript"),
    ("下标", "sub", "structure:subscript"),
    ("(", "text", "text:("),
    (")", "text", "text:)"),
    ("<", "text", "text:<"),
    (">", "text", "text:>"),
    ("|a|", "abs", "text:|"),
    (",", "text", "text:,"),
    ("≤", "text", "command:leq"),
    ("≥", "text", "command:geq"),
    ("ABC", "text", "toggle:abc"),
    ("□/□", "frac", "structure:fraction"),
    ("√□", "sqrt", "structure:sqrt"),
    ("π", "text", "command:pi"),
]

FUNCTIONS_BUTTONS = [
    ("sin", "text", "command:sin"),
    ("cos", "text", "command:cos"),
    ("tan", "text", "command:tan"),
    ("%", "text", "command:%"),
    ("sin⁻¹", "invsin", "structure:inverse_sin"),
    ("cos⁻¹", "invsin", "structure:inverse_cos"),
    ("tan⁻¹", "invsin", "structure:inverse_tan"),
    ("!", "text", "text:!"),
    ("ln", "text", "command:ln"),
    ("log₁₀", "log10", "structure:log10"),
    ("logₐb", "log10", "structure:logab"),
    ("eˣ", "script", "structure:exp"),
    ("10ˣ", "script", "structure:exp10"),
    ("ⁿ√x", "nroot", "structure:nth_root"),
    ("矩阵", "matrix", "structure:matrix"),
    ("分段", "cases", "structure:cases"),
]

GREEK_BUTTONS = [
    ("α", "text", "command:alpha"),
    ("β", "text", "command:beta"),
    ("γ", "text", "command:gamma"),
    ("δ", "text", "command:delta"),
    ("ε", "text", "command:epsilon"),
    ("ζ", "text", "command:zeta"),
    ("η", "text", "command:eta"),
    ("θ", "text", "command:theta"),
    ("λ", "text", "command:lambda"),
    ("μ", "text", "command:mu"),
    ("π", "text", "command:pi"),
    ("ρ", "text", "command:rho"),
    ("σ", "text", "command:sigma"),
    ("φ", "text", "command:phi"),
    ("ω", "text", "command:omega"),
    ("Δ", "text", "command:Delta"),
    ("Σ", "text", "command:Sigma"),
    ("Ω", "text", "command:Omega"),
]

CALCULUS_BUTTONS = [
    ("∫", "big", "structure:integral"),
    ("∑", "big", "structure:sum"),
    ("∏", "big", "structure:prod"),
    ("lim", "text", "structure:lim"),
    ("d/dx", "doverdx", "structure:derivative"),
    ("上标", "script", "structure:superscript"),
    ("下标", "sub", "structure:subscript"),
    ("√□", "sqrt", "structure:sqrt"),
    ("ⁿ√x", "nroot", "structure:nth_root"),
    ("矩阵", "matrix", "structure:matrix"),
    ("分段", "cases", "structure:cases"),
    ("i", "text", "text:i"),
    ("(", "text", "text:("),
    (")", "text", "text:)"),
    ("π", "text", "command:pi"),
    ("%", "text", "command:%"),
]

MATRIX_BUTTONS = [
    ("矩阵", "matrix", "structure:matrix"),
    ("分段", "cases", "structure:cases"),
    ("□/□", "frac", "structure:fraction"),
    ("√□", "sqrt", "structure:sqrt"),
    ("上标", "script", "structure:superscript"),
    ("下标", "sub", "structure:subscript"),
    ("∑", "big", "structure:sum"),
    ("∫", "big", "structure:integral"),
]

NUMBER_BUTTONS = [
    ("7", "text", "text:7", True),
    ("8", "text", "text:8", True),
    ("9", "text", "text:9", True),
    ("÷", "text", "command:div", False),
    ("4", "text", "text:4", True),
    ("5", "text", "text:5", True),
    ("6", "text", "text:6", True),
    ("×", "text", "command:times", False),
    ("1", "text", "text:1", True),
    ("2", "text", "text:2", True),
    ("3", "text", "text:3", True),
    ("−", "text", "text:-", False),
    ("0", "text", "text:0", True),
    (".", "text", "text:.", True),
    ("=", "text", "text:=", False),
    ("+", "text", "text:+", False),
]

CONTROL_BUTTONS = [
    ("←", "text", "cursor:left"),
    ("→", "text", "cursor:right"),
    ("删除", "text", "delete"),
    ("Tab", "text", "cursor:tab"),
]


class MathKeyboard(QWidget):
    """Category tabs, structure/symbol grids, number pad, and cursor controls."""

    actionRequested = Signal(str)

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._letters_visible = False
        self._root_layout = QVBoxLayout(self)
        self._root_layout.setContentsMargins(4, 4, 4, 4)
        self._root_layout.setSpacing(6)

        self.category_group = QButtonGroup(self)
        self.category_group.setExclusive(True)
        self.category_bar = QHBoxLayout()
        for key, label in CATEGORY_LABELS.items():
            button = QPushButton(label)
            button.setCheckable(True)
            button.setMinimumHeight(34)
            button.setStyleSheet(
                "QPushButton { padding: 2px 8px; min-height: 26px; border-radius: 8px; border: 1px solid #d0d0d0; background: #f7f7f7; }"
                "QPushButton:checked { background: #d2e4fa; border-color: #9cc3e5; }"
            )
            self.category_group.addButton(button)
            button.clicked.connect(lambda _checked=False, k=key: self._switch_category(k))
            self.category_bar.addWidget(button)
            if key == "base":
                button.setChecked(True)
        self._root_layout.addLayout(self.category_bar)

        self.stack = QStackedWidget()
        self._base_page = self._build_base_page()
        self.stack.addWidget(self._base_page)
        self.stack.addWidget(self._build_grid_page(FUNCTIONS_BUTTONS, 4))
        self.stack.addWidget(self._build_grid_page(GREEK_BUTTONS, 4))
        self.stack.addWidget(self._build_grid_page(CALCULUS_BUTTONS, 4))
        self.stack.addWidget(self._build_grid_page(MATRIX_BUTTONS, 4))
        self.stack.addWidget(self.letters_row)

        self.number_pad = self._build_number_pad()
        self.controls = self._build_controls()
        self._content_layout = QGridLayout()
        self._root_layout.addLayout(self._content_layout)
        self._wide_layout = None
        self._apply_layout(wide=True)

    # ------------------------------------------------------------------

    def _build_base_page(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(6)
        grid = self._grid_from(BASE_BUTTONS, 4)
        layout.addLayout(grid)
        self.letters_row = QWidget()
        letters_layout = QGridLayout(self.letters_row)
        letters_layout.setContentsMargins(0, 0, 0, 0)
        letters_layout.setSpacing(4)
        back_button = QPushButton("返回基础符号")
        back_button.setAutoDefault(False)
        back_button.clicked.connect(lambda: self._emit("toggle:abc"))
        letters_layout.addWidget(back_button, 0, 0, 1, 6)
        for index, letter in enumerate("abcdefghijklmnopqrstuvwxyz"):
            button = MathKeyButton(letter, "text", f"text:{letter}", numeric=False)
            button.setMinimumHeight(30)
            button.clicked.connect(lambda _checked=False, b=button: self._emit(b.action))
            letters_layout.addWidget(button, index // 6 + 1, index % 6)
        return page

    def _build_grid_page(self, specs, columns: int) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addLayout(self._grid_from(specs, columns))
        return page

    @staticmethod
    def _grid_from(specs, columns: int) -> QGridLayout:
        grid = QGridLayout()
        grid.setContentsMargins(0, 0, 0, 0)
        grid.setSpacing(6)
        for index, spec in enumerate(specs):
            label, kind, action = spec[0], spec[1], spec[2]
            numeric = spec[3] if len(spec) > 3 else False
            button = MathKeyButton(label, kind, action, numeric=numeric)
            button.clicked.connect(lambda _checked=False, b=button: _dispatch(b))
            grid.addWidget(button, index // columns, index % columns)
        return grid

    def _build_number_pad(self) -> QWidget:
        pad = QWidget()
        layout = QVBoxLayout(pad)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)
        layout.addWidget(QLabel("数字"))
        layout.addLayout(self._grid_from(NUMBER_BUTTONS, 4))
        return pad

    def _build_controls(self) -> QWidget:
        panel = QWidget()
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)
        layout.addWidget(QLabel("功能"))
        for label, kind, action in CONTROL_BUTTONS:
            button = MathKeyButton(label, kind, action, emphasized=(action == "apply"))
            button.clicked.connect(lambda _checked=False, b=button: self._emit(b.action))
            layout.addWidget(button)
        layout.addStretch()
        return panel

    def _switch_category(self, key: str) -> None:
        self._letters_visible = False
        index = list(CATEGORY_LABELS).index(key)
        self.stack.setCurrentIndex(index)
        self.category_group.buttons()[index].setChecked(True)

    def _apply_layout(self, *, wide: bool | None = None) -> None:
        wide = self.width() >= 740 if wide is None else wide
        if self._wide_layout == wide:
            return
        self._wide_layout = wide
        for widget in (self.stack, self.number_pad, self.controls):
            self._content_layout.removeWidget(widget)
        self._content_layout.addWidget(self.stack, 0, 0, 1, 1 if wide else 2)
        if wide:
            self._content_layout.addWidget(self.number_pad, 0, 1)
            self._content_layout.addWidget(self.controls, 0, 2)
        else:
            self._content_layout.addWidget(self.number_pad, 1, 0)
            self._content_layout.addWidget(self.controls, 1, 1)
        self._content_layout.setColumnStretch(0, 4)
        self._content_layout.setColumnStretch(1, 3 if wide else 1)
        self._content_layout.setColumnStretch(2, 1 if wide else 0)

    def resizeEvent(self, event) -> None:  # type: ignore[no-untyped-def]
        super().resizeEvent(event)
        self._apply_layout()

    def _emit(self, action: str) -> None:
        if action.startswith("category:"):
            self._switch_category(action[9:])
            return
        if action.startswith("toggle:"):
            self._letters_visible = not self._letters_visible
            self.stack.setCurrentWidget(self.letters_row if self._letters_visible else self._base_page)
            return
        self.actionRequested.emit(action)


def _dispatch(button: MathKeyButton) -> None:
    parent = button.parentWidget()
    while parent is not None and not isinstance(parent, MathKeyboard):
        parent = parent.parentWidget()
    if isinstance(parent, MathKeyboard):
        parent._emit(button.action)
