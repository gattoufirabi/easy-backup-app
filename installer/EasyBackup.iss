; Installeur hors-ligne de Easy Backup (Inno Setup 6).
; Tout est inclus dans le setup : aucune connexion Internet n'est nécessaire.
; Compilé par build_installer.bat.

#define AppName "Easy Backup"
; version passée par build_installer.bat (ex. depuis un tag Git v1.2.0)
#ifndef AppVersion
  #define AppVersion "1.0.0"
#endif
#define AppURL "https://gattoufirabi.github.io/easy-backup/"
#define RepoURL "https://github.com/gattoufirabi/easy-backup-app"
#define AppPublisher "StaysaProd"
#define AppExe "EasyBackup.exe"

[Setup]
AppId={{F84C2E6A-62FA-4AAD-92BB-280063756F7E}
AppName={#AppName}
AppVersion={#AppVersion}
AppVerName={#AppName} {#AppVersion}
AppPublisher={#AppPublisher}
AppPublisherURL={#AppURL}
AppSupportURL={#RepoURL}/issues
AppUpdatesURL={#RepoURL}/releases
DefaultDirName={autopf}\{#AppName}
DefaultGroupName={#AppName}
DisableProgramGroupPage=yes
; installation sans droits administrateur par défaut, au choix de l'utilisateur
PrivilegesRequired=lowest
PrivilegesRequiredOverridesAllowed=dialog
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
MinVersion=10.0
OutputDir=..\dist
OutputBaseFilename=EasyBackup-Setup-{#AppVersion}
SetupIconFile=..\assets\icon.ico
UninstallDisplayIcon={app}\{#AppExe}
UninstallDisplayName={#AppName}
WizardStyle=modern
WizardImageFile=..\assets\wizard_large.bmp,..\assets\wizard_large_200.bmp
WizardSmallImageFile=..\assets\wizard_small.bmp,..\assets\wizard_small_200.bmp
Compression=lzma2/max
SolidCompression=yes
CloseApplications=yes
VersionInfoCompany={#AppPublisher}
VersionInfoProductName={#AppName}
VersionInfoVersion={#AppVersion}

; La langue choisie au début de l'installation est aussi celle de l'application.
ShowLanguageDialog=yes

[Languages]
Name: "french"; MessagesFile: "compiler:Languages\French.isl"
Name: "english"; MessagesFile: "compiler:Default.isl"

[INI]
; lu par l'application au démarrage (easybackup/i18n.py)
Filename: "{app}\language.ini"; Section: "app"; Key: "language"; String: "{language}"

[Registry]
; efface un ancien choix fait dans l'application : la langue de l'installation s'applique
Root: HKCU; Subkey: "Software\StaysaProd\Easy Backup"; ValueName: "language"; ValueType: none; Flags: deletevalue

[UninstallDelete]
Type: files; Name: "{app}\language.ini"

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"

[Files]
Source: "..\dist\EasyBackup\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs
Source: "..\LICENSE"; DestDir: "{app}"; DestName: "LICENSE.txt"; Flags: ignoreversion
Source: "..\THIRD_PARTY_NOTICES.md"; DestDir: "{app}"; Flags: ignoreversion
Source: "..\licenses\*"; DestDir: "{app}\licenses"; Flags: ignoreversion

[Icons]
Name: "{autoprograms}\{#AppName}"; Filename: "{app}\{#AppExe}"
Name: "{autodesktop}\{#AppName}"; Filename: "{app}\{#AppExe}"; Tasks: desktopicon

[Run]
Filename: "{app}\{#AppExe}"; Description: "{cm:LaunchProgram,{#AppName}}"; Flags: nowait postinstall skipifsilent
