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
import re

from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import QColor, QFont, QFontMetricsF, QKeyEvent, QPainter, QPen
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


_CARET = QColor(35, 110, 200)
_SELECTION = QColor(170, 205, 245, 130)
_SLOT_HINT = QColor(160, 160, 160, 90)
_TEXT = QColor(30, 30, 30)
_BACKGROUND = QColor(255, 255, 255)
_TRAILING_TOKEN = re.compile(r"[A-Za-z0-9]+$")


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


class MathEditorWidget(QWidget):
    """A WYSIWYG math draft editor backed by ``MathSequence`` trees."""

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.root: MathSequence = MathSequence()
        self.path: list[tuple[str, int, int]] = [("root", 0, -1)]
        self.index = 0
        self.anchor: tuple[list[tuple[str, int, int]], int] | None = None
        self._undo: list[tuple[MathSequence, list[tuple[str, int, int]], int]] = []
        self._redo: list[tuple[MathSequence, list[tuple[str, int, int]], int]] = []
        self._pending_command = ""
        self.setMinimumHeight(90)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def set_latex(self, text: str) -> None:
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

        self._push_history()
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

    def insert_text(self, text: str) -> None:
        """Insert plain characters at the cursor (one at a time)."""

        if not text:
            return
        self._push_history()
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

    def paste_clipboard(self, text: str) -> None:
        """Paste LaTeX or plain text at the cursor.

        A pasted text that is exactly one supported formula wrapper (``$...$``,
        ``\\(...\\)``, ``\\[...\\]``, equation, equation*) is inserted with its
        wrapper stripped: the dialog's formula mode owns the outer wrapper.
        Unsupported or malformed content is preserved losslessly through the
        math parser. Newlines and tabs are collapsed to spaces (mathematics
        ignores whitespace, and the visual editor renders single-line).
        """

        if not text:
            return
        cleaned = (
            text.replace("\r\n", " ")
            .replace("\r", " ")
            .replace("\n", " ")
            .replace("\t", " ")
            .strip()
        )
        if not cleaned:
            return
        envelope = recognize_formula(cleaned)
        body = envelope.body if envelope is not None else cleaned

        if self.anchor is not None:
            self._delete_selection()  # pushes history
        else:
            self._push_history()

        slot, boundary_index = self._current_slot_and_index()
        boundary = self._boundary_at(slot, boundary_index)
        insert_index = self._split_text_at(slot, boundary)
        parsed = parse_math_latex(body)
        slot.items[insert_index:insert_index] = parsed.items
        if parsed.items:
            last_index = insert_index + len(parsed.items) - 1
            self.index = self._boundary_after(slot, last_index)
        else:
            self.index = boundary_index
        self.anchor = None
        self._pending_command = ""
        self.update()

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

    def cursor_left(self) -> None:
        self._move_horizontal(-1)

    def cursor_right(self) -> None:
        self._move_horizontal(1)

    def cursor_up(self) -> None:
        self._move_vertical(-1)

    def cursor_down(self) -> None:
        self._move_vertical(1)

    def cursor_tab(self) -> None:
        slots = self._all_slots()
        current = self._resolve_slot()
        try:
            current_index = slots.index(id(current))
        except ValueError:
            return
        next_slot = slots[(current_index + 1) % len(slots)]
        self._jump_into_slot(next_slot, 0)

    def cursor_home(self) -> None:
        self.index = 0
        self.update()

    def cursor_end(self) -> None:
        slot = self._resolve_slot()
        self.index = len(_boundaries(slot))
        self.update()

    def delete_backspace(self) -> None:
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

    def undo(self) -> None:
        if not self._undo:
            return
        self._redo.append(self._snapshot())
        root, path, index = self._undo.pop()
        self.root, self.path, self.index = root, path, index
        self.anchor = None
        self._pending_command = ""
        self.update()

    def redo(self) -> None:
        if not self._redo:
            return
        self._undo.append(self._snapshot())
        root, path, index = self._redo.pop()
        self.root, self.path, self.index = root, path, index
        self.anchor = None
        self._pending_command = ""
        self.update()

    def select_all(self) -> None:
        self.anchor = ([("root", 0, -1)], 0)
        self.path = [("root", 0, -1)]
        self.index = len(_boundaries(self.root))
        self.update()

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
        self.index = container_index + (1 if direction > 0 else 0)
        self._clamp()

    def _move_horizontal(self, direction: int) -> None:
        self._push_anchor()
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

    def _move_vertical(self, direction: int) -> None:
        if len(self.path) < 2:
            return
        self._push_anchor()
        role = self.path[-1][0]
        if role == "frac_num" and direction > 0:
            self._switch_role("frac_den")
        elif role == "frac_den" and direction < 0:
            self._switch_role("frac_num")
        elif role in ("super", "sub"):
            other = "sub" if role == "super" else "super"
            if self._sibling_slot(other) is not None:
                self._switch_role(other)
        elif role == "base":
            target = "super" if direction > 0 else "sub"
            if self._sibling_slot(target) is not None:
                self._switch_role(target)
        self.update()

    def _switch_role(self, role: str) -> None:
        slot = self._resolve_slot()
        old_index = self.index
        self.path[-1] = (role, 0, self.path[-1][2])
        self._clamp()
        self.index = min(old_index, len(_boundaries(self._resolve_slot())))

    def _sibling_slot(self, role: str) -> MathSequence | None:
        container_index = self.path[-1][2]
        parent_slot = self._resolve_parent_slot()
        if parent_slot is None:
            return None
        container = parent_slot.items[container_index]
        return _slot_of(container, role)

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

    def _delete_selection(self) -> bool:
        if self.anchor is None:
            return False
        anchor_path, anchor_index = self.anchor
        if anchor_path != self.path:
            self.anchor = None
            self.update()
            return False
        low, high = sorted((anchor_index, self.index))
        if low == high:
            self.anchor = None
            return False
        self._push_history()
        slot = self._resolve_slot()
        boundaries = _boundaries(slot)
        if low >= len(boundaries):
            self.anchor = None
            return False
        first = boundaries[low]
        last = boundaries[high - 1] if high - 1 < len(boundaries) else boundaries[-1]
        start_item = first.item_index
        end_item = last.item_index
        if first.kind == "text" and first.node is not None and first.offset > 0:
            first.node.text = first.node.text[: first.offset]
            start_item += 1
        if last.kind == "text" and last.node is not None and last.offset < len(last.node.text) and last.item_index >= start_item:
            last.node.text = last.node.text[last.offset :]
            end_item -= 1
        del slot.items[start_item : end_item + 1]
        self.index = low
        self.anchor = None
        self._clamp()
        self.update()
        return True

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
        if not pending.startswith("\\") or len(pending) < 2:
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

        font = QFont("Menlo", 15)
        font.setStyleHint(QFont.StyleHint.Monospace)
        small_font = QFont(font)
        small_font.setPointSizeF(max(9.0, font.pointSizeF() * 0.72))
        big_font = QFont(font)
        big_font.setPointSizeF(font.pointSizeF() * 1.6)

        fm = QFontMetricsF(font)
        small_fm = QFontMetricsF(small_font)
        big_fm = QFontMetricsF(big_font)

        box = self._measure(self.root, fm, small_fm, big_fm)
        self._place(box, 10, 10)
        self._draw(painter, box, font, small_font, big_font)

        # Caret and selection overlay.
        selection_rects = self._selection_rects(box, small_font)
        for rect in selection_rects:
            painter.fillRect(rect, _SELECTION)
        caret_rect = self._caret_rect(box, font)
        if caret_rect is not None:
            painter.fillRect(caret_rect, _CARET)

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
            pad = 3.0
            width = max(num.w, den.w) + pad * 2
            height = num.h + rule + den.h
            baseline = num.h + rule / 2
            box = Box("frac", width, height, baseline, node=node)
            box.children = [
                (num, (width - num.w) / 2, 0),
                (den, (width - den.w) / 2, num.h + rule),
            ]
            return box
        if isinstance(node, Sqrt):
            rad = self._measure(node.radicand, fm, small_fm, big_fm)
            radical = fm.horizontalAdvance("√") * 1.25
            over = 2.0
            width = radical + rad.w + 2
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
            width = base.w + side_w
            height = max(base.h, (sup.h if sup else 0.0) + (sub.h if sub else 0.0))
            baseline = base.baseline
            box = Box("script", width, height, baseline, node=node)
            box.children = [(base, 0, 0)]
            if sup is not None:
                box.children.append((sup, base.w, 0))
            if sub is not None:
                box.children.append((sub, base.w, height - sub.h))
            return box
        if isinstance(node, BigOp):
            symbol = {"sum": "∑", "int": "∫", "lim": "lim"}.get(node.symbol, node.symbol)
            op_fm = big_fm if node.symbol in ("sum", "int") else fm
            op_box = self._text_box(symbol, node, op_fm)
            lower = self._measure(node.lower, small_fm, small_fm, big_fm) if node.lower is not None else None
            upper = self._measure(node.upper, small_fm, small_fm, big_fm) if node.upper is not None else None
            body = self._measure(node.body, fm, small_fm, big_fm)
            limits_h = (upper.h if upper else 0.0) + (lower.h if lower else 0.0)
            width = op_box.w + 3 + body.w
            height = max(limits_h + op_box.h, body.h, op_box.h)
            baseline = (upper.h if upper else 0.0) + op_box.baseline
            box = Box("bigop", width, height, baseline, node=node)
            op_y = upper.h if upper else 0.0
            box.children = [(op_box, 0, op_y)]
            if upper is not None:
                box.children.append((upper, max(0.0, (op_box.w - upper.w) / 2), 0))
            if lower is not None:
                box.children.append((lower, max(0.0, (op_box.w - lower.w) / 2), op_y + op_box.h))
            box.children.append((body, op_box.w + 3, (height - body.h) / 2))
            return box
        raise TypeError(f"unknown node: {type(node).__name__}")

    @staticmethod
    def _text_box(text: str, node: MathNode, fm: QFontMetricsF) -> Box:
        if not text:
            return Box("empty", 3.0, fm.height(), fm.ascent(), node=node)
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
            return Box("empty", 3.0, 20.0, 15.0, node=node)
        spacing = 1.0
        width = sum(child.w for child in children) + spacing * (len(children) - 1)
        height = max(child.h for child in children)
        baseline = max(child.baseline for child in children)
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
            rule_y = box.y + box.h - box.baseline
            painter.drawLine(QPointF(box.x, rule_y), QPointF(box.x + box.w, rule_y))
        elif box.kind == "sqrt":
            painter.setFont(font)
            painter.setPen(QPen(_TEXT))
            painter.drawText(QPointF(box.x, box.y + box.baseline), "√")
            painter.drawLine(
                QPointF(box.x + box.children[0][1] - 1, box.y + 1),
                QPointF(box.x + box.w, box.y + 1),
            )
        elif box.kind == "bigop":
            painter.setFont(big_font if box.node is not None and box.node.symbol in ("sum", "int") else font)
            painter.setPen(QPen(_TEXT))
            painter.drawText(QPointF(box.x, box.y + box.baseline), {"sum": "∑", "int": "∫", "lim": "lim"}.get(box.node.symbol, box.node.symbol))
        for child, _dx, _dy in box.children:
            self._draw(painter, child, font, small_font, big_font)

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
        self.setFocus()
        self._hit_test(event.position().x(), event.position().y())
        self.anchor = (deepcopy(self.path), self.index)
        self.update()

    def mouseMoveEvent(self, event) -> None:  # type: ignore[no-untyped-def]
        if self.anchor is None:
            return
        self._hit_test(event.position().x(), event.position().y())
        self.update()

    def _hit_test(self, x: float, y: float) -> None:
        font = QFont("Menlo", 15)
        small_font = QFont(font)
        small_font.setPointSizeF(max(9.0, font.pointSizeF() * 0.72))
        big_font = QFont(font)
        big_font.setPointSizeF(font.pointSizeF() * 1.6)
        fm = QFontMetricsF(font)
        box = self._measure(self.root, fm, QFontMetricsF(small_font), QFontMetricsF(big_font))
        self._place(box, 10, 10)
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

    def keyPressEvent(self, event: QKeyEvent) -> None:
        key = event.key()
        modifiers = event.modifiers()
        if key == Qt.Key.Key_Left:
            self.cursor_left()
            return
        if key == Qt.Key.Key_Right:
            self.cursor_right()
            return
        if key == Qt.Key.Key_Up:
            self.cursor_up()
            return
        if key == Qt.Key.Key_Down:
            self.cursor_down()
            return
        if key == Qt.Key.Key_Tab:
            self.cursor_tab()
            return
        if key in (Qt.Key.Key_Home, Qt.Key.Key_End):
            self.cursor_home() if key == Qt.Key.Key_Home else self.cursor_end()
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
        if text:
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
