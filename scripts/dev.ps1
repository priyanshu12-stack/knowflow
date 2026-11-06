<#
.SYNOPSIS
  Developer commands for Windows (mirrors the Makefile targets).
.EXAMPLE
  ./scripts/dev.ps1 setup   # create API venv + install web deps
  ./scripts/dev.ps1 migrate # apply database migrations (alembic upgrade head)
  ./scripts/dev.ps1 api     # FastAPI on http://127.0.0.1:8000
  ./scripts/dev.ps1 worker  # ingestion worker (separate terminal)
  ./scripts/dev.ps1 web     # Next.js on http://localhost:3000
  ./scripts/dev.ps1 check   # all linters, type checks and tests
#>
param(
    [Parameter(Mandatory = $true, Position = 0)]
    [ValidateSet('setup', 'migrate', 'api', 'worker', 'web', 'lint', 'test', 'check')]
    [string]$Command
)

$ErrorActionPreference = 'Stop'
$RepoRoot = Split-Path -Parent $PSScriptRoot
$Api = Join-Path $RepoRoot 'apps\api'
$Web = Join-Path $RepoRoot 'apps\web'
$Py = Join-Path $Api '.venv\Scripts'

function Invoke-Step([string]$Dir, [scriptblock]$Block) {
    # Windows PowerShell 5.1 turns native stderr into terminating errors under 'Stop' when output
    # is redirected (CI, logs). Run tools with 'Continue' and judge success by exit code only.
    $ErrorActionPreference = 'Continue'
    Push-Location $Dir
    try {
        & $Block
        if ($LASTEXITCODE -ne 0) { throw "Step failed in $Dir (exit $LASTEXITCODE)" }
    }
    finally { Pop-Location }
}

function Assert-Venv {
    if (-not (Test-Path (Join-Path $Py 'python.exe'))) { throw 'API venv missing. Run: ./scripts/dev.ps1 setup' }
}

switch ($Command) {
    'setup' {
        Invoke-Step $Api { python -m venv .venv }
        Invoke-Step $Api { & "$Py\python.exe" -m pip install -e '.[dev]' }
        Invoke-Step $Web { npm ci }
        if (-not (Test-Path (Join-Path $RepoRoot '.env'))) {
            Copy-Item (Join-Path $RepoRoot '.env.example') (Join-Path $RepoRoot '.env')
            Write-Host 'Created .env from .env.example - change POSTGRES_PASSWORD before ./scripts/db.ps1 init'
        }
    }
    'migrate' { Assert-Venv; Invoke-Step $Api { & "$Py\alembic.exe" upgrade head } }
    'api' { Assert-Venv; Invoke-Step $Api { & "$Py\uvicorn.exe" app.main:app --host 127.0.0.1 --port 8000 --reload } }
    'worker' { Assert-Venv; Invoke-Step $Api { & "$Py\python.exe" -m app.workers.ingestion } }
    'web' { Invoke-Step $Web { npm run dev } }
    'lint' {
        Assert-Venv
        Invoke-Step $Api { & "$Py\ruff.exe" check . }
        Invoke-Step $Api { & "$Py\ruff.exe" format --check . }
        Invoke-Step $Api { & "$Py\mypy.exe" }
        Invoke-Step $Web { npm run lint }
        Invoke-Step $Web { npm run format:check }
        Invoke-Step $Web { npm run typecheck }
    }
    'test' {
        Assert-Venv
        $env:KNOWFLOW_RUN_INTEGRATION = '1'
        try { Invoke-Step $Api { & "$Py\pytest.exe" } }
        finally { Remove-Item Env:KNOWFLOW_RUN_INTEGRATION -ErrorAction SilentlyContinue }
        Invoke-Step $Web { npm test }
    }
    'check' {
        & $PSCommandPath lint
        & $PSCommandPath test
        Invoke-Step $Web { npm run build }
    }
}
