@echo off
rem Construit l'installeur hors-ligne : dist\EasyBackup-Setup-<version>.exe
rem Usage : build_installer.bat [version]   (par defaut : la version de easybackup\__init__.py)
rem (outils de developpement requis : Go, Python + .venv, Inno Setup 6)
rem
rem Signature (optionnelle) : definir EB_SIGN avec la commande de signature, le fichier a
rem signer est ajoute a la fin. Exemple :
rem   set EB_SIGN=signtool sign /fd sha256 /tr http://timestamp.digicert.com /td sha256 /a
rem L'application, le moteur, l'installeur et le desinstalleur sont alors signes.
setlocal
cd /d "%~dp0"
set "VERSION=%~1"
if "%VERSION%"=="" for /f "tokens=3" %%v in ('findstr /b "__version__" "%~dp0easybackup\__init__.py"') do set "VERSION=%%~v"
echo Version %VERSION%

echo [1/4] Moteur Go...
call "%~dp0build_engine.bat" %VERSION% || goto :error

echo [2/4] Icone et images de l'installeur...
.venv\Scripts\python tools\make_assets.py || goto :error

echo [3/4] Application (PyInstaller)...
.venv\Scripts\python -m PyInstaller --noconfirm --clean --log-level WARN EasyBackup.spec || goto :error

set "SIGN_ARGS="
if defined EB_SIGN (
    echo Signature de l'application et du moteur...
    %EB_SIGN% "dist\EasyBackup\EasyBackup.exe" || goto :error
    %EB_SIGN% "dist\EasyBackup\_internal\bin\ebengine.exe" || goto :error
    set SIGN_ARGS="/Ssigner=%EB_SIGN% $f" /DSIGN
)

echo [4/4] Installeur (Inno Setup)...
set "ISCC=iscc"
where iscc >nul 2>nul || set "ISCC=%ProgramFiles(x86)%\Inno Setup 6\ISCC.exe"
"%ISCC%" /Q /DAppVersion=%VERSION% %SIGN_ARGS% installer\EasyBackup.iss || goto :error

echo.
echo Termine : dist\EasyBackup-Setup-%VERSION%.exe
exit /b 0

:error
echo.
echo ECHEC de la construction.
exit /b 1
