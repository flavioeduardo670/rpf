param(
  [int]$Port = 8000,
  [switch]$OpenFirewall
)

$ErrorActionPreference = "Stop"

function Test-IsAdmin {
  $currentIdentity = [Security.Principal.WindowsIdentity]::GetCurrent()
  $principal = New-Object Security.Principal.WindowsPrincipal($currentIdentity)
  return $principal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
}

function Get-LanIps {
  Get-NetIPAddress -AddressFamily IPv4 -ErrorAction SilentlyContinue |
    Where-Object {
      $_.IPAddress -ne "127.0.0.1" -and
      $_.IPAddress -notlike "169.254.*" -and
      $_.PrefixOrigin -ne "WellKnown"
    } |
    Select-Object -ExpandProperty IPAddress -Unique
}

$repoRoot = Split-Path -Parent $PSScriptRoot
$python = Join-Path $repoRoot "venv\\Scripts\\python.exe"
$managePy = Join-Path $repoRoot "manage.py"

if (-not (Test-Path $python)) {
  throw "Não encontrei o Python do venv em: $python. Crie/ative o venv primeiro."
}
if (-not (Test-Path $managePy)) {
  throw "Não encontrei manage.py em: $managePy"
}

if ($OpenFirewall) {
  if (-not (Test-IsAdmin)) {
    throw "Para abrir o firewall automaticamente, execute este script como Administrador (PowerShell -> Run as administrator)."
  }

  $ruleName = "Django dev server (TCP $Port)"
  $existing = Get-NetFirewallRule -DisplayName $ruleName -ErrorAction SilentlyContinue
  if (-not $existing) {
    New-NetFirewallRule -DisplayName $ruleName -Direction Inbound -Action Allow -Protocol TCP -LocalPort $Port | Out-Null
  }
}

$ips = @(Get-LanIps)
if ($ips.Count -gt 0) {
  Write-Host "Acesse no celular (mesmo Wi-Fi):"
  foreach ($ip in $ips) {
    Write-Host "  http://$ip`:$Port/"
  }
} else {
  Write-Host "Não consegui detectar um IPv4 de rede. Rode: ipconfig"
}

Write-Host ""
Write-Host "Iniciando Django em 0.0.0.0:$Port ..."
& $python $managePy runserver "0.0.0.0:$Port"

