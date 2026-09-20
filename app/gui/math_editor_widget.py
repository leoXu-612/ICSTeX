"""Structured visual math editor widget (WYSIWYG draft surface).

Renders a math expression tree with QPainter and supports structured cursor
movement, direct typing, structure insertion, mouse positioning, selection,
undo/redo, and lossless LaTeX export. LaTeX text remains the only source of
truth: the widget is an editable projection of ``app.core.formula_tree`` and
never writes to an editor or file by itself.
"""
from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass, field
from functools import wraps
import re

from PySide6.QtCore import QEvent, QPointF, QRectF, Qt, Signal
from PySide6.QtGui import (
    QColor, QFont, QFontMetricsF, QInputMethodEvent, QKeyEvent, QKeySequence,
    QPainter, QPen, QTextCharFormat, QTextLayout,
)
from PySide6.QtWidgets import QApplication, QWidget

from app.core.formula_tree import (
    BigOp,
    Command,
    Frac,
    Group,
    MathNode,
    MathSequence,
    Script,
    Sqrt,
    Text,
    latex_of,
    parse_math_latex,
    symbol_display,
)
from app.core.formula_input import recognize_formula
from app.gui.theme import COLOR_ACCENT, COLOR_SELECTED


_CARET = QColor(COLOR_ACCENT)
_SELECTION = QColor(COLOR_SELECTED)
_SLOT_HINT = QColor(160, 160, 160, 90)
_TEXT = QColor(30, 30, 30)
_BACKGROUND = QColor(255, 255, 255)
_TRAILING_TOKEN = re.compile(r"[A-Za-z0-9]+$")
_CONTROL_LATEX = {
    "%": (r"\%", "%"),
    "#": (r"\#", "#"),
    "&": (r"\&", "&"),
    "_": (r"\_", "_"),
    "$": (r"\$", "$"),
    "{": (r"\{", "{"),
    "}": (r"\}", "}"),
    "|": (r"\|", "|"),
}


@dataclass
class Box:
    """Measured layout box with absolute position filled during placement."""

    kind: str
    w: float
    h: float
    baseline: float
    node: MathNode | None = None
    text: str = ""
    boundaries: list[float] = field(default_factory=list)
    children: list[tuple["Box", float, float]] = field(default_factory=list)
    x: float = 0
    y: float = 0


@dataclass
class Boundary:
    """A cursor boundary inside a math slot."""

    item_index: int
    kind: str  # "text" | "command" | "node"
    node: MathNode | None
    offset: int


_ROLE_SLOTS = {
    "base": lambda node: node.base,
    "frac_num": lambda node: node.numerator,
    "frac_den": lambda node: node.denominator,
    "sqrt": lambda node: node.radicand,
    "super": lambda node: node.super,
    "sub": lambda node: node.sub,
    "lower": lambda node: node.lower,
    "upper": lambda node: node.upper,
    "body": lambda node: node.body,
    "group": lambda node: node.items,
}


def _slot_of(node: MathNode, role: str) -> MathSequence | None:
    getter = _ROLE_SLOTS.get(role)
    if getter is None:
        return None
    return getter(node)


def _boundaries(slot: MathSequence) -> list[Boundary]:
    out: list[Boundary] = []
    for item_index, item in enumerate(slot.items):
        if isinstance(item, Text):
            for offset in range(len(item.text) + 1):
                out.append(Boundary(item_index, "text", item, offset))
        elif isinstance(item, Command):
            out.append(Boundary(item_index, "command", item, 0))
            out.append(Boundary(item_index, "command", item, 1))
        else:
            out.append(Boundary(item_index, "node", item, 0))
            out.append(Boundary(item_index, "node", item, 1))
    return out


def _edit_operation(method):
    """Publish one state update for nested keyboard/template operations."""
    @wraps(method)
    def wrapped(self, *args, **kwargs):
        outer = self._edit_depth == 0
        if (outer and method.__name__ not in ("inputMethodEvent", "set_latex")
                and not self.finish_composition()):
            return
        if outer:
            before = self.latex()
        self._edit_depth += 1
        try:
            return method(self, *args, **kwargs)
        finally:
            self._edit_depth -= 1
            if outer:
                after = self.latex()
                if after != before:
                    self.latexChanged.emit(after)
                self.stateChanged.emit()
    return wrapped


