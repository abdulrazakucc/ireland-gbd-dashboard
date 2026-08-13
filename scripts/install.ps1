<#
.SYNOPSIS
    One-command setup for Ireland Health Evidence on Windows.

.DESCRIPTION
    Installs everything this project needs and starts it, without ever
    requiring administrator rights. Everything lands inside the user's own
    profile folder.

    The script picks whichever engine the machine can actually support:

      * Docker  -- used only if Docker is already installed AND running.
                   Nothing to install: the image carries its own Python.
      * Python  -- the fallback, and the usual case. If there is no suitable
                   Python already, pyenv-win installs one into
                   %USERPROFILE%\.pyenv, which needs no admin rights.

    Safe to run more than once: existing pieces are detected and reused
    rather than reinstalled.

.PARAMETER Engine
    Which engine to use: auto (default), docker, or python. 'auto' prefers
    Docker when it is present and running, otherwise uses Python.

.PARAMETER InstallDir
    Where to put the project. Defaults to %USERPROFILE%\ucc_gbd_pipeline.
    Ignored when the script is run from inside an existing copy.

.PARAMETER PythonVersion
    Python to install if one has to be installed. Default 3.12.10.

.PARAMETER Port
    Port to serve on. Default 8000; if it is busy, the next free port is used.

.PARAMETER NoStart
    Set everything up but do not start the app or open the browser.

.PARAMETER NoShortcut
    Do not create the desktop shortcut.

.EXAMPLE
    irm https://raw.githubusercontent.com/abdulrazakucc/ucc_gbd_pipeline/main/scripts/install.ps1 | iex

.EXAMPLE
    .\scripts\install.ps1 -Engine python -Port 8080
#>
[CmdletBinding()]
param(
    [ValidateSet('auto', 'docker', 'python')]
    [string] $Engine = 'auto',

    [string] $InstallDir,

    [string] $PythonVersion = '3.12.10',

    [int]    $Port = 8000,

    [switch] $NoStart,

    [switch] $NoShortcut
)

$ErrorActionPreference = 'Stop'
$ProgressPreference    = 'SilentlyContinue'   # Invoke-WebRequest is ~10x faster without it

# Windows PowerShell 5.1 still defaults to TLS 1.0 on older builds, which
# github.com and python.org now refuse.
try {
    [Net.ServicePointManager]::SecurityProtocol =
        [Net.ServicePointManager]::SecurityProtocol -bor [Net.SecurityProtocolType]::Tls12
} catch {
    # .NET Core (PowerShell 7+) manages this itself and may not expose the property.
}

$RepoSlug   = 'abdulrazakucc/ucc_gbd_pipeline'
$RepoZipUrl = "https://github.com/$RepoSlug/archive/refs/heads/main.zip"
$AppName    = 'Ireland Health Evidence'

# Pandas 2.2.2 publishes wheels for CPython 3.9-3.12 only. On 3.13+ pip falls
# back to building from source, which fails without a C toolchain -- so an
# existing Python is only reused if it is inside this range.
$MinPy = [Version]'3.11.0'
$MaxPy = [Version]'3.13.0'   # exclusive

## ------------------------------------------------------------- output ----

function Write-Banner {
    Write-Host ''
    Write-Host '  ============================================================' -ForegroundColor DarkCyan
    Write-Host "   $AppName" -ForegroundColor Cyan
    Write-Host '   School of Public Health, University College Cork' -ForegroundColor DarkGray
    Write-Host '  ============================================================' -ForegroundColor DarkCyan
    Write-Host ''
    Write-Host '   Setting your computer up. This needs no admin rights and' -ForegroundColor Gray
    Write-Host '   installs nothing outside your own user folder.' -ForegroundColor Gray
    Write-Host ''
}

$script:StepNo = 0
function Write-Step {
    param([string] $Message)
    $script:StepNo++
    Write-Host ''
    Write-Host ("  [{0}] {1}" -f $script:StepNo, $Message) -ForegroundColor White
}

function Write-Ok    { param([string] $m) Write-Host "      OK    $m" -ForegroundColor Green }
function Write-Info  { param([string] $m) Write-Host "            $m" -ForegroundColor DarkGray }
function Write-Warn2 { param([string] $m) Write-Host "      note  $m" -ForegroundColor Yellow }

