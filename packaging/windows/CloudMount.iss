; Inno Setup script for CloudMount (Windows)
; Compiled by scripts/build-windows.ps1 with /DMyAppVersion=... /DMyAppSource=... etc.

#ifndef MyAppVersion
  #define MyAppVersion "0.0.1"
#endif
#ifndef MyAppSource
  #define MyAppSource "..\..\dist\windows-stage\CloudMount"
#endif
#ifndef MyOutputDir
  #define MyOutputDir "..\..\dist"
#endif
#ifndef MyOutputBase
  #define MyOutputBase "CloudMount-" + MyAppVersion + "-windows-setup"
#endif

#define MyAppName "CloudMount"
#define MyAppPublisher "CloudMount"
#define MyAppURL "https://github.com/arthurtsang/CloudMount"
#define MyAppExeName "CloudMount-Tray.bat"

[Setup]
AppId={{A7C0D4E1-8B2F-4C9A-9E31-1F2E3D4C5B6A}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher={#MyAppPublisher}
AppPublisherURL={#MyAppURL}
AppSupportURL={#MyAppURL}
AppUpdatesURL={#MyAppURL}/releases
DefaultDirName={localappdata}\Programs\CloudMount
DefaultGroupName=CloudMount
DisableProgramGroupPage=yes
LicenseFile={#MyAppSource}\LICENSE
OutputDir={#MyOutputDir}
OutputBaseFilename={#MyOutputBase}
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
PrivilegesRequired=lowest
ArchitecturesInstallIn64BitMode=x64compatible
UninstallDisplayIcon={app}\CloudMount-Tray.bat
InfoBeforeFile=
SetupLogging=yes

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "Create a &desktop shortcut for the tray"; GroupDescription: "Additional icons:"; Flags: unchecked
Name: "startupicon"; Description: "Start CloudMount tray when I sign in"; GroupDescription: "Startup:"; Flags: unchecked

[Files]
Source: "{#MyAppSource}\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{group}\CloudMount Tray"; Filename: "{app}\CloudMount-Tray.bat"; WorkingDir: "{app}"
Name: "{group}\CloudMount UI"; Filename: "{app}\CloudMount-UI.bat"; WorkingDir: "{app}"
Name: "{group}\First-Run Setup"; Filename: "{app}\First-Run-Setup.bat"; WorkingDir: "{app}"
Name: "{group}\Windows README"; Filename: "{app}\README-Windows.txt"
Name: "{group}\Uninstall CloudMount"; Filename: "{uninstallexe}"
Name: "{autodesktop}\CloudMount"; Filename: "{app}\CloudMount-Tray.bat"; WorkingDir: "{app}"; Tasks: desktopicon
Name: "{userstartup}\CloudMount"; Filename: "{app}\CloudMount-Tray.bat"; WorkingDir: "{app}"; Tasks: startupicon

[Run]
Filename: "{app}\First-Run-Setup.bat"; Description: "Run first-time setup (Python deps, rclone, tray)"; Flags: nowait postinstall skipifsilent shellexec
Filename: "https://winfsp.dev/rel/"; Description: "Open WinFsp download page (required for mounts)"; Flags: postinstall shellexec skipifsilent unchecked

[Code]
function InitializeSetup(): Boolean;
begin
  Result := True;
end;
