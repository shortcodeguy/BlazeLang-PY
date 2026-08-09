param([string]$InstallDir = (Join-Path $env:LOCALAPPDATA "BlazeLang"))

$ErrorActionPreference = "Stop"

$SourceDir = $PSScriptRoot

$Files = @(
    "blz.exe",
    "BLAZELANG_REFERENCE.md",
    "WINDOWS_COMMANDS.md",
    "blz-terminal.cmd",
    "blz-terminal.ps1",
    "BlazeLang-Terminal.json"
)

New-Item -ItemType Directory -Path $InstallDir -Force | Out-Null

foreach ($File in $Files) {
    $Source = Join-Path $SourceDir $File

    if (-not (Test-Path -LiteralPath $Source)) {
        throw "Installer file is missing: $File"
    }

    Copy-Item `
        -LiteralPath $Source `
        -Destination (Join-Path $InstallDir $File) `
        -Force
}

# Add BlazeLang to the user's PATH
$UserPath = [Environment]::GetEnvironmentVariable("Path", "User")

$Entries = @(
    $UserPath -split ";" |
    Where-Object { $_ }
)

if ($Entries -notcontains $InstallDir) {
    [Environment]::SetEnvironmentVariable(
        "Path",
        (($Entries + $InstallDir) -join ";"),
        "User"
    )
}

$env:Path = "$InstallDir;$env:Path"

# Notify Windows that the environment has changed
Add-Type @"
using System;
using System.Runtime.InteropServices;

public static class EnvironmentNotifier
{
    [DllImport("user32.dll", CharSet = CharSet.Auto, SetLastError = true)]
    public static extern IntPtr SendMessageTimeout(
        IntPtr hWnd,
        uint msg,
        UIntPtr wParam,
        string lParam,
        uint flags,
        uint timeout,
        out UIntPtr result
    );
}
"@

$Result = [UIntPtr]::Zero

[EnvironmentNotifier]::SendMessageTimeout(
    [IntPtr]0xffff,
    0x001A,
    [UIntPtr]::Zero,
    "Environment",
    2,
    5000,
    [ref]$Result
) | Out-Null


# Ensure a legacy PowerShell function named "blz"
# cannot override the PATH executable in future sessions.

$ProfilePath = $PROFILE.CurrentUserCurrentHost
$ProfileDirectory = Split-Path -Parent $ProfilePath

New-Item `
    -ItemType Directory `
    -Path $ProfileDirectory `
    -Force | Out-Null

$StartMarker = "# BlazeLang launcher (managed by installer)"
$EndMarker = "# End BlazeLang launcher"

$ProfileBlock = @"
$StartMarker
function blz { & '$InstallDir\blz.exe' @args }
$EndMarker
"@

$ProfileText = if (
    Test-Path -LiteralPath $ProfilePath
) {
    Get-Content -LiteralPath $ProfilePath -Raw
}
else {
    ""
}

$ManagedPattern = "(?s)" +
    [regex]::Escape($StartMarker) +
    ".*?" +
    [regex]::Escape($EndMarker)

if ($ProfileText -match $ManagedPattern) {
    $ProfileText = [regex]::Replace(
        $ProfileText,
        $ManagedPattern,
        $ProfileBlock
    )
}
else {
    $ProfileText =
        $ProfileText.TrimEnd() +
        "`r`n`r`n" +
        $ProfileBlock +
        "`r`n"
}

Set-Content `
    -LiteralPath $ProfilePath `
    -Value $ProfileText `
    -Encoding utf8


Write-Host "BlazeLang installed to $InstallDir" -ForegroundColor Green
Write-Host "Open a new terminal and use: blz run main.blz" -ForegroundColor Green