function Stop-WithError {
    param([string] $Message, [string[]] $Hints)
    Write-Host ''
    Write-Host '  ------------------------------------------------------------' -ForegroundColor Red
    Write-Host "   Setup could not finish" -ForegroundColor Red
    Write-Host '  ------------------------------------------------------------' -ForegroundColor Red
    Write-Host ''
    Write-Host "   $Message" -ForegroundColor Red
    if ($Hints) {
        Write-Host ''
        Write-Host '   What to try:' -ForegroundColor Yellow
        foreach ($h in $Hints) { Write-Host "     * $h" -ForegroundColor Yellow }
    }
    Write-Host ''
    Write-Host '   If you are stuck, send a screenshot of this whole window to' -ForegroundColor DarkGray
    Write-Host '   whoever gave you this project.' -ForegroundColor DarkGray
    Write-Host ''
    exit 1
}

## -------------------------------------------------------- small helpers ----

function Test-CommandExists {
    param([string] $Name)
    $null -ne (Get-Command $Name -ErrorAction SilentlyContinue)
}

function Invoke-Exe {
    <#
      Runs a program and returns an object with ExitCode and Output, without
      throwing. $ErrorActionPreference='Stop' turns native stderr writes into
      terminating errors in some hosts, so stderr is folded into stdout here.
    #>
    param([string] $File, [string[]] $Arguments = @(), [string] $WorkDir)

    $prev = $ErrorActionPreference
    $ErrorActionPreference = 'Continue'
    try {
        Push-Location ($(if ($WorkDir) { $WorkDir } else { (Get-Location).Path }))
        try {
            $out  = & $File @Arguments 2>&1 | Out-String
            $code = $LASTEXITCODE
        } finally { Pop-Location }
    } catch {
        return [pscustomobject]@{ ExitCode = 1; Output = $_.Exception.Message }
    } finally {
        $ErrorActionPreference = $prev
    }
    if ($null -eq $code) { $code = 0 }
    [pscustomobject]@{ ExitCode = $code; Output = $out }
}

function Test-PortFree {
    param([int] $Number)
    try {
        $listener = [Net.Sockets.TcpListener]::new([Net.IPAddress]::Loopback, $Number)
        $listener.Start(); $listener.Stop()
        return $true
    } catch {
        return $false
    }
}

function Find-FreePort {
    param([int] $Preferred)
    foreach ($p in $Preferred..($Preferred + 20)) {
        if (Test-PortFree -Number $p) { return $p }
    }
    Stop-WithError -Message "No free port found between $Preferred and $($Preferred + 20)." `
                   -Hints @('Restart the computer and run this again.')
}

function Wait-ForApp {
    param([int] $Number, [int] $TimeoutSeconds = 90)
    $deadline = (Get-Date).AddSeconds($TimeoutSeconds)
    while ((Get-Date) -lt $deadline) {
        try {
            $r = Invoke-WebRequest -UseBasicParsing -TimeoutSec 3 `
                    -Uri "http://127.0.0.1:$Number/api/health"
            if ($r.StatusCode -eq 200) { return $true }
        } catch {
            Start-Sleep -Seconds 1
        }
    }
    return $false
}

## ------------------------------------------------------ getting the code ----

function Get-LocalRepoRoot {
    <# Returns the project root if this script sits inside a copy of it. #>
    if (-not $PSScriptRoot) { return $null }          # piped through iex: no file on disk
    $candidate = Split-Path -Parent $PSScriptRoot
    if (Test-Path (Join-Path $candidate 'requirements.txt')) { return $candidate }
    return $null
}

