"""Langues de l'interface : français (texte source) et anglais.

    tr("Analyse de {path}…", path=p)        texte simple
    ntr(n, "{n} fichier", "{n} fichiers")   singulier / pluriel

Ordre de choix de la langue :
1. choix fait dans l'application (QSettings « language ») ;
2. langue choisie à l'installation (language.ini à côté de l'exécutable) ;
3. langue de Windows.
"""

import configparser
import os
import sys

from PySide6.QtCore import QLibraryInfo, QLocale, QSettings, QTranslator

LANGUAGES = {"fr": "Français", "en": "English"}
DEFAULT = "en"

LANG = "fr"
_translators = []  # gardés en vie pour Qt

EN = {
    # --- onglets et listes ---------------------------------------------------
    "Images": "Images",
    "Vidéos": "Videos",
    "Audio": "Audio",
    "Documents": "Documents",
    "Archives": "Archives",
    "Autres": "Others",
    "📁  Dossiers": "📁  Folders",
    "📁  Dossiers ({checked})": "📁  Folders ({checked})",
    "{n} coché": "{n} checked",
    "{n} cochés": "{n} checked",
    "Nom": "Name",
    "Taille": "Size",
    "Modifié le": "Modified",
    "Dossier": "Folder",
    "Fichiers": "Files",
    "\n(inclus dans un dossier parent coché)": "\n(included in a checked parent folder)",
    "🔍  Filtrer par nom ou dossier…": "🔍  Filter by name or folder…",
    "Tout cocher": "Check all",
    "Tout décocher": "Uncheck all",
    "Inverser": "Invert",
    "Tout réduire": "Collapse all",
    "Astuce : sélectionnez plusieurs lignes (Maj/Ctrl + clic) puis appuyez sur "
    "<b>Espace</b> pour les cocher. Double-clic pour ouvrir.":
        "Tip: select several rows (Shift/Ctrl + click), then press <b>Space</b> to check "
        "them. Double-click to open.",
    "Cochez un dossier pour le transférer <b>en entier</b> : sous-dossiers, fichiers "
    "cachés et structure compris.":
        "Check a folder to transfer it <b>as a whole</b>: subfolders, hidden files and "
        "structure included.",
    "Astuce : sélectionnez plusieurs dossiers puis appuyez sur <b>Espace</b>. Clic droit "
    "pour ouvrir un dossier dans l'Explorateur.":
        "Tip: select several folders, then press <b>Space</b>. Right-click to open a folder "
        "in Explorer.",
    "Cocher la sélection": "Check selection",
    "Décocher la sélection": "Uncheck selection",
    "Ouvrir": "Open",
    "Afficher dans l'Explorateur": "Show in Explorer",
    "Ouvrir dans l'Explorateur": "Open in Explorer",

    # --- fenêtre -------------------------------------------------------------
    "Easy Backup — transfert de fichiers": "Easy Backup — file transfer",
    "par StaysaProd": "by StaysaProd",
    "Langue :": "Language:",
    "Changer de langue": "Change language",
    "L'application va redémarrer pour passer en {language}.":
        "The application will restart in {language}.",
    "Journal des opérations": "Activity log",
    "① Dossier ou disque source": "① Source folder or drive",
    "Choisissez le dossier à analyser…": "Choose the folder to scan…",
    "Parcourir…": "Browse…",
    "Inclure les fichiers cachés": "Include hidden files",
    "Analyser": "Scan",
    "Arrêter": "Stop",
    "② Destination (disque dur, clé USB, carte SD…)":
        "② Destination (hard drive, USB stick, SD card…)",
    "Actualiser la liste des disques (après branchement d'une clé…)":
        "Refresh the drive list (after plugging in a USB stick…)",
    "Dossier de destination": "Destination folder",
    "Support :": "Drive:",
    "Dossier :": "Folder:",
    "③ Options": "③ Options",
    "Copier (les originaux restent)": "Copy (originals are kept)",
    "Déplacer (les originaux sont supprimés)": "Move (originals are deleted)",
    "Ranger par type (Images, Vidéos…)": "Sort by type (Images, Videos…)",
    "Conserver l'arborescence d'origine": "Keep the original folder structure",
    "Tout dans le même dossier": "Everything in one folder",
    "Renommer — « photo (1).jpg »": "Rename — “photo (1).jpg”",
    "Ignorer le fichier déjà présent": "Skip the existing file",
    "Remplacer le fichier existant": "Replace the existing file",
    "Mode :": "Mode:",
    "Organisation :": "Layout:",
    "Si le fichier existe :": "If the file exists:",
    "Les dossiers cochés gardent toujours leur structure.":
        "Checked folders always keep their structure.",
    "Transférer  ➜": "Transfer  ➜",
    "Annuler": "Cancel",

    # --- analyse -------------------------------------------------------------
    "Dossier source": "Source folder",
    "Source invalide": "Invalid source",
    "Choisissez un dossier source existant.": "Choose an existing source folder.",
    "Analyse de {path}…": "Scanning {path}…",
    "Moteur introuvable": "Engine not found",
    "{n} fichier": "{n} file",
    "{n} fichiers": "{n} files",
    "{n} dossier": "{n} folder",
    "{n} dossiers": "{n} folders",
    "{files} trouvé(s) — préparation de la liste…": "{files} found — preparing the list…",
    "Analyse en cours…  {pct}{files}  ·  {size}  ·  {dirs}  ·  {elapsed}":
        "Scanning…  {pct}{files}  ·  {size}  ·  {dirs}  ·  {elapsed}",
    "Classement de {n} fichiers…": "Sorting {n} files…",
    "{files} trouvé(s) ({size})": "{files} found ({size})",
    " — {n} dossier(s) illisible(s) ignoré(s)": " — {n} unreadable folder(s) skipped",
    " — analyse interrompue": " — scan interrupted",
    "❌ Erreur du moteur : {error}": "❌ Engine error: {error}",
    "Analyse": "Scan",
    "L'analyse a échoué :\n{error}": "The scan failed:\n{error}",
    "{msg} en {elapsed}": "{msg} in {elapsed}",
    "Analyse terminée en {elapsed}": "Scan finished in {elapsed}",

    # --- destination ---------------------------------------------------------
    "Sans nom": "Unnamed",
    "{root}  {name}  —  {kind}  —  {free} libres sur {total}":
        "{root}  {name}  —  {kind}  —  {free} free of {total}",
    "Amovible": "Removable",
    "Disque local": "Local disk",
    "Réseau": "Network",
    "CD/DVD": "CD/DVD",
    "Disque RAM": "RAM disk",
    "Disque": "Disk",
    "Volume": "Volume",
    "Espace libre : {free}  ·  Système de fichiers : {fs}":
        "Free space: {free}  ·  File system: {fs}",
    "  ·  ⚠️ il manque {missing}": "  ·  ⚠️ {missing} short",

    # --- sélection et transfert ----------------------------------------------
    "Sélection : {items} — {size}": "Selection: {items} — {size}",
    " + ": " + ",
    " et ": " and ",
    "Aucune sélection": "Nothing selected",
    "Cochez les fichiers ou dossiers à transférer.": "Check the files or folders to transfer.",
    "Destination": "Destination",
    "Choisissez une destination.": "Choose a destination.",
    "Le support de destination est inaccessible.": "The destination drive is not accessible.",
    "Le support de destination est en lecture seule.": "The destination drive is read-only.",
    "La destination se trouve à l'intérieur du dossier sélectionné :\n{path}":
        "The destination is inside the selected folder:\n{path}",
    "Espace insuffisant": "Not enough space",
    "La sélection fait {needed} mais il ne reste que {free} sur la destination.\n\n"
    "Décochez des éléments ou choisissez un autre support.":
        "The selection takes {needed} but only {free} is left on the destination.\n\n"
        "Uncheck some items or choose another drive.",
    "Fichiers trop gros pour FAT32": "Files too large for FAT32",
    "\n… et {n} autres": "\n… and {n} more",
    "Le support est formaté en {fs}, qui n'accepte pas les fichiers de plus de 4 Go :"
    "\n\n{names}{more}\n\nContinuer sans ces fichiers ?\n"
    "(Astuce : formatez le support en exFAT ou NTFS pour les copier.)":
        "The drive is formatted as {fs}, which does not accept files larger than 4 GB:"
        "\n\n{names}{more}\n\nContinue without these files?\n"
        "(Tip: format the drive as exFAT or NTFS to copy them.)",
    "Confirmer le déplacement": "Confirm move",
    "Déplacer {what} vers\n{dest} ?\n\nLes originaux seront supprimés après copie.":
        "Move {what} to\n{dest}?\n\nThe originals will be deleted after copying.",
    "Déplacement de {what} ({size}) vers {dest}": "Moving {what} ({size}) to {dest}",
    "Copie de {what} ({size}) vers {dest}": "Copying {what} ({size}) to {dest}",
    "Fichier {i}/{n} : {name}": "File {i}/{n}: {name}",
    "Dossier {i}/{n} : {name}": "Folder {i}/{n}: {name}",
    "  ·  {speed}/s  ·  reste ≈ {remaining}": "  ·  {speed}/s  ·  ≈ {remaining} left",
    "Transfert annulé": "Transfer cancelled",
    "Transfert terminé": "Transfer complete",
    "Transfert interrompu": "Transfer interrupted",
    "✅ {what} transféré(s) — {size}": "✅ {what} transferred — {size}",
    "⏭️ {n} élément(s) ignoré(s)": "⏭️ {n} item(s) skipped",
    "❌ {n} erreur(s) — voir le journal": "❌ {n} error(s) — see the log",
    "{title} : {details}": "{title}: {details}",
    "Ouvrir la destination": "Open destination",
    "Annulation demandée…": "Cancelling…",
    "Transfert en cours": "Transfer in progress",
    "Un transfert est en cours. L'annuler et quitter ?":
        "A transfer is in progress. Cancel it and quit?",
    "Ignoré (source = destination) : {path}": "Skipped (source = destination): {path}",
    "Déjà présent, ignoré : {path}": "Already exists, skipped: {path}",
    "📁 Dossier transféré : {src} → {dest}": "📁 Folder transferred: {src} → {dest}",
    "Dossier déjà présent, ignoré : {path}": "Folder already exists, skipped: {path}",
    "❌ Dossier {path} → {error}": "❌ Folder {path} → {error}",

    # --- moteur --------------------------------------------------------------
    "Le moteur {name} est introuvable ({path}).\n"
    "Lancez build_engine.bat pour le compiler (nécessite Go).":
        "The {name} engine was not found ({path}).\n"
        "Run build_engine.bat to compile it (requires Go).",
    "impossible de lancer le moteur : {error}": "could not start the engine: {error}",
    "le moteur s'est arrêté de façon inattendue (code {code})":
        "the engine stopped unexpectedly (code {code})",
}


