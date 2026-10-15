"""Pilotage du moteur Go (ebengine.exe) via QProcess.

Le moteur écrit un événement JSON par ligne sur stdout ; on l'annule en
écrivant « cancel » sur son stdin.
"""

import json
import os
import sys

from PySide6.QtCore import QObject, QProcess

from .i18n import engine_args, tr
from .utils import resource_path

ENGINE_NAME = "ebengine.exe" if sys.platform == "win32" else "ebengine"


def engine_path() -> str:
    path = resource_path(os.path.join("bin", ENGINE_NAME))
    if os.path.isfile(path):
        return path
    raise FileNotFoundError(tr(
        "Le moteur {name} est introuvable ({path}).\n"
        "Lancez build_engine.bat pour le compiler (nécessite Go).", name=ENGINE_NAME, path=path))


class EngineJob(QObject):
    """Base commune : lance le moteur et décode ses événements."""

    def __init__(self, args, parent=None):
        super().__init__(parent)
        self._proc = QProcess(self)
        self._proc.setProgram(engine_path())
        self._proc.setArguments(args + engine_args())
        self._proc.readyReadStandardOutput.connect(self._read_stdout)
        self._proc.finished.connect(self._on_exit)
        self._proc.errorOccurred.connect(self._on_error)
        self._buf = b""
        self._done = False
        self._error = ""

    def start(self):
        self._proc.start()

    def cancel(self):
        if self._proc.state() == QProcess.Running:
            self._proc.write(b"cancel\n")

    def wait(self, msecs: int):
        if self._proc.state() != QProcess.NotRunning and \
                not self._proc.waitForFinished(msecs):
            self._proc.kill()
            self._proc.waitForFinished(1000)

    # --- à implémenter ------------------------------------------------------
    def on_event(self, evt: dict):
        raise NotImplementedError

    def on_failure(self, message: str):
        raise NotImplementedError

    # --- interne ------------------------------------------------------------
    def _read_stdout(self):
        self._buf += bytes(self._proc.readAllStandardOutput())
        *lines, self._buf = self._buf.split(b"\n")
        for line in lines:
            line = line.strip()
            if not line:
                continue
            try:
                evt = json.loads(line)
            except ValueError:
                continue
            kind = evt.get("type")
            if kind == "error":
                self._error = evt.get("msg", "")
                continue
            if kind == "done":
                self._done = True
            self.on_event(evt)

    def _on_exit(self, code, _status):
        self._read_stdout()
        if not self._done:
            stderr = bytes(self._proc.readAllStandardError()).decode(errors="replace")
            self.on_failure(self._error or stderr.strip()
                            or tr("le moteur s'est arrêté de façon inattendue (code {code})", code=code))

    def _on_error(self, error):
        if error == QProcess.FailedToStart:  # pas de signal finished dans ce cas
            self.on_failure(tr("impossible de lancer le moteur : {error}",
                               error=self._proc.errorString()))
