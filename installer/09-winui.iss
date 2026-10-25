#ifndef ReleaseRoot
  #error ReleaseRoot must point to the complete WinUI publish directory.
#endif
#ifndef InstallerOutput
  #error InstallerOutput must point to an output directory.
#endif

[Setup]
AppId=VIC.Control.WinUI09
AppName=VIC Control WinUI 3
AppVersion=09-0.1.0
AppPublisher=VIC
DefaultDirName={localappdata}\Programs\VIC Control WinUI 09
DefaultGroupName=VIC Control WinUI 3
UninstallDisplayIcon={app}\VICControl.WinUI.exe
OutputDir={#InstallerOutput}
OutputBaseFilename=VIC-Control-WinUI-09-Setup
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
PrivilegesRequired=lowest
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
CloseApplications=yes
RestartApplications=no
DisableProgramGroupPage=yes
VersionInfoVersion=0.9.1.0
VersionInfoDescription=VIC Control WinUI 3 installer
VersionInfoProductName=VIC Control WinUI 3

[Languages]
Name: "chinesesimp"; MessagesFile: "ChineseSimplified.isl"

[Tasks]
Name: "desktopicon"; Description: "创建桌面快捷方式"; GroupDescription: "附加选项："; Flags: unchecked

[Files]
Source: "{#ReleaseRoot}\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{group}\VIC Control WinUI 3"; Filename: "{app}\VICControl.WinUI.exe"
Name: "{autodesktop}\VIC Control WinUI 3"; Filename: "{app}\VICControl.WinUI.exe"; Tasks: desktopicon

[Run]
Filename: "{app}\VICControl.WinUI.exe"; Description: "启动 VIC Control WinUI 3"; Flags: nowait postinstall skipifsilent
