# Build with:
#   pyinstaller packaging/ICSTeX.spec --noconfirm

from pathlib import Path
import re


ROOT = Path(SPECPATH).parent
APP_INIT = (ROOT / "app" / "__init__.py").read_text(encoding="utf-8")
APP_VERSION = re.search(r'__version__\s*=\s*"([^"]+)"', APP_INIT).group(1)


a = Analysis(
    [str(ROOT / "app" / "__main__.py")],
    pathex=[str(ROOT)],
    binaries=[],
    datas=[(str(ROOT / "app" / "assets"), "app/assets")],
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
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
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

app = BUNDLE(
    coll,
    name="ICSTeX.app",
    icon=str(ROOT / "packaging" / "assets" / "ICSTeX.icns"),
    bundle_identifier="com.icstex.app",
    info_plist={
        "CFBundleDisplayName": "ICSTeX",
        "CFBundleName": "ICSTeX",
        "CFBundleShortVersionString": APP_VERSION,
        "CFBundleVersion": APP_VERSION,
        "NSRequiresAquaSystemAppearance": True,
    },
)
