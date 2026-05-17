; Inno Setup Script for TradingAgents Windows Installer
; Build: "C:\Program Files (x86)\Inno Setup 6\ISCC.exe" installer.iss
; Output: Output\TradingAgents-Setup.exe

#define MyAppName "TradingAgents"
#define MyAppVersion "0.8.0"
#define MyAppPublisher "TradingAgents-dp"
#define MyAppURL "https://github.com/andyning/tradingagents-dp"
#define MyAppExeName "TradingAgents.exe"

[Setup]
AppId={{A1B2C3D4-E5F6-7890-ABCD-EF1234567890}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher={#MyAppPublisher}
AppPublisherURL={#MyAppURL}
AppSupportURL={#MyAppURL}
AppUpdatesURL={#MyAppURL}
DefaultDirName={autopf}\{#MyAppName}
DefaultGroupName={#MyAppName}
AllowNoIcons=yes
OutputDir=Output
OutputBaseFilename=TradingAgents-Setup
Compression=lzma2/ultra64
SolidCompression=yes
WizardStyle=modern
PrivilegesRequired=admin
ArchitecturesInstallIn64BitMode=x64compatible

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"
Name: "chinesesimplified"; MessagesFile: "compiler:Languages\ChineseSimplified.isl"

[Tasks]
Name: "desktopicon"; Description: "Create a &desktop shortcut"; GroupDescription: "Additional icons:"

[Files]
Source: "dist\{#MyAppExeName}"; DestDir: "{app}"; Flags: ignoreversion
Source: ".env.example"; DestDir: "{app}"; Flags: ignoreversion

[Icons]
Name: "{autoprograms}\{#MyAppName}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"
Name: "{autoprograms}\{#MyAppName}\Uninstall {#MyAppName}"; Filename: "{uninstallexe}"
Name: "{autoprograms}\{#MyAppName}\Edit Config (.env)"; Filename: "notepad.exe"; Parameters: "{app}\.env"
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; Tasks: desktopicon

[Run]
Filename: "{app}\{#MyAppExeName}"; Description: "Launch TradingAgents"; Flags: nowait postinstall skipifsilent

[Code]
var
  ApiKeyPage: TInputQueryWizardPage;

procedure InitializeWizard;
begin
  ApiKeyPage := CreateInputQueryPage(wpSelectDir,
    'DeepSeek API Configuration',
    'Enter your DeepSeek API key to get started.',
    'Get a free key at https://platform.deepseek.com. You can skip this step and edit the .env file later.');
  ApiKeyPage.Add('DEEPSEEK_API_KEY:', False);
end;

function NextButtonClick(CurPageID: Integer): Boolean;
begin
  Result := True;
end;

procedure CurStepChanged(CurStep: TSetupStep);
var
  EnvFile: String;
  EnvLines: TStringList;
  I: Integer;
  KeySet: Boolean;
begin
  if CurStep = ssPostInstall then
  begin
    EnvFile := ExpandConstant('{app}\.env');

    if not FileExists(EnvFile) then
    begin
      // Copy template from .env.example if .env doesn't exist
      FileCopy(ExpandConstant('{app}\.env.example'), EnvFile, False);
    end;

    // If user provided an API key, write it to .env
    if ApiKeyPage.Values[0] <> '' then
    begin
      EnvLines := TStringList.Create;
      try
        EnvLines.LoadFromFile(EnvFile);
        KeySet := False;
        for I := 0 to EnvLines.Count - 1 do
        begin
          if Pos('DEEPSEEK_API_KEY=', EnvLines[I]) = 1 then
          begin
            EnvLines[I] := 'DEEPSEEK_API_KEY=' + ApiKeyPage.Values[0];
            KeySet := True;
            Break;
          end;
        end;
        if not KeySet then
          EnvLines.Add('DEEPSEEK_API_KEY=' + ApiKeyPage.Values[0]);
        EnvLines.SaveToFile(EnvFile);
      finally
        EnvLines.Free;
      end;
    end;
  end;
end;
