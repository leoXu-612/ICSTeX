"""The small writing exercise: owned project creation and plain-title recognition."""
from __future__ import annotations

from enum import IntEnum
from pathlib import Path
import re
from uuid import uuid4

from app.core.latex_insertions import TEMPLATES
from app.core.project_dependencies import safe_project_input
from app.core.project_profile import ProjectProfile
from app.core.project_tools import ProjectInitSpec, initialize_project

TEMPLATE_KEY = "chinese_xelatex_article"
EXAMPLE_PREFIX = "writing-example-"
TITLE = re.compile(r"^[ \t]*\\title\{([^{}\n]*)\}", re.MULTILINE)
INITIAL_TITLE = TITLE.search(TEMPLATES[TEMPLATE_KEY].text).group(1)


class TutorialStep(IntEnum):
    EDIT = 1
    COMPILE = 2
    VIEW = 3
    DONE = 4


def title_span(text: str) -> tuple[int, int] | None:
    """Python indexes of the exercise's plain, single-line title; not a TeX parser."""
    match = TITLE.search(text)
    return match.span(1) if match else None


def tutorial_step(text: str, *, manual_requested: bool, current_pdf: bool,
                  acknowledged: bool) -> TutorialStep:
    span = title_span(text)
    title = text[slice(*span)].strip() if span else ""
    if not title or title == INITIAL_TITLE:
        return TutorialStep.EDIT
    if not manual_requested or not current_pdf:
        return TutorialStep.COMPILE
    return TutorialStep.DONE if acknowledged else TutorialStep.VIEW


def create_example(base: Path) -> Path:
    """Create a fresh project with the existing no-overwrite transaction."""
    base.mkdir(parents=True, exist_ok=True)
    return initialize_project(ProjectInitSpec(
        parent_dir=base, project_name=EXAMPLE_PREFIX + uuid4().hex[:10],
        template_key=TEMPLATE_KEY,
        profile=ProjectProfile(template=TEMPLATE_KEY, engine="xelatex"),
    )).tex_file


def existing_example(base: Path, value: object) -> Path | None:
    """Accept only a regular main file in a direct, non-symlink exercise directory."""
    if not isinstance(value, str) or not value:
        return None
    try:
        base = base.resolve()
        path = safe_project_input(base, Path(value))
        if (path is not None and path.name == "main.tex" and path.parent.parent == base
                and path.parent.name.startswith(EXAMPLE_PREFIX) and path.is_file()):
            return path
    except (OSError, ValueError):
        pass
    return None
