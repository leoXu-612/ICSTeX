"""Fail-closed, local-development macOS isolation for restricted TeX jobs.

Uses the deprecated sandbox-exec/SBPL interface, not an App Sandbox entitlement.
Only standard, installed TeX Live trees are supported. No unconfined fallback.
"""
from __future__ import annotations

from contextlib import contextmanager
from dataclasses import dataclass
import json
import os
from pathlib import Path
import stat
import subprocess
from tempfile import TemporaryDirectory
from typing import Iterator

from app.core.latex_tools import LaTeXEngine, LaTeXToolchain


SANDBOX_EXEC = Path("/usr/bin/sandbox-exec")
TEXLIVE_PARENT = Path("/usr/local/texlive")
GUARD_TIMEOUT_SECONDS = 5.0


@dataclass(frozen=True)
class SandboxLaunch:
    command: list[str]
    environment: dict[str, str]


def _installed_tool(path: str | Path, texroot: Path) -> Path:
    supplied = Path(path)
    resolved = supplied.resolve(strict=True)
    if (not supplied.is_absolute() or not resolved.is_relative_to(texroot)
            or not resolved.is_file() or not os.access(resolved, os.X_OK)):
        raise OSError("Restricted macOS compilation requires installed TeX Live tools")
    return resolved


def _tool_paths(toolchain: LaTeXToolchain, engine: LaTeXEngine) -> tuple[Path, Path, tuple[Path, ...]]:
    selected = toolchain._direct_engine_executable(engine)
    if not selected:
        raise OSError("Restricted macOS compilation requires an explicit installed engine")
    executable = Path(selected).resolve(strict=True)
    # Standard MacTeX/TeX Live layout: <year>/bin/<architecture>/<engine>.
    binary_dir = executable.parent
    texroot = binary_dir.parent.parent
    if (binary_dir.parent.name != "bin" or texroot.parent != TEXLIVE_PARENT.resolve()
            or not (texroot / "texmf-dist").is_dir()):
        raise OSError("Restricted macOS compilation supports /usr/local/texlive installations only")
    programs = {_installed_tool(selected, texroot)}
    for candidate in (toolchain.latexmk, toolchain.bibtex, toolchain.biber):
        if candidate:
            programs.add(_installed_tool(candidate, texroot))
    if toolchain.latexmk:
        programs.add(_installed_tool(binary_dir / "kpsewhich", texroot))
    if engine is LaTeXEngine.XELATEX:
        programs.add(_installed_tool(binary_dir / "xdvipdfmx", texroot))
    # latexmk uses Perl and may invoke its allowed children through sh/env.
    # No executable project/output path or general /usr/bin grant is allowed.
    programs.update(Path(p) for p in ("/bin/sh", "/bin/bash", "/bin/pwd", "/usr/bin/env", "/usr/bin/perl"))
    programs.update(Path("/usr/bin").glob("perl5.[0-9]*"))
    return texroot, binary_dir, tuple(sorted(programs))


def _rule(operation: str, paths: tuple[Path, ...], matcher: str) -> str:
    filters = " ".join(f"({matcher} {json.dumps(str(p), ensure_ascii=False)})" for p in paths)
    return f"(allow {operation} {filters})"


def _profile(*, readable: tuple[Path, ...], writable: tuple[Path, ...],
             programs: tuple[Path, ...], texroot: Path) -> str:
    system = tuple(Path(p) for p in ("/System", "/usr/lib", "/usr/share", "/Library/Fonts"))
    devices = tuple(Path(p) for p in ("/dev/null", "/dev/random", "/dev/urandom"))
    return "\n".join((
        '(version 1)', '(deny default)', '(import "dyld-support.sb")',
        '(allow process-fork)',
        _rule("process-exec", programs, "literal"),
        _rule("file-read*", (*system, texroot, *readable, *writable), "subpath"),
        _rule("file-read*", (*programs, *devices), "literal"),
        _rule("file-map-executable", (Path("/System"), Path("/usr/lib"), texroot), "subpath"),
        _rule("file-map-executable", programs, "literal"),
        '(allow file-read-metadata)',
        _rule("file-write*", writable, "subpath"),
        '(allow file-write-data (literal "/dev/null"))',
        '(allow sysctl-read)', '(allow signal (target self))',
    ))


_GUARD = r'''
use strict; use warnings; use Cwd qw(getcwd cwd);
my ($input, $denied, $link, $output, $write_link, $cwd) = @ARGV;
die "cwd boundary" unless getcwd() eq $cwd && cwd() eq $cwd;
sub opened { my ($path, $mode) = @_; my $ok = open(my $f, $mode, $path);
  close($f) if $ok; return $ok ? 1 : 0; }
die "read boundary" unless opened($input, '<') && !opened($denied, '<') && !opened($link, '<');
die "write boundary" unless opened($output, '>') && !opened($input, '>>')
  && !opened($denied, '>>') && !opened($write_link, '>>');
die "exec boundary" if system('/usr/bin/true') == 0;
print "ICSTEX_SANDBOX_GUARD_OK\n";
'''


