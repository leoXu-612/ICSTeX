from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from pathlib import Path

from app.core.runtime_paths import which_tool


class LaTeXEngine(str, Enum):
    AUTO = "auto"
    PDFLATEX = "pdflatex"
    XELATEX = "xelatex"
    LUALATEX = "lualatex"

    @property
    def display_name(self) -> str:
        return {
            LaTeXEngine.AUTO: "Auto",
            LaTeXEngine.PDFLATEX: "pdfLaTeX",
            LaTeXEngine.XELATEX: "XeLaTeX",
            LaTeXEngine.LUALATEX: "LuaLaTeX",
        }[self]


@dataclass(frozen=True)
class LaTeXToolchain:
    latexmk: str | None
    pdflatex: str | None
    xelatex: str | None = None
    lualatex: str | None = None
    biber: str | None = None
    bibtex: str | None = None
    texcount: str | None = None
    synctex: str | None = None

    @property
    def compiler(self) -> str | None:
        return self.latexmk or self.pdflatex or self.xelatex or self.lualatex

    @property
    def compiler_name(self) -> str | None:
        if self.latexmk:
            return "latexmk"
        if self.pdflatex:
            return "pdflatex"
        if self.xelatex:
            return "xelatex"
        if self.lualatex:
            return "lualatex"
        return None

    @property
    def is_compile_ready(self) -> bool:
        return self.compiler is not None

    @property
    def missing_compile_message(self) -> str:
        return (
            "未找到 LaTeX 编译器。请先安装 MacTeX、TeX Live 或 MiKTeX，"
            "并确认 latexmk 或 pdflatex 可以在 PATH 中被找到。"
        )

    def compile_command(
        self,
        root_file: Path,
        output_dir: Path,
        engine: LaTeXEngine | str = LaTeXEngine.AUTO,
    ) -> list[str]:
        selected_engine = LaTeXEngine(engine)
        if self.latexmk:
            return [
                self.latexmk,
                "-norc",
                self._latexmk_engine_flag(selected_engine),
                "-no-shell-escape",
                "-synctex=1",
                "-interaction=nonstopmode",
                "-file-line-error",
                f"-outdir={output_dir}",
                str(root_file),
            ]
        executable = self._direct_engine_executable(selected_engine)
        if executable:
            return [
                executable,
                "-no-shell-escape",
                "-synctex=1",
                "-interaction=nonstopmode",
                "-halt-on-error",
                "-file-line-error",
                f"-output-directory={output_dir}",
                str(root_file),
            ]
        raise RuntimeError(self.missing_compile_message)

    def supports_engine(self, engine: LaTeXEngine | str) -> bool:
        selected_engine = LaTeXEngine(engine)
        if selected_engine == LaTeXEngine.AUTO:
            return self.is_compile_ready
        if self.latexmk:
            return self._direct_engine_executable(selected_engine) is not None
        return self._direct_engine_executable(selected_engine) is not None

    def _latexmk_engine_flag(self, engine: LaTeXEngine) -> str:
        if engine == LaTeXEngine.XELATEX:
            return "-xelatex"
        if engine == LaTeXEngine.LUALATEX:
            return "-lualatex"
        return "-pdf"

    def _direct_engine_executable(self, engine: LaTeXEngine) -> str | None:
        if engine in (LaTeXEngine.AUTO, LaTeXEngine.PDFLATEX):
            return self.pdflatex
        if engine == LaTeXEngine.XELATEX:
            return self.xelatex
        if engine == LaTeXEngine.LUALATEX:
            return self.lualatex
        return None


def detect_toolchain() -> LaTeXToolchain:
    return LaTeXToolchain(
        latexmk=which_tool("latexmk"),
        pdflatex=which_tool("pdflatex"),
        xelatex=which_tool("xelatex"),
        lualatex=which_tool("lualatex"),
        biber=which_tool("biber"),
        bibtex=which_tool("bibtex"),
        texcount=which_tool("texcount"),
        synctex=which_tool("synctex"),
    )
