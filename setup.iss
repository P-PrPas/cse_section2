; Script generated for EDFVS Application.
; Requires Inno Setup 6+ to compile (https://jrsoftware.org/isdl.php)

#define MyAppName "EDFVS"
#define MyAppVersion "1.0.0"
#define MyAppPublisher "KU Tech Section 2"
#define MyAppExeName "EDFVS.exe"

[Setup]
; NOTE: The value of AppId uniquely identifies this application.
AppId={{EDFVS-7A8B9C0D-1E2F-3G4H-5I6J-7K8L9M0N1O2P}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher={#MyAppPublisher}
; Installs into Program Files by default
DefaultDirName={autopf}\{#MyAppName}
DisableProgramGroupPage=yes
; Output installer file name
OutputDir=Output
OutputBaseFilename=EDFVS_Setup_v1.0
Compression=lzma
SolidCompression=yes
WizardStyle=modern

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"; Flags: unchecked

[Files]
; Main executable
Source: "dist\{#MyAppName}\{#MyAppExeName}"; DestDir: "{app}"; Flags: ignoreversion
; All other files (models, ui, config, DLLs, etc.)
Source: "dist\{#MyAppName}\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{autoprograms}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; Tasks: desktopicon

[Run]
; Option to launch app after installation
Filename: "{app}\{#MyAppExeName}"; Description: "{cm:LaunchProgram,{#StringChange(MyAppName, '&', '&&')}}"; Flags: nowait postinstall skipifsilent