def tr(text: str, **kwargs) -> str:
    if LANG == "en":
        text = EN.get(text, text)
    return text.format(**kwargs) if kwargs else text


def ntr(n: int, singular: str, plural: str) -> str:
    return tr(plural if n > 1 else singular, n=fmt_int(n))


def fmt_int(n: int) -> str:
    return f"{n:,}".replace(",", " " if LANG == "fr" else ",")


def install_language_file() -> str:
    """language.ini écrit par l'installeur à côté de l'exécutable."""
    if getattr(sys, "frozen", False):
        base = os.path.dirname(sys.executable)
    else:
        base = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    return os.path.join(base, "language.ini")


def detect_language() -> str:
    saved = QSettings().value("language", "")
    if saved in LANGUAGES:
        return saved
    ini = configparser.ConfigParser()
    try:
        ini.read(install_language_file(), encoding="utf-8")
        installed = ini.get("app", "language", fallback="")
    except (OSError, configparser.Error):
        installed = ""
    installed = {"french": "fr", "english": "en"}.get(installed, installed)
    if installed in LANGUAGES:
        return installed
    system = QLocale.system().name()[:2]
    return system if system in LANGUAGES else DEFAULT


def init(app) -> str:
    """Choisit la langue et traduit aussi les textes de Qt (Oui/Non, sélecteur de dossier…)."""
    global LANG
    LANG = detect_language()
    paths = [QLibraryInfo.path(QLibraryInfo.TranslationsPath)]
    if getattr(sys, "frozen", False):  # emplacement dans l'exécutable PyInstaller
        paths.append(os.path.join(sys._MEIPASS, "PySide6", "translations"))
    translator = QTranslator(app)
    if any(translator.load(f"qtbase_{LANG}", p) for p in paths):
        app.installTranslator(translator)
        _translators.append(translator)
    return LANG


def engine_args() -> list:
    return ["--lang", LANG]
