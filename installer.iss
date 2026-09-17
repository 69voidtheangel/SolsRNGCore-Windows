#define MyAppName "SolsRNGCore"
#define MyAppVersion "0.1.0"
#define MyAppPublisher "VoidTheAngel"
#define MyAppExeName "SolsRNGCore.exe"

[Setup]
AppId={{8E0F3F4F-3E3E-4E9E-9D6F-2F1F1B1A9C41}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher={#MyAppPublisher}
DefaultDirName={localappdata}\Programs\SolsRNGCore
DefaultGroupName={#MyAppName}
OutputDir=installer\output
OutputBaseFilename=SolsRNGCore-Setup
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
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
