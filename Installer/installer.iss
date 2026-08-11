#define MyAppName "BlazeLang"
#define MyAppVersion "1.7.0"
#define MyAppPublisher "ShortCodeGuy Studio"

[Setup]
AppId={{F9B91F0B-8B89-4C11-9D47-4F7A1B0A1001}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher={#MyAppPublisher}

DefaultDirName={autopf}\BlazeLang
DefaultGroupName=BlazeLang

OutputDir=Output
OutputBaseFilename=BlazeLangSetup

Compression=lzma2
SolidCompression=yes
WizardStyle=modern

PrivilegesRequired=admin

SetupIconFile=media\blaze.ico
UninstallDisplayIcon={app}\blaze.ico

ChangesEnvironment=yes

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; \
    Description: "Create Desktop Shortcut"; \
    Flags: unchecked

Name: "addpath"; \
    Description: "Add BlazeLang to PATH"; \
    Flags: checkedonce

[Files]

; ============================================================
; BlazeLang executable
; ============================================================

Source: "blz.exe"; \
    DestDir: "{app}"; \
    Flags: ignoreversion

; ============================================================
; Installer helper scripts
; ============================================================

Source: "install-blazelang.cmd"; \
    DestDir: "{app}"; \
    Flags: ignoreversion

Source: "Install-BlazeLang.ps1"; \
    DestDir: "{app}"; \
    Flags: ignoreversion

; ============================================================
; Configuration
; ============================================================

Source: "BlazeLang-Terminal.json"; \
    DestDir: "{app}"; \
    Flags: ignoreversion

; ============================================================
; Documentation
; ============================================================

Source: "README.md"; \
    DestDir: "{app}"; \
    Flags: ignoreversion

Source: "BLAZELANG_REFERENCE.md"; \
    DestDir: "{app}"; \
    Flags: ignoreversion

Source: "WINDOWS_COMMANDS.md"; \
    DestDir: "{app}"; \
    Flags: ignoreversion

; ============================================================
; BlazeLang icon
; ============================================================

Source: "media\blaze.ico"; \
    DestDir: "{app}"; \
    Flags: ignoreversion

[Icons]

Name: "{group}\BlazeLang"; \
    Filename: "{app}\blz.exe"; \
    WorkingDir: "{app}"

Name: "{group}\Uninstall BlazeLang"; \
    Filename: "{uninstallexe}"

Name: "{autodesktop}\BlazeLang"; \
    Filename: "{app}\blz.exe"; \
    WorkingDir: "{app}"; \
    Tasks: desktopicon

[Registry]

; ============================================================
; Add BlazeLang to PATH
; ============================================================

Root: HKCU; \
    Subkey: "Environment"; \
    ValueType: expandsz; \
    ValueName: "Path"; \
    ValueData: "{olddata};{app}"; \
    Check: NeedsAddPath(ExpandConstant('{app}')); \
    Tasks: addpath

[Run]

; ============================================================
; Configure BlazeLang
; ============================================================

Filename: "{sys}\WindowsPowerShell\v1.0\powershell.exe"; \
    Parameters: "-NoProfile -ExecutionPolicy Bypass -File ""{app}\Install-BlazeLang.ps1"""; \
    Description: "Configure BlazeLang"; \
    Flags: waituntilterminated postinstall skipifsilent

; ============================================================
; Launch BlazeLang
; ============================================================

Filename: "{app}\blz.exe"; \
    Description: "Launch BlazeLang"; \
    Flags: nowait postinstall skipifsilent

[Code]

function NeedsAddPath(Dir: string): Boolean;
var
  Path: string;
begin
  Result := True;

  if RegQueryStringValue(
    HKCU,
    'Environment',
    'Path',
    Path
  ) then
  begin
    if Pos(
      LowerCase(Dir),
      LowerCase(Path)
    ) > 0 then
      Result := False;
  end;
end;