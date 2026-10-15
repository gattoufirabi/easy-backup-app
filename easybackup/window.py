"""Fenêtre principale de Easy Backup."""

import os
import sys
import time

from PySide6.QtCore import (QDir, QEvent, QFileInfo, QProcess, QSettings, QStorageInfo, Qt,
                            QTimer, QUrl)
from PySide6.QtGui import QDesktopServices, QPixmap
from PySide6.QtWidgets import (QAbstractItemView, QApplication, QCheckBox, QComboBox,
                               QFileDialog, QFileIconProvider, QGroupBox, QHBoxLayout,
                               QHeaderView, QLabel, QLineEdit, QMainWindow, QMenu, QMessageBox,
                               QPlainTextEdit, QProgressBar, QPushButton, QTableView,
                               QTabWidget, QTreeView, QVBoxLayout, QWidget)

from . import REPO_URL, __version__, i18n
from .categories import ICONS, ORDER, OTHER
from .i18n import fmt_int, ntr, tr
from .models import DirTreeModel, FileTableModel
from .scanner import ScanWorker
from .transfer import TransferOptions, TransferWorker
from .utils import (drive_kind, existing_parent, format_duration, human_size,
                    is_removable, resource_path, reveal_in_explorer, same_volume)

FAT32_MAX = 4 * 1024 ** 3 - 1
DEFAULT_SUBFOLDER = "EasyBackup"


def n_files(n):
    return ntr(n, "{n} fichier", "{n} fichiers")


def n_dirs(n):
    return ntr(n, "{n} dossier", "{n} dossiers")


def is_covered(entry, dir_rels):
    """Le fichier est-il dans un des dossiers cochés ?"""
    folder = entry.folder
    while folder:
        if folder in dir_rels:
            return True
        folder = os.path.dirname(folder)
    return False


class CategoryTab(QWidget):
    """Un sous-onglet : liste des fichiers d'un type, avec filtre et cases à cocher."""

    def __init__(self, category: str, parent=None):
        super().__init__(parent)
        self.category = category
        self.model = FileTableModel(self)

        self.search = QLineEdit(placeholderText=tr("🔍  Filtrer par nom ou dossier…"))
        self.search.setClearButtonEnabled(True)
        self._search_timer = QTimer(self, singleShot=True, interval=250)
        self._search_timer.timeout.connect(lambda: self.model.set_filter(self.search.text()))
        self.search.textChanged.connect(self._search_timer.start)

        btn_all = QPushButton(tr("Tout cocher"))
        btn_none = QPushButton(tr("Tout décocher"))
        btn_inv = QPushButton(tr("Inverser"))
        btn_all.clicked.connect(lambda: self.model.set_checked_rows(self.visible_rows(), True))
        btn_none.clicked.connect(lambda: self.model.set_checked_rows(self.visible_rows(), False))
        btn_inv.clicked.connect(lambda: self.model.invert_rows(self.visible_rows()))

        bar = QHBoxLayout()
        bar.addWidget(self.search, 1)
        for b in (btn_all, btn_none, btn_inv):
            bar.addWidget(b)

        self.view = QTableView()
        self.view.setModel(self.model)
        self.view.horizontalHeader().setSortIndicator(0, Qt.AscendingOrder)
        self.view.setSortingEnabled(True)
        self.view.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.view.setSelectionMode(QAbstractItemView.ExtendedSelection)
        self.view.setAlternatingRowColors(True)
        self.view.setWordWrap(False)
        self.view.setShowGrid(False)
        self.view.verticalHeader().hide()
        self.view.verticalHeader().setDefaultSectionSize(24)
        header = self.view.horizontalHeader()
        header.setSectionResizeMode(QHeaderView.Interactive)
        header.resizeSection(0, 380)
        header.resizeSection(1, 90)
        header.resizeSection(2, 130)
        header.setStretchLastSection(True)
        self.view.doubleClicked.connect(self._open_index)
        self.view.setContextMenuPolicy(Qt.CustomContextMenu)
        self.view.customContextMenuRequested.connect(self._context_menu)
        self.view.installEventFilter(self)

        hint = QLabel(tr("Astuce : sélectionnez plusieurs lignes (Maj/Ctrl + clic) puis "
                         "appuyez sur <b>Espace</b> pour les cocher. Double-clic pour ouvrir."))
        hint.setStyleSheet("color: gray;")

        lay = QVBoxLayout(self)
        lay.addLayout(bar)
        lay.addWidget(self.view, 1)
        lay.addWidget(hint)

    def visible_rows(self):
        return range(self.model.rowCount())

    def selected_rows(self):
        return sorted({i.row() for i in self.view.selectionModel().selectedRows()})

    def toggle_selection(self):
        rows = self.selected_rows()
        if rows:
            state = not all(self.model.entry(r).checked for r in rows)
            self.model.set_checked_rows(rows, state)

    def eventFilter(self, obj, event):
        if obj is self.view and event.type() == QEvent.KeyPress \
                and event.key() == Qt.Key_Space:
            self.toggle_selection()
            return True
        return super().eventFilter(obj, event)

    def _open_index(self, index):
        QDesktopServices.openUrl(QUrl.fromLocalFile(self.model.entry(index.row()).path))

    def _context_menu(self, pos):
        index = self.view.indexAt(pos)
        menu = QMenu(self)
        menu.addAction(tr("Cocher la sélection"),
                       lambda: self.model.set_checked_rows(self.selected_rows(), True))
        menu.addAction(tr("Décocher la sélection"),
                       lambda: self.model.set_checked_rows(self.selected_rows(), False))
        if index.isValid():
            e = self.model.entry(index.row())
            menu.addSeparator()
            menu.addAction(tr("Ouvrir"), lambda: self._open_index(index))
            menu.addAction(tr("Afficher dans l'Explorateur"), lambda: reveal_in_explorer(e.path))
        menu.exec(self.view.viewport().mapToGlobal(pos))


