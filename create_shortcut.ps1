$WshShell = New-Object -comObject WScript.Shell
$DesktopPath = [Environment]::GetFolderPath("Desktop")
$ShortcutPath = Join-Path $DesktopPath "Remote Keyboard.lnk"
$Target = Join-Path $PSScriptRoot "run.bat"
$IconPath = Join-Path $PSScriptRoot "static\favicon.ico" # Assuming favicon exists, or use shell32

$Shortcut = $WshShell.CreateShortcut($ShortcutPath)
$Shortcut.TargetPath = $Target
$Shortcut.WorkingDirectory = $PSScriptRoot
$Shortcut.IconLocation = "shell32.dll,3" # Folder icon as fallback
if (Test-Path $IconPath) {
    $Shortcut.IconLocation = $IconPath
}
$Shortcut.Save()

Write-Host "Shortcut created on Desktop: $ShortcutPath"
pause
