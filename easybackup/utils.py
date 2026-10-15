"""Petites fonctions utilitaires."""

import ctypes
import os
import subprocess
import sys

from . import i18n
from .i18n import tr


def resource_path(relative: str) -> str:
    """Chemin d'un fichier fourni avec l'application (dev ou exécutable PyInstaller)."""
    if getattr(sys, "frozen", False):
        base = sys._MEIPASS
    else:
        base = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    return os.path.join(base, relative)


_UNITS = {"fr": ("o", "Ko", "Mo", "Go", "To"), "en": ("B", "KB", "MB", "GB", "TB")}


def human_size(n: float) -> str:
    units = _UNITS.get(i18n.LANG, _UNITS["en"])
    for i, unit in enumerate(units):
        if n < 1024 or i == len(units) - 1:
            if i == 0:
                return f"{n:.0f} {unit}"
            text = f"{n:.1f} {unit}"
            return text.replace(".", ",") if i18n.LANG == "fr" else text
        n /= 1024
    return ""


def format_duration(seconds: float) -> str:
    seconds = int(seconds)
    if seconds < 60:
        return f"{seconds} s"
    m, s = divmod(seconds, 60)
    h, m = divmod(m, 60)
    return f"{h} h {m:02d} min" if h else f"{m} min {s:02d} s"


_DRIVE_TYPES = {
    2: "Amovible",
    3: "Disque local",
    4: "Réseau",
    5: "CD/DVD",
    6: "Disque RAM",
}


DRIVE_REMOVABLE = 2


def _drive_type(root: str) -> int:
    if sys.platform != "win32":
        return 0
    return ctypes.windll.kernel32.GetDriveTypeW(ctypes.c_wchar_p(root))


def drive_kind(root: str) -> str:
    """Type de lecteur Windows (amovible, local, réseau…)."""
    if sys.platform != "win32":
        return tr("Volume")
    return tr(_DRIVE_TYPES.get(_drive_type(root), "Disque"))


def is_removable(root: str) -> bool:
    return _drive_type(root) == DRIVE_REMOVABLE


def existing_parent(path: str) -> str:
    """Premier dossier existant en remontant depuis `path`."""
    p = os.path.abspath(path)
    while not os.path.exists(p):
        parent = os.path.dirname(p)
        if parent == p:
            break
        p = parent
    return p


def same_volume(a: str, b: str) -> bool:
    da = os.path.splitdrive(os.path.abspath(a))[0].lower()
    db = os.path.splitdrive(os.path.abspath(b))[0].lower()
    return da == db


def reveal_in_explorer(path: str) -> None:
    path = os.path.normpath(path)
    if sys.platform == "win32":
        subprocess.Popen(f'explorer /select,"{path}"')
    else:
        subprocess.Popen(["xdg-open", os.path.dirname(path)])
