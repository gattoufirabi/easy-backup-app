@echo off
rem Construit l'installeur hors-ligne : dist\EasyBackup-Setup-<version>.exe
rem Usage : build_installer.bat [version]      ex. build_installer.bat 1.2.0
rem (outils de developpement requis : Go, Python + .venv, Inno Setup 6)
setlocal
cd /d "%~dp0"
set "VERSION_ARG="
if not "%~1"=="" set "VERSION_ARG=/DAppVersion=%~1"

echo [1/4] Moteur Go...
call "%~dp0build_engine.bat" || goto :error

echo [2/4] Icone et images de l'installeur...
.venv\Scripts\python tools\make_assets.py || goto :error

echo [3/4] Application (PyInstaller)...
.venv\Scripts\python -m PyInstaller --noconfirm --clean --log-level WARN EasyBackup.spec || goto :error

echo [4/4] Installeur (Inno Setup)...
set "ISCC=iscc"
where iscc >nul 2>nul || set "ISCC=%ProgramFiles(x86)%\Inno Setup 6\ISCC.exe"
"%ISCC%" /Q %VERSION_ARG% installer\EasyBackup.iss || goto :error

echo.
echo Termine : dist\EasyBackup-Setup-*.exe
exit /b 0

:error
echo.
echo ECHEC de la construction.
exit /b 1
