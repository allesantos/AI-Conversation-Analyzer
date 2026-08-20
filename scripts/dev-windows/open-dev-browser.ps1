param(
    [string]$ProjectRoot = "E:\Projetos\AI-Conversation-Analyzer",
    [int]$FrontendPort = 14200,
    [int]$BackendPort = 18000
)

$ErrorActionPreference = "Continue"

function Wait-ForUrl {
    param(
        [string]$Url,
        [int]$TimeoutSeconds = 120
    )

    $deadline = (Get-Date).AddSeconds($TimeoutSeconds)
    while ((Get-Date) -lt $deadline) {
        try {
            $response = Invoke-WebRequest -Uri $Url -UseBasicParsing -TimeoutSec 3
            if ($response.StatusCode -ge 200 -and $response.StatusCode -lt 500) {
                return $true
            }
        } catch {
            Start-Sleep -Seconds 2
        }
    }
    return $false
}

$frontendUrl = "http://localhost:$FrontendPort"
$healthUrl = "http://127.0.0.1:$BackendPort/health"

Write-Host "Aguardando backend..."
if (-not (Wait-ForUrl -Url $healthUrl)) {
    Write-Host "Backend nao respondeu a tempo. Abrindo login mesmo assim."
    Start-Process "$frontendUrl/login"
    exit 0
}

Write-Host "Aguardando frontend..."
if (-not (Wait-ForUrl -Url $frontendUrl -TimeoutSeconds 150)) {
    Write-Host "Frontend nao respondeu a tempo. Abrindo login mesmo assim."
    Start-Process "$frontendUrl/login"
    exit 0
}

Write-Host "Abrindo navegador..."
Start-Process "$frontendUrl/login"
