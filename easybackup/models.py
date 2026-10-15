"""Modèles Qt : liste des fichiers d'un type et arborescence des dossiers."""

import os
from datetime import datetime

from PySide6.QtCore import (QAbstractItemModel, QAbstractTableModel, QFileInfo, QModelIndex,
                            Qt, Signal)
from PySide6.QtWidgets import QFileIconProvider

from . import i18n
from .i18n import tr
from .utils import human_size

COLUMNS = ["Nom", "Taille", "Modifié le", "Dossier"]

# Clés de tri par colonne (tri Python natif : rapide même sur 500 000 lignes)
_SORT_KEYS = (
    lambda e: e.search,
    lambda e: e.size,
    lambda e: e.mtime,
    lambda e: e.folder.lower(),
)


class FileTableModel(QAbstractTableModel):
    """Liste des fichiers d'un type. Tri, filtre et compteurs sont gérés ici,
    sans QSortFilterProxyModel (trop lent : il rappelle Python pour chaque comparaison)."""

    checkedChanged = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._all = []  # tous les fichiers
        self._rows = []  # fichiers visibles (filtrés et triés)
        self._filter = ""
        self._sort = (0, Qt.AscendingOrder)
        self.checked_count = 0
        self.checked_size = 0
        self._icons = {}
        self._icon_provider = QFileIconProvider()

    # --- accès aux données -------------------------------------------------
    def all_entries(self):
        return self._all

    def entry(self, row):
        return self._rows[row]

    def set_entries(self, entries, presorted=False):
        """`presorted` : déjà triés par nom (fait dans le thread d'analyse)."""
        self._all = list(entries)
        if not presorted or self._sort != (0, Qt.AscendingOrder):
            self._all.sort(key=_SORT_KEYS[self._sort[0]],
                           reverse=self._sort[1] == Qt.DescendingOrder)
        self._recount()
        self._rebuild()

    def remove_entries(self, to_remove):
        ids = {id(e) for e in to_remove}
        self._all = [e for e in self._all if id(e) not in ids]
        self._recount()
        self._rebuild()

    def set_filter(self, text):
        self._filter = text.strip().lower()
        self._rebuild()

    def checked_entries(self):
        return [e for e in self._all if e.checked]

    def _recount(self):
        checked = [e for e in self._all if e.checked]
        self.checked_count = len(checked)
        self.checked_size = sum(e.size for e in checked)

    def _rebuild(self):
        self.beginResetModel()
        f = self._filter
        self._rows = [e for e in self._all if f in e.search] if f else self._all
        self.endResetModel()
        self.checkedChanged.emit()

    def set_checked_rows(self, rows, checked: bool):
        changed = []
        for r in rows:
            e = self._rows[r]
            if e.checked != checked:
                e.checked = checked
                self.checked_count += 1 if checked else -1
                self.checked_size += e.size if checked else -e.size
                changed.append(r)
        self._emit_check_changed(changed)

    def invert_rows(self, rows):
        rows = list(rows)
        for r in rows:
            e = self._rows[r]
            e.checked = not e.checked
            self.checked_count += 1 if e.checked else -1
            self.checked_size += e.size if e.checked else -e.size
        self._emit_check_changed(rows)

    def uncheck_entries(self, entries):
        for e in entries:
            if e.checked:
                e.checked = False
                self.checked_count -= 1
                self.checked_size -= e.size
        if self._rows:
            self._emit_check_changed([0, len(self._rows) - 1])

    def _emit_check_changed(self, rows):
        if rows:
            self.dataChanged.emit(self.index(min(rows), 0), self.index(max(rows), 0),
                                  [Qt.CheckStateRole])
        self.checkedChanged.emit()

    def _icon(self, e):
        ext = os.path.splitext(e.name)[1].lower()
        if ext not in self._icons:
            self._icons[ext] = self._icon_provider.icon(QFileInfo(e.path))
        return self._icons[ext]

    # --- API Qt -------------------------------------------------------------
    def rowCount(self, parent=QModelIndex()):
        return 0 if parent.isValid() else len(self._rows)

    def columnCount(self, parent=QModelIndex()):
        return 0 if parent.isValid() else len(COLUMNS)

    def headerData(self, section, orientation, role=Qt.DisplayRole):
        if orientation == Qt.Horizontal and role == Qt.DisplayRole:
            return tr(COLUMNS[section])
        return None

    def flags(self, index):
        f = Qt.ItemIsEnabled | Qt.ItemIsSelectable
        if index.column() == 0:
            f |= Qt.ItemIsUserCheckable
        return f

    def sort(self, column, order=Qt.AscendingOrder):
        if (column, order) == self._sort or not 0 <= column < len(COLUMNS):
            return
        self._sort = (column, order)
        self._all.sort(key=_SORT_KEYS[column], reverse=order == Qt.DescendingOrder)
        self._rebuild()

    def data(self, index, role=Qt.DisplayRole):
        if not index.isValid():
            return None
        e = self._rows[index.row()]
        col = index.column()

        if role == Qt.DisplayRole:
            if col == 0:
                return e.name
            if col == 1:
                return human_size(e.size)
            if col == 2:
                return datetime.fromtimestamp(e.mtime).strftime("%d/%m/%Y %H:%M" if i18n.LANG == "fr" else "%Y-%m-%d %H:%M")
            return e.folder or "."
        if role == Qt.CheckStateRole and col == 0:
            return Qt.Checked if e.checked else Qt.Unchecked
        if role == Qt.DecorationRole and col == 0:
            return self._icon(e)
        if role == Qt.ToolTipRole:
            return e.path
        if role == Qt.TextAlignmentRole and col == 1:
            return int(Qt.AlignRight | Qt.AlignVCenter)
        return None

    def setData(self, index, value, role=Qt.EditRole):
        if role == Qt.CheckStateRole and index.column() == 0:
            self.set_checked_rows([index.row()], Qt.CheckState(value) == Qt.CheckState.Checked)
            return True
        return False


