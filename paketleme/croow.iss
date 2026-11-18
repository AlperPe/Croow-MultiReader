; Croow MultiReader - Windows kurulum sihirbazı (Inno Setup 6)
; Croow — Alper Pektas tarafından geliştirilmiştir. © 2026 Alper Pektas. AGPLv3.
#define AppName "Croow MultiReader"
#define AppVersion GetEnv("CROOW_SURUM")
#if AppVersion == ""
  #define AppVersion "1.0.0"
#endif

[Setup]
AppId={{8C1F6E2A-2B5D-4C7E-9A41-6D2E5B3C7F10}
AppName={#AppName}
AppVersion={#AppVersion}
AppVerName={#AppName} {#AppVersion}
AppPublisher=Alper Pektas
AppPublisherURL=https://github.com/AlperPe/Croow-MultiReader
AppSupportURL=https://github.com/AlperPe/Croow-MultiReader/issues
AppCopyright=© 2026 Alper Pektas
DefaultDirName={autopf}\Croow MultiReader
DefaultGroupName=Croow MultiReader
OutputDir=..\dist
OutputBaseFilename=CroowMultiReader-Setup-x64
SetupIconFile=ikon.ico
UninstallDisplayIcon={app}\CroowMultiReader.exe
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
PrivilegesRequiredOverridesAllowed=dialog
ChangesAssociations=yes
LicenseFile=..\LICENSE
Compression=lzma2
SolidCompression=yes
WizardStyle=modern

[Languages]
Name: "turkish"; MessagesFile: "compiler:Languages\Turkish.isl"
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"
Name: "crwassoc"; Description: ".crw dosyalarını Croow MultiReader ile aç"; GroupDescription: "Dosya ilişkilendirme:"

[Files]
Source: "..\dist\CroowMultiReader\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs
Source: "..\NOTICE"; DestDir: "{app}"; DestName: "NOTICE.txt"; Flags: ignoreversion
Source: "..\LICENSE"; DestDir: "{app}"; DestName: "LICENSE.txt"; Flags: ignoreversion

[Icons]
Name: "{group}\Croow MultiReader"; Filename: "{app}\CroowMultiReader.exe"
Name: "{group}\{cm:UninstallProgram,Croow MultiReader}"; Filename: "{uninstallexe}"
Name: "{autodesktop}\Croow MultiReader"; Filename: "{app}\CroowMultiReader.exe"; Tasks: desktopicon

[Registry]
; .crw: çift tıklayınca Croow MultiReader (görev seçiliyse)
Root: HKA; Subkey: "Software\Classes\.crw"; ValueType: string; ValueName: ""; ValueData: "CroowMultiReader.crw"; Flags: uninsdeletevalue; Tasks: crwassoc
Root: HKA; Subkey: "Software\Classes\.crw\OpenWithProgids"; ValueType: string; ValueName: "CroowMultiReader.crw"; ValueData: ""; Flags: uninsdeletevalue
Root: HKA; Subkey: "Software\Classes\CroowMultiReader.crw"; ValueType: string; ValueName: ""; ValueData: "Croow CRW"; Flags: uninsdeletekey
Root: HKA; Subkey: "Software\Classes\CroowMultiReader.crw\DefaultIcon"; ValueType: string; ValueName: ""; ValueData: "{app}\CroowMultiReader.exe,0"
Root: HKA; Subkey: "Software\Classes\CroowMultiReader.crw\shell\open\command"; ValueType: string; ValueName: ""; ValueData: """{app}\CroowMultiReader.exe"" ""%1"""
; PDF ve resimler: yalnızca "Birlikte aç" listesine eklenir (varsayılan program değişmez)
Root: HKA; Subkey: "Software\Classes\CroowMultiReader.file"; ValueType: string; ValueName: ""; ValueData: "Croow MultiReader"; Flags: uninsdeletekey
Root: HKA; Subkey: "Software\Classes\CroowMultiReader.file\DefaultIcon"; ValueType: string; ValueName: ""; ValueData: "{app}\CroowMultiReader.exe,0"
Root: HKA; Subkey: "Software\Classes\CroowMultiReader.file\shell\open\command"; ValueType: string; ValueName: ""; ValueData: """{app}\CroowMultiReader.exe"" ""%1"""
Root: HKA; Subkey: "Software\Classes\.pdf\OpenWithProgids"; ValueType: string; ValueName: "CroowMultiReader.file"; ValueData: ""; Flags: uninsdeletevalue
Root: HKA; Subkey: "Software\Classes\.png\OpenWithProgids"; ValueType: string; ValueName: "CroowMultiReader.file"; ValueData: ""; Flags: uninsdeletevalue
Root: HKA; Subkey: "Software\Classes\.jpg\OpenWithProgids"; ValueType: string; ValueName: "CroowMultiReader.file"; ValueData: ""; Flags: uninsdeletevalue
Root: HKA; Subkey: "Software\Classes\.jpeg\OpenWithProgids"; ValueType: string; ValueName: "CroowMultiReader.file"; ValueData: ""; Flags: uninsdeletevalue
Root: HKA; Subkey: "Software\Classes\.webp\OpenWithProgids"; ValueType: string; ValueName: "CroowMultiReader.file"; ValueData: ""; Flags: uninsdeletevalue

[Run]
Filename: "{app}\CroowMultiReader.exe"; Description: "{cm:LaunchProgram,Croow MultiReader}"; Flags: nowait postinstall skipifsilent