def _verify_kernel(profile: str, environment: dict[str, str], guard: Path, cwd: Path) -> None:
    readonly, writable = guard / "read", guard / "write"
    readonly.mkdir()
    writable.mkdir()
    source, denied = readonly / "input", guard / "denied"
    source.write_bytes(b"synthetic readonly input")
    denied.write_bytes(b"synthetic denied input")
    (readonly / "link").symlink_to(denied)
    (writable / "link").symlink_to(source)
    try:
        result = subprocess.run(
            [str(SANDBOX_EXEC), "-p", profile, "/usr/bin/perl", "-e", _GUARD,
             str(source), str(denied), str(readonly / "link"),
             str(writable / "output"), str(writable / "link"), str(cwd)],
            cwd=cwd, env=environment, stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
            encoding="utf-8", errors="replace", close_fds=True,
            timeout=GUARD_TIMEOUT_SECONDS,
        )
    except subprocess.TimeoutExpired as exc:
        raise OSError("macOS sandbox capability check timed out; compilation refused") from exc
    if result.returncode or result.stdout != "ICSTEX_SANDBOX_GUARD_OK\n":
        raise OSError("macOS sandbox capability check failed; compilation refused: " + result.stderr[-2000:])


@contextmanager
def macos_sandbox_launch(
    command: list[str], *, toolchain: LaTeXToolchain, engine: LaTeXEngine,
    project_scope: Path, root_file: Path, output_dir: Path,
    overlay_dir: Path | None = None,
) -> Iterator[SandboxLaunch]:
    if not SANDBOX_EXEC.is_file() or not os.access(SANDBOX_EXEC, os.X_OK):
        raise OSError("macOS sandbox-exec is unavailable; restricted compilation refused")
    scope = project_scope.resolve(strict=True)
    root = root_file.resolve(strict=True)
    output = output_dir.resolve(strict=True)
    texroot, binary_dir, programs = _tool_paths(toolchain, engine)
    if (not root.is_relative_to(scope) or not output.is_relative_to(scope)
            or root.is_relative_to(output) or scope == output
            or scope.is_relative_to(texroot) or texroot.is_relative_to(scope)):
        raise OSError("Unsafe project/output scope for restricted macOS compilation")
    if Path(command[0]).resolve(strict=True) not in programs:
        raise OSError("Compile command is not an allowed installed tool")
    if overlay_dir is not None and not overlay_dir.resolve(strict=True).is_relative_to(scope):
        raise OSError("Preview overlay is outside the restricted project")
    # Existing hardlinks in a writable output directory can alias readonly input
    # inodes. Kernel path isolation alone cannot protect that pre-existing alias.
    def fail_walk(error: OSError) -> None:
        raise error
    for parent, _, files in os.walk(output, followlinks=False, onerror=fail_walk):
        for name in files:
            info = (Path(parent) / name).lstat()
            if stat.S_ISREG(info.st_mode) and info.st_nlink > 1:
                raise OSError("Hardlinked build output is unsafe; restricted compilation refused")
    cache = output / ".sandbox-cache"
    if cache.is_symlink():
        raise OSError("Sandbox cache must not be a symbolic link")
    cache.mkdir(exist_ok=True)
    with TemporaryDirectory(prefix="icstex-sandbox-") as directory:
        guard = Path(directory).resolve()
        if guard.is_relative_to(scope):
            raise OSError("Project scope includes the sandbox guard; compilation refused")
        temporary = guard / "tmp"
        temporary.mkdir()
        home = guard / "home"
        home.mkdir()
        environment = {
            "PATH": os.pathsep.join((str(binary_dir), "/usr/bin", "/bin")),
            "LANG": "en_US.UTF-8", "USER": "icstex", "HOME": str(home), "TMPDIR": str(temporary),
            "TEXMFVAR": str(cache), "TEXMFCACHE": str(cache), "PAR_TMPDIR": str(temporary),
            "openin_any": "p", "openout_any": "p",
        }
        if overlay_dir is not None:
            environment["TEXINPUTS"] = str(overlay_dir.resolve()) + os.pathsep
        profile = _profile(
            readable=(scope, home, guard / "read"),
            writable=(output, temporary, guard / "write"), programs=programs, texroot=texroot,
        )
        _verify_kernel(profile, environment, guard, root.parent)
        # Only the verified OS boundary permits absolute distribution reads.
        # Never return this policy with an unwrapped command.
        environment["openin_any"] = "a"
        yield SandboxLaunch([str(SANDBOX_EXEC), "-p", profile, *command], environment)