class MathEditorWidget(QWidget):
    """A WYSIWYG math draft editor backed by ``MathSequence`` trees."""

    latexChanged = Signal(str)
    stateChanged = Signal()

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._edit_depth = 0
        self.root: MathSequence = MathSequence()
        self.path: list[tuple[str, int, int]] = [("root", 0, -1)]
        self.index = 0
        self.anchor: tuple[list[tuple[str, int, int]], int] | None = None
        self._undo: list[tuple[MathSequence, list[tuple[str, int, int]], int]] = []
        self._redo: list[tuple[MathSequence, list[tuple[str, int, int]], int]] = []
        self._pending_command = ""
        self._preedit = ""
        self._preedit_attributes = []
        self._composition_undo = None
        self.setMinimumHeight(120)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.setAttribute(Qt.WidgetAttribute.WA_InputMethodEnabled)
        self.setAccessibleName("可视公式编辑区")
        self.stateChanged.connect(self._update_input_method)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    @_edit_operation
    def set_latex(self, text: str) -> None:
        self._reset_composition()
        self.root = parse_math_latex(text)
        self.path = [("root", 0, -1)]
        self.index = len(_boundaries(self.root))
        self.anchor = None
        self._pending_command = ""
        self._undo = []
        self._redo = []
        self.update()

    def latex(self) -> str:
        return latex_of(self.root)

    @_edit_operation
    def insert_structure(self, key: str) -> None:
        """Insert an empty structure at the cursor (template action)."""

        if key == "fraction":
            node: MathNode = Frac()
            role = "frac_num"
        elif key == "sqrt":
            node = Sqrt()
            role = "sqrt"
        elif key == "sum":
            node = BigOp(symbol="sum", lower=MathSequence(), upper=MathSequence(), body=MathSequence())
            role = "body"
        elif key == "integral":
            node = BigOp(symbol="int", lower=MathSequence(), upper=MathSequence(), body=MathSequence())
            role = "body"
        elif key == "prod":
            node = BigOp(symbol="prod", lower=MathSequence(), upper=MathSequence(), body=MathSequence())
            role = "body"
        elif key == "lim":
            node = BigOp(symbol="lim", lower=None, upper=None, body=MathSequence())
            role = "body"
        elif key == "derivative":
            node = Frac(
                numerator=MathSequence(items=[Text("d")]),
                denominator=MathSequence(items=[Text("dx")]),
            )
            role = None
        elif key == "log10":
            self._insert_scripted_command("log", "10", sub=True)
            return
        elif key == "logab":
            self._insert_scripted_command("log", "", sub=True)
            return
        elif key == "exp":
            self._insert_scripted_command("", "", super=True, base_text="e")
            return
        elif key == "exp10":
            self._insert_scripted_command("", "", super=True, base_text="10")
            return
        elif key in ("inverse_sin", "inverse_cos", "inverse_tan"):
            name = key.removeprefix("inverse_")
            self._insert_scripted_command(name, "-1", super=True)
            return
        elif key == "nth_root":
            node = Command(latex=r"\sqrt[n]{}", display="ⁿ√x")
            role = None
        elif key == "matrix":
            node = Command(
                latex=r"\begin{matrix}  &  \\  &  \end{matrix}",
                display="矩阵",
            )
            role = None
        elif key == "cases":
            node = Command(
                latex=r"\begin{cases}  &  \\  &  \end{cases}",
                display="分段",
            )
            role = None
        elif key == "greek_alpha":
            node = Command(latex=r"\alpha", display="α")
            role = None
        elif key == "superscript":
            self._insert_script("^")
            return
        elif key == "subscript":
            self._insert_script("_")
            return
        else:
            return

        self._prepare_insertion()
        slot, boundary_index = self._current_slot_and_index()
        boundary = self._boundary_at(slot, boundary_index)
        insert_index = self._split_text_at(slot, boundary)
        slot.items.insert(insert_index, node)
        if role is not None:
            child_slot = _slot_of(node, role)
            assert child_slot is not None
            self.path = [
                *self.path,
                (role, 0, insert_index),
            ]
            self.index = 0
        else:
            self.index = self._boundary_after(slot, insert_index)
        self.anchor = None
        self._pending_command = ""
        self.update()

    def _insert_scripted_command(
        self,
        name: str,
        script_text: str,
        *,
        super: bool = False,
        sub: bool = False,
        base_text: str = "",
    ) -> None:
        """Insert a command (or text) with an attached script slot."""

        self._prepare_insertion()
        slot, boundary_index = self._current_slot_and_index()
        boundary = self._boundary_at(slot, boundary_index)
        insert_index = self._split_text_at(slot, boundary)
        if name:
            display = symbol_display(name) or name
            base_item: MathNode = Command(latex="\\" + name, display=display)
        elif base_text:
            base_item = Text(base_text)
        else:
            base_item = Text("")
        script = Script(base=MathSequence(items=[base_item]))
        if super:
            script.super = MathSequence(items=[Text(script_text)]) if script_text else MathSequence()
            role = "super"
        else:
            script.sub = MathSequence(items=[Text(script_text)]) if script_text else MathSequence()
            role = "sub"
        slot.items.insert(insert_index, script)
        self.path.append((role, 0, insert_index))
        self.index = 0
        self.anchor = None
        self._pending_command = ""
        self.update()

    @_edit_operation
    def insert_command(self, name: str) -> None:
        """Insert a LaTeX command node at the cursor."""

        self._prepare_insertion()
        slot, boundary_index = self._current_slot_and_index()
        boundary = self._boundary_at(slot, boundary_index)
        insert_index = self._split_text_at(slot, boundary)
        if name in _CONTROL_LATEX:
            latex, display = _CONTROL_LATEX[name]
        else:
            latex = "\\" + name
            display = symbol_display(name) or name
        slot.items.insert(insert_index, Command(latex=latex, display=display))
        self._set_boundary_after(slot, insert_index, 0)
        self.anchor = None
        self._pending_command = ""
        self.update()

    @_edit_operation
    def insert_text(self, text: str) -> None:
        """Insert plain characters at the cursor (one at a time)."""

        if not text:
            return
        self._prepare_insertion()
        slot, boundary_index = self._current_slot_and_index()
        boundary = self._boundary_at(slot, boundary_index)

        if boundary is not None and boundary.kind == "text" and boundary.node is not None:
            text_node = boundary.node
            if 0 < boundary.offset < len(text_node.text):
                # Split the text run around the caret.
                left = Text(text_node.text[: boundary.offset])
                right = Text(text_node.text[boundary.offset :])
                slot.items[boundary.item_index : boundary.item_index + 1] = [left, Text(text), right]
                self._set_boundary_after(slot, boundary.item_index + 1, len(text))
            elif boundary.offset == 0:
                slot.items[boundary.item_index] = Text(text + text_node.text)
                self._set_boundary_after(slot, boundary.item_index, len(text))
            else:
                slot.items[boundary.item_index] = Text(text_node.text + text)
                self._set_boundary_after(slot, boundary.item_index, len(text_node.text) + len(text))
        else:
            insert_index = self._insert_index_at(boundary, slot)
            slot.items.insert(insert_index, Text(text))
            self._set_boundary_after(slot, insert_index, len(text))
        self.anchor = None
        self._pending_command = ""
        self.update()

    @_edit_operation
    def paste_clipboard(self, text: str) -> None:
        """Paste LaTeX or plain text at the cursor.

        A pasted text that is exactly one supported formula wrapper (``$...$``,
        ``\\(...\\)``, ``\\[...\\]``, equation, equation*) is inserted with its
        wrapper stripped: the dialog's formula mode owns the outer wrapper.
        Preserve body whitespace and comment newlines: TeX does not generally
        ignore them. A projection that cannot round-trip stays as literal text;
        the dialog's normal source editor remains available for editing it.
        """

        if not text:
            return
        envelope = recognize_formula(text)
        body = envelope.body if envelope is not None else text

        if self.anchor is not None:
            self._delete_selection()  # pushes history
        else:
            self._push_history()

        slot, boundary_index = self._current_slot_and_index()
        boundary = self._boundary_at(slot, boundary_index)
        insert_index = self._split_text_at(slot, boundary)
        parsed = parse_math_latex(body)
        if latex_of(parsed) != body:
            parsed = MathSequence(items=[Text(body)])
        slot.items[insert_index:insert_index] = parsed.items
        if parsed.items:
            last_index = insert_index + len(parsed.items) - 1
            self.index = self._boundary_after(slot, last_index)
        else:
            self.index = boundary_index
        self.anchor = None
        self._pending_command = ""
        self.update()

    @_edit_operation
    def type_key(self, text: str) -> None:
        """Handle a typed character, including shortcut conversions."""

        if text == "/":
            self.insert_structure("fraction")
            return
        if text == "^":
            self._insert_script("^")
            return
        if text == "_":
            self._insert_script("_")
            return
        if text == "\\":
            self._pending_command = "\\"
            return
        if self._pending_command:
            if text.isalpha():
                self._pending_command += text
                return
            self._finish_pending_command()
            if text == " ":
                return
        self.insert_text(text)

    @_edit_operation
    def cursor_left(self, select: bool = False) -> None:
        self._selection_for_move(select)
        self._move_horizontal(-1)

    @_edit_operation
    def cursor_right(self, select: bool = False) -> None:
        self._selection_for_move(select)
        self._move_horizontal(1)

    @_edit_operation
    def cursor_up(self, select: bool = False) -> None:
        self._selection_for_move(select)
        self._move_vertical(-1)

    @_edit_operation
    def cursor_down(self, select: bool = False) -> None:
        self._selection_for_move(select)
        self._move_vertical(1)

    @_edit_operation
    def cursor_tab(self, backwards: bool = False) -> None:
        self.anchor = None
        slots = self._all_slots()
        current = self._resolve_slot()
        try:
            current_index = slots.index(id(current))
        except ValueError:
            return
        next_slot = slots[(current_index + (-1 if backwards else 1)) % len(slots)]
        self._jump_into_slot(next_slot, 0)

    @_edit_operation
    def cursor_home(self, select: bool = False) -> None:
        self._selection_for_move(select)
        self.index = 0
        self.update()

    @_edit_operation
    def cursor_end(self, select: bool = False) -> None:
        self._selection_for_move(select)
        slot = self._resolve_slot()
        self.index = len(_boundaries(slot))
        self.update()

    @_edit_operation
    def delete_backspace(self) -> None:
        if self._pending_command:
            self._pending_command = self._pending_command[:-1]
            return
        if self._delete_selection():
            return
        self._push_history()
        slot, boundary_index = self._current_slot_and_index()
        boundaries = _boundaries(slot)
        if not boundaries:
            self._exit_slot(-1)
            return
        boundary = self._boundary_at(slot, boundary_index)
        if boundary is None:
            self._clamp()
            return
        if boundary.kind == "text" and boundary.node is not None and boundary.offset > 0:
            node = boundary.node
            node.text = node.text[: boundary.offset - 1] + node.text[boundary.offset :]
            self.index = max(0, boundary_index - 1)
            if not node.text:
                slot.items.pop(boundary.item_index)
            self._clamp()
            self.update()
            return
        if boundary_index > 0:
            previous = boundaries[boundary_index - 1]
            if previous.kind == "text" and previous.node is not None and previous.offset == len(previous.node.text):
                previous.node.text = previous.node.text[:-1]
                self.index = boundary_index - 1
                if not previous.node.text:
                    slot.items.pop(previous.item_index)
                self._clamp()
                self.update()
                return
            slot.items.pop(previous.item_index)
            self.index = max(0, boundary_index - 1)
            self._clamp()
            self.update()
            return
        if len(self.path) > 1:
            self._exit_slot(-1)
            self.update()

    @_edit_operation
    def delete_forward(self) -> None:
        if self._delete_selection():
            return
        self._push_history()
        slot, boundary_index = self._current_slot_and_index()
        boundaries = _boundaries(slot)
        if not boundaries:
            if len(self.path) > 1:
                self._exit_slot(1)
            return
        boundary = self._boundary_at(slot, boundary_index)
        if boundary is None:
            self._clamp()
            return
        if boundary.kind == "text" and boundary.node is not None and boundary.offset < len(boundary.node.text):
            node = boundary.node
            node.text = node.text[: boundary.offset] + node.text[boundary.offset + 1 :]
            if not node.text:
                slot.items.pop(boundary.item_index)
            self._clamp()
            self.update()
            return
        if boundary_index < len(boundaries) - 1:
            slot.items.pop(boundary.item_index)
            self._clamp()
            self.update()
            return
        if len(self.path) > 1:
            self._exit_slot(1)
            self.update()

    @_edit_operation
    def undo(self) -> None:
        if not self._undo:
            return
        self._redo.append(self._snapshot())
        root, path, index = self._undo.pop()
        self.root, self.path, self.index = root, path, index
        self.anchor = None
        self._pending_command = ""
        self.update()

    @_edit_operation
    def redo(self) -> None:
        if not self._redo:
            return
        self._undo.append(self._snapshot())
        root, path, index = self._redo.pop()
        self.root, self.path, self.index = root, path, index
        self.anchor = None
        self._pending_command = ""
        self.update()

    @_edit_operation
    def select_all(self) -> None:
        self.anchor = ([("root", 0, -1)], 0)
        self.path = [("root", 0, -1)]
        self.index = len(_boundaries(self.root))
        self.update()

    @property
    def pending_command(self) -> str:
        return self._pending_command

    @property
    def can_undo(self) -> bool:
        return bool(self._undo)

    @property
    def can_redo(self) -> bool:
        return bool(self._redo)

    @_edit_operation
    def commit_pending_command(self) -> None:
        self._finish_pending_command()

    # ------------------------------------------------------------------
    # Input methods. The surrounding text is the current mathematical slot;
    # structural nodes are atomic object characters, never editable TeX bytes.
    # Preedit is a painted overlay and is excluded from LaTeX and undo history.
    # ------------------------------------------------------------------

    @staticmethod
    def _input_text(items) -> str:
        return "".join(item.text if isinstance(item, Text) else "\ufffc" for item in items)

    @staticmethod
    def _utf16_length(text: str) -> int:
        return len(text.encode("utf-16-le")) // 2

    @classmethod
    def _input_position(cls, slot: MathSequence, index: int) -> int:
        boundaries = _boundaries(slot)
        if index >= len(boundaries):
            return len(cls._input_text(slot.items))
        boundary = boundaries[max(0, index)]
        return len(cls._input_text(slot.items[:boundary.item_index])) + boundary.offset

    @classmethod
    def _input_index(cls, slot: MathSequence, position: int) -> int:
        starts = []
        total = 0
        for item in slot.items:
            starts.append(total)
            total += len(item.text) if isinstance(item, Text) else 1
        boundaries = _boundaries(slot)
        for index, boundary in enumerate(boundaries):
            if starts[boundary.item_index] + boundary.offset == position:
                return index
        return len(boundaries)

    @staticmethod
    def _input_offsets(text: str) -> dict[int, int]:
        offsets = {0: 0}
        total = 0
        for index, char in enumerate(text):
            total += 2 if ord(char) > 0xffff else 1
            offsets[total] = index + 1
        return offsets

    @staticmethod
    def _input_slice(items, start: int, end: int):
        result = []
        position = 0
        for item in items:
            width = len(item.text) if isinstance(item, Text) else 1
            low, high = max(start, position), min(end, position + width)
            if low < high:
                result.append(Text(item.text[low - position:high - position])
                              if isinstance(item, Text) else item)
            position += width
        return result

    def _update_input_method(self) -> None:
        if self.hasFocus():
            QApplication.inputMethod().update(Qt.InputMethodQuery.ImQueryAll)

    def _reset_composition(self) -> None:
        if self._preedit and self.hasFocus():
            QApplication.inputMethod().reset()
        self._preedit = ""
        self._preedit_attributes = []
        self._composition_undo = None

    @property
    def has_preedit(self) -> bool:
        return bool(self._preedit)

    def finish_composition(self) -> bool:
        if self._preedit and self.hasFocus():
            QApplication.inputMethod().commit()
        # Never invent a candidate or silently apply an incomplete preedit.
        return not self._preedit

    def inputMethodQuery(self, query):
        slot = self._resolve_slot()
        text = self._input_text(slot.items)
        position = self._input_position(slot, self.index)
        anchor = (self._input_position(slot, self.anchor[1])
                  if self.anchor is not None and self.anchor[0] == self.path else position)
        values = {
            Qt.InputMethodQuery.ImEnabled: self.isEnabled(),
            Qt.InputMethodQuery.ImFont: QFont("Menlo", 15),
            Qt.InputMethodQuery.ImSurroundingText: text,
            Qt.InputMethodQuery.ImCursorPosition: self._utf16_length(text[:position]),
            Qt.InputMethodQuery.ImAnchorPosition: self._utf16_length(text[:anchor]),
            Qt.InputMethodQuery.ImAbsolutePosition: self._utf16_length(text[:position]),
            Qt.InputMethodQuery.ImCurrentSelection: text[min(anchor, position):max(anchor, position)],
            Qt.InputMethodQuery.ImTextBeforeCursor: text[:position],
            Qt.InputMethodQuery.ImTextAfterCursor: text[position:],
        }
        if query == Qt.InputMethodQuery.ImCursorRectangle:
            font, small, big, box = self._paint_layout()
            rect = self._caret_rect(box, font) or QRectF(10, 10, 1, 20)
            if self._preedit:
                layout, cursor, _visible, _color = self._preedit_layout(font)
                x, _position = layout.lineAt(0).cursorToX(cursor)
                rect.translate(x, 0)
            return rect
        return values[query] if query in values else super().inputMethodQuery(query)

    @_edit_operation
    def inputMethodEvent(self, event: QInputMethodEvent) -> None:
        starting = not self._preedit
        if starting and (event.preeditString() or event.commitString()):
            self._finish_pending_command()
        slot = self._resolve_slot()
        items = slot.items
        text = self._input_text(items)
        position = self._input_position(slot, self.index)
        has_edit = bool(event.preeditString() or event.commitString() or event.replacementLength())
        selected = self.anchor is not None and self.anchor[0] == self.path and has_edit
        if selected:
            anchor = self._input_position(slot, self.anchor[1])
            low, high = sorted((position, anchor))
            items = self._input_slice(items, 0, low) + self._input_slice(items, high, len(text))
            text = self._input_text(items)
            position = low
        # Qt positions are UTF-16 units. A replacement must not split a surrogate
        # pair or consume a different structural slot than the context we expose.
        offsets = self._input_offsets(text)
        start = self._utf16_length(text[:position]) + event.replacementStart()
        end = start + event.replacementLength()
        if start not in offsets or end not in offsets or end < start:
            event.ignore()
            return
        low, high = offsets[start], offsets[end]
        commit = event.commitString()
        if commit or event.replacementLength():
            items = (self._input_slice(items, 0, low) + ([Text(commit)] if commit else [])
                     + self._input_slice(items, high, len(text)))
            position = low + len(commit)
        if latex_of(MathSequence(items=items)) != latex_of(slot):
            if not (self._undo and self._undo[-1] is self._composition_undo):
                self._push_history()
                self._composition_undo = self._undo[-1] if starting and selected else None
            slot.items = items
        self.index = self._input_index(slot, position)
        if has_edit:
            self.anchor = None
        for attribute in event.attributes():
            if attribute.type == QInputMethodEvent.AttributeType.Selection:
                current = self._input_text(slot.items)
                positions = self._input_offsets(current)
                a, b = attribute.start, attribute.start + attribute.length
                if a in positions and b in positions:
                    self.anchor = (deepcopy(self.path), self._input_index(slot, positions[a])) if a != b else None
                    self.index = self._input_index(slot, positions[b])
        self._preedit = event.preeditString()
        self._preedit_attributes = list(event.attributes())
        # Selection removal belongs to the first commit only. A subsequent
        # commit in the same input-method session needs its own undo record.
        if not self._preedit or commit or event.replacementLength():
            self._composition_undo = None
        self.update()
        event.accept()

    # ------------------------------------------------------------------
    # Cursor machinery
    # ------------------------------------------------------------------

    def _current_slot_and_index(self) -> tuple[MathSequence, int]:
        return self._resolve_slot(), self.index

    @staticmethod
    def _boundary_at(slot: MathSequence, index: int) -> Boundary | None:
        boundaries = _boundaries(slot)
        if not boundaries or index >= len(boundaries):
            return None
        return boundaries[index]

    def _resolve_slot(self) -> MathSequence:
        node: MathNode = self.root
        for role, _index, container_index in self.path[1:]:
            assert isinstance(node, MathSequence)
            container = node.items[container_index]
            slot = _slot_of(container, role)
            assert slot is not None
            node = slot
        assert isinstance(node, MathSequence)
        return node

    def _boundary_after(self, slot: MathSequence, item_index: int, offset: int = 0) -> int:
        boundaries = _boundaries(slot)
        for position, boundary in enumerate(boundaries):
            if boundary.item_index == item_index and boundary.kind == "text" and boundary.offset >= offset:
                return position
            if boundary.item_index == item_index and boundary.kind in ("command", "node") and boundary.offset == 1:
                return position
            if boundary.item_index > item_index:
                return position
        return len(boundaries)

    @staticmethod
    def _insert_index_at(boundary: Boundary | None, slot: MathSequence) -> int:
        if boundary is None:
            return len(slot.items)
        if boundary.kind == "text" and boundary.node is not None:
            return boundary.item_index + (1 if boundary.offset == len(boundary.node.text) else 0)
        return boundary.item_index + (1 if boundary.offset == 1 else 0)

    def _split_text_at(self, slot: MathSequence, boundary: Boundary | None) -> int:
        """Split a text run at an internal caret boundary and return the
        insertion index for the character that follows the caret."""

        if boundary is None or boundary.kind != "text" or boundary.node is None:
            return self._insert_index_at(boundary, slot)
        node = boundary.node
        if 0 < boundary.offset < len(node.text):
            left = Text(node.text[: boundary.offset])
            right = Text(node.text[boundary.offset :])
            slot.items[boundary.item_index : boundary.item_index + 1] = [left, right]
            return boundary.item_index + 1
        return self._insert_index_at(boundary, slot)

    def _set_boundary_after(self, slot: MathSequence, item_index: int, offset: int) -> None:
        self.index = self._boundary_after(slot, item_index, offset)
        self._clamp()

    def _clamp(self) -> None:
        slot = self._resolve_slot()
        total = len(_boundaries(slot))
        self.index = min(max(0, self.index), total)

    def _exit_slot(self, direction: int) -> None:
        if len(self.path) <= 1:
            return
        _, _, container_index = self.path[-1]
        self.path.pop()
        # A node index is not a caret index: preceding text has many boundaries.
        self.index = next(index for index, boundary in enumerate(_boundaries(self._resolve_slot()))
                          if boundary.item_index == container_index and boundary.offset == (1 if direction > 0 else 0))
        self._clamp()
        self.update()

    def _move_horizontal(self, direction: int) -> None:
        slot, boundary_index = self._current_slot_and_index()
        boundaries = _boundaries(slot)
        if direction > 0:
            boundary = self._boundary_at(slot, boundary_index)
            if boundary is not None and boundary.kind == "node" and boundary.node is not None and boundary.offset == 0:
                self._enter_slot(boundary.node, 0)
                return
            if boundary is not None and boundary_index < len(boundaries) - 1:
                self.index += 1
            else:
                self._exit_slot(1)
        else:
            if boundary_index > 0:
                current = self._boundary_at(slot, boundary_index)
                if current is not None and current.kind == "node" and current.node is not None and current.offset == 1:
                    self._enter_slot(current.node, -1)
                    return
                self.index -= 1
            else:
                self._exit_slot(-1)
        self._clamp()
        self.update()

    def _enter_slot(self, node: MathNode, direction: int) -> None:
        roles = _child_roles(node)
        if not roles:
            return
        role = roles[0] if direction >= 0 else roles[-1]
        slot = _slot_of(node, role)
        if slot is None:
            return
        container_index = next(
            index for index, item in enumerate(self._resolve_slot().items) if item is node
        )
        self.path.append((role, 0, container_index))
        self.index = 0 if direction >= 0 else len(_boundaries(slot))
        self.update()

    def _move_vertical(self, direction: int) -> None:
        # First enter a structure next to the caret, without creating empty slots.
        slot = self._resolve_slot()
        boundary = self._boundary_at(slot, self.index)
        adjacent = None
        if boundary is None:
            adjacent = len(slot.items) - 1
        elif boundary.kind == "node":
            adjacent = boundary.item_index
        elif boundary.offset == 0:
            adjacent = boundary.item_index - 1
        elif boundary.offset == (len(boundary.node.text) if boundary.kind == "text" else 1):
            adjacent = boundary.item_index + 1
        if adjacent is not None and 0 <= adjacent < len(slot.items):
            node = slot.items[adjacent]
            roles = ("super", "sub") if isinstance(node, Script) else (
                ("frac_num", "frac_den") if isinstance(node, Frac) else ("upper", "lower"))
            role = roles[0 if direction < 0 else 1]
            if isinstance(node, (Script, Frac, BigOp)) and _slot_of(node, role) is not None:
                self._move_to_vertical_path([*self.path, (role, 0, adjacent)])
                return

        transitions = {
            ("frac_num", 1): "frac_den", ("frac_den", -1): "frac_num",
            ("base", -1): "super", ("base", 1): "sub",
            ("super", 1): "base", ("sub", -1): "base",
            ("body", -1): "upper", ("body", 1): "lower",
            ("upper", 1): "body", ("lower", -1): "body",
        }
        # A root/group inside a fraction should still reach its numerator/denominator.
        parent = self.root
        ancestors = []
        for depth, (role, _index, container_index) in enumerate(self.path[1:], 1):
            node = parent.items[container_index]
            ancestors.append((depth, role, container_index, node))
            parent = _slot_of(node, role)
        for depth, role, container_index, node in reversed(ancestors):
            target = transitions.get((role, direction))
            if target is not None and _slot_of(node, target) is not None:
                self._move_to_vertical_path([*self.path[:depth], (target, 0, container_index)])
                return

    def _move_to_vertical_path(self, path: list[tuple[str, int, int]]) -> None:
        """Keep the nearest rendered horizontal position while changing slots."""
        font, _small, _big, box = self._paint_layout()
        caret = self._caret_rect(box, font)
        old_index = self.index
        self.path = path
        slot = self._resolve_slot()
        slot_box = self._find_box(box, slot)
        boundaries = _boundaries(slot)
        self.index = min(old_index, len(boundaries))
        if caret is not None and slot_box is not None:
            boxes = {id(child.node): child for child, _x, _y in slot_box.children}
            positions = []
            for boundary in boundaries:
                item = boxes.get(id(boundary.node))
                if item is None:
                    positions.append(slot_box.x)
                elif boundary.kind == "text" and item.boundaries:
                    positions.append(item.x + item.boundaries[boundary.offset])
                else:
                    positions.append(item.x + (item.w if boundary.offset else 0))
            positions.append(slot_box.x + slot_box.w)
            self.index = min(range(len(positions)), key=lambda i: abs(positions[i] - caret.center().x()))
        self.update()

    def _resolve_parent_slot(self) -> MathSequence | None:
        if len(self.path) <= 1:
            return None
        node: MathNode = self.root
        for role, _index, container_index in self.path[1:-1]:
            assert isinstance(node, MathSequence)
            container = node.items[container_index]
            slot = _slot_of(container, role)
            assert slot is not None
            node = slot
        assert isinstance(node, MathSequence)
        return node

    def _all_slots(self) -> list[int]:
        out: list[int] = []

        def walk(node: MathNode) -> None:
            if isinstance(node, MathSequence):
                out.append(id(node))
                for item in node.items:
                    walk(item)
            elif isinstance(node, Frac):
                walk(node.numerator)
                walk(node.denominator)
            elif isinstance(node, Sqrt):
                walk(node.radicand)
            elif isinstance(node, Script):
                walk(node.base)
                if node.super is not None:
                    walk(node.super)
                if node.sub is not None:
                    walk(node.sub)
            elif isinstance(node, BigOp):
                if node.lower is not None:
                    walk(node.lower)
                if node.upper is not None:
                    walk(node.upper)
                walk(node.body)
            elif isinstance(node, Group):
                walk(node.items)

        walk(self.root)
        return out

    def _jump_into_slot(self, slot_id: int, index: int) -> None:
        self._push_anchor()
        new_path: list[tuple[str, int, int]] = [("root", 0, -1)]

        def find_slot(node: MathNode, path: list[tuple[str, int, int]], parent_index: int) -> bool:
            if isinstance(node, MathSequence):
                if id(node) == slot_id:
                    self.path = path
                    self.index = index
                    return True
                for item_index, item in enumerate(node.items):
                    if find_in_container(item, path, item_index):
                        return True
            return False

        def find_in_container(node: MathNode, path: list[tuple[str, int, int]], container_index: int) -> bool:
            if isinstance(node, Frac):
                return find_slot(node.numerator, [*path, ("frac_num", 0, container_index)], container_index) or find_slot(
                    node.denominator, [*path, ("frac_den", 0, container_index)], container_index
                )
            if isinstance(node, Sqrt):
                return find_slot(node.radicand, [*path, ("sqrt", 0, container_index)], container_index)
            if isinstance(node, Script):
                found = find_slot(node.base, [*path, ("base", 0, container_index)], container_index)
                if node.super is not None:
                    found = found or find_slot(node.super, [*path, ("super", 0, container_index)], container_index)
                if node.sub is not None:
                    found = found or find_slot(node.sub, [*path, ("sub", 0, container_index)], container_index)
                return found
            if isinstance(node, BigOp):
                found = False
                if node.lower is not None:
                    found = found or find_slot(node.lower, [*path, ("lower", 0, container_index)], container_index)
                if node.upper is not None:
                    found = found or find_slot(node.upper, [*path, ("upper", 0, container_index)], container_index)
                return found or find_slot(node.body, [*path, ("body", 0, container_index)], container_index)
            if isinstance(node, Group):
                return find_slot(node.items, [*path, ("group", 0, container_index)], container_index)
            return False

        find_slot(self.root, new_path, -1)
        self._clamp()
        self.update()

    def _push_anchor(self) -> None:
        if self.anchor is None:
            self.anchor = (deepcopy(self.path), self.index)

    def _selection_for_move(self, select: bool) -> None:
        if select:
            self._push_anchor()
        else:
            self.anchor = None

    def _delete_selection(self) -> bool:
        parts = self._selection_parts()
        if parts is None or not parts[1].items:
            self.anchor = None
            return False
        self._push_history()
        before, _selected, after = parts
        slot = self._resolve_slot()
        slot.items = before.items + after.items
        if before.items:
            last = before.items[-1]
            self.index = self._boundary_after(slot, len(before.items) - 1, len(last.text) if isinstance(last, Text) else 0)
        else:
            self.index = 0
        self.anchor = None
        self._clamp()
        self.update()
        return True

    def _selection_parts(self):
        if self.anchor is None or self.anchor[0] != self.path:
            return None
        slot = self._resolve_slot()
        boundaries = _boundaries(slot)
        widths = [len(item.text) if isinstance(item, Text) else 1 for item in slot.items]
        def offset(index):
            if index >= len(boundaries):
                return sum(widths)
            boundary = boundaries[index]
            return sum(widths[:boundary.item_index]) + boundary.offset
        start, end = sorted((offset(self.anchor[1]), offset(self.index)))
        parts = [MathSequence(), MathSequence(), MathSequence()]
        position = 0
        for item, width in zip(slot.items, widths):
            for target, low, high in ((parts[0], 0, start), (parts[1], start, end), (parts[2], end, sum(widths))):
                a, b = max(position, low), min(position + width, high)
                if a < b:
                    target.items.append(Text(item.text[a - position:b - position]) if isinstance(item, Text) else item)
            position += width
        return parts

    def selected_latex(self) -> str:
        parts = self._selection_parts()
        return latex_of(parts[1]) if parts is not None else ""

    def _prepare_insertion(self) -> None:
        if not self._delete_selection():
            self._push_history()

    def _insert_script(self, marker: str) -> None:
        self._push_history()
        slot, boundary_index = self._current_slot_and_index()
        boundary = self._boundary_at(slot, boundary_index)
        if boundary is not None and boundary.kind == "node" and boundary.offset == 0 and boundary.node is not None:
            base = boundary.node
            script = Script(base=MathSequence(items=[base]))
            if marker == "^":
                script.super = MathSequence()
            else:
                script.sub = MathSequence()
            slot.items[boundary.item_index] = script
            role = "super" if marker == "^" else "sub"
            self.path.append((role, 0, boundary.item_index))
            self.index = 0
        else:
            insert_index = self._insert_index_at(boundary, slot)
            base: MathNode | None = None
            container_index = insert_index
            if insert_index > 0:
                previous = slot.items[insert_index - 1]
                if isinstance(previous, Text):
                    match = _TRAILING_TOKEN.search(previous.text)
                    if match is not None and match.start() > 0:
                        previous.text = previous.text[: match.start()]
                        base = Text(match.group(0))
                        slot.items.insert(insert_index, base)
                    elif match is not None and match.start() == 0:
                        base = previous
                        container_index = insert_index - 1
                    else:
                        base = previous
                        container_index = insert_index - 1
                else:
                    base = previous
                    container_index = insert_index - 1
            if base is None:
                base = Text("")
                slot.items.insert(insert_index, base)
            script = Script(base=MathSequence(items=[base]))
            if marker == "^":
                script.super = MathSequence()
            else:
                script.sub = MathSequence()
            slot.items[container_index] = script
            role = "super" if marker == "^" else "sub"
            self.path.append((role, 0, container_index))
            self.index = 0
        self.anchor = None
        self._pending_command = ""
        self.update()

    def _finish_pending_command(self) -> None:
        pending = self._pending_command
        self._pending_command = ""
        if not pending:
            return
        if len(pending) < 2:
            self.insert_text(pending)
            return
        name = pending[1:]
        if name == "frac":
            self.insert_structure("fraction")
            return
        if name == "sqrt":
            self.insert_structure("sqrt")
            return
        if name == "sum":
            self.insert_structure("sum")
            return
        if name == "int":
            self.insert_structure("integral")
            return
        display = symbol_display(name)
        if display is not None:
            self._push_history()
            slot, boundary_index = self._current_slot_and_index()
            boundary = self._boundary_at(slot, boundary_index)
            insert_index = self._split_text_at(slot, boundary)
            slot.items.insert(insert_index, Command(latex="\\" + name, display=display))
            self._set_boundary_after(slot, insert_index, 0)
            self.anchor = None
            self.update()
            return
        self.insert_text(pending)

    # ------------------------------------------------------------------
    # History
    # ------------------------------------------------------------------

    def _push_history(self) -> None:
        self._undo.append(self._snapshot())
        if len(self._undo) > 200:
            self._undo.pop(0)
        self._redo.clear()

    def _snapshot(self) -> tuple[MathSequence, list[tuple[str, int, int]], int]:
        return deepcopy(self.root), deepcopy(self.path), self.index

    # ------------------------------------------------------------------
    # Painting
    # ------------------------------------------------------------------

    def paintEvent(self, _event) -> None:  # type: ignore[no-untyped-def]
        painter = QPainter(self)
        painter.fillRect(self.rect(), _BACKGROUND)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        font, small_font, big_font, box = self._paint_layout()
        self._draw(painter, box, font, small_font, big_font)

        # Caret and selection overlay.
        selection_rects = self._selection_rects(box, small_font)
        for rect in selection_rects:
            painter.fillRect(rect, _SELECTION)
        caret_rect = self._caret_rect(box, font)
        if caret_rect is not None:
            if self._preedit:
                self._paint_preedit(painter, caret_rect, font)
            else:
                painter.fillRect(caret_rect, _CARET)

    def _paint_layout(self):
        font = QFont("Menlo", 15)
        font.setStyleHint(QFont.StyleHint.Monospace)
        font.setLetterSpacing(QFont.SpacingType.AbsoluteSpacing, 1.2)
        small_font = QFont(font)
        small_font.setPointSizeF(max(9.0, font.pointSizeF() * 0.72))
        big_font = QFont(font)
        big_font.setPointSizeF(font.pointSizeF() * 1.6)

        fm = QFontMetricsF(font)
        small_fm = QFontMetricsF(small_font)
        big_fm = QFontMetricsF(big_font)

        box = self._measure(self.root, fm, small_fm, big_fm)
        self._place(box, 16, 16)
        return font, small_font, big_font, box

    def _preedit_layout(self, font: QFont):
        layout = QTextLayout(self._preedit, font)
        formats = []
        cursor = self._utf16_length(self._preedit)
        visible = True
        color = _CARET
        for attribute in self._preedit_attributes:
            if attribute.type == QInputMethodEvent.AttributeType.TextFormat:
                value = attribute.value
                if hasattr(value, "toCharFormat"):
                    value = value.toCharFormat()
                if isinstance(value, QTextCharFormat):
                    span = QTextLayout.FormatRange()
                    span.start, span.length, span.format = attribute.start, attribute.length, value
                    formats.append(span)
            elif attribute.type == QInputMethodEvent.AttributeType.Cursor:
                cursor, visible = attribute.start, bool(attribute.length)
                if isinstance(attribute.value, QColor):
                    color = attribute.value
        if not formats:
            span = QTextLayout.FormatRange()
            span.start, span.length = 0, self._utf16_length(self._preedit)
            style = QTextCharFormat()
            style.setFontUnderline(True)
            span.format = style
            formats.append(span)
        layout.setFormats(formats)
        layout.beginLayout()
        line = layout.createLine()
        line.setLineWidth(max(1.0, QFontMetricsF(font).horizontalAdvance(self._preedit) + 2))
        layout.endLayout()
        return layout, cursor, visible, color

    def _paint_preedit(self, painter: QPainter, caret: QRectF, font: QFont) -> None:
        layout, cursor, visible, color = self._preedit_layout(font)
        line = layout.lineAt(0)
        origin = QPointF(caret.x(), caret.y())
        painter.fillRect(QRectF(origin.x(), origin.y(), line.naturalTextWidth() + 2, line.height()), _BACKGROUND)
        painter.setPen(_TEXT)
        layout.draw(painter, origin)
        if visible:
            painter.setPen(color)
            layout.drawCursor(painter, origin, cursor)

    def _measure(self, node: MathNode, fm: QFontMetricsF, small_fm: QFontMetricsF, big_fm: QFontMetricsF) -> Box:
        if isinstance(node, Text):
            return self._text_box(node.text, node, fm)
        if isinstance(node, Command):
            return self._text_box(node.display, node, fm)
        if isinstance(node, MathSequence):
            children = [self._measure(item, fm, small_fm, big_fm) for item in node.items]
            return self._sequence_box(children, node)
        if isinstance(node, Group):
            children = [self._measure(item, fm, small_fm, big_fm) for item in node.items.items]
            return self._sequence_box(children, node)
        if isinstance(node, Frac):
            num = self._measure(node.numerator, fm, small_fm, big_fm)
            den = self._measure(node.denominator, fm, small_fm, big_fm)
            rule = 1.6
            pad, gap = 6.0, 5.0
            width = max(num.w, den.w) + pad * 2
            height = num.h + gap * 2 + rule + den.h
            baseline = num.h + gap + rule / 2
            box = Box("frac", width, height, baseline, node=node)
            box.children = [
                (num, (width - num.w) / 2, 0),
                (den, (width - den.w) / 2, num.h + gap * 2 + rule),
            ]
            return box
        if isinstance(node, Sqrt):
            rad = self._measure(node.radicand, fm, small_fm, big_fm)
            radical = fm.horizontalAdvance("√") * 1.25 + 3.0
            over = 5.0
            width = radical + rad.w + 4
            height = rad.h + over + 2
            baseline = rad.baseline + over + 1
            box = Box("sqrt", width, height, baseline, node=node)
            box.children = [(rad, radical, over + 1)]
            return box
        if isinstance(node, Script):
            base = self._measure(node.base, fm, small_fm, big_fm)
            sup = self._measure(node.super, small_fm, small_fm, big_fm) if node.super is not None else None
            sub = self._measure(node.sub, small_fm, small_fm, big_fm) if node.sub is not None else None
            side_w = max((sup.w if sup else 0.0), (sub.w if sub else 0.0))
            side_x = base.w + 5.0
            base_y = max(sup.h * 0.65, sup.h - base.baseline) + 4.0 if sup else 0.0
            sub_y = base_y + base.baseline + 4.0
            width = side_x + side_w if sup or sub else base.w
            height = max(base_y + base.h, sup.h if sup else 0.0, sub_y + sub.h if sub else 0.0)
            baseline = base_y + base.baseline
            box = Box("script", width, height, baseline, node=node)
            box.children = [(base, 0, base_y)]
            if sup is not None:
                box.children.append((sup, side_x, 0))
            if sub is not None:
                box.children.append((sub, side_x, sub_y))
            return box
        if isinstance(node, BigOp):
            symbol = {"sum": "∑", "int": "∫", "lim": "lim"}.get(node.symbol, node.symbol)
            op_fm = big_fm if node.symbol in ("sum", "int") else fm
            op_box = self._text_box(symbol, node, op_fm)
            lower = self._measure(node.lower, small_fm, small_fm, big_fm) if node.lower is not None else None
            upper = self._measure(node.upper, small_fm, small_fm, big_fm) if node.upper is not None else None
            body = self._measure(node.body, fm, small_fm, big_fm)
            column_w = max(op_box.w, upper.w if upper else 0.0, lower.w if lower else 0.0)
            op_y = upper.h + 5.0 if upper else 0.0
            baseline = max(op_y + op_box.baseline, body.baseline)
            top = baseline - (op_y + op_box.baseline)
            op_y += top
            lower_y = op_y + op_box.h + 5.0
            body_y = baseline - body.baseline
            width = column_w + 8.0 + body.w
            height = max(lower_y + lower.h if lower else op_y + op_box.h, body_y + body.h)
            box = Box("bigop", width, height, baseline, node=node)
            box.children = [(op_box, (column_w - op_box.w) / 2, op_y)]
            if upper is not None:
                box.children.append((upper, (column_w - upper.w) / 2, top))
            if lower is not None:
                box.children.append((lower, (column_w - lower.w) / 2, lower_y))
            box.children.append((body, column_w + 8.0, body_y))
            return box
        raise TypeError(f"unknown node: {type(node).__name__}")

    @staticmethod
    def _text_box(text: str, node: MathNode, fm: QFontMetricsF) -> Box:
        if not text:
            return Box("empty", 8.0, fm.height(), fm.ascent(), node=node)
        boundaries = [fm.horizontalAdvance(text[:index]) for index in range(len(text) + 1)]
        return Box(
            "text",
            fm.horizontalAdvance(text),
            fm.height(),
            fm.ascent(),
            node=node,
            text=text,
            boundaries=boundaries,
        )

    @staticmethod
    def _sequence_box(children: list[Box], node: MathNode) -> Box:
        if not children:
            return Box("empty", 8.0, 20.0, 15.0, node=node)
        spacing = 4.0
        width = sum(child.w for child in children) + spacing * (len(children) - 1)
        baseline = max(child.baseline for child in children)
        # Aligned children can have different ascents and descents (e.g. nested fractions).
        height = baseline + max(child.h - child.baseline for child in children)
        box = Box("seq", width, height, baseline, node=node)
        x = 0.0
        for child in children:
            box.children.append((child, x, baseline - child.baseline))
            x += child.w + spacing
        return box

    def _place(self, box: Box, x: float, y: float) -> None:
        box.x, box.y = x, y
        for child, dx, dy in box.children:
            self._place(child, x + dx, y + dy)

    def _draw(self, painter: QPainter, box: Box, font: QFont, small_font: QFont, big_font: QFont) -> None:
        if box.kind == "text":
            painter.setFont(font)
            painter.setPen(QPen(_TEXT))
            painter.drawText(QPointF(box.x, box.y + box.baseline), box.text)
        elif box.kind == "empty" and box.node is not None and isinstance(box.node, MathSequence):
            painter.setPen(QPen(_SLOT_HINT, 1, Qt.PenStyle.DashLine))
            painter.drawRect(QRectF(box.x, box.y, max(8.0, box.w), box.h))
        elif box.kind == "frac":
            painter.setPen(QPen(_TEXT, 1.4))
            rule_y = box.y + box.baseline
            painter.drawLine(QPointF(box.x, rule_y), QPointF(box.x + box.w, rule_y))
        elif box.kind == "sqrt":
            painter.setFont(font)
            painter.setPen(QPen(_TEXT))
            painter.drawText(QPointF(box.x, box.y + box.baseline), "√")
            painter.drawLine(
                QPointF(box.x + box.children[0][1] - 1, box.y + 1),
                QPointF(box.x + box.w, box.y + 1),
            )
        for child, _dx, _dy in box.children:
            # Match the metrics used by _measure; otherwise small slots paint into neighbours.
            child_font = font
            if isinstance(box.node, Script) and (child.node is box.node.super or child.node is box.node.sub):
                child_font = small_font
            elif isinstance(box.node, BigOp):
                if child.node is box.node:
                    child_font = big_font if box.node.symbol in ("sum", "int") else font
                elif child.node is box.node.upper or child.node is box.node.lower:
                    child_font = small_font
            self._draw(painter, child, child_font, small_font, big_font)

    def _caret_rect(self, root_box: Box, font: QFont) -> QRectF | None:
        slot = self._resolve_slot()
        slot_box = self._find_box(root_box, slot)
        if slot_box is None:
            return None
        boundaries = _boundaries(slot)
        index = min(self.index, len(boundaries))
        x = slot_box.x
        if index < len(boundaries):
            boundary = boundaries[index]
            item_box = self._find_box(slot_box, boundary.node)
            if item_box is not None and boundary.kind == "text" and boundary.node is not None:
                offset = min(boundary.offset, len(item_box.boundaries) - 1)
                x = item_box.x + (item_box.boundaries[offset] if item_box.boundaries else 0.0)
            elif item_box is not None:
                x = item_box.x + (item_box.w if boundary.offset else 0.0)
            else:
                for child, dx, _dy in slot_box.children:
                    if child.node is boundary.node:
                        x = slot_box.x + dx + (child.w if boundary.offset else 0.0)
                        break
        else:
            x = slot_box.x + slot_box.w
        return QRectF(x - 0.6, slot_box.y, 1.2, max(14.0, slot_box.h))

    def _selection_rects(self, root_box: Box, small_font: QFont) -> list[QRectF]:
        if self.anchor is None:
            return []
        anchor_path, anchor_index = self.anchor
        if anchor_path != self.path:
            return []
        slot = self._resolve_slot()
        slot_box = self._find_box(root_box, slot)
        if slot_box is None:
            return []
        boundaries = _boundaries(slot)
        low, high = sorted((anchor_index, self.index))
        low = min(low, len(boundaries))
        high = min(high, len(boundaries))
        if low >= high:
            return []
        rects: list[QRectF] = []
        for position in range(low, high):
            boundary = boundaries[position]
            item_box = self._find_box(slot_box, boundary.node)
            if item_box is None:
                continue
            if boundary.kind == "text" and boundary.node is not None:
                start = min(boundary.offset, len(item_box.boundaries) - 1)
                end = start + 1
                x0 = item_box.x + item_box.boundaries[start]
                x1 = item_box.x + item_box.boundaries[min(end, len(item_box.boundaries) - 1)]
                rects.append(QRectF(x0, item_box.y, max(1.0, x1 - x0), item_box.h))
            else:
                rects.append(QRectF(item_box.x, item_box.y, item_box.w, item_box.h))
        return rects

    def _find_box(self, box: Box, node: MathNode) -> Box | None:
        if box.node is node:
            return box
        for child, _dx, _dy in box.children:
            found = self._find_box(child, node)
            if found is not None:
                return found
        return None

    # ------------------------------------------------------------------
    # Mouse
    # ------------------------------------------------------------------

    def mousePressEvent(self, event) -> None:  # type: ignore[no-untyped-def]
        if not self.finish_composition():
            event.accept()
            return
        self.setFocus()
        self._hit_test(event.position().x(), event.position().y())
        self.anchor = (deepcopy(self.path), self.index)
        self.update()

    def mouseMoveEvent(self, event) -> None:  # type: ignore[no-untyped-def]
        if not self.finish_composition():
            event.accept()
            return
        if self.anchor is None:
            return
        self._hit_test(event.position().x(), event.position().y())
        self.update()

    def _hit_test(self, x: float, y: float) -> None:
        _font, _small, _big, box = self._paint_layout()
        target = self._hit_box(box, x, y)
        if target is None:
            return
        if isinstance(target.node, MathSequence):
            self._jump_into_slot(id(target.node), 0 if x < target.x + target.w / 2 else len(_boundaries(target.node)))
            return
        slot = self._resolve_slot()
        slot_box = self._find_box(box, slot)
        if slot_box is None:
            return
        if target.kind == "text" and target.node is not None:
            best = 0
            local = x - target.x
            for index, boundary_x in enumerate(target.boundaries):
                if boundary_x <= local:
                    best = index
            boundaries = _boundaries(slot)
            for position, boundary in enumerate(boundaries):
                if boundary.node is target.node and boundary.kind == "text" and boundary.offset == best:
                    self.path = self._path_to_slot(slot)
                    self.index = position
                    return
        boundaries = _boundaries(slot)
        if target.node is not None:
            for position, boundary in enumerate(boundaries):
                if boundary.node is target.node:
                    self.path = self._path_to_slot(slot)
                    self.index = position + (1 if x > target.x + target.w / 2 else 0)
                    return
        self.index = len(boundaries)

    def _hit_box(self, box: Box, x: float, y: float) -> Box | None:
        if not (box.x <= x <= box.x + box.w and box.y <= y <= box.y + box.h):
            return None
        for child, _dx, _dy in box.children:
            hit = self._hit_box(child, x, y)
            if hit is not None:
                return hit
        return box

    def _path_to_slot(self, slot: MathSequence) -> list[tuple[str, int, int]]:
        new_path: list[tuple[str, int, int]] = [("root", 0, -1)]

        def find_slot(node: MathNode, path: list[tuple[str, int, int]], container_index: int) -> bool:
            if isinstance(node, MathSequence):
                if node is slot:
                    self.path = path
                    return True
                for item_index, item in enumerate(node.items):
                    if find_in_container(item, path, item_index):
                        return True
            return False

        def find_in_container(node: MathNode, path: list[tuple[str, int, int]], container_index: int) -> bool:
            if isinstance(node, Frac):
                return find_slot(node.numerator, [*path, ("frac_num", 0, container_index)], container_index) or find_slot(
                    node.denominator, [*path, ("frac_den", 0, container_index)], container_index
                )
            if isinstance(node, Sqrt):
                return find_slot(node.radicand, [*path, ("sqrt", 0, container_index)], container_index)
            if isinstance(node, Script):
                if find_slot(node.base, [*path, ("base", 0, container_index)], container_index):
                    return True
                if node.super is not None and find_slot(node.super, [*path, ("super", 0, container_index)], container_index):
                    return True
                if node.sub is not None and find_slot(node.sub, [*path, ("sub", 0, container_index)], container_index):
                    return True
                return False
            if isinstance(node, BigOp):
                if node.lower is not None and find_slot(node.lower, [*path, ("lower", 0, container_index)], container_index):
                    return True
                if node.upper is not None and find_slot(node.upper, [*path, ("upper", 0, container_index)], container_index):
                    return True
                return find_slot(node.body, [*path, ("body", 0, container_index)], container_index)
            if isinstance(node, Group):
                return find_slot(node.items, [*path, ("group", 0, container_index)], container_index)
            return False

        find_slot(self.root, new_path, -1)
        return self.path

    # ------------------------------------------------------------------
    # Keyboard
    # ------------------------------------------------------------------

    def event(self, event) -> bool:
        # QWidget otherwise consumes Tab before keyPressEvent can visit slots.
        if event.type() == QEvent.Type.KeyPress and event.key() in (Qt.Key.Key_Tab, Qt.Key.Key_Backtab):
            if not self.finish_composition():
                event.accept()
                return True
            self.commit_pending_command()
            self.cursor_tab(event.key() == Qt.Key.Key_Backtab or bool(event.modifiers() & Qt.KeyboardModifier.ShiftModifier))
            event.accept()
            return True
        result = super().event(event)
        if event.type() in (QEvent.Type.KeyPress, QEvent.Type.MouseButtonPress,
                            QEvent.Type.MouseMove, QEvent.Type.FocusIn, QEvent.Type.Resize):
            self._update_input_method()
        return result

    @_edit_operation
    def keyPressEvent(self, event: QKeyEvent) -> None:
        key = event.key()
        modifiers = event.modifiers()
        select = bool(modifiers & Qt.KeyboardModifier.ShiftModifier)
        if event.matches(QKeySequence.StandardKey.Copy):
            text = self.selected_latex()
            if text:
                QApplication.clipboard().setText(text)
            return
        if event.matches(QKeySequence.StandardKey.Cut):
            text = self.selected_latex()
            if text:
                QApplication.clipboard().setText(text)
                self._delete_selection()
            return
        if event.matches(QKeySequence.StandardKey.SelectAll):
            self.select_all()
            return
        if event.matches(QKeySequence.StandardKey.Undo):
            self.undo()
            return
        if event.matches(QKeySequence.StandardKey.Redo):
            self.redo()
            return
        if key in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
            self.commit_pending_command()
            return
        if key == Qt.Key.Key_Left:
            self.cursor_left(select)
            return
        if key == Qt.Key.Key_Right:
            self.cursor_right(select)
            return
        if key == Qt.Key.Key_Up:
            self.cursor_up(select)
            return
        if key == Qt.Key.Key_Down:
            self.cursor_down(select)
            return
        if key == Qt.Key.Key_Tab:
            self.cursor_tab()
            return
        if key in (Qt.Key.Key_Home, Qt.Key.Key_End):
            self.cursor_home(select) if key == Qt.Key.Key_Home else self.cursor_end(select)
            return
        if key == Qt.Key.Key_Backspace:
            self.delete_backspace()
            return
        if key == Qt.Key.Key_Delete:
            self.delete_forward()
            return
        if key == Qt.Key.Key_Z and modifiers & Qt.KeyboardModifier.ControlModifier:
            self.undo() if not (modifiers & Qt.KeyboardModifier.ShiftModifier) else self.redo()
            return
        if key == Qt.Key.Key_Y and modifiers & Qt.KeyboardModifier.ControlModifier:
            self.redo()
            return
        if key == Qt.Key.Key_V and modifiers & (
            Qt.KeyboardModifier.ControlModifier | Qt.KeyboardModifier.MetaModifier
        ):
            self.paste_clipboard(QApplication.clipboard().text())
            return
        if key == Qt.Key.Key_A and modifiers & Qt.KeyboardModifier.ControlModifier:
            self.select_all()
            return
        if key == Qt.Key.Key_Escape:
            self.anchor = None
            self._pending_command = ""
            self.update()
            return
        text = event.text()
        if text and not (modifiers & (Qt.KeyboardModifier.ControlModifier | Qt.KeyboardModifier.MetaModifier)):
            self.type_key(text)


def _child_roles(node: MathNode) -> list[str]:
    if isinstance(node, Frac):
        return ["frac_num", "frac_den"]
    if isinstance(node, Sqrt):
        return ["sqrt"]
    if isinstance(node, Script):
        roles = ["base", "super", "sub"]
        return [role for role in roles if _slot_of(node, role) is not None]
    if isinstance(node, BigOp):
        roles: list[str] = []
        for role in ("lower", "upper", "body"):
            if _slot_of(node, role) is not None:
                roles.append(role)
        return roles
    if isinstance(node, Group):
        return ["group"]
    return []
