#define MyAppName "SolsRNGCore"
#define MyAppVersion "0.1.0"
#define MyAppPublisher "VoidTheAngel"
#define MyAppExeName "SolsRNGCore-Windows.exe"

[Setup]
AppId={{6D8E4C5F-0F12-4D2A-9B7B-2E9A8B8A1D41}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher={#MyAppPublisher}
DefaultDirName={autopf}\SolsRNGCore
DefaultGroupName={#MyAppName}
OutputDir=installer\output
OutputBaseFilename=SolsRNGCore-Windows-Setup
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
ArchitecturesInstallIn64BitMode=x64
PrivilegesRequired=lowest
UninstallDisplayName={#MyAppName}

[Files]
Source: "dist\{#MyAppExeName}"; DestDir: "{app}"; Flags: ignoreversion

[Icons]
Name: "{group}\SolsRNGCore"; Filename: "{app}\{#MyAppExeName}"
Name: "{autodesktop}\SolsRNGCore"; Filename: "{app}\{#MyAppExeName}"; Tasks: desktopicon

[Tasks]
Name: "desktopicon"; Description: "Create a desktop shortcut"; Flags: unchecked

[Run]
Filename: "{app}\{#MyAppExeName}"; Description: "Launch SolsRNGCore"; Flags: nowait postinstall skipifsilent
