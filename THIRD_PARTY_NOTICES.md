# Third-party notices

Easy Backup is licensed under the [GNU General Public License v3.0](LICENSE).
The Windows installer also contains the following third-party software.

| Component | Used for | License |
|---|---|---|
| [Qt 6](https://www.qt.io/) and [PySide6 / Shiboken6](https://doc.qt.io/qtforpython-6/) | User interface | Used under GPL-3.0 (PySide6 is offered under LGPL-3.0, GPL-2.0 or GPL-3.0) — text in [`LICENSE`](LICENSE) |
| [Python](https://www.python.org/) runtime, with OpenSSL, libffi, bzip2, xz and the other libraries of the official Windows build | Application runtime | PSF License Agreement and the licenses listed in [`licenses/Python-LICENSE.txt`](licenses/Python-LICENSE.txt) |
| [Go](https://go.dev/) runtime and standard library (compiled into `ebengine.exe`) | Scan and transfer engine | BSD 3-Clause — [`licenses/Go-LICENSE.txt`](licenses/Go-LICENSE.txt) |
| Microsoft Visual C++ runtime (`vcruntime140.dll`, `ucrtbase.dll`, `api-ms-win-*.dll`) | Required by Python and Qt | Redistributable under the Microsoft Visual Studio license terms |

Build tools that are **not** shipped in the installer: [PyInstaller](https://pyinstaller.org/)
(its bootloader is distributed under GPL-2.0 with an exception that allows bundling it with
any program), [Pillow](https://python-pillow.org/) (used only to generate the icons) and
[Inno Setup](https://jrsoftware.org/isinfo.php).

The StaysaProd logo and name are the property of StaysaProd. They are not covered by the
GPL; forks should use their own branding.
