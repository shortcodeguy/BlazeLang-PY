[Version]
Class=IEXPRESS
SEDVersion=3

[Options]
PackagePurpose=InstallApp
ShowInstallProgramWindow=0
HideExtractAnimation=1
UseLongFileName=1
InsideCompressed=1
CAB_FixedSize=0
CAB_ResvCodeSigning=0
RebootMode=N
InstallPrompt=%InstallPrompt%
DisplayLicense=%DisplayLicense%
FinishMessage=%FinishMessage%
TargetName=%TargetName%
FriendlyName=%FriendlyName%
AppLaunched=%AppLaunched%
PostInstallCmd=%PostInstallCmd%
AdminQuietInstCmd=%AdminQuietInstCmd%
UserQuietInstCmd=%UserQuietInstCmd%
SourceFiles=SourceFiles

[SourceFiles]
SourceFiles0=C:\Users\guddu\Desktop\blazelang\Installer\

[SourceFiles0]
%FILE0%=
%FILE1%=
%FILE2%=
%FILE3%=
%FILE4%=
%FILE5%=
%FILE6%=
%FILE7%=
%FILE8%=
%FILE9%=

[Strings]
InstallPrompt=
DisplayLicense=
FinishMessage=BlazeLang has been installed. Open a new terminal and run blz help.
TargetName=C:\Users\guddu\Desktop\blazelang\Output\BlazeLang-Setup.exe
FriendlyName=BlazeLang Setup
AppLaunched=cmd.exe /d /s /c ""install-blazelang.cmd""
PostInstallCmd=<None>
AdminQuietInstCmd=
UserQuietInstCmd=
FILE0="blz.exe"
FILE1="blzinterpreter.exe"
FILE2="blzcompiler.exe"
FILE3="BLAZELANG_REFERENCE.md"
FILE4="WINDOWS_COMMANDS.md"
FILE5="blz-terminal.cmd"
FILE6="blz-terminal.ps1"
FILE7="BlazeLang-Terminal.json"
FILE8="Install-BlazeLang.ps1"
FILE9="install-blazelang.cmd"
