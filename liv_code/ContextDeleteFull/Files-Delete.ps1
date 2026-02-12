# File to delete
$FilePath = "C:\Users\dheer\AppData\Roaming\Microsoft\Windows\Start Menu\Programs\Startup\RBHook.dll"

# Check for admin rights
If (-not ([Security.Principal.WindowsPrincipal] `
        [Security.Principal.WindowsIdentity]::GetCurrent()
        ).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)) {
    Write-Error "This script must be run as Administrator!"
    Exit 1
}

Write-Host "Target file: $FilePath"

# Step 1: Take ownership
Write-Host "Taking ownership..."
takeown /f "$FilePath" /a /r /d y | Out-Null

# Step 2: Grant full control to Administrators
Write-Host "Granting full permissions..."
icacls "$FilePath" /grant Administrators:F /t /c | Out-Null

# Step 3: Kill any process locking the file
Write-Host "Checking for processes using the file..."

$Processes = Get-Process -ErrorAction SilentlyContinue | Where-Object {
    try {
        $_.Path -eq $FilePath
    } catch {
        $false
    }
}

if ($Processes) {
    foreach ($p in $Processes) {
        Write-Host "Killing process: $($p.Name) (PID: $($p.Id))"
        Stop-Process -Id $p.Id -Force
    }
} else {
    Write-Host "No running process directly matched by file path."
}

# Step 4: Final forced delete
Write-Host "Attempting forced deletion..."
try {
    Remove-Item -Path "$FilePath" -Force -ErrorAction Stop
    Write-Host "File deleted successfully."
}
catch {
    Write-Error "Deletion failed. The file may still be locked by the system or protected by another service."
}