function Install-ProjectFiles {
    param([string] $Destination)

    if (Test-Path (Join-Path $Destination 'requirements.txt')) {
        Write-Ok "Project already present at $Destination"
        Write-Info 'Reusing it. Delete that folder first if you want a clean copy.'
        return $Destination
    }

    Write-Info "Downloading the project from github.com/$RepoSlug"
    $tmp = Join-Path ([IO.Path]::GetTempPath()) ("gbd_" + [Guid]::NewGuid().ToString('N'))
    New-Item -ItemType Directory -Path $tmp -Force | Out-Null
    $zip = Join-Path $tmp 'main.zip'

    try {
        Invoke-WebRequest -UseBasicParsing -Uri $RepoZipUrl -OutFile $zip
    } catch {
        Stop-WithError -Message "Could not download the project: $($_.Exception.Message)" -Hints @(
            'Check your internet connection.',
            'On a university or hospital network, github.com may be blocked -- try a home or mobile connection.',
            "Or download it by hand from https://github.com/$RepoSlug (green Code button -> Download ZIP)."
        )
    }

    Expand-Archive -Path $zip -DestinationPath $tmp -Force
    $extracted = Get-ChildItem -Path $tmp -Directory |
                 Where-Object { Test-Path (Join-Path $_.FullName 'requirements.txt') } |
                 Select-Object -First 1
    if (-not $extracted) { Stop-WithError -Message 'The downloaded archive did not look like this project.' }

    $parent = Split-Path -Parent $Destination
    if (-not (Test-Path $parent)) { New-Item -ItemType Directory -Path $parent -Force | Out-Null }
    Move-Item -Path $extracted.FullName -Destination $Destination -Force
    Remove-Item -Path $tmp -Recurse -Force -ErrorAction SilentlyContinue

    Write-Ok "Project downloaded to $Destination"
    return $Destination
}

## ------------------------------------------------------------- python ----

function Get-PythonVersionOf {
    param([string] $Exe)
    $r = Invoke-Exe -File $Exe -Arguments @('-c', 'import sys; print("%d.%d.%d" % sys.version_info[:3])')
    if ($r.ExitCode -ne 0) { return $null }
    $text = ($r.Output -split "`n" | Where-Object { $_ -match '^\s*\d+\.\d+\.\d+\s*$' } | Select-Object -First 1)
    if (-not $text) { return $null }
    try { return [Version]$text.Trim() } catch { return $null }
}

function Test-PythonUsable {
    param([string] $Exe)
    if (-not $Exe) { return $false }
    # The Microsoft Store stub in WindowsApps is a redirector, not a Python.
    if ($Exe -like '*\WindowsApps\*') { return $false }
    $v = Get-PythonVersionOf -Exe $Exe
    if (-not $v) { return $false }
    return ($v -ge $MinPy -and $v -lt $MaxPy)
}

function Get-PyenvRoot { Join-Path $HOME '.pyenv\pyenv-win' }

function Enable-PyenvInSession {
    <# Makes pyenv usable in THIS window, so the user never has to reopen it. #>
    $root = Get-PyenvRoot
    $env:PYENV      = "$root\"
    $env:PYENV_ROOT = "$root\"
    $env:PYENV_HOME = "$root\"
    $bin   = Join-Path $root 'bin'
    $shims = Join-Path $root 'shims'
    if ($env:PATH -notlike "*$bin*")   { $env:PATH = "$bin;$shims;$env:PATH" }
}

function Install-Pyenv {
    $root = Get-PyenvRoot
    if (Test-Path (Join-Path $root 'bin\pyenv.bat')) {
        Write-Ok 'pyenv is already installed'
        Enable-PyenvInSession
        return
    }

    Write-Info 'Installing pyenv into your user folder (no admin rights needed)'
    $installer = Join-Path ([IO.Path]::GetTempPath()) 'install-pyenv-win.ps1'
    $url = 'https://raw.githubusercontent.com/pyenv-win/pyenv-win/master/pyenv-win/install-pyenv-win.ps1'
    try {
        Invoke-WebRequest -UseBasicParsing -Uri $url -OutFile $installer
    } catch {
        Stop-WithError -Message "Could not download the pyenv installer: $($_.Exception.Message)" -Hints @(
            'Check your internet connection.',
            'Your network may block raw.githubusercontent.com -- try a home or mobile connection.'
        )
    }

    # Run it in a child process with an execution policy that applies only to
    # that process: nothing is changed permanently, and no admin is involved.
    $r = Invoke-Exe -File 'powershell.exe' -Arguments @(
        '-NoProfile', '-ExecutionPolicy', 'Bypass', '-File', $installer
    )
    Remove-Item $installer -Force -ErrorAction SilentlyContinue

    Enable-PyenvInSession
    if (-not (Test-Path (Join-Path $root 'bin\pyenv.bat'))) {
        Stop-WithError -Message 'pyenv did not install correctly.' -Hints @(
            'Your antivirus may have blocked it -- check its quarantine list.',
            "Installer output follows:`n$($r.Output)"
        )
    }
    Write-Ok 'pyenv installed'
}

