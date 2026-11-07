<#
.SYNOPSIS
  Create, start, stop and update the KnowFlow demo server on Azure (Azure for Students friendly).
.DESCRIPTION
  Start/stop model to save credit: `stop` deallocates the VM (no compute charge) and deletes its
  public IP (no IP charge), so a stopped server only costs its small disk. `start` re-creates the
  IP with the same DNS name, so the link never changes. A free Azure auto-shutdown runs nightly as
  a safety net. See docs/deploy-azure.md.
.EXAMPLE
  ./deploy/azure/knowflow-azure.ps1 create        # one time: VM, network, firewall, install
  ./deploy/azure/knowflow-azure.ps1 set-password  # prompts locally; the password never leaves as text in a command
  ./deploy/azure/knowflow-azure.ps1 start         # before a demo (~3-5 min until answers are fast)
  ./deploy/azure/knowflow-azure.ps1 stop          # after the demo
  
  
   | update | ssh | logs
#>
param(
    [Parameter(Mandatory = $true, Position = 0)]
    [ValidateSet('create', 'start', 'stop', 'status', 'update', 'set-password', 'ssh', 'logs')]
    [string]$Command
)

$ErrorActionPreference = 'Stop'

# ---- Settings (change before `create` if needed) --------------------------------------------
$Rg        = 'knowflow-rg'
$Vm        = 'knowflow-vm'
$Location  = if ($env:KNOWFLOW_AZ_LOCATION) { $env:KNOWFLOW_AZ_LOCATION } else { 'centralindia' }
$Size      = if ($env:KNOWFLOW_AZ_SIZE) { $env:KNOWFLOW_AZ_SIZE } else { 'Standard_B4as_v2' }
$DnsLabel  = if ($env:KNOWFLOW_AZ_DNS) { $env:KNOWFLOW_AZ_DNS } else { 'knowflow-priyanshu' }
$AdminUser = 'azureuser'
$IpName    = 'knowflow-ip'
$NsgName   = 'knowflow-nsg'
$Shutdown  = '1800'   # 18:00 UTC = 23:30 IST nightly auto-shutdown
$KeyPath   = Join-Path $HOME '.ssh\knowflow_azure'
$Domain    = "$DnsLabel.$Location.cloudapp.azure.com"
$SetupUrl  = 'https://raw.githubusercontent.com/priyanshu12-stack/knowflow/main/deploy/azure/setup.sh'

$azDir = 'C:\Program Files\Microsoft SDKs\Azure\CLI2\wbin'
if (-not (Get-Command az -ErrorAction SilentlyContinue) -and (Test-Path $azDir)) { $env:Path += ";$azDir" }

# Probe that returns $null instead of throwing when the resource doesn't exist ("not found" is
# printed on stderr, which PowerShell 5.1 would otherwise turn into a terminating error).
function Get-AzValue {
    $ErrorActionPreference = 'Continue'
    $out = & az @args --only-show-errors 2>$null
    if ($LASTEXITCODE -ne 0) { return $null }
    return $out
}

function Invoke-Az {
    $ErrorActionPreference = 'Continue'
    $out = & az @args --only-show-errors 2>&1
    if ($LASTEXITCODE -ne 0) { throw "az $($args -join ' ') failed:`n$out" }
    return $out
}

function Get-NicIpConfig {
    $nicId = Invoke-Az vm show -g $Rg -n $Vm --query 'networkProfile.networkInterfaces[0].id' -o tsv
    $nic = ($nicId -split '/')[-1]
    $ipc = Invoke-Az network nic show -g $Rg -n $nic --query 'ipConfigurations[0].name' -o tsv
    return @($nic, $ipc)
}

