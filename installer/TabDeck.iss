; TabDeck - programma di installazione (Inno Setup 6). Lo costruisce pubblica.ps1:
;   ISCC.exe /DAppVer=1.2.3 /DSrc=<cartella con i file del rilascio> /O<uscita> installer\TabDeck.iss
; Installa per il solo utente (niente amministratore) in %LOCALAPPDATA%\TabDeck, crea le icone e alla fine
; lancia la configurazione guidata (installa.bat: rete, firewall, avvio automatico, QR).

#ifndef AppVer
  #define AppVer "0.0.0"
#endif
#ifndef Src
  #define Src ".."
#endif

[Setup]
AppId={{7AEEA677-21CD-402C-AC74-6CC3D2F40359}
AppName=TabDeck
AppVersion={#AppVer}
AppVerName=TabDeck {#AppVer}
AppPublisher=MannAk1
AppPublisherURL=https://github.com/MannAk1/TabDeck
AppSupportURL=https://github.com/MannAk1/TabDeck
DefaultDirName={localappdata}\TabDeck
DisableDirPage=yes
DisableProgramGroupPage=yes
PrivilegesRequired=lowest
OutputBaseFilename=TabDeck-Setup
SetupIconFile={#Src}\tabdeck.ico
UninstallDisplayIcon={app}\tabdeck.ico
UninstallDisplayName=TabDeck
InfoBeforeFile=prima.txt
WizardStyle=modern
Compression=lzma2
SolidCompression=yes
CloseApplications=no

[Languages]
Name: "it"; MessagesFile: "compiler:Languages\Italian.isl"

[Tasks]
Name: "desktopicon"; Description: "Icona TabDeck sul Desktop"

[Files]
Source: "{#Src}\*"; DestDir: "{app}"; Flags: recursesubdirs ignoreversion; Excludes: "data\*,cache\*,backup\*,__pycache__\*"

[Icons]
Name: "{userprograms}\TabDeck\TabDeck"; Filename: "{sys}\WindowsPowerShell\v1.0\powershell.exe"; Parameters: "-NoProfile -WindowStyle Hidden -ExecutionPolicy Bypass -File ""{app}\apri.ps1"""; WorkingDir: "{app}"; IconFilename: "{app}\tabdeck.ico"; Comment: "Apre TabDeck (stato, QR per collegare il telefono, dispositivi)"
Name: "{userprograms}\TabDeck\TabDeck - Configura"; Filename: "{app}\installa.bat"; WorkingDir: "{app}"; IconFilename: "{app}\tabdeck.ico"; Comment: "Rete, firewall e avvio automatico (da rifare se cambi rete o router)"
Name: "{userprograms}\TabDeck\Disinstalla TabDeck"; Filename: "{uninstallexe}"
Name: "{userdesktop}\TabDeck"; Filename: "{sys}\WindowsPowerShell\v1.0\powershell.exe"; Parameters: "-NoProfile -WindowStyle Hidden -ExecutionPolicy Bypass -File ""{app}\apri.ps1"""; WorkingDir: "{app}"; IconFilename: "{app}\tabdeck.ico"; Comment: "Apre TabDeck (stato, QR per collegare il telefono, dispositivi)"; Tasks: desktopicon

[Run]
Filename: "{app}\installa.bat"; Description: "Configura TabDeck adesso (consigliato): rete, firewall, collegamento del telefono"; Flags: postinstall shellexec nowait

[UninstallRun]
; Prima di togliere i file: regola del firewall, avvio automatico e (solo se lo chiedi) i tuoi dati
Filename: "{app}\disinstalla.bat"; RunOnceId: "TabDeckUninstall"; Flags: shellexec waituntilterminated

[Code]
{ Dopo la disinstallazione toglie anche i file arrivati con gli aggiornamenti, ma NON la cartella data
  (impostazioni e chiavi): la cancella solo disinstalla.bat, se l'utente scrive CANCELLA. }
procedure DelAllExceptData(Dir: String);
var
  R: TFindRec;
begin
  if FindFirst(Dir + '\*', R) then
  try
    repeat
      if (R.Name <> '.') and (R.Name <> '..') and (CompareText(R.Name, 'data') <> 0) then
      begin
        if (R.Attributes and FILE_ATTRIBUTE_DIRECTORY) <> 0 then
          DelTree(Dir + '\' + R.Name, True, True, True)
        else
          DeleteFile(Dir + '\' + R.Name);
      end;
    until not FindNext(R);
  finally
    FindClose(R);
  end;
  RemoveDir(Dir);
end;

procedure CurUninstallStepChanged(CurUninstallStep: TUninstallStep);
begin
  if CurUninstallStep = usPostUninstall then
    DelAllExceptData(ExpandConstant('{app}'));
end;