function Install-PythonWithPyenv {
    param([string] $Version)

    Enable-PyenvInSession
    $root   = Get-PyenvRoot
    $pyexe  = Join-Path $root "versions\$Version\python.exe"
    if (Test-Path $pyexe) {
        Write-Ok "Python $Version is already installed"
        return $pyexe
    }

    Write-Info "Installing Python $Version -- this takes 2-5 minutes, please wait"
    $pyenvBat = Join-Path $root 'bin\pyenv.bat'
    $r = Invoke-Exe -File $pyenvBat -Arguments @('install', $Version)
    if (-not (Test-Path $pyexe)) {
        Stop-WithError -Message "Python $Version could not be installed." -Hints @(
            'Check your internet connection -- pyenv downloads Python from python.org.',
            'Your antivirus may have blocked the installer.',
            "pyenv output follows:`n$($r.Output)"
        )
    }
    Invoke-Exe -File $pyenvBat -Arguments @('rehash') | Out-Null
    Write-Ok "Python $Version installed"
    return $pyexe
}

function Resolve-Python {
    param([string] $Version)

    # 1. A pyenv-managed Python of exactly the wanted version.
    $pyenvPython = Join-Path (Get-PyenvRoot) "versions\$Version\python.exe"
    if (Test-Path $pyenvPython) {
        Write-Ok "Using the Python $Version that pyenv already manages"
        Enable-PyenvInSession
        return $pyenvPython
    }

    # 2. Any already-installed Python in the supported range, via the Windows
    #    launcher first (it knows about every registered install) then PATH.
    $candidates = @()
    if (Test-CommandExists 'py') {
        foreach ($tag in @('-3.12', '-3.11')) {
            $probe = Invoke-Exe -File 'py' -Arguments @($tag, '-c', 'import sys; print(sys.executable)')
            if ($probe.ExitCode -eq 0) {
                $path = ($probe.Output -split "`n" | Where-Object { $_ -match '\S' } | Select-Object -First 1)
                if ($path) { $candidates += $path.Trim() }
            }
        }
    }
    foreach ($name in @('python', 'python3')) {
        $cmd = Get-Command $name -ErrorAction SilentlyContinue
        if ($cmd) { $candidates += $cmd.Source }
    }

    foreach ($c in ($candidates | Where-Object { $_ } | Select-Object -Unique)) {
        if (Test-PythonUsable -Exe $c) {
            $v = Get-PythonVersionOf -Exe $c
            Write-Ok "Found a usable Python $v already installed"
            Write-Info $c
            return $c
        }
    }

    # 3. Nothing usable: pyenv is the priority route, because it needs no
    #    admin rights and cannot disturb any other Python on the machine.
    Write-Info 'No suitable Python found, so one will be installed for you'
    Install-Pyenv
    return (Install-PythonWithPyenv -Version $Version)
}

## -------------------------------------------------------------- engines ----

function Test-DockerUsable {
    if (-not (Test-CommandExists 'docker')) { return $false }
    $info = Invoke-Exe -File 'docker' -Arguments @('info', '--format', '{{.ServerVersion}}')
    if ($info.ExitCode -ne 0) { return $false }
    $compose = Invoke-Exe -File 'docker' -Arguments @('compose', 'version')
    return ($compose.ExitCode -eq 0)
}

function Initialize-DockerEngine {
    param([string] $Root, [int] $Number)

    Write-Info 'Building the container. The first build takes a few minutes.'
    $r = Invoke-Exe -File 'docker' -Arguments @('compose', 'build') -WorkDir $Root
    if ($r.ExitCode -ne 0) {
        Stop-WithError -Message 'Docker could not build the image.' -Hints @(
            'Make sure Docker Desktop is running (whale icon in the system tray).',
            "Docker output follows:`n$($r.Output)"
        )
    }
    Write-Ok 'Container image built'
}

