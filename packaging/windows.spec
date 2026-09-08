# Build on Windows with:
#   pyinstaller packaging\windows.spec --noconfirm

from pathlib import Path
import runpy


ROOT = Path(SPECPATH).parent
UPDATES = runpy.run_path(str(ROOT / "packaging" / "native_updates.py"))
UPDATE_RUNTIME, UPDATE_CONFIG = UPDATES["runtime_from_environment"]()


a = Analysis(
    [str(ROOT / "app" / "__main__.py")],
    pathex=[str(ROOT)],
    binaries=[(str(UPDATE_RUNTIME / "updates" / "WinSparkle.dll"), "updates")] if UPDATE_RUNTIME else [],
    datas=[(str(ROOT / "app" / "assets"), "app/assets"), *UPDATES["runtime_datas"](UPDATE_RUNTIME)],
    hiddenimports=[
        "PySide6.QtPdf",
        "PySide6.QtPdfWidgets",
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="ICSTeX",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=str(ROOT / "packaging" / "assets" / "ICSTeX.ico"),
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name="ICSTeX",
)
