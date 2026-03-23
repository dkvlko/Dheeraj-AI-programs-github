# Must run as Administrator

Write-Host "Choose network configuration:"
Write-Host "1. Dynamic IP (DHCP from router)"
Write-Host "2. Static IP (192.168.29.25)"
Write-Host "3. Static IP (192.168.0.25)"

$choice = Read-Host "Enter 1, 2 or 3"

# Get active adapter
$adapter = Get-NetAdapter | Where-Object {$_.Status -eq "Up"} | Select-Object -First 1

if (-not $adapter) {
    Write-Host "No active network adapter found!" -ForegroundColor Red
    exit
}

$iface = $adapter.Name

# Function to clean existing IPv4 config
function Clear-IPConfig {
    Get-NetIPAddress -InterfaceAlias $iface -AddressFamily IPv4 -ErrorAction SilentlyContinue |
        Remove-NetIPAddress -Confirm:$false -ErrorAction SilentlyContinue
}

if ($choice -eq "1") {
    Write-Host "Switching to DHCP..."

    Set-NetIPInterface -InterfaceAlias $iface -Dhcp Enabled
    Set-DnsClientServerAddress -InterfaceAlias $iface -ResetServerAddresses

    Write-Host "DHCP enabled successfully." -ForegroundColor Green
}
elseif ($choice -eq "2") {
    Write-Host "Setting Static IP: 192.168.29.25..."

    Clear-IPConfig

    New-NetIPAddress `
        -InterfaceAlias $iface `
        -IPAddress "192.168.29.25" `
        -PrefixLength 24 `
        -DefaultGateway "192.168.29.1"

    Set-DnsClientServerAddress `
        -InterfaceAlias $iface `
        -ServerAddresses ("8.8.8.8","8.8.4.4")

    Write-Host "Static IP 192.168.29.25 applied." -ForegroundColor Green
}
elseif ($choice -eq "3") {
    Write-Host "Setting Static IP: 192.168.0.25..."

    Clear-IPConfig

    New-NetIPAddress `
        -InterfaceAlias $iface `
        -IPAddress "192.168.0.25" `
        -PrefixLength 24 `
        -DefaultGateway "192.168.0.1"

    Set-DnsClientServerAddress `
        -InterfaceAlias $iface `
        -ServerAddresses ("8.8.8.8","8.8.4.4")

    Write-Host "Static IP 192.168.0.25 applied." -ForegroundColor Green
}
else {
    Write-Host "Invalid choice. Exiting." -ForegroundColor Yellow
}