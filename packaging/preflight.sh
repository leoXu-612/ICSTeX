#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

APP_VERSION="$(python3 -c 'from app import __version__; print(__version__)')"
PYPROJECT_VERSION="$(python3 -c 'import tomllib; print(tomllib.load(open("pyproject.toml", "rb"))["project"]["version"])')"

echo "ICSTeX preflight"
echo "App version: $APP_VERSION"

if [[ "$APP_VERSION" != "$PYPROJECT_VERSION" ]]; then
  echo "Version mismatch: app=$APP_VERSION pyproject=$PYPROJECT_VERSION" >&2
  exit 1
fi

grep -Fq "Current version: $APP_VERSION" README.md
grep -Fq "版本：$APP_VERSION" packaging/README_macOS.md
grep -Fq "版本：$APP_VERSION" packaging/README_windows.md
grep -Fq "Current app version: **$APP_VERSION**" CLAUDE.md
grep -Fq "__version__ = \"$APP_VERSION\"" app/__init__.py
grep -Fq "#define MyAppVersion \"$APP_VERSION\"" packaging/installer_windows.iss
grep -Fq '"CFBundleShortVersionString": APP_VERSION' packaging/ICSTeX.spec
grep -Fq '"CFBundleVersion": APP_VERSION' packaging/ICSTeX.spec
grep -Fq "ICSTeX-$APP_VERSION.dmg" README.md
grep -Fq "## $APP_VERSION" CHANGELOG.md
grep -Fq "更新：" CHANGELOG.md

python3 -m compileall -q app tests packaging/install_build_dependencies.py
python3 -m unittest discover -s tests

if [[ -f "dist/ICSTeX-$APP_VERSION.dmg" ]]; then
  echo "Found versioned DMG: dist/ICSTeX-$APP_VERSION.dmg"
else
  echo "No versioned DMG for $APP_VERSION yet. Build with: bash packaging/build_macos.sh"
fi

if [[ -f "dist/ICSTeX.dmg" ]]; then
  echo "Found latest DMG alias: dist/ICSTeX.dmg"
fi

FOUND_WINDOWS_ARTIFACT=false
for WINDOWS_ARCH in x64 arm64; do
  WINDOWS_ZIP="dist/ICSTeX-$APP_VERSION-Windows-$WINDOWS_ARCH.zip"
  if [[ -f "$WINDOWS_ZIP" ]]; then
    echo "Found versioned Windows $WINDOWS_ARCH ZIP: $WINDOWS_ZIP"
    echo "Verify it on matching Windows hardware before distributing version $APP_VERSION."
    FOUND_WINDOWS_ARTIFACT=true
  fi
done

if [[ "$FOUND_WINDOWS_ARTIFACT" == false && -f "dist/ICSTeX-Windows.zip" ]]; then
  echo "Found only an unversioned Windows ZIP; it may be stale: dist/ICSTeX-Windows.zip"
  echo "Rebuild it on Windows to create an architecture-specific versioned ZIP."
elif [[ "$FOUND_WINDOWS_ARTIFACT" == false && -f "ICSTeX-Windows.zip" ]]; then
  echo "Found only a root-level unversioned Windows ZIP; it may be stale: ICSTeX-Windows.zip"
  echo "Rebuild it on Windows to create an architecture-specific versioned ZIP."
fi

echo "Preflight passed."
