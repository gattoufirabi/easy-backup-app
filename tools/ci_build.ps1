# Construction de l'installeur sur GitHub Actions (CI et releases).
#
# PyInstaller est installé depuis ses sources : son lanceur (bootloader) est compilé ici
# avec Visual Studio, au lieu d'utiliser celui distribué tout fait, qui est aussi utilisé
# par des logiciels malveillants et donc souvent signalé par les antivirus.
param([Parameter(Mandatory)][string]$Version)
$ErrorActionPreference = "Stop"

function Check($step) { if ($LASTEXITCODE) { throw "$step a échoué (code $LASTEXITCODE)" } }

python -m venv .venv; Check "venv"
.venv\Scripts\python -m pip install --upgrade pip; Check "pip"

$env:PYINSTALLER_COMPILE_BOOTLOADER = "1"
.venv\Scripts\python -m pip install --no-binary pyinstaller -r requirements-dev.txt; Check "installation des dépendances"

# Vérifie que le lanceur installé n'est pas celui du paquet tout fait.
$pyiVersion = .venv\Scripts\python -c "import PyInstaller; print(PyInstaller.__version__)"
$wheelDir = Join-Path $env:RUNNER_TEMP "pyinstaller-wheel"
.venv\Scripts\python -m pip download "pyinstaller==$pyiVersion" --no-deps --only-binary :all: --platform win_amd64 -d $wheelDir; Check "téléchargement de référence"
.venv\Scripts\python tools\check_bootloader.py (Get-ChildItem $wheelDir -Filter *.whl)[0].FullName; Check "vérification du lanceur"

if (-not (Get-Command iscc -ErrorAction SilentlyContinue) -and
    -not (Test-Path "${env:ProgramFiles(x86)}\Inno Setup 6\ISCC.exe")) {
    choco install innosetup --no-progress -y; Check "Inno Setup"
}

cmd /c "build_installer.bat $Version"; Check "build_installer.bat"

# Vérifie les informations de version Windows des exécutables produits.
$exes = "dist\EasyBackup\EasyBackup.exe", "dist\EasyBackup\_internal\bin\ebengine.exe", "dist\EasyBackup-Setup-$Version.exe"
foreach ($exe in $exes) {
    $info = (Get-Item $exe).VersionInfo
    "{0,-45} {1} | {2} | {3}" -f $exe, $info.CompanyName, $info.ProductName, $info.ProductVersion
    if ("$($info.CompanyName)".Trim() -ne "StaysaProd" -or -not "$($info.ProductVersion)".Trim().StartsWith($Version)) {
        throw "Informations de version manquantes ou incorrectes : $exe"
    }
}