class DirectoryTab(QWidget):
    """Onglet « Dossiers » : cocher un dossier le transfère en entier."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.model = DirTreeModel(self)

        info = QLabel(tr("Cochez un dossier pour le transférer <b>en entier</b> : "
                         "sous-dossiers, fichiers cachés et structure compris."))
        info.setWordWrap(True)
        btn_none = QPushButton(tr("Tout décocher"))
        btn_none.clicked.connect(self.model.uncheck_all)
        btn_collapse = QPushButton(tr("Tout réduire"))
        btn_collapse.clicked.connect(lambda: self.view.collapseAll())
        bar = QHBoxLayout()
        bar.addWidget(info, 1)
        bar.addWidget(btn_none)
        bar.addWidget(btn_collapse)

        self.view = QTreeView()
        self.view.setModel(self.model)
        self.view.setUniformRowHeights(True)
        self.view.header().setSortIndicator(0, Qt.AscendingOrder)
        self.view.setSortingEnabled(True)
        self.view.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.view.setSelectionMode(QAbstractItemView.ExtendedSelection)
        self.view.setAlternatingRowColors(True)
        header = self.view.header()
        header.setStretchLastSection(False)
        header.setSectionResizeMode(0, QHeaderView.Stretch)
        header.resizeSection(1, 100)
        header.resizeSection(2, 90)
        self.view.setContextMenuPolicy(Qt.CustomContextMenu)
        self.view.customContextMenuRequested.connect(self._context_menu)
        self.view.installEventFilter(self)

        hint = QLabel(tr("Astuce : sélectionnez plusieurs dossiers puis appuyez sur "
                         "<b>Espace</b>. Clic droit pour ouvrir un dossier dans l'Explorateur."))
        hint.setStyleSheet("color: gray;")

        lay = QVBoxLayout(self)
        lay.addLayout(bar)
        lay.addWidget(self.view, 1)
        lay.addWidget(hint)

    def set_root(self, root):
        self.model.set_root(root)  # déjà trié par nom
        h = self.view.header()
        if (h.sortIndicatorSection(), h.sortIndicatorOrder()) != (0, Qt.AscendingOrder):
            self.model.sort(h.sortIndicatorSection(), h.sortIndicatorOrder())

    def selected_nodes(self):
        return [i.internalPointer() for i in self.view.selectionModel().selectedRows()]

    def toggle_selection(self):
        nodes = [n for n in self.selected_nodes() if not n.ancestor_checked()]
        if nodes:
            self.model.set_checked(nodes, not all(n.checked for n in nodes))

    def eventFilter(self, obj, event):
        if obj is self.view and event.type() == QEvent.KeyPress \
                and event.key() == Qt.Key_Space:
            self.toggle_selection()
            return True
        return super().eventFilter(obj, event)

    def _context_menu(self, pos):
        index = self.view.indexAt(pos)
        menu = QMenu(self)
        menu.addAction(tr("Cocher la sélection"),
                       lambda: self.model.set_checked(self.selected_nodes(), True))
        menu.addAction(tr("Décocher la sélection"),
                       lambda: self.model.set_checked(self.selected_nodes(), False))
        if index.isValid():
            node = index.internalPointer()
            menu.addSeparator()
            menu.addAction(tr("Ouvrir dans l'Explorateur"),
                           lambda: QDesktopServices.openUrl(QUrl.fromLocalFile(node.path)))
        menu.exec(self.view.viewport().mapToGlobal(pos))


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle(tr("Easy Backup — transfert de fichiers"))
        self.resize(1100, 780)
        self.settings = QSettings()

        self._worker = None
        self._busy = None  # None | "scan" | "transfer"
        self._source_root = ""
        self._t0 = 0.0
        self._sel_bytes = 0
        self._has_selection = False
        self._scan_stats = (0, 0, 0, "")
        self._scan_phase = ""
        self._scan_used = 0  # octets occupés du disque (analyse d'un disque entier)
        self._scan_timer = QTimer(self, interval=500)  # fait avancer le chrono
        self._scan_timer.timeout.connect(self._refresh_scan_status)

        central = QWidget()
        self.setCentralWidget(central)
        root = QVBoxLayout(central)

        root.addLayout(self._build_header())
        root.addWidget(self._build_source_box())

        self.tabs = QTabWidget()
        self.tabs.setDocumentMode(True)
        self.dir_tab = DirectoryTab()
        self.dir_tab.model.checkedChanged.connect(self._update_counts)
        self.tabs.addTab(self.dir_tab, "")
        self.cat_tabs = {}
        for cat in ORDER:
            tab = CategoryTab(cat)
            tab.model.checkedChanged.connect(self._update_counts)
            self.cat_tabs[cat] = tab
            self.tabs.addTab(tab, "")
        root.addWidget(self.tabs, 1)

        bottom = QHBoxLayout()
        bottom.addWidget(self._build_dest_box(), 3)
        bottom.addWidget(self._build_options_box(), 2)
        root.addLayout(bottom)

        root.addLayout(self._build_footer())

        self.log = QPlainTextEdit(readOnly=True)
        self.log.setMaximumHeight(90)
        self.log.setPlaceholderText(tr("Journal des opérations"))
        root.addWidget(self.log)

        self._restore_settings()
        self.refresh_drives()
        self._update_counts()

    # ------------------------------------------------------------------ UI
    def _build_header(self):
        logo = QLabel()
        pix = QPixmap(resource_path(os.path.join("assets", "logo_symbol.png")))
        if not pix.isNull():
            dpr = self.devicePixelRatioF()
            pix = pix.scaled(int(40 * dpr), int(40 * dpr), Qt.KeepAspectRatio,
                             Qt.SmoothTransformation)
            pix.setDevicePixelRatio(dpr)
            logo.setPixmap(pix)
        title = QLabel("<span style='font-size:17pt; font-weight:600;'>Easy Backup</span>"
                       f"<br><span style='color:gray;'>{tr('par StaysaProd')} · v{__version__}"
                       f" · <a href='{REPO_URL}'>GitHub</a></span>")
        title.setOpenExternalLinks(True)

        self.lang_combo = QComboBox()
        for code, name in i18n.LANGUAGES.items():
            self.lang_combo.addItem(name, code)
        self.lang_combo.setCurrentIndex(self.lang_combo.findData(i18n.LANG))
        self.lang_combo.activated.connect(self._language_chosen)

        row = QHBoxLayout()
        row.addWidget(logo)
        row.addWidget(title)
        row.addStretch(1)
        row.addWidget(QLabel(tr("Langue :")))
        row.addWidget(self.lang_combo)
        return row

    def _build_source_box(self):
        box = QGroupBox(tr("① Dossier ou disque source"))
        self.source_edit = QLineEdit(placeholderText=tr("Choisissez le dossier à analyser…"))
        self.source_edit.returnPressed.connect(self.start_scan)
        btn = QPushButton(tr("Parcourir…"))
        btn.clicked.connect(self._browse_source)
        self.hidden_check = QCheckBox(tr("Inclure les fichiers cachés"))
        self.scan_btn = QPushButton(tr("Analyser"))
        self.scan_btn.setDefault(True)
        self.scan_btn.clicked.connect(self._scan_clicked)
        self.scan_label = QLabel("")
        self.scan_label.setStyleSheet("color: gray;")

        row = QHBoxLayout()
        row.addWidget(self.source_edit, 1)
        row.addWidget(btn)
        row.addWidget(self.hidden_check)
        row.addWidget(self.scan_btn)
        lay = QVBoxLayout(box)
        lay.addLayout(row)
        lay.addWidget(self.scan_label)
        return box

    def _build_dest_box(self):
        box = QGroupBox(tr("② Destination (disque dur, clé USB, carte SD…)"))
        self.drive_combo = QComboBox()
        self.drive_combo.activated.connect(self._drive_chosen)
        refresh = QPushButton("↻")
        refresh.setToolTip(tr("Actualiser la liste des disques (après branchement d'une clé…)"))
        refresh.setFixedWidth(34)
        refresh.clicked.connect(self.refresh_drives)

        self.dest_edit = QLineEdit(placeholderText=tr("Dossier de destination"))
        self.dest_edit.textChanged.connect(self._update_free_space)
        browse = QPushButton(tr("Parcourir…"))
        browse.clicked.connect(self._browse_dest)
        self.free_label = QLabel("")

        r1 = QHBoxLayout()
        r1.addWidget(QLabel(tr("Support :")))
        r1.addWidget(self.drive_combo, 1)
        r1.addWidget(refresh)
        r2 = QHBoxLayout()
        r2.addWidget(QLabel(tr("Dossier :")))
        r2.addWidget(self.dest_edit, 1)
        r2.addWidget(browse)
        lay = QVBoxLayout(box)
        lay.addLayout(r1)
        lay.addLayout(r2)
        lay.addWidget(self.free_label)
        return box

    def _build_options_box(self):
        box = QGroupBox(tr("③ Options"))
        self.mode_combo = QComboBox()
        self.mode_combo.addItem(tr("Copier (les originaux restent)"), "copy")
        self.mode_combo.addItem(tr("Déplacer (les originaux sont supprimés)"), "move")
        self.mode_combo.currentIndexChanged.connect(self._update_free_space)
        self.layout_combo = QComboBox()
        self.layout_combo.addItem(tr("Ranger par type (Images, Vidéos…)"), "by_type")
        self.layout_combo.addItem(tr("Conserver l'arborescence d'origine"), "keep_tree")
        self.layout_combo.addItem(tr("Tout dans le même dossier"), "flat")
        self.conflict_combo = QComboBox()
        self.conflict_combo.addItem(tr("Renommer — « photo (1).jpg »"), "rename")
        self.conflict_combo.addItem(tr("Ignorer le fichier déjà présent"), "skip")
        self.conflict_combo.addItem(tr("Remplacer le fichier existant"), "overwrite")

        lay = QVBoxLayout(box)
        for label, combo in ((tr("Mode :"), self.mode_combo),
                             (tr("Organisation :"), self.layout_combo),
                             (tr("Si le fichier existe :"), self.conflict_combo)):
            row = QHBoxLayout()
            lbl = QLabel(label)
            lbl.setMinimumWidth(115)
            row.addWidget(lbl)
            row.addWidget(combo, 1)
            lay.addLayout(row)
        note = QLabel(tr("Les dossiers cochés gardent toujours leur structure."))
        note.setStyleSheet("color: gray;")
        lay.addWidget(note)
        return box

    def _build_footer(self):
        self.summary_label = QLabel()
        self.summary_label.setStyleSheet("font-weight: bold;")
        self.progress = QProgressBar()
        self.progress.setRange(0, 1000)
        self.progress.setTextVisible(False)
        self.status_label = QLabel("")
        self.status_label.setStyleSheet("color: gray;")

        self.go_btn = QPushButton(tr("Transférer  ➜"))
        self.go_btn.setMinimumHeight(36)
        self.go_btn.setMinimumWidth(150)
        self.go_btn.setStyleSheet(
            "QPushButton { background:#0067c0; color:white; font-weight:bold;"
            " border-radius:4px; padding:4px 14px; }"
            "QPushButton:disabled { background:#9bbbe0; }"
            "QPushButton:hover:!disabled { background:#1975c5; }")
        self.go_btn.clicked.connect(self.start_transfer)
        self.cancel_btn = QPushButton(tr("Annuler"))
        self.cancel_btn.setMinimumHeight(36)
        self.cancel_btn.setEnabled(False)
        self.cancel_btn.clicked.connect(self._cancel)

        left = QVBoxLayout()
        left.addWidget(self.summary_label)
        left.addWidget(self.progress)
        left.addWidget(self.status_label)
        row = QHBoxLayout()
        row.addLayout(left, 1)
        row.addWidget(self.cancel_btn)
        row.addWidget(self.go_btn)
        return row

    # ------------------------------------------------------------- langue
    def _language_chosen(self, index):
        code = self.lang_combo.itemData(index)
        if code == i18n.LANG:
            return
        if self._busy:  # pas de redémarrage pendant une analyse ou un transfert
            self.lang_combo.setCurrentIndex(self.lang_combo.findData(i18n.LANG))
            return
        self.settings.setValue("language", code)
        QMessageBox.information(
            self, tr("Changer de langue"),
            tr("L'application va redémarrer pour passer en {language}.",
               language=i18n.LANGUAGES[code]))
        self.close()
        if getattr(sys, "frozen", False):
            QProcess.startDetached(sys.executable, sys.argv[1:])
        else:
            QProcess.startDetached(sys.executable, sys.argv)
        QApplication.quit()

    # ------------------------------------------------------------ settings
    def _restore_settings(self):
        s = self.settings
        self.source_edit.setText(s.value("source", ""))
        self.dest_edit.setText(s.value("dest", ""))
        self.hidden_check.setChecked(s.value("hidden", False, type=bool))
        for combo, key in ((self.mode_combo, "mode"), (self.layout_combo, "layout"),
                           (self.conflict_combo, "conflict")):
            i = combo.findData(s.value(key, ""))
            if i >= 0:
                combo.setCurrentIndex(i)

    def _save_settings(self):
        s = self.settings
        s.setValue("source", self.source_edit.text())
        s.setValue("dest", self.dest_edit.text())
        s.setValue("hidden", self.hidden_check.isChecked())
        s.setValue("mode", self.mode_combo.currentData())
        s.setValue("layout", self.layout_combo.currentData())
        s.setValue("conflict", self.conflict_combo.currentData())

    # -------------------------------------------------------------- source
    def _browse_source(self):
        d = QFileDialog.getExistingDirectory(self, tr("Dossier source"), self.source_edit.text())
        if d:
            self.source_edit.setText(QDir.toNativeSeparators(d))
            self.start_scan()

    def _scan_clicked(self):
        if self._busy == "scan":
            self._cancel()
        else:
            self.start_scan()

    def start_scan(self):
        if self._busy:
            return
        src = self.source_edit.text().strip()
        if not src or not os.path.isdir(src):
            QMessageBox.warning(self, tr("Source invalide"),
                                tr("Choisissez un dossier source existant."))
            return
        self._source_root = os.path.abspath(src)
        self._log(tr("Analyse de {path}…", path=self._source_root))
        try:
            worker = ScanWorker(self._source_root, self.hidden_check.isChecked(), self)
        except FileNotFoundError as exc:
            QMessageBox.critical(self, tr("Moteur introuvable"), str(exc))
            return
        worker.progress.connect(self._on_scan_progress)
        worker.phase.connect(self._on_scan_phase)
        worker.finished.connect(self._on_scan_finished)

        # disque entier : on connaît l'espace occupé, d'où un pourcentage réaliste
        self._scan_used = 0
        if os.path.dirname(self._source_root) == self._source_root:
            st = QStorageInfo(self._source_root)
            if st.isValid():
                self._scan_used = max(st.bytesTotal() - st.bytesAvailable(), 1)
        self._scan_stats = (0, 0, 0, self._source_root)
        self._scan_phase = ""
        self._t0 = time.monotonic()
        if self._scan_used:
            self.progress.setRange(0, 1000)
            self.progress.setValue(0)
        else:
            self.progress.setRange(0, 0)  # animation « en cours »
        self._start_worker(worker, "scan")
        self._scan_timer.start()
        self._refresh_scan_status()

    def _on_scan_progress(self, count, nbytes, ndirs, current):
        self._scan_stats = (count, nbytes, ndirs, current)
        self._refresh_scan_status()

    def _on_scan_phase(self, text):
        self._scan_phase = text
        self.progress.setRange(0, 0)
        self._refresh_scan_status()

    def _refresh_scan_status(self):
        count, nbytes, ndirs, current = self._scan_stats
        elapsed = format_duration(time.monotonic() - self._t0)
        if self._scan_phase:
            self.status_label.setText(f"{self._scan_phase}  ·  {elapsed}")
            self.scan_label.setText(tr("{files} trouvé(s) — préparation de la liste…",
                                       files=n_files(count)))
            return
        pct = ""
        if self._scan_used and self.progress.maximum():
            frac = min(nbytes / self._scan_used, 0.99)
            self.progress.setValue(int(frac * 1000))
            pct = f"{frac:.0%}  ·  "
        self.status_label.setText(tr(
            "Analyse en cours…  {pct}{files}  ·  {size}  ·  {dirs}  ·  {elapsed}",
            pct=pct, files=n_files(count), size=human_size(nbytes), dirs=n_dirs(ndirs),
            elapsed=elapsed))
        self.scan_label.setText(self.scan_label.fontMetrics().elidedText(
            f"📂 {current}", Qt.ElideMiddle, max(self.scan_label.width(), 200)))

    def _on_scan_finished(self, res):
        self._scan_timer.stop()
        elapsed = format_duration(time.monotonic() - self._t0)
        self.dir_tab.set_root(res["tree"])
        for cat, tab in self.cat_tabs.items():
            tab.model.set_entries(res["by_cat"][cat], presorted=True)

        msg = tr("{files} trouvé(s) ({size})", files=n_files(res["count"]),
                 size=human_size(res["bytes"]))
        if res["errors"]:
            msg += tr(" — {n} dossier(s) illisible(s) ignoré(s)", n=res["errors"])
        if res["cancelled"]:
            msg += tr(" — analyse interrompue")
        if res["error"]:
            self._log(tr("❌ Erreur du moteur : {error}", error=res["error"]))
            QMessageBox.warning(self, tr("Analyse"),
                                tr("L'analyse a échoué :\n{error}", error=res["error"]))
        self.scan_label.setText(msg)
        self._log(tr("{msg} en {elapsed}", msg=msg, elapsed=elapsed))
        self.progress.setRange(0, 1000)
        self.progress.setValue(0 if res["cancelled"] else 1000)
        self.status_label.setText(tr("Analyse terminée en {elapsed}", elapsed=elapsed))
        # ouvre le premier onglet de fichiers non vide
        for cat in ORDER:
            if res["by_cat"][cat]:
                self.tabs.setCurrentWidget(self.cat_tabs[cat])
                break
        self._worker_done()

    # --------------------------------------------------------- destination
    def refresh_drives(self):
        current = self.drive_combo.currentData()
        self.drive_combo.clear()
        icons = QFileIconProvider()
        vols = []
        for vol in QStorageInfo.mountedVolumes():
            if not vol.isValid() or not vol.isReady() or vol.isReadOnly():
                continue
            root = QDir.toNativeSeparators(vol.rootPath())
            vols.append((not is_removable(root), root, vol))
        for _, root, vol in sorted(vols, key=lambda v: (v[0], v[1])):
            text = tr("{root}  {name}  —  {kind}  —  {free} libres sur {total}",
                      root=root, name=vol.name() or tr("Sans nom"), kind=drive_kind(root),
                      free=human_size(vol.bytesAvailable()), total=human_size(vol.bytesTotal()))
            self.drive_combo.addItem(icons.icon(QFileInfo(root)), text, root)

        i = self.drive_combo.findData(current)
        if i < 0 and self.dest_edit.text():
            i = self._combo_index_for_path(self.dest_edit.text())
        if i < 0:
            i = self._default_drive_index()
            if i >= 0:
                self.drive_combo.setCurrentIndex(i)
                self._drive_chosen(i)
        if i >= 0:
            self.drive_combo.setCurrentIndex(i)
        self._update_free_space()

    def _default_drive_index(self):
        """Premier disque amovible, sinon premier disque différent de la source."""
        src = self.source_edit.text()
        for i in range(self.drive_combo.count()):
            root = self.drive_combo.itemData(i)
            if not src or not same_volume(root, src):
                return i
        return 0 if self.drive_combo.count() else -1

    def _combo_index_for_path(self, path):
        for i in range(self.drive_combo.count()):
            if same_volume(self.drive_combo.itemData(i), path):
                return i
        return -1

    def _drive_chosen(self, index):
        root = self.drive_combo.itemData(index)
        if root:
            self.dest_edit.setText(os.path.join(root, DEFAULT_SUBFOLDER))

    def _browse_dest(self):
        start = existing_parent(self.dest_edit.text()) if self.dest_edit.text() else ""
        d = QFileDialog.getExistingDirectory(self, tr("Dossier de destination"), start)
        if d:
            self.dest_edit.setText(QDir.toNativeSeparators(d))
            i = self._combo_index_for_path(d)
            if i >= 0:
                self.drive_combo.setCurrentIndex(i)

    def _dest_storage(self):
        dest = self.dest_edit.text().strip()
        if not dest:
            return None
        st = QStorageInfo(existing_parent(dest))
        return st if st.isValid() and st.isReady() else None

    def _update_free_space(self):
        st = self._dest_storage()
        if not st:
            self.free_label.setText("")
            return
        free = st.bytesAvailable()
        needed = self._needed_bytes()
        fs = bytes(st.fileSystemType()).decode(errors="ignore")
        text = tr("Espace libre : {free}  ·  Système de fichiers : {fs}",
                  free=human_size(free), fs=fs)
        if needed > free:
            text += tr("  ·  ⚠️ il manque {missing}", missing=human_size(needed - free))
            self.free_label.setStyleSheet("color: #c42b1c;")
        else:
            self.free_label.setStyleSheet("")
        self.free_label.setText(text)

    def _needed_bytes(self):
        dest = self.dest_edit.text()
        if self.mode_combo.currentData() == "move" and dest and self._source_root \
                and same_volume(self._source_root, dest):
            return 0  # déplacement sur le même disque : simple renommage
        return self._sel_bytes

    # ---------------------------------------------------------- sélection
    def _selection(self):
        """(dossiers cochés, fichiers cochés qui ne sont pas déjà dans ces dossiers)."""
        dirs = self.dir_tab.model.checked_nodes()
        files = [e for tab in self.cat_tabs.values() for e in tab.model.checked_entries()]
        if dirs:
            rels = {d.rel for d in dirs}
            files = [e for e in files if not is_covered(e, rels)]
        return dirs, files

    def _update_counts(self):
        # compteurs tenus à jour par les modèles : pas de recomptage à chaque clic
        count = size_files = 0
        for cat in ORDER:
            model = self.cat_tabs[cat].model
            count += model.checked_count
            size_files += model.checked_size
            total = fmt_int(len(model.all_entries()))
            label = (f"{ICONS[cat]}  {tr(cat)}  ({fmt_int(model.checked_count)}/{total})"
                     if model.checked_count else f"{ICONS[cat]}  {tr(cat)}  ({total})")
            self.tabs.setTabText(self.tabs.indexOf(self.cat_tabs[cat]), label)

        dirs = self.dir_tab.model.checked_nodes()
        if dirs and count:  # un fichier déjà inclus dans un dossier ne compte qu'une fois
            _, files = self._selection()
            count, size_files = len(files), sum(e.size for e in files)
        self.tabs.setTabText(
            self.tabs.indexOf(self.dir_tab),
            tr("📁  Dossiers ({checked})", checked=ntr(len(dirs), "{n} coché", "{n} cochés"))
            if dirs else tr("📁  Dossiers"))
        self._sel_bytes = size_files + sum(d.size for d in dirs)
        self._has_selection = bool(dirs or count)

        parts = []
        if dirs:
            parts.append(n_dirs(len(dirs)))
        if count or not dirs:
            parts.append(n_files(count))
        self.summary_label.setText(tr("Sélection : {items} — {size}",
                                      items=tr(" + ").join(parts),
                                      size=human_size(self._sel_bytes)))
        if not self._busy:
            self.go_btn.setEnabled(self._has_selection)
        self._update_free_space()

    # ----------------------------------------------------------- transfert
    def start_transfer(self):
        if self._busy:
            return
        dirs, entries = self._selection()
        if not dirs and not entries:
            QMessageBox.information(self, tr("Aucune sélection"),
                                    tr("Cochez les fichiers ou dossiers à transférer."))
            return
        dest = self.dest_edit.text().strip()
        if not dest:
            QMessageBox.warning(self, tr("Destination"), tr("Choisissez une destination."))
            return
        dest = os.path.abspath(dest)
        st = self._dest_storage()
        if not st:
            QMessageBox.warning(self, tr("Destination"),
                                tr("Le support de destination est inaccessible."))
            return
        if st.isReadOnly():
            QMessageBox.warning(self, tr("Destination"),
                                tr("Le support de destination est en lecture seule."))
            return
        for d in dirs:
            if os.path.normcase(dest + os.sep).startswith(os.path.normcase(d.path + os.sep)):
                QMessageBox.warning(self, tr("Destination"), tr(
                    "La destination se trouve à l'intérieur du dossier sélectionné :\n{path}",
                    path=d.path))
                return

        needed = self._needed_bytes()
        if needed > st.bytesAvailable():
            QMessageBox.warning(self, tr("Espace insuffisant"), tr(
                "La sélection fait {needed} mais il ne reste que {free} sur la destination.\n\n"
                "Décochez des éléments ou choisissez un autre support.",
                needed=human_size(needed), free=human_size(st.bytesAvailable())))
            return

        fs = bytes(st.fileSystemType()).decode(errors="ignore").upper()
        if fs in ("FAT32", "FAT", "VFAT", "MSDOS"):
            rels = {d.rel for d in dirs}
            in_dirs = [e for tab in self.cat_tabs.values() for e in tab.model.all_entries()
                       if e.size > FAT32_MAX and is_covered(e, rels)] if dirs else []
            too_big = [e for e in entries if e.size > FAT32_MAX] + in_dirs
            if too_big:
                names = "\n".join(f"• {e.name} ({human_size(e.size)})" for e in too_big[:8])
                more = tr("\n… et {n} autres", n=len(too_big) - 8) if len(too_big) > 8 else ""
                r = QMessageBox.question(self, tr("Fichiers trop gros pour FAT32"), tr(
                    "Le support est formaté en {fs}, qui n'accepte pas les fichiers de plus "
                    "de 4 Go :\n\n{names}{more}\n\nContinuer sans ces fichiers ?\n"
                    "(Astuce : formatez le support en exFAT ou NTFS pour les copier.)",
                    fs=fs, names=names, more=more))
                if r != QMessageBox.Yes:
                    return
                big = {id(e) for e in too_big}
                entries = [e for e in entries if id(e) not in big]
                if not entries and not dirs:
                    return

        what = []
        if dirs:
            what.append(n_dirs(len(dirs)))
        if entries:
            what.append(n_files(len(entries)))
        what = tr(" et ").join(what)

        mode = self.mode_combo.currentData()
        if mode == "move":
            r = QMessageBox.question(self, tr("Confirmer le déplacement"), tr(
                "Déplacer {what} vers\n{dest} ?\n\nLes originaux seront supprimés après copie.",
                what=what, dest=dest))
            if r != QMessageBox.Yes:
                return

        options = TransferOptions(mode=mode,
                                  layout=self.layout_combo.currentData(),
                                  conflict=self.conflict_combo.currentData())
        self._save_settings()
        message = ("Déplacement de {what} ({size}) vers {dest}" if mode == "move"
                   else "Copie de {what} ({size}) vers {dest}")
        self._log(tr(message, what=what, size=human_size(self._sel_bytes), dest=dest))
        try:
            worker = TransferWorker(entries, dirs, self._source_root, dest, options, self)
        except FileNotFoundError as exc:
            QMessageBox.critical(self, tr("Moteur introuvable"), str(exc))
            return
        worker.file_started.connect(self._on_file_started)
        worker.dir_started.connect(self._on_dir_started)
        worker.progress.connect(self._on_transfer_progress)
        worker.log.connect(self._log)
        worker.finished.connect(self._on_transfer_finished)
        self._current_file = ""
        self._t0 = time.monotonic()
        self.progress.setRange(0, 1000)
        self.progress.setValue(0)
        self._start_worker(worker, "transfer")

    def _on_file_started(self, i, n, name):
        self._current_file = tr("Fichier {i}/{n} : {name}", i=i, n=n, name=name)

    def _on_dir_started(self, i, n, name):
        self._current_file = tr("Dossier {i}/{n} : {name}", i=i, n=n, name=name)

    def _on_transfer_progress(self, done, total):
        frac = done / total if total else 1.0
        self.progress.setValue(int(frac * 1000))
        elapsed = time.monotonic() - self._t0
        extra = ""
        if elapsed > 1 and done:
            speed = done / elapsed
            remaining = (total - done) / speed if speed else 0
            extra = tr("  ·  {speed}/s  ·  reste ≈ {remaining}", speed=human_size(speed),
                       remaining=format_duration(remaining))
        self.status_label.setText(
            f"{self._current_file}  ·  {human_size(done)} / {human_size(total)} "
            f"({frac:.0%}){extra}")

    def _on_transfer_finished(self, res):
        ok, skipped, failed = res["ok"], res["skipped"], res["failed"]
        dirs_ok, dirs_skipped, dirs_failed = (res["dirs_ok"], res["dirs_skipped"],
                                              res["dirs_failed"])
        by_cat = {}
        for e in ok:
            by_cat.setdefault(e.category if e.category in self.cat_tabs else OTHER, []).append(e)
        for cat, lst in by_cat.items():
            model = self.cat_tabs[cat].model
            if res["mode"] == "move":
                model.remove_entries(lst)
            else:  # en copie, on décoche ce qui a été transféré
                model.uncheck_entries(lst)
        if res["mode"] == "copy" and dirs_ok:
            rels = {d.rel for d in dirs_ok}
            for tab in self.cat_tabs.values():  # fichiers cochés déjà copiés avec leur dossier
                tab.model.uncheck_entries([e for e in tab.model.checked_entries()
                                           if is_covered(e, rels)])
            self.dir_tab.model.set_checked(dirs_ok, False)
        # des dossiers ont été déplacés : les listes ne sont plus à jour, on réanalyse
        rescan = res["mode"] == "move" and bool(dirs_ok or dirs_failed)

        title = tr("Transfert annulé") if res["cancelled"] else tr("Transfert terminé")
        done = []
        if dirs_ok:
            done.append(n_dirs(len(dirs_ok)))
        if ok or not dirs_ok:
            done.append(n_files(len(ok)))
        lines = [tr("✅ {what} transféré(s) — {size}", what=tr(" et ").join(done),
                    size=human_size(res["bytes"]))]
        if skipped or dirs_skipped:
            lines.append(tr("⏭️ {n} élément(s) ignoré(s)", n=len(skipped) + len(dirs_skipped)))
        if failed or dirs_failed:
            lines.append(tr("❌ {n} erreur(s) — voir le journal",
                            n=len(failed) + len(dirs_failed)))
        if res["error"]:
            title = tr("Transfert interrompu")
            lines.append(f"⚠️ {res['error']}")
        self._log(tr("{title} : {details}", title=title, details=", ".join(lines)))
        self.status_label.setText(title)
        if not res["cancelled"]:
            self.progress.setValue(1000)
        self._worker_done()

        box = QMessageBox(QMessageBox.Warning if failed or dirs_failed or res["error"]
                          else QMessageBox.Information,
                          title, "\n".join(lines), parent=self)
        open_btn = box.addButton(tr("Ouvrir la destination"), QMessageBox.ActionRole)
        box.addButton(QMessageBox.Ok)
        box.exec()
        if box.clickedButton() is open_btn and os.path.isdir(res["dest"]):
            QDesktopServices.openUrl(QUrl.fromLocalFile(res["dest"]))
        if rescan:
            self.start_scan()

    # ------------------------------------------------- moteur (processus Go)
    def _start_worker(self, worker, kind):
        self._busy = kind
        self._worker = worker
        self._set_busy_ui(True)
        worker.start()

    def _worker_done(self):
        if self._worker:
            self._worker.deleteLater()
        self._worker = None
        self._busy = None
        self._set_busy_ui(False)
        self._update_counts()

    def _cancel(self):
        if self._worker:
            self._worker.cancel()
            self.cancel_btn.setEnabled(False)
            self._log(tr("Annulation demandée…"))

    def _set_busy_ui(self, busy):
        scanning = busy and self._busy == "scan"
        transferring = busy and self._busy == "transfer"
        self.scan_btn.setText(tr("Arrêter") if scanning else tr("Analyser"))
        self.scan_btn.setEnabled(not transferring)
        self.source_edit.setEnabled(not busy)
        self.tabs.setEnabled(not busy)
        self.lang_combo.setEnabled(not busy)
        for w in (self.drive_combo, self.dest_edit, self.mode_combo,
                  self.layout_combo, self.conflict_combo):
            w.setEnabled(not transferring)
        self.go_btn.setEnabled(not busy and self._has_selection)
        self.cancel_btn.setEnabled(busy)

    def _log(self, text):
        self.log.appendPlainText(f"[{time.strftime('%H:%M:%S')}] {text}")

    def closeEvent(self, event):
        if self._busy == "transfer":
            r = QMessageBox.question(self, tr("Transfert en cours"),
                                     tr("Un transfert est en cours. L'annuler et quitter ?"))
            if r != QMessageBox.Yes:
                event.ignore()
                return
        if self._worker:
            self._worker.cancel()  # le moteur supprime ses fichiers temporaires
            self._worker.wait(5000)
        self._save_settings()
        event.accept()
