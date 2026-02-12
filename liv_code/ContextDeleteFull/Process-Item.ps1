param(
    [string]$TargetPath
)

Add-Content "D:\OneDrive-Local\OneDrive\DheerajOnHP\liv_code\ContextDeleteFull\log.txt" "Clicked: $TargetPath"

takeown /F "$TargetPath" /R /D Y ; icacls "$TargetPath" /grant Administrators:F /T /C ; Remove-Item "$TargetPath" -Recurse -Force -ErrorAction Stop

