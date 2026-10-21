# reelforge one-line installer for Windows.
#
#   irm https://raw.githubusercontent.com/atharellahi/reelforge/main/install.ps1 | iex
#
# Installs what is missing (Python, git, ffmpeg, Chrome), then reelforge and its
# Claude Code skill. Safe to run again: everything is checked before it is
# installed. Keys are NOT asked for here - put them in ~/.reelforge/.env or in
# <repo>/.reelforge/.env (see .env.example), or let Claude ask you.
$ErrorActionPreference = "Stop"
$repo = if ($env:REELFORGE_REPO) { $env:REELFORGE_REPO } else { "https://github.com/atharellahi/reelforge.git" }

function Have($cmd) { return [bool](Get-Command $cmd -ErrorAction SilentlyContinue) }
function Step($msg) { Write-Host ""; Write-Host "==> $msg" -ForegroundColor Cyan }
function WingetInstall($id, $name) {
  Step "Installing $name"
  winget install --id $id -e --silent --accept-source-agreements --accept-package-agreements | Out-Null
}

if (-not (Have "winget")) { throw "winget is required (it ships with Windows 10/11). Install 'App Installer' from the Microsoft Store and re-run." }

if (-not (Have "python"))  { WingetInstall "Python.Python.3.12" "Python 3.12" }
if (-not (Have "git"))     { WingetInstall "Git.Git" "Git" }
if (-not (Have "ffmpeg"))  { WingetInstall "Gyan.FFmpeg" "ffmpeg" }
$chrome = @("$env:ProgramFiles\Google\Chrome\Application\chrome.exe",
            "${env:ProgramFiles(x86)}\Google\Chrome\Application\chrome.exe",
            "$env:LOCALAPPDATA\Google\Chrome\Application\chrome.exe",
            "$env:ProgramFiles\Microsoft\Edge\Application\msedge.exe") | Where-Object { Test-Path $_ } | Select-Object -First 1
if (-not $chrome) { WingetInstall "Google.Chrome" "Google Chrome" }

# refresh PATH for this session so newly installed tools are callable
$env:Path = [Environment]::GetEnvironmentVariable("Path", "Machine") + ";" + [Environment]::GetEnvironmentVariable("Path", "User")

Step "Installing pipx (isolated command-line apps)"
python -m pip install --user --quiet --disable-pip-version-check pipx
python -m pipx ensurepath | Out-Null
$pipxBin = Join-Path $env:USERPROFILE ".local\bin"
if (-not (($env:Path -split ";") -contains $pipxBin)) { $env:Path = "$pipxBin;$env:Path" }

Step "Installing reelforge from $repo"
python -m pipx install --force "git+$repo" | Out-Null
python -m pipx inject reelforge faster-whisper | Out-Null

Step "Installing the Claude Code skill"
& "$pipxBin\reelforge.exe" skill install

Step "Checking the machine"
& "$pipxBin\reelforge.exe" doctor

$envFile = Join-Path $env:USERPROFILE ".reelforge\.env"
if (-not (Test-Path $envFile)) {
  @"
# reelforge keys - this file is yours, never committed.
# Required:
GEMINI_API_KEY=
# Optional (publishing):
YOUTUBE_CLIENT_SECRET=
INSTAGRAM_ACCESS_TOKEN=
INSTAGRAM_USER_ID=
# Optional (live-action hook plates, billed per second):
VEO_API_KEY=
VEO_PROJECT=
"@ | Set-Content -Encoding utf8 $envFile
}

Write-Host ""
Write-Host "Done." -ForegroundColor Green
Write-Host "  1. Put your Gemini key in: $envFile"
Write-Host "  2. Open a NEW terminal, cd into your project, run: claude"
Write-Host "  3. Say: make a 30-second short about <a feature>   (or: open the reelforge ui)"
