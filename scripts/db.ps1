<#
.SYNOPSIS
  Manage the native (non-Docker) PostgreSQL 16 + pgvector instance for local development.
.DESCRIPTION
  See docs/decisions/ADR-008. Binaries come from the conda env 'knowflow-pg'
  (override with $env:KNOWFLOW_PG_HOME). The cluster lives in data/postgres (gitignored).
  Credentials are read from the repo-root .env (same variables as docker-compose).
.EXAMPLE
  ./scripts/db.ps1 install   # one-time: create conda env
  ./scripts/db.ps1 init      # one-time: create cluster, database and extensions
  ./scripts/db.ps1 start | stop | status | psql
#>
param(
    [Parameter(Mandatory = $true, Position = 0)]
    [ValidateSet('install', 'init', 'start', 'stop', 'status', 'psql')]
    [string]$Command
)

$ErrorActionPreference = 'Stop'
$RepoRoot = Split-Path -Parent $PSScriptRoot
$DataDir = Join-Path $RepoRoot 'data\postgres'
$LogFile = Join-Path $RepoRoot 'data\postgres.log'
$EnvName = 'knowflow-pg'

# Windows PowerShell 5.1 turns native stderr into terminating errors under 'Stop' when output is
# redirected (CI, logs). Run native tools with 'Continue' and judge success by exit code only.
function Invoke-Native([string]$What, [scriptblock]$Block) {
    $ErrorActionPreference = 'Continue'
    & $Block
    if ($LASTEXITCODE -ne 0) { throw "$What failed (exit $LASTEXITCODE)" }
}

function Read-DotEnv {
    $path = Join-Path $RepoRoot '.env'
    if (-not (Test-Path $path)) {
        throw "Missing .env. Run: Copy-Item .env.example .env  (then change POSTGRES_PASSWORD)"
    }
    $vars = @{}
    foreach ($line in Get-Content $path) {
        if ($line -match '^\s*([A-Z0-9_]+)\s*=\s*(.*)\s*$') { $vars[$Matches[1]] = $Matches[2] }
    }
    foreach ($k in 'POSTGRES_USER', 'POSTGRES_PASSWORD', 'POSTGRES_DB') {
        if (-not $vars[$k]) { throw "$k is not set in .env" }
    }
    if (-not $vars['POSTGRES_PORT']) { $vars['POSTGRES_PORT'] = '5432' }
    return $vars
}

function Get-PgBin {
    $pgHome = $env:KNOWFLOW_PG_HOME
    if (-not $pgHome) {
        $ErrorActionPreference = 'Continue'
        $base = (& conda info --base | Out-String).Trim()
        if ($LASTEXITCODE -ne 0 -or -not $base) { throw 'conda not found. Install Anaconda/Miniconda or set KNOWFLOW_PG_HOME.' }
        $pgHome = Join-Path $base "envs\$EnvName"
    }
    $bin = Join-Path $pgHome 'Library\bin'
    if (-not (Test-Path (Join-Path $bin 'pg_ctl.exe'))) {
        throw "PostgreSQL binaries not found in $bin. Run: ./scripts/db.ps1 install"
    }
    return $bin
}

function Invoke-Psql($bin, $cfg, $database, [string[]]$extra) {
    $env:PGPASSWORD = $cfg['POSTGRES_PASSWORD']
    try {
        Invoke-Native 'psql' {
            & (Join-Path $bin 'psql.exe') -v ON_ERROR_STOP=1 -h localhost -p $cfg['POSTGRES_PORT'] `
                -U $cfg['POSTGRES_USER'] -d $database @extra
        }
    }
    finally { Remove-Item Env:PGPASSWORD -ErrorAction SilentlyContinue }
}

function Start-Db($bin, $cfg) {
    # pg_ctl starts the server through a cmd wrapper that inherits pg_ctl's stdout/stderr. If those
    # are a pipe (CI, `| Select-Object`), the long-lived server keeps the pipe open and the caller
    # hangs. Point pg_ctl's handles at files instead, and wait for pg_ctl only, not the server.
    $out = Join-Path $RepoRoot 'data\pg_ctl.out'
    $err = Join-Path $RepoRoot 'data\pg_ctl.err'
    $pgArgs = @('-D', "`"$DataDir`"", '-l', "`"$LogFile`"", '-w',
        '-o', "`"-p $($cfg['POSTGRES_PORT']) -c listen_addresses=localhost`"", 'start')
    $proc = Start-Process -FilePath (Join-Path $bin 'pg_ctl.exe') -ArgumentList $pgArgs `
        -NoNewWindow -PassThru -RedirectStandardOutput $out -RedirectStandardError $err
    $null = $proc.Handle  # cache the handle so ExitCode is available after exit (PS 5.1 quirk)
    $proc.WaitForExit()
    Get-Content $out, $err -ErrorAction SilentlyContinue | Write-Host
    if ($proc.ExitCode -ne 0) { throw "pg_ctl start failed (exit $($proc.ExitCode)); see $LogFile" }
}

switch ($Command) {
    'install' {
        Invoke-Native 'conda create' {
            & conda create -y -n $EnvName -c conda-forge --override-channels 'postgresql=16' 'pgvector=0.8.6'
        }
    }
    'init' {
        $cfg = Read-DotEnv
        $bin = Get-PgBin
        if (Test-Path (Join-Path $DataDir 'PG_VERSION')) { throw "Cluster already exists in $DataDir" }
        New-Item -ItemType Directory -Force $DataDir | Out-Null
        $pwFile = New-TemporaryFile
        try {
            # ASCII without BOM so initdb reads the password exactly.
            [IO.File]::WriteAllText($pwFile.FullName, $cfg['POSTGRES_PASSWORD'])
            Invoke-Native 'initdb' {
                & (Join-Path $bin 'initdb.exe') -D $DataDir -U $cfg['POSTGRES_USER'] `
                    --pwfile=$($pwFile.FullName) --auth=scram-sha-256 -E UTF8 --locale=C
            }
        }
        finally { Remove-Item $pwFile.FullName -Force }
        Start-Db $bin $cfg
        $db = $cfg['POSTGRES_DB']
        Invoke-Psql $bin $cfg 'postgres' @('-c', "CREATE DATABASE `"$db`"")
        Invoke-Psql $bin $cfg $db @('-f', (Join-Path $RepoRoot 'infra\postgres\init\01-extensions.sql'))
        Write-Host "Initialized database '$db' with pgvector on localhost:$($cfg['POSTGRES_PORT'])"
    }
    'start' { Start-Db (Get-PgBin) (Read-DotEnv) }
    'stop' {
        $bin = Get-PgBin
        Invoke-Native 'pg_ctl stop (is the server running?)' { & (Join-Path $bin 'pg_ctl.exe') -D $DataDir -m fast stop }
    }
    'status' { $bin = Get-PgBin; Invoke-Native 'pg_ctl status (server not running?)' { & (Join-Path $bin 'pg_ctl.exe') -D $DataDir status } }
    'psql' { $cfg = Read-DotEnv; Invoke-Psql (Get-PgBin) $cfg $cfg['POSTGRES_DB'] @() }
}