function Initialize-PythonEngine {
    param([string] $Root, [string] $PythonExe)

    $venv   = Join-Path $Root '.venv'
    $venvPy = Join-Path $venv 'Scripts\python.exe'

    if (-not (Test-Path $venvPy)) {
        Write-Info 'Creating a private workspace for this project (.venv)'
        $r = Invoke-Exe -File $PythonExe -Arguments @('-m', 'venv', $venv)
        if (-not (Test-Path $venvPy)) {
            Stop-WithError -Message 'The virtual environment could not be created.' -Hints @(
                "Output follows:`n$($r.Output)"
            )
        }
    }
    Write-Ok 'Workspace ready'

    Write-Info 'Installing the components this project needs (1-3 minutes)'
    Invoke-Exe -File $venvPy -Arguments @('-m', 'pip', 'install', '--quiet', '--upgrade', 'pip') | Out-Null
    $req = Join-Path $Root 'requirements.txt'
    $r = Invoke-Exe -File $venvPy -Arguments @('-m', 'pip', 'install', '--quiet', '-r', $req) -WorkDir $Root
    if ($r.ExitCode -ne 0) {
        Stop-WithError -Message 'The components could not be installed.' -Hints @(
            'On a university network that inspects traffic, try again from a home or mobile connection.',
            'Or retry with: .venv\Scripts\python.exe -m pip install --trusted-host pypi.org --trusted-host files.pythonhosted.org -r requirements.txt',
            "pip output follows:`n$($r.Output)"
        )
    }
    Write-Ok 'Components installed'

    Write-Info 'Building the database from the bundled data'
    $r = Invoke-Exe -File $venvPy -Arguments @('etl/load_seed.py') -WorkDir $Root
    if ($r.ExitCode -ne 0) {
        Stop-WithError -Message 'The database could not be built.' -Hints @(
            "ETL output follows:`n$($r.Output)"
        )
    }
    Write-Ok 'Database built'
    return $venvPy
}

## ------------------------------------------------------------ launchers ----

function New-Launchers {
    param([string] $Root, [string] $Chosen, [int] $Number)

    $cmdPath = Join-Path $Root 'Start Dashboard.cmd'

    if ($Chosen -eq 'docker') {
        $body = @"
@echo off
title $AppName
cd /d "%~dp0"
rem Must match the port the installer published; docker-compose.yml reads it.
set GBD_PORT=$Number
echo.
echo   Starting $AppName...
echo   Keep this window open while you use the dashboard.
echo   Close it, or press Ctrl+C, to stop.
echo.
start "" http://127.0.0.1:$Number
docker compose up
"@
    } else {
        $body = @"
@echo off
title $AppName
cd /d "%~dp0"
echo.
echo   Starting $AppName...
echo   Keep this window open while you use the dashboard.
echo   Close it, or press Ctrl+C, to stop.
echo.
start "" http://127.0.0.1:$Number
".venv\Scripts\python.exe" -m uvicorn app.main:app --host 127.0.0.1 --port $Number
"@
    }

    Set-Content -Path $cmdPath -Value $body -Encoding ASCII
    Write-Ok "Created $cmdPath"

    if (-not $NoShortcut) {
        try {
            $desktop  = [Environment]::GetFolderPath('Desktop')
            $lnkPath  = Join-Path $desktop "$AppName.lnk"
            $shell    = New-Object -ComObject WScript.Shell
            $lnk      = $shell.CreateShortcut($lnkPath)
            $lnk.TargetPath       = $cmdPath
            $lnk.WorkingDirectory = $Root
            $lnk.Description      = "Start the $AppName dashboard"
            $lnk.Save()
            Write-Ok "Desktop shortcut created: $AppName"
        } catch {
            Write-Warn2 "Could not create the desktop shortcut. Use 'Start Dashboard.cmd' in the project folder instead."
        }
    }
    return $cmdPath
}

function Start-App {
    param([string] $Root, [string] $Chosen, [int] $Number, [string] $VenvPy)

    if ($Chosen -eq 'docker') {
        $r = Invoke-Exe -File 'docker' -Arguments @('compose', 'up', '-d') -WorkDir $Root
        if ($r.ExitCode -ne 0) {
            Stop-WithError -Message 'The container would not start.' -Hints @("Docker output:`n$($r.Output)")
        }
    } else {
        Start-Process -FilePath $VenvPy `
            -ArgumentList @('-m', 'uvicorn', 'app.main:app', '--host', '127.0.0.1', '--port', "$Number") `
            -WorkingDirectory $Root -WindowStyle Minimized
    }

    Write-Info 'Waiting for the dashboard to come up'
    if (-not (Wait-ForApp -Number $Number)) {
        Stop-WithError -Message 'The dashboard did not start in time.' -Hints @(
            "Run 'Start Dashboard.cmd' in $Root and read the error it prints."
        )
    }
    Write-Ok 'Dashboard is running'
}

