"""Copie / déplacement des fichiers sélectionnés, réalisé par le moteur Go."""

import json
import os
import tempfile
from dataclasses import dataclass

from PySide6.QtCore import Signal

from .engine import EngineJob
from .i18n import tr


@dataclass
class TransferOptions:
    mode: str = "copy"  # copy | move
    layout: str = "by_type"  # by_type | keep_tree | flat
    conflict: str = "rename"  # rename | skip | overwrite


class TransferWorker(EngineJob):
    file_started = Signal(int, int, str)  # index (à partir de 1), total, nom
    dir_started = Signal(int, int, str)
    progress = Signal(object, object)  # octets faits, octets totaux
    log = Signal(str)
    finished = Signal(object)  # dict récapitulatif

    def __init__(self, entries, dirs, source_root: str, dest_dir: str,
                 options: TransferOptions, parent=None):
        self.entries = list(entries)
        self.dirs = list(dirs)  # DirNode : dossiers transférés en entier
        self.options = options
        self.dest_dir = os.path.abspath(dest_dir)
        fd, self._job_path = tempfile.mkstemp(prefix="ebjob_", suffix=".json")
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump({
                "dest": self.dest_dir,
                "source_root": source_root,
                "mode": options.mode,
                "layout": options.layout,
                "conflict": options.conflict,
                "files": [{"path": e.path, "rel": e.rel, "category": tr(e.category),
                           "size": e.size} for e in self.entries],
                "dirs": [{"path": d.path, "rel": d.rel, "size": d.size} for d in self.dirs],
            }, f)
        super().__init__(["transfer", "--job", self._job_path], parent)
        self._ok, self._skipped, self._failed = [], [], []
        self._dirs_ok, self._dirs_skipped, self._dirs_failed = [], [], []
        self._finished = False

    def on_event(self, evt):
        kind = evt["type"]
        if kind == "file_start":
            self.file_started.emit(evt["index"] + 1, evt["total"], evt["name"])
        elif kind == "progress":
            self.progress.emit(evt["done"], evt["total"])
        elif kind == "result":
            e = self.entries[evt["index"]]
            status = evt["status"]
            if status == "ok":
                self._ok.append(e)
            elif status == "skipped":
                self._skipped.append(e)
                if evt.get("reason") == "same_path":
                    self.log.emit(tr("Ignoré (source = destination) : {path}", path=e.path))
                else:
                    self.log.emit(tr("Déjà présent, ignoré : {path}", path=evt.get("target", "")))
            else:
                self._failed.append((e, evt.get("error", "")))
                self.log.emit(f"❌ {e.path} → {evt.get('error', '')}")
        elif kind == "dir_start":
            self.dir_started.emit(evt["index"] + 1, evt["total"], evt["name"])
        elif kind == "dir_result":
            d = self.dirs[evt["index"]]
            status = evt["status"]
            if status == "ok":
                self._dirs_ok.append(d)
                self.log.emit(tr("📁 Dossier transféré : {src} → {dest}", src=d.path,
                                  dest=evt.get("target", "")))
            elif status == "skipped":
                self._dirs_skipped.append(d)
                self.log.emit(tr("Dossier déjà présent, ignoré : {path}", path=evt.get("target", "")))
            else:
                self._dirs_failed.append((d, evt.get("error", "")))
                self.log.emit(tr("❌ Dossier {path} → {error}", path=d.path, error=evt.get("error", "")))
        elif kind == "dir_file_error":
            self.log.emit(f"❌ {evt['path']} → {evt['error']}")
        elif kind == "done":
            self._finish(evt["cancelled"], "")

    def on_failure(self, message):
        self.log.emit(tr("❌ Erreur du moteur : {error}", error=message))
        self._finish(True, message)

    def _finish(self, cancelled, error):
        if self._finished:
            return
        self._finished = True
        try:
            os.remove(self._job_path)
        except OSError:
            pass
        self.finished.emit({
            "ok": self._ok,
            "skipped": self._skipped,
            "failed": self._failed,
            "cancelled": cancelled,
            "error": error,
            "dirs_ok": self._dirs_ok,
            "dirs_skipped": self._dirs_skipped,
            "dirs_failed": self._dirs_failed,
            "bytes": sum(e.size for e in self._ok) + sum(d.size for d in self._dirs_ok),
            "mode": self.options.mode,
            "dest": self.dest_dir,
        })
