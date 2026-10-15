"""Vérifie que le lanceur PyInstaller installé a été compilé localement.

Usage : python tools/check_bootloader.py <roue pyinstaller officielle .whl>

Compare le lanceur fenêtré (runw.exe) installé avec celui de la roue officielle :
ils doivent être différents.
"""

import hashlib
import pathlib
import sys
import zipfile

import PyInstaller

RUNW = "PyInstaller/bootloader/Windows-64bit-intel/runw.exe"

installed = pathlib.Path(PyInstaller.__file__).parent / "bootloader" / "Windows-64bit-intel" / "runw.exe"
local = hashlib.sha256(installed.read_bytes()).hexdigest()
with zipfile.ZipFile(sys.argv[1]) as wheel:
    official = hashlib.sha256(wheel.read(RUNW)).hexdigest()

print(f"lanceur installé : {local}")
print(f"lanceur officiel : {official}")
if local == official:
    sys.exit("Le lanceur est celui de la roue officielle : il n'a pas été compilé localement.")
print("OK : lanceur compilé localement.")
