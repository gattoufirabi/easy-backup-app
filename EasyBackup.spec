# PyInstaller : application fenêtrée (pas de console), en dossier (démarrage rapide).
# Utilisé par build_installer.bat.

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
    console=False,
    upx=False,
)
coll = COLLECT(exe, a.binaries, a.datas, name="EasyBackup", upx=False)