## ----------------------------------------------------------------- main ----

Write-Banner

if ($env:OS -ne 'Windows_NT') {
    Stop-WithError -Message 'This installer is for Windows.' -Hints @(
        'On a Mac, follow INSTALL_WINDOWS.md -- it has a Mac section.'
    )
}

# --- 1. the project files -----------------------------------------------
Write-Step 'Getting the project files'
$root = Get-LocalRepoRoot
if ($root) {
    Write-Ok "Using the copy you already have"
    Write-Info $root
} else {
    if (-not $InstallDir) { $InstallDir = Join-Path $HOME 'ucc_gbd_pipeline' }
    $root = Install-ProjectFiles -Destination $InstallDir
}

# --- 2. choose the engine -----------------------------------------------
Write-Step 'Working out how best to run it on this machine'
$chosen = $Engine
if ($Engine -eq 'auto') {
    if (Test-DockerUsable) {
        $chosen = 'docker'
        Write-Ok 'Docker is installed and running -- using it'
        Write-Info 'Nothing else to install: the container brings its own Python.'
    } else {
        $chosen = 'python'
        if (Test-CommandExists 'docker') {
            Write-Info 'Docker is installed but not running -- using Python instead'
        } else {
            Write-Info 'No Docker on this machine -- using Python (no admin rights needed)'
        }
    }
} else {
    Write-Ok "Using the $Engine engine, as requested"
}

if ($chosen -eq 'docker' -and -not (Test-DockerUsable)) {
    Stop-WithError -Message 'Docker was requested but is not usable.' -Hints @(
        'Start Docker Desktop and wait for the whale icon to stop animating, then run this again.',
        'Or run this installer again with:  -Engine python'
    )
}

# --- 3. pick a port ------------------------------------------------------
# Done before anything is started, because the Docker path has to publish the
# chosen port at `compose up` time via GBD_PORT.
$resolvedPort = Find-FreePort -Preferred $Port
if ($resolvedPort -ne $Port) {
    Write-Warn2 "Port $Port is already in use, so port $resolvedPort will be used instead."
}
$env:GBD_PORT = "$resolvedPort"

# --- 4. set the engine up ------------------------------------------------
Write-Step 'Setting up'
$venvPy = $null
if ($chosen -eq 'docker') {
    Initialize-DockerEngine -Root $root -Number $resolvedPort
} else {
    $pythonExe = Resolve-Python -Version $PythonVersion
    $venvPy    = Initialize-PythonEngine -Root $root -PythonExe $pythonExe
}

# --- 5. launchers --------------------------------------------------------
Write-Step 'Creating a shortcut you can use from now on'
$cmdPath = New-Launchers -Root $root -Chosen $chosen -Number $resolvedPort

# --- 6. start ------------------------------------------------------------
if (-not $NoStart) {
    Write-Step 'Starting the dashboard'
    Start-App -Root $root -Chosen $chosen -Number $resolvedPort -VenvPy $venvPy
    Start-Process "http://127.0.0.1:$resolvedPort"
}

Write-Host ''
Write-Host '  ============================================================' -ForegroundColor DarkGreen
Write-Host '   All done' -ForegroundColor Green
Write-Host '  ============================================================' -ForegroundColor DarkGreen
Write-Host ''
if (-not $NoStart) {
    Write-Host "   The dashboard is open at  http://127.0.0.1:$resolvedPort" -ForegroundColor White
} else {
    Write-Host "   Everything is installed. It is not running yet." -ForegroundColor White
}
Write-Host ''
Write-Host '   To start it again later, either:' -ForegroundColor Gray
if (-not $NoShortcut) {
    Write-Host "     * double-click ""$AppName"" on your Desktop" -ForegroundColor Gray
}
Write-Host "     * or double-click 'Start Dashboard.cmd' in:" -ForegroundColor Gray
Write-Host "       $root" -ForegroundColor DarkGray
Write-Host ''
if ($chosen -eq 'docker') {
    Write-Host '   To stop it: close that window, or run  docker compose down' -ForegroundColor Gray
} else {
    Write-Host '   To stop it: close that window, or press Ctrl+C in it.' -ForegroundColor Gray
}
Write-Host ''
