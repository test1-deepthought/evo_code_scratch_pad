<#
.SYNOPSIS
  EVO — Explicit-assumption Verification Orchestrator
  PowerShell launcher for Windows

.DESCRIPTION
  Run EVO reasoning tasks from PowerShell.
  Detects SWI-Prolog automatically.

.EXAMPLE
  .\run.ps1 solve "Socrates is mortal"
  .\run.ps1 self-test
  .\run.ps1 shell
  .\run.ps1 help
#>

param(
  [string]$Command = "help",
  [string]$Problem = ""
)

$ErrorActionPreference = "Continue"
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $ScriptDir

# ── Check Python ─────────────────────────────────────────────────────────
$python = $null
foreach ($candidate in @("python3", "python")) {
  $exe = Get-Command $candidate -ErrorAction SilentlyContinue
  if ($exe) { $python = $exe.Source; break }
}

if (-not $python) {
  Write-Host "  [FAIL] Python 3 not found. Install from https://www.python.org/downloads/windows/" -ForegroundColor Red
  exit 1
}
Write-Host "  [OK] Python: $python" -ForegroundColor Green

# ── Check SWI-Prolog ─────────────────────────────────────────────────────
$swipl = $null
foreach ($candidate in @("swipl.exe", "swipl")) {
  $exe = Get-Command $candidate -ErrorAction SilentlyContinue
  if ($exe) { $swipl = $exe.Source; break }
}

if (-not $swipl) {
  # Check common install paths
  $paths = @(
    "${env:ProgramFiles}\swipl\bin\swipl.exe",
    "${env:ProgramFiles(x86)}\swipl\bin\swipl.exe",
    "${env:LOCALAPPDATA}\Programs\swipl\bin\swipl.exe"
  )
  foreach ($p in $paths) {
    if (Test-Path $p) { $swipl = $p; break }
  }
}

if (-not $swipl) {
  Write-Host "  [FAIL] SWI-Prolog not found. Install from:" -ForegroundColor Red
  Write-Host "         https://www.swi-prolog.org/download/stable" -ForegroundColor Yellow
  Write-Host ""
  Write-Host "  After installing, ensure swipl.exe is in your PATH or re-run this script."
  exit 1
}
Write-Host "  [OK] SWI-Prolog: $swipl" -ForegroundColor Green

# ── Check Lean 4 ──────────────────────────────────────────────────────────
$lean = Get-Command "lean" -ErrorAction SilentlyContinue
if ($lean) {
  Write-Host "  [OK] Lean 4: $($lean.Source)" -ForegroundColor Green
} else {
  Write-Host "  [..] Lean 4: not found (optional, needed for PROVE tier)" -ForegroundColor DarkYellow
}

Write-Host ""

# ── Dispatch command ─────────────────────────────────────────────────────
switch ($Command.ToLower()) {
  "solve" {
    if ([string]::IsNullOrWhiteSpace($Problem)) {
      $Problem = Read-Host "Enter problem description"
    }
    Write-Host "  Problem: $Problem" -ForegroundColor Cyan
    Write-Host ""
    & $python evo.py solve $Problem
  }
  "self-test" {
    & $python evo.py self-test
  }
  "test" {
    & $python evo.py self-test
  }
  "shell" {
    & $python evo.py shell
  }
  "help" {
    & $python evo.py help
  }
  default {
    if ($Command -ne "help") {
      Write-Host "Unknown command: $Command" -ForegroundColor Red
    }
    & $python evo.py help
  }
}