function Add-PublicIp {
    $exists = Get-AzValue network public-ip show -g $Rg -n $IpName --query id -o tsv
    if (-not $exists) {
        Write-Host "Creating public IP with DNS name $Domain"
        Invoke-Az network public-ip create -g $Rg -n $IpName -l $Location --sku Standard `
            --allocation-method Static --dns-name $DnsLabel | Out-Null
    }
    $nic, $ipc = Get-NicIpConfig
    Invoke-Az network nic ip-config update -g $Rg --nic-name $nic -n $ipc --public-ip-address $IpName | Out-Null
    return (Invoke-Az network public-ip show -g $Rg -n $IpName --query ipAddress -o tsv)
}

function Remove-PublicIp {
    $exists = Get-AzValue network public-ip show -g $Rg -n $IpName --query id -o tsv
    if (-not $exists) { return }
    $nic, $ipc = Get-NicIpConfig
    Invoke-Az network nic ip-config update -g $Rg --nic-name $nic -n $ipc --remove publicIpAddress | Out-Null
    Invoke-Az network public-ip delete -g $Rg -n $IpName | Out-Null
    Write-Host 'Public IP released (no IP charge while stopped).'
}

function Set-SshRule {
    # SSH is open only to this computer's current public IP.
    $myIp = (Invoke-RestMethod -Uri 'https://api.ipify.org' -TimeoutSec 15).Trim()
    Invoke-Az network nsg rule create -g $Rg --nsg-name $NsgName -n ssh-owner --priority 100 `
        --access Allow --protocol Tcp --direction Inbound --destination-port-ranges 22 `
        --source-address-prefixes "$myIp/32" | Out-Null
}

# Windows PowerShell 5.1 turns native stderr (e.g. ssh's known-hosts notice) into a terminating
# error under 'Stop' when output is redirected, so ssh calls run with 'Continue' and are judged
# by exit code only (same pattern as scripts/db.ps1).
function Invoke-Ssh([string]$RemoteCommand) {
    $ErrorActionPreference = 'Continue'
    & ssh -i $KeyPath -o StrictHostKeyChecking=accept-new -o ServerAliveInterval=30 "$AdminUser@$Domain" $RemoteCommand
    if ($LASTEXITCODE -ne 0) { throw "ssh command failed (exit $LASTEXITCODE)" }
}

function Wait-Ssh {
    $ErrorActionPreference = 'Continue'
    Write-Host 'Waiting for SSH...'
    for ($i = 0; $i -lt 40; $i++) {
        & ssh -i $KeyPath -o StrictHostKeyChecking=accept-new -o ConnectTimeout=5 -o BatchMode=yes "$AdminUser@$Domain" true 2>$null
        if ($LASTEXITCODE -eq 0) { return }
        Start-Sleep -Seconds 5
    }
    throw "Could not reach $Domain over SSH."
}

switch ($Command) {
    'create' {
        if (-not (Test-Path $KeyPath)) {
            New-Item -ItemType Directory -Force (Split-Path $KeyPath) | Out-Null
            & ssh-keygen -t ed25519 -f $KeyPath -N '""' -C 'knowflow-azure' | Out-Null
        }
        Write-Host "Resource group $Rg in $Location"
        Invoke-Az group create -n $Rg -l $Location | Out-Null
        Invoke-Az network nsg create -g $Rg -n $NsgName -l $Location | Out-Null
        Invoke-Az network nsg rule create -g $Rg --nsg-name $NsgName -n web --priority 110 `
            --access Allow --protocol Tcp --direction Inbound --destination-port-ranges 80 443 | Out-Null
        Set-SshRule
        $existing = Get-AzValue vm show -g $Rg -n $Vm --query id -o tsv
        if ($existing) {
            Write-Host "VM $Vm already exists; starting it and re-running the install."
            Invoke-Az vm start -g $Rg -n $Vm | Out-Null
            Add-PublicIp | Out-Null
        } else {
        Write-Host "Creating VM $Vm ($Size, Ubuntu 24.04, 32 GB Standard SSD)"
        Invoke-Az network public-ip create -g $Rg -n $IpName -l $Location --sku Standard `
            --allocation-method Static --dns-name $DnsLabel | Out-Null
        Invoke-Az vm create -g $Rg -n $Vm -l $Location --size $Size `
            --image Canonical:ubuntu-24_04-lts:server:latest `
            --admin-username $AdminUser --ssh-key-values "$KeyPath.pub" `
            --os-disk-size-gb 32 --storage-sku StandardSSD_LRS `
            --nsg $NsgName --public-ip-address $IpName | Out-Null
        }
        Invoke-Az vm auto-shutdown -g $Rg -n $Vm --time $Shutdown | Out-Null
        Write-Host 'Nightly auto-shutdown set for 23:30 IST.'
        Wait-Ssh
        Write-Host 'Installing KnowFlow (15-25 minutes on the first run)...'
        Invoke-Ssh "curl -fsSL $SetupUrl -o setup.sh && bash setup.sh $Domain"
        Write-Host "`nCreated. Next: ./deploy/azure/knowflow-azure.ps1 set-password"
        Write-Host "Then open https://$Domain"
    }
    'start' {
        Write-Host 'Starting the VM...'
        Invoke-Az vm start -g $Rg -n $Vm | Out-Null
        $ip = Add-PublicIp
        Set-SshRule
        Write-Host "Running at $ip. Services start on boot; the first answer also loads the model."
        Write-Host "Open: https://$Domain"
    }
    'stop' {
        Write-Host 'Stopping (deallocating) the VM...'
        Invoke-Az vm deallocate -g $Rg -n $Vm | Out-Null
        Remove-PublicIp
        Write-Host 'Stopped. Only the 32 GB disk is billed (~$2.64/month).'
    }
    'status' {
        $state = Invoke-Az vm get-instance-view -g $Rg -n $Vm --query "instanceView.statuses[?starts_with(code,'PowerState')].displayStatus | [0]" -o tsv
        $ip = Get-AzValue network public-ip show -g $Rg -n $IpName --query ipAddress -o tsv
        Write-Host "VM: $state"
        Write-Host ("Public IP: " + $(if ($ip) { "$ip  ->  https://$Domain" } else { 'none (released)' }))
    }
    'update' {
        Set-SshRule
        Invoke-Ssh "curl -fsSL $SetupUrl -o setup.sh && bash setup.sh $Domain"
    }
    'set-password' {
        $user = Read-Host 'Username [admin]'
        if (-not $user) { $user = 'admin' }
        if ($user -notmatch '^[A-Za-z0-9_.-]{1,32}$') { throw 'Use letters, digits, _ . - only.' }
        $sec = Read-Host 'New password (12+ characters)' -AsSecureString
        $plain = [Runtime.InteropServices.Marshal]::PtrToStringBSTR([Runtime.InteropServices.Marshal]::SecureStringToBSTR($sec))
        if ($plain.Length -lt 12) { throw 'Password must be at least 12 characters.' }
        Set-SshRule
        # The password goes over SSH stdin, never on a command line or into a log.
        $remote = "read -r pw; h=`$(caddy hash-password --plaintext ""`$pw""); unset pw; " +
                  "printf 'basicauth {\n\t%s %s\n}\n' '$user' ""`$h"" | sudo tee /etc/caddy/knowflow-auth.caddy >/dev/null; " +
                  "sudo systemctl reload caddy && echo 'Password updated.'"
        $ErrorActionPreference = 'Continue'
        $plain | & ssh -i $KeyPath -o StrictHostKeyChecking=accept-new "$AdminUser@$Domain" $remote
        $plain = $null
        if ($LASTEXITCODE -ne 0) { throw 'Setting the password failed.' }
        Write-Host "Log in at https://$Domain as '$user'."
    }
    'ssh' { Set-SshRule; $ErrorActionPreference = 'Continue'; & ssh -i $KeyPath "$AdminUser@$Domain" }
    'logs' {
        Set-SshRule
        Invoke-Ssh 'sudo journalctl -u knowflow-api -u knowflow-worker -u knowflow-web -u caddy -n 80 --no-pager'
    }
}
