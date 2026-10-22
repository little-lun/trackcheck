; trackcheck.iss —— 备用方案：装了 Inno Setup 6 之后，可以用它打一个"正规"安装包
;
; 本仓库默认用 build_win.py 自己打（不需要任何第三方工具、不需要管理员权限）。
; 如果哪天想要标准的 Add/Remove Programs 条目、卸载日志、签名友好，
; 就先跑 `python -m tools.trackcheck.build_win --only app` 和 `--only uninst`
; 拿到 dist\TrackCheck.exe 与 dist\Uninstall.exe，再执行：
;
;     "C:\Program Files (x86)\Inno Setup 6\ISCC.exe" trackcheck.iss
;
; 产物：dist\trackcheck-v0.1-inno-setup.exe

#define MyName    "TrackCheck"
#define MyVer     "0.1"
#define MyExe     "TrackCheck.exe"
#define MySrc     "..\..\dist"

[Setup]
AppId={{8F1E2A64-7C3B-4C21-9E51-TRACKCHECK01}
AppName={#MyName}
AppVersion={#MyVer}
AppPublisher=PVZ 生存无尽研究 · trackcheck
DefaultDirName={autopf}\{#MyName}
DefaultGroupName={#MyName}
DisableProgramGroupPage=yes
OutputDir={#MySrc}
OutputBaseFilename=trackcheck-v{#MyVer}-inno-setup
Compression=lzma2/max
SolidCompression=yes
WizardStyle=modern
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
UninstallDisplayIcon={app}\{#MyExe}

[Languages]
Name: "cn"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "在桌面创建快捷方式"; GroupDescription: "附加任务:"

[Files]
Source: "{#MySrc}\{#MyExe}";          DestDir: "{app}"; Flags: ignoreversion
Source: "{#MySrc}\Uninstall.exe";     DestDir: "{app}"; Flags: ignoreversion

[Icons]
Name: "{group}\{#MyName}";            Filename: "{app}\{#MyExe}"
Name: "{autodesktop}\{#MyName}";      Filename: "{app}\{#MyExe}"; Tasks: desktopicon

[Run]
Filename: "{app}\{#MyExe}"; Description: "启动 {#MyName}"; Flags: nowait postinstall skipifsilent
