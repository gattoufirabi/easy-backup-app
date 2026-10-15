# PyInstaller : application fenêtrée (pas de console), en dossier (démarrage rapide).
# Utilisé par build_installer.bat.

import os
import re

from PyInstaller.utils.win32.versioninfo import (FixedFileInfo, StringFileInfo, StringStruct,
                                                 StringTable, VarFileInfo, VarStruct,
                                                 VSVersionInfo)

# Informations de version Windows (Propriétés du fichier → Détails) : un exécutable
# qui indique son éditeur et sa version est moins suspect pour les antivirus.
with open(os.path.join(SPECPATH, "easybackup", "__init__.py"), encoding="utf-8") as f:
    VERSION = re.search(r'__version__ = "([^"]+)"', f.read()).group(1)
numbers = tuple(int(n) for n in re.findall(r"\d+", VERSION)[:4])
numbers += (0,) * (4 - len(numbers))

version_info = VSVersionInfo(
    ffi=FixedFileInfo(filevers=numbers, prodvers=numbers),
    kids=[
        StringFileInfo([StringTable("040904B0", [
            StringStruct("CompanyName", "StaysaProd"),
            StringStruct("FileDescription", "Easy Backup"),
            StringStruct("FileVersion", VERSION),
            StringStruct("InternalName", "EasyBackup"),
            StringStruct("LegalCopyright", "Copyright (C) StaysaProd. Licensed under the GNU GPL v3."),
            StringStruct("OriginalFilename", "EasyBackup.exe"),
            StringStruct("ProductName", "Easy Backup"),
            StringStruct("ProductVersion", VERSION),
            StringStruct("Comments", "https://github.com/gattoufirabi/easy-backup-app"),
        ])]),
        VarFileInfo([VarStruct("Translation", [0x0409, 1200])]),
    ],
)

a = Analysis(
    ["main.py"],
    binaries=[("bin/ebengine.exe", "bin")],
    datas=[
        ("assets/icon.ico", "assets"),
        ("assets/logo_symbol.png", "assets"),
    ],
    excludes=["tkinter", "unittest", "pydoc", "PIL"],
)
pyz = PYZ(a.pure)
exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="EasyBackup",
    icon="assets/icon.ico",
    version=version_info,
    console=False,
    upx=False,
)
coll = COLLECT(exe, a.binaries, a.datas, name="EasyBackup", upx=False)