# --------------------------------------------------------------------------
# Arborescence des dossiers (onglet « Dossiers »)
# --------------------------------------------------------------------------

class DirNode:
    __slots__ = ("name", "rel", "path", "parent", "children", "row", "size", "files",
                 "checked", "checked_below", "_by_name")

    def __init__(self, name, rel, path, parent):
        self.name, self.rel, self.path, self.parent = name, rel, path, parent
        self.children = []
        self.row = 0
        self.size = 0
        self.files = 0
        self.checked = False
        self.checked_below = 0  # nombre de dossiers cochés en dessous
        self._by_name = {}

    def ancestor_checked(self):
        p = self.parent
        while p is not None:
            if p.checked:
                return True
            p = p.parent
        return False


def build_dir_tree(root_path, entries):
    """Construit l'arbre des dossiers (taille et nombre de fichiers cumulés)."""
    root = DirNode("", "", root_path, None)
    cache = {"": root}
    for e in entries:
        folder = e.folder
        node = cache.get(folder)
        if node is None:
            node = root
            rel = ""
            for part in folder.split(os.sep):
                rel = os.path.join(rel, part) if rel else part
                child = node._by_name.get(part)
                if child is None:
                    child = DirNode(part, rel, os.path.join(root_path, rel), node)
                    node._by_name[part] = child
                node = child
                cache[rel] = node
        while node is not None:
            node.size += e.size
            node.files += 1
            node = node.parent
    stack = [root]
    while stack:
        node = stack.pop()
        node.children = sorted(node._by_name.values(), key=lambda n: n.name.lower())
        node._by_name = None
        for i, c in enumerate(node.children):
            c.row = i
        stack.extend(node.children)
    return root


DIR_COLUMNS = ["Dossier", "Taille", "Fichiers"]


