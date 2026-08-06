@echo off
setlocal

set ROOT_DIR=%~dp0..
cd /d "%ROOT_DIR%"

echo Building ICSTeX for Windows...
echo Project root: %CD%
echo.

for /f "usebackq delims=" %%V in (`python -c "from app import __version__; print(__version__)"`) do set APP_VERSION=%%V
if not defined APP_VERSION (
  echo Could not read ICSTeX version from app package.
  goto :fail
)
set VERSIONED_ZIP=dist\ICSTeX-%APP_VERSION%-Windows.zip
set VERSIONED_SETUP=dist\ICSTeX-%APP_VERSION%-Setup.exe
echo Version: %APP_VERSION%
echo.

if /I "%CD:~0,7%"=="C:\Mac\" (
  echo This project is currently inside a Mac-Windows shared folder.
  echo PyInstaller often fails to clean PySide6/Qt files in shared folders.
  echo Copy the whole project to a Windows local path first, for example:
  echo   C:\Users\%USERNAME%\Desktop\ICSTeX_Build
  echo Then run packaging\build_windows.bat again from that local copy.
  echo.
  pause
  exit /b 1
)

set PYINSTALLER_CONFIG_DIR=%CD%\build\pyinstaller-config
set PIP_CACHE_DIR=%CD%\build\pip-cache

python packaging\install_build_dependencies.py
if errorlevel 1 goto :fail

powershell -NoProfile -ExecutionPolicy Bypass -Command "foreach ($p in @('build\ICSTeX','dist\ICSTeX','dist\ICSTeX-Windows.zip','dist\ICSTeX-Setup.exe','%VERSIONED_ZIP%','%VERSIONED_SETUP%')) { if (Test-Path $p) { Remove-Item $p -Recurse -Force -ErrorAction Stop } }"
if errorlevel 1 goto :fail

python -m PyInstaller packaging\windows.spec --noconfirm
if errorlevel 1 goto :fail

if not exist "dist\ICSTeX\ICSTeX.exe" (
  echo Missing dist\ICSTeX\ICSTeX.exe
  goto :fail
)

copy /Y "packaging\README_windows.md" "dist\ICSTeX\README.txt" >nul
if errorlevel 1 goto :fail
copy /Y "CHANGELOG.md" "dist\ICSTeX\CHANGELOG.md" >nul
if errorlevel 1 goto :fail

powershell -NoProfile -ExecutionPolicy Bypass -Command "Compress-Archive -Path 'dist\ICSTeX\*' -DestinationPath '%VERSIONED_ZIP%' -Force"
if errorlevel 1 goto :fail
copy /Y "%VERSIONED_ZIP%" "dist\ICSTeX-Windows.zip" >nul
if errorlevel 1 goto :fail

where iscc >nul 2>nul
if %ERRORLEVEL% EQU 0 (
  iscc packaging\installer_windows.iss
  if errorlevel 1 goto :fail
) else (
  echo Inno Setup is not installed or iscc is not on PATH; skipped installer exe.
)

echo.
echo Built dist\ICSTeX\ICSTeX.exe
echo Built %VERSIONED_ZIP%
echo Built dist\ICSTeX-Windows.zip
if exist "%VERSIONED_SETUP%" echo Built %VERSIONED_SETUP%
echo.
echo Build completed successfully.
pause
exit /b 0

:fail
echo.
echo Build failed. Read the error message above.
echo Common causes:
echo - Python is not installed or not on PATH.
echo - pip cannot install dependencies.
echo - A configured proxy is unreachable and could not be recovered.
echo - PyInstaller failed to collect PySide6.
echo - The project is inside a Mac-Windows shared folder.
echo - The project path contains characters Windows tooling cannot handle.
echo.
pause
exit /b 1
