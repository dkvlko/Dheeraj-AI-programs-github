# Must run as Administrator

Write-Host "=============================="
Write-Host " Static IP Configuration"
Write-Host "=============================="
Write-Host "1. 192.168.29.25 (Jio)"
Write-Host "2. 192.168.0.25 (TP-Link)"
Write-Host "=============================="

$choice = Read-Host "Enter 1 or 2"

# Get active adapter (Ethernet preferred)
$adapter = Get-NetAdapter | Where-Object {$_.Status -eq "Up"} | Select-Object -First 1

if (-not $adapter) {
    Write-Host "❌ No active adapter found!" -ForegroundColor Red
    exit
}

$iface = $adapter.Name
Write-Host "Using adapter: $iface"

# 🔥 Clean existing config completely
Write-Host "Cleaning previous IP configuration..."

# Remove IP addresses
Get-NetIPAddress -InterfaceAlias $iface -AddressFamily IPv4 -ErrorAction SilentlyContinue |
    Remove-NetIPAddress -Confirm:$false -ErrorAction SilentlyContinue

# Remove routes (THIS is what you were missing)
Get-NetRoute -InterfaceAlias $iface -AddressFamily IPv4 -ErrorAction SilentlyContinue |
    Remove-NetRoute -Confirm:$false -ErrorAction SilentlyContinue

# Reset DNS
Set-DnsClientServerAddress -InterfaceAlias $iface -ResetServerAddresses -ErrorAction SilentlyContinue

Start-Sleep -Seconds 1

# Apply selected static profile
if ($choice -eq "1") {

    Write-Host "➡️ Setting IP: 192.168.29.25"

    New-NetIPAddress `
        -InterfaceAlias $iface `
        -IPAddress "192.168.29.25" `
        -PrefixLength 24 `
        -DefaultGateway "192.168.29.1"

}
elseif ($choice -eq "2") {

    Write-Host "➡️ Setting IP: 192.168.0.25"

    New-NetIPAddress `
        -InterfaceAlias $iface `
        -IPAddress "192.168.0.25" `
        -PrefixLength 24 `
        -DefaultGateway "192.168.0.1"

}
else {
    Write-Host "❌ Invalid choice" -ForegroundColor Yellow
    exit
}

# Set DNS (common for both)
Set-DnsClientServerAddress `
    -InterfaceAlias $iface `
    -ServerAddresses ("8.8.8.8","8.8.4.4")

# Show result
Write-Host ""
Write-Host "✅ Configuration applied."
Write-Host "📡 Current IP(s):"

Get-NetIPAddress -InterfaceAlias $iface -AddressFamily IPv4 |
    Select-Object IPAddress