class DirTreeModel(QAbstractItemModel):
    checkedChanged = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._root = DirNode("", "", "", None)
        self._icon = QFileIconProvider().icon(QFileIconProvider.Folder)

    def set_root(self, root):
        self.beginResetModel()
        self._root = root
        self.endResetModel()
        self.checkedChanged.emit()

    def root(self):
        return self._root

    def node(self, index):
        return index.internalPointer() if index.isValid() else self._root

    def checked_nodes(self):
        """Dossiers cochés les plus hauts (leurs sous-dossiers sont inclus)."""
        result, stack = [], list(self._root.children)
        while stack:
            n = stack.pop()
            if n.checked:
                result.append(n)
            elif n.checked_below:
                stack.extend(n.children)
        return result

    def set_checked(self, nodes, checked: bool):
        for n in nodes:
            if n.ancestor_checked() or n.checked == checked:
                continue
            if checked:
                self._clear_below(n)  # devenus redondants
            n.checked = checked
            delta = 1 if checked else -1
            p = n.parent
            while p is not None:
                p.checked_below += delta
                p = p.parent
        if self._root.children:
            self._refresh()
        self.checkedChanged.emit()

    def uncheck_all(self):
        self.set_checked(self.checked_nodes(), False)

    def _clear_below(self, node):
        stack = list(node.children)
        while stack:
            n = stack.pop()
            if n.checked:
                n.checked = False
                p = n.parent
                while p is not None:
                    p.checked_below -= 1
                    p = p.parent
            if n.checked_below:
                stack.extend(n.children)

    def _refresh(self):
        # une plage de plusieurs cellules provoque le rafraîchissement de toute la vue
        last = len(self._root.children) - 1
        self.dataChanged.emit(self.index(0, 0), self.index(last, len(DIR_COLUMNS) - 1),
                              [Qt.CheckStateRole])

    def sort(self, column, order=Qt.AscendingOrder):
        key = (lambda n: n.name.lower(), lambda n: n.size, lambda n: n.files)[column]
        self.beginResetModel()
        stack = [self._root]
        while stack:
            node = stack.pop()
            node.children.sort(key=key, reverse=order == Qt.DescendingOrder)
            for i, c in enumerate(node.children):
                c.row = i
            stack.extend(node.children)
        self.endResetModel()

    # --- API Qt -------------------------------------------------------------
    def index(self, row, column, parent=QModelIndex()):
        node = self.node(parent)
        if 0 <= row < len(node.children):
            return self.createIndex(row, column, node.children[row])
        return QModelIndex()

    def parent(self, index):
        if not index.isValid():
            return QModelIndex()
        p = index.internalPointer().parent
        if p is None or p is self._root:
            return QModelIndex()
        return self.createIndex(p.row, 0, p)

    def rowCount(self, parent=QModelIndex()):
        if parent.column() > 0:
            return 0
        return len(self.node(parent).children)

    def columnCount(self, parent=QModelIndex()):
        return len(DIR_COLUMNS)

    def hasChildren(self, parent=QModelIndex()):
        return bool(self.node(parent).children)

    def headerData(self, section, orientation, role=Qt.DisplayRole):
        if orientation == Qt.Horizontal and role == Qt.DisplayRole:
            return tr(DIR_COLUMNS[section])
        return None

    def flags(self, index):
        f = Qt.ItemIsEnabled | Qt.ItemIsSelectable
        if index.column() == 0 and not index.internalPointer().ancestor_checked():
            f |= Qt.ItemIsUserCheckable
        return f

    def data(self, index, role=Qt.DisplayRole):
        if not index.isValid():
            return None
        n = index.internalPointer()
        col = index.column()
        if role == Qt.DisplayRole:
            return (n.name, human_size(n.size), str(n.files))[col]
        if role == Qt.UserRole:  # tri
            return (n.name.lower(), n.size, n.files)[col]
        if role == Qt.CheckStateRole and col == 0:
            if n.checked or n.ancestor_checked():
                return Qt.Checked
            return Qt.PartiallyChecked if n.checked_below else Qt.Unchecked
        if role == Qt.DecorationRole and col == 0:
            return self._icon
        if role == Qt.ToolTipRole:
            if n.ancestor_checked():
                return n.path + tr("\n(inclus dans un dossier parent coché)")
            return n.path
        if role == Qt.TextAlignmentRole and col > 0:
            return int(Qt.AlignRight | Qt.AlignVCenter)
        return None

    def setData(self, index, value, role=Qt.EditRole):
        if role == Qt.CheckStateRole and index.column() == 0:
            n = index.internalPointer()
            self.set_checked([n], not n.checked)
            return True
        return False
