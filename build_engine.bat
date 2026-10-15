@echo off
rem Compile le moteur Go -> bin\ebengine.exe
rem -H windowsgui : programme sans console, il tourne en arriere-plan sans fenetre noire.
pushd "%~dp0engine"
go build -trimpath -ldflags "-s -w -H windowsgui" -o ..\bin\ebengine.exe .
set "RESULT=%errorlevel%"
popd
if not "%RESULT%"=="0" (
    echo Echec de la compilation du moteur. Go est-il installe ? https://go.dev/dl/
    exit /b 1
)
