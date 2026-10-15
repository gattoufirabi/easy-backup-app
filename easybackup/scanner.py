"""Analyse d'un dossier source.

Le moteur Go parcourt le disque ; un thread Python lit ses résultats, classe
les fichiers et construit l'arborescence. La fenêtre ne reçoit que le résultat
final : elle reste réactive même avec des centaines de milliers de fichiers.
"""

import json
import os
import subprocess
import sys
import threading

from PySide6.QtCore import QObject, Signal

from .categories import ORDER, OTHER
from .engine import engine_path
from .i18n import engine_args, fmt_int, tr

CREATE_NO_WINDOW = 0x08000000 if sys.platform == "win32" else 0


class FileEntry:
    __slots__ = ("path", "rel", "name", "folder", "size", "mtime", "category",
                 "search", "checked")

    def __init__(self, path, rel, size, mtime, category):
        self.path = path
        self.rel = rel  # chemin relatif au dossier source
        self.name = os.path.basename(path)
        self.folder = os.path.dirname(rel)
        self.size = size
        self.mtime = mtime
        self.category = category
        self.search = f"{self.name}\0{self.folder}".lower()  # pour le filtre
        self.checked = False


class ScanWorker(QObject):
    # fichiers trouvés, octets, dossiers lus, dossier courant
    progress = Signal(int, object, object, str)
    phase = Signal(str)  # étape en cours (texte)
    finished = Signal(object)  # dict résultat

    def __init__(self, root: str, include_hidden: bool = False, parent=None):
        super().__init__(parent)
        self.root = os.path.abspath(root)
        self._args = [engine_path(), "scan", "--root", self.root, *engine_args()]
        if include_hidden:
            self._args.append("--hidden")
        self._proc = None
        self._thread = None
        self._cancelled = False

    def start(self):
        self._thread = threading.Thread(target=self._run, name="scan", daemon=True)
        self._thread.start()

    def cancel(self):
        self._cancelled = True
        proc = self._proc
        if proc and proc.poll() is None:
            try:
                proc.stdin.write(b"cancel\n")
                proc.stdin.flush()
            except OSError:
                pass

    def wait(self, msecs: int):
        if self._thread:
            self._thread.join(msecs / 1000)
        if self._proc and self._proc.poll() is None:
            self._proc.kill()

    # --- thread de lecture --------------------------------------------------
    def _run(self):
        entries, info = [], {"cancelled": False, "errors": 0, "error": ""}
        try:
            self._proc = subprocess.Popen(
                self._args, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                stderr=subprocess.PIPE, creationflags=CREATE_NO_WINDOW)
            done = False
            for line in self._proc.stdout:
                try:
                    evt = json.loads(line)
                except ValueError:
                    continue
                kind = evt.get("type")
                if kind == "files":
                    entries.extend(FileEntry(f["p"], f["r"], f["s"], f["m"], f["c"])
                                   for f in evt["files"])
                elif kind == "progress":
                    self.progress.emit(evt["count"], evt["bytes"], evt["dirs"], evt["dir"])
                elif kind == "done":
                    done = True
                    info["cancelled"] = evt["cancelled"]
                    info["errors"] = evt["errors"]
                elif kind == "error":
                    info["error"] = evt.get("msg", "")
            self._proc.wait()
            if not done and not info["error"]:
                err = self._proc.stderr.read().decode(errors="replace").strip()
                info["error"] = err or tr("le moteur s'est arrêté de façon inattendue (code {code})",
                                         code=self._proc.returncode)
        except OSError as exc:
            info["error"] = tr("impossible de lancer le moteur : {error}", error=exc)
        info["cancelled"] = info["cancelled"] or self._cancelled

        self.phase.emit(tr("Classement de {n} fichiers…", n=fmt_int(len(entries))))
        self.finished.emit(prepare_result(self.root, entries, info))


def prepare_result(root, entries, info):
    """Travail lourd fait hors de la fenêtre : tri par type et arborescence."""
    from .models import build_dir_tree  # import local : évite un cycle

    by_cat = {cat: [] for cat in ORDER}
    for e in entries:
        by_cat.get(e.category, by_cat[OTHER]).append(e)
    for lst in by_cat.values():
        lst.sort(key=lambda e: e.search)
    return {
        "root": root,
        "by_cat": by_cat,
        "tree": build_dir_tree(root, entries),
        "count": len(entries),
        "bytes": sum(e.size for e in entries),
        **info,
    }
