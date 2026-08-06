#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
DIST_DIR="$ROOT_DIR/dist"
BUILD_DIR="$ROOT_DIR/build"
STAGE_DIR="$DIST_DIR/ICSTeX-dmg"
APP_PATH="$DIST_DIR/ICSTeX.app"
APP_VERSION="$(python3 -c 'from app import __version__; print(__version__)')"
VERSIONED_DMG_PATH="$DIST_DIR/ICSTeX-$APP_VERSION.dmg"
DMG_PATH="$DIST_DIR/ICSTeX.dmg"

cd "$ROOT_DIR"
export PYINSTALLER_CONFIG_DIR="${PYINSTALLER_CONFIG_DIR:-$BUILD_DIR/pyinstaller-config}"
export PIP_CACHE_DIR="${PIP_CACHE_DIR:-$BUILD_DIR/pip-cache}"

python3 packaging/install_build_dependencies.py
python3 -m PyInstaller packaging/ICSTeX.spec --noconfirm

rm -rf "$STAGE_DIR" "$DMG_PATH" "$VERSIONED_DMG_PATH"
mkdir -p "$STAGE_DIR"
ditto --noextattr --noqtn "$APP_PATH" "$STAGE_DIR/ICSTeX.app"
xattr -cr "$STAGE_DIR/ICSTeX.app"
codesign --verify --deep --strict "$STAGE_DIR/ICSTeX.app"
cp "$ROOT_DIR/packaging/README_macOS.md" "$STAGE_DIR/README.md"
cp "$ROOT_DIR/CHANGELOG.md" "$STAGE_DIR/CHANGELOG.md"
ln -s /Applications "$STAGE_DIR/Applications"

for required in "$STAGE_DIR/ICSTeX.app" "$STAGE_DIR/README.md" "$STAGE_DIR/CHANGELOG.md" "$STAGE_DIR/Applications"; do
  if [[ ! -e "$required" ]]; then
    echo "Missing DMG item: $required" >&2
    exit 1
  fi
done

if ! hdiutil create \
    -volname "ICSTeX" \
    -srcfolder "$STAGE_DIR" \
    -ov \
    -format UDZO \
    "$VERSIONED_DMG_PATH"; then
  echo "DMG creation failed. Run this script from a normal macOS Terminal session" >&2
  echo "with permission to attach disk images; no unsafe hybrid fallback was created." >&2
  exit 1
fi

cp "$VERSIONED_DMG_PATH" "$DMG_PATH"

echo "Built $APP_PATH"
echo "Built $VERSIONED_DMG_PATH"
echo "Updated latest alias $DMG_PATH"
du -h "$VERSIONED_DMG_PATH" "$DMG_PATH"
