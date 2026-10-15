# Contributing to Easy Backup

Thanks for your interest! Bug reports, ideas, translations and code are all welcome.
Issues and pull requests can be written in **English or French**.

## Report a bug or suggest an idea

Open an [issue](https://github.com/gattoufirabi/easy-backup-app/issues) and include:

- your Windows version and the Easy Backup version (shown under the title in the app);
- what you did, what you expected, and what happened;
- the lines of the activity log at the bottom of the window, if relevant.

## Set up the project

Requirements: Windows, Python 3.11+, Go 1.22+ (and Inno Setup 6 only to build the installer).

```bash
git clone https://github.com/gattoufirabi/easy-backup-app.git
cd easy-backup-app
python -m venv .venv
.venv\Scripts\pip install -r requirements-dev.txt
build_engine.bat
.venv\Scripts\python main.py
```

Run the tests before opening a pull request:

```bash
.venv\Scripts\python -m pytest
cd engine && go vet ./...
```

## Code overview

- `easybackup/` — the Python / Qt interface. Heavy work never runs on the UI thread: the
  scan results are read and sorted in a background thread (`scanner.py`), and the lists sort
  and filter themselves (`models.py`).
- `engine/` — the Go engine (`ebengine.exe`), started as a hidden process. It writes one JSON
  event per line on stdout and stops cleanly when it reads `cancel` on stdin.
- Code comments and source texts are in French; new code can be commented in English or French.

## Texts and translations

All texts shown to users go through `tr()`:

```python
from .i18n import tr, ntr
label.setText(tr("Analyse de {path}…", path=folder))
ntr(count, "{n} fichier", "{n} fichiers")
```

The source text is French; its English translation goes in the `EN` dictionary of
[`easybackup/i18n.py`](easybackup/i18n.py). `tests/test_i18n.py` fails if a text has no
translation or if the `{placeholders}` differ. Engine messages use `T("français", "english")`.

**Adding a language**: add it to `LANGUAGES` and add a dictionary next to `EN` in `i18n.py`,
add the matching `T()` texts in the engine, and add the language to `[Languages]` in
`installer/EasyBackup.iss` (Inno Setup ships translations for its own screens).

## Pull requests

- Keep each pull request focused on one change.
- Add or update tests in `tests/` when you change the engine or the selection logic.
- Make sure `pytest` and `go vet` pass; the CI runs them on every pull request.
- Contributions are accepted under the project's license, the [GPL-3.0](LICENSE).

## Releases (maintainers)

Push a tag such as `v1.2.0`. The [release workflow](.github/workflows/release.yml) builds the
engine, the app and the installer, then publishes `EasyBackup-Setup.exe` on the GitHub release.
The website's download button always points to the latest release.

Every push to `main` also builds a test installer, available for 14 days in the *Artifacts*
section of the CI run.

The release build compiles PyInstaller's bootloader from source (`tools/ci_build.ps1`) and
gives every executable Windows version information, which reduces antivirus false positives.

**Code signing**: `build_installer.bat` signs the app, the engine, the installer and the
uninstaller when the `EB_SIGN` environment variable contains a signing command (the file to
sign is appended), for example:

```bat
set EB_SIGN=signtool sign /fd sha256 /tr http://timestamp.digicert.com /td sha256 /a
build_installer.bat
```
