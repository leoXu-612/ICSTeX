"""Desmos/GeoGebra-style math keyboard for the formula composer.

A calculator-like keypad with large rounded buttons that display real math
structures (fractions, roots, scripts, operators, integrals) instead of LaTeX
source. Every button maps to a structured model action handled by the formula
editor widget; the keyboard never inserts raw LaTeX strings by itself.
"""
from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QColor, QFont, QFontMetricsF, QPainter, QPen
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
_BORDER = QColor(208, 208, 208)
_TEXT = QColor(38, 38, 38)
_PLACEHOLDER = QColor(205, 205, 205)
_FONT_MAIN = QFont("Menlo", 22)
_FONT_MAIN.setStyleHint(QFont.StyleHint.Monospace)
_FONT_SMALL = QFont(_FONT_MAIN)
_FONT_SMALL.setPointSizeF(14)


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
        self.setMinimumHeight(58)
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
        painter.drawRoundedRect(rect, 12, 12)

        painter.setPen(QPen(_TEXT))
        self._draw_preview(painter)

    def _draw_preview(self, painter: QPainter) -> None:
        center_x = self.width() / 2
        center_y = self.height() / 2
        if self._kind == "text":
            painter.setFont(_FONT_MAIN)
            painter.drawText(self.rect(), Qt.AlignmentFlag.AlignCenter, self._label)
            return
        if self._kind == "big":
            font = QFont(_FONT_MAIN)
            font.setPointSizeF(30)
            painter.setFont(font)
            painter.drawText(self.rect(), Qt.AlignmentFlag.AlignCenter, self._label)
            return

        if self._kind == "frac":
            w, h = self.width(), self.height()
            box_w = min(30.0, w * 0.26)
            gap = 9.0
            top = center_y - gap - 12
            bottom = center_y + gap
            painter.setBrush(_PLACEHOLDER)
            painter.setPen(QPen(_PLACEHOLDER, 1))
            painter.drawRoundedRect(int(center_x - box_w / 2), int(top), int(box_w), 13, 3, 3)
            painter.drawRoundedRect(int(center_x - box_w / 2), int(bottom), int(box_w), 13, 3, 3)
            painter.setPen(QPen(_TEXT, 2))
            painter.drawLine(int(center_x - box_w / 2 - 4), int(center_y), int(center_x + box_w / 2 + 4), int(center_y))
            return
        if self._kind == "sqrt":
            painter.setFont(_FONT_MAIN)
            painter.drawText(int(center_x - 30), int(center_y + 8), "√")
            painter.setPen(QPen(_TEXT, 2))
            painter.drawLine(int(center_x - 22), int(center_y - 13), int(center_x + 20), int(center_y - 13))
            painter.setBrush(_PLACEHOLDER)
            painter.setPen(QPen(_PLACEHOLDER, 1))
            painter.drawRoundedRect(int(center_x + 20), int(center_y - 7), 14, 14, 3, 3)
            return
        if self._kind in ("script", "sub"):
            main = "x"
            small = "2" if self._kind == "script" else "□"
            painter.setFont(_FONT_MAIN)
            painter.drawText(int(center_x - 18), int(center_y + 8), main)
            painter.setFont(_FONT_SMALL)
            painter.drawText(
                int(center_x + 2),
                int(center_y - 10 if self._kind == "script" else center_y + 14),
                small,
            )
            return
        if self._kind == "abs":
            painter.setFont(_FONT_MAIN)
            painter.drawText(int(center_x - 20), int(center_y + 8), "|")
            painter.drawText(int(center_x + 12), int(center_y + 8), "|")
            painter.setBrush(_PLACEHOLDER)
            painter.setPen(QPen(_PLACEHOLDER, 1))
            painter.drawRoundedRect(int(center_x - 12), int(center_y - 8), 16, 16, 3, 3)
            return
        if self._kind == "doverdx":
            painter.setFont(_FONT_SMALL)
            painter.drawText(int(center_x - 8), int(center_y - 10), "d")
            painter.drawText(int(center_x - 12), int(center_y + 16), "dx")
            painter.setPen(QPen(_TEXT, 2))
            painter.drawLine(int(center_x - 16), int(center_y), int(center_x + 16), int(center_y))
            return
        if self._kind == "nroot":
            painter.setFont(_FONT_SMALL)
            painter.drawText(int(center_x - 28), int(center_y - 6), "n")
            painter.setFont(_FONT_MAIN)
            painter.drawText(int(center_x - 18), int(center_y + 8), "√")
            painter.setPen(QPen(_TEXT, 2))
            painter.drawLine(int(center_x - 10), int(center_y - 13), int(center_x + 22), int(center_y - 13))
            painter.setBrush(_PLACEHOLDER)
            painter.setPen(QPen(_PLACEHOLDER, 1))
            painter.drawRoundedRect(int(center_x + 22), int(center_y - 7), 14, 14, 3, 3)
            return
        if self._kind == "matrix":
            painter.setBrush(_PLACEHOLDER)
            painter.setPen(QPen(_PLACEHOLDER, 1))
            size = 10
            for row in range(2):
                for column in range(2):
                    painter.drawRoundedRect(
                        int(center_x - 15 + column * (size + 5)),
                        int(center_y - 12 + row * (size + 5)),
                        size,
                        size,
                        2,
                        2,
                    )
            return
        if self._kind == "cases":
            painter.setFont(_FONT_MAIN)
            painter.drawText(int(center_x - 24), int(center_y + 9), "{")
            painter.setBrush(_PLACEHOLDER)
            painter.setPen(QPen(_PLACEHOLDER, 1))
            painter.drawRoundedRect(int(center_x - 8), int(center_y - 13), 24, 9, 2, 2)
            painter.drawRoundedRect(int(center_x - 8), int(center_y + 4), 24, 9, 2, 2)
            return
        if self._kind == "log10":
            painter.setFont(_FONT_MAIN)
            painter.drawText(int(center_x - 30), int(center_y + 8), "log")
            painter.setFont(_FONT_SMALL)
            painter.drawText(int(center_x + 12), int(center_y + 16), "10")
            return
        if self._kind == "invsin":
            painter.setFont(_FONT_MAIN)
            painter.drawText(int(center_x - 34), int(center_y + 8), self._label.replace("⁻¹", ""))
            painter.setFont(_FONT_SMALL)
            painter.drawText(int(center_x + 6), int(center_y - 8), "⁻¹")
            return

        painter.setFont(_FONT_MAIN)
        painter.drawText(self.rect(), Qt.AlignmentFlag.AlignCenter, self._label)


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
    ("x²", "script", "structure:superscript"),
    ("aᵇ", "script", "structure:superscript"),
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
    ("功能", "text", "category:functions"),
    ("←", "text", "cursor:left"),
    ("→", "text", "cursor:right"),
    ("删除", "text", "delete"),
    ("确认", "text", "apply"),
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
                "QPushButton { border-radius: 10px; border: 1px solid #d0d0d0; background: #f7f7f7; }"
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

        self.number_pad = self._build_number_pad()
        self.controls = self._build_controls()

        self._apply_layout()

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
        for index, letter in enumerate("abcdefghijklmnopqrstuvwxyz"):
            button = MathKeyButton(letter, "text", f"text:{letter}", numeric=False)
            button.setMinimumHeight(40)
            button.clicked.connect(lambda _checked=False, b=button: self._emit(b.action))
            letters_layout.addWidget(button, index // 13, index % 13)
        self.letters_row.hide()
        layout.addWidget(self.letters_row)
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
        grid.setSpacing(8)
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
        index = list(CATEGORY_LABELS).index(key)
        self.stack.setCurrentIndex(index)

    def _apply_layout(self) -> None:
        while self._root_layout.count():
            item = self._root_layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.setParent(None)
        self._root_layout.addLayout(self.category_bar)

        if self.width() >= 860:
            wide = QHBoxLayout()
            wide.addWidget(self.stack, stretch=3)
            wide.addWidget(self.number_pad, stretch=2)
            wide.addWidget(self.controls, stretch=1)
            self._root_layout.addLayout(wide)
        else:
            self._root_layout.addWidget(self.stack)
            row = QHBoxLayout()
            row.addWidget(self.number_pad, stretch=3)
            row.addWidget(self.controls, stretch=1)
            self._root_layout.addLayout(row)

    def resizeEvent(self, event) -> None:  # type: ignore[no-untyped-def]
        super().resizeEvent(event)
        self._apply_layout()

    def _emit(self, action: str) -> None:
        if action.startswith("toggle:"):
            self._letters_visible = not self._letters_visible
            self.letters_row.setVisible(self._letters_visible)
            return
        self.actionRequested.emit(action)


def _dispatch(button: MathKeyButton) -> None:
    parent = button.parentWidget()
    while parent is not None and not isinstance(parent, MathKeyboard):
        parent = parent.parentWidget()
    if isinstance(parent, MathKeyboard):
        parent._emit(button.action)
