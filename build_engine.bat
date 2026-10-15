@echo off
rem Compile le moteur Go -> bin\ebengine.exe
rem Usage : build_engine.bat [version]   (par defaut : la version de easybackup\__init__.py)
rem -H windowsgui : programme sans console, il tourne en arriere-plan sans fenetre noire.
setlocal
set "VERSION=%~1"
if "%VERSION%"=="" for /f "tokens=3" %%v in ('findstr /b "__version__" "%~dp0easybackup\__init__.py"') do set "VERSION=%%~v"

pushd "%~dp0engine"
rem informations de version, icone et manifeste Windows (fichier .syso pris en compte par go build)
go run github.com/tc-hib/go-winres@v0.3.3 make --in winres\winres.json --arch amd64 --product-version %VERSION% --file-version %VERSION% || goto :fail
go build -trimpath -ldflags "-s -w -H windowsgui -X main.version=%VERSION%" -o ..\bin\ebengine.exe . || goto :fail
popd
exit /b 0

:fail
popd
echo Echec de la compilation du moteur. Go est-il installe ? https://go.dev/dl/
exit /b 1
