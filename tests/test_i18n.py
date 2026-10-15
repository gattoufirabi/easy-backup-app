"""Every text shown to the user must have an English translation with the same placeholders."""

import ast
import pathlib
import string

from easybackup import categories, i18n, models, utils

PACKAGE = pathlib.Path(__file__).resolve().parent.parent / "easybackup"


def _fields(text):
    return sorted(f for _, f, _, _ in string.Formatter().parse(text) if f)


def _translated_literals():
    """String literals passed to tr() / ntr() anywhere in the package."""
    for path in PACKAGE.glob("*.py"):
        for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
            if isinstance(node, ast.Call) and getattr(node.func, "id", None) in ("tr", "ntr"):
                args = node.args[1:3] if node.func.id == "ntr" else node.args[:1]
                for arg in args:
                    if isinstance(arg, ast.Constant) and isinstance(arg.value, str):
                        yield path.name, arg.value


def _all_keys():
    keys = list(_translated_literals())
    keys += [("categories", c) for c in categories.ORDER]
    keys += [("models", c) for c in models.COLUMNS + models.DIR_COLUMNS]
    keys += [("utils", v) for v in list(utils._DRIVE_TYPES.values()) + ["Disque", "Volume"]]
    keys += [("window", "Déplacement de {what} ({size}) vers {dest}"),
             ("window", "Copie de {what} ({size}) vers {dest}")]
    return keys


def test_every_text_has_an_english_translation():
    missing = [(where, k) for where, k in _all_keys() if k not in i18n.EN]
    assert not missing


def test_placeholders_match():
    wrong = [k for _, k in _all_keys() if k in i18n.EN and _fields(k) != _fields(i18n.EN[k])]
    assert not wrong


def test_tr_switches_language(monkeypatch):
    monkeypatch.setattr(i18n, "LANG", "en")
    assert i18n.tr("Analyse de {path}…", path="C:\\") == "Scanning C:\\…"
    assert i18n.ntr(2, "{n} fichier", "{n} fichiers") == "2 files"
    assert utils.human_size(1536) == "1.5 KB"
    monkeypatch.setattr(i18n, "LANG", "fr")
    assert i18n.tr("Analyse de {path}…", path="C:\\") == "Analyse de C:\\…"
    assert utils.human_size(1536) == "1,5 Ko"
