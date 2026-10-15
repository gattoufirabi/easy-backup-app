import ctypes
import os
import sys

from PySide6.QtGui import QIcon
from PySide6.QtWidgets import QApplication

from easybackup import i18n
from easybackup.utils import resource_path
from easybackup.window import MainWindow

APP_ID = "StaysaProd.EasyBackup"


def main():
    if sys.platform == "win32":
        # pour que la barre des tâches affiche notre icône (et pas celle de Python)
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(APP_ID)
    app = QApplication(sys.argv)
    app.setApplicationName("Easy Backup")
    app.setOrganizationName("StaysaProd")
    i18n.init(app)  # langue choisie dans l'appli, à l'installation, ou celle de Windows
    icon = resource_path(os.path.join("assets", "icon.ico"))
    if os.path.isfile(icon):
        app.setWindowIcon(QIcon(icon))
    window = MainWindow()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
