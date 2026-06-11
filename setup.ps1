<#
.SYNOPSIS
  EVO Setup Script for Windows

.DESCRIPTION
  Checks dependencies, creates directories, and verifies
  the EVO system is ready to run on Windows.
#>

$ErrorActionPreference = "Continue"
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $ScriptDir

Write-Host "═══════════════════════════════════════════════════════════" -ForegroundColor Cyan
Write-Host "  EVO Setup — Windows Dependency Check" -ForegroundColor Cyan
Write-Host "═══════════════════════════════════════════════════════════" -ForegroundColor Cyan
Write-Host ""

# ── Python ─────────────────────────────────────────────────────────────────
Write-Host "── [1/4] Python ──" -ForegroundColor Cyan
$python = $null
$pythonVer = $null
foreach ($candidate in @("python3", "python")) {
  $exe = Get-Command $candidate -ErrorAction SilentlyContinue
  if ($exe) {
    $python = $exe.Source
    try {
      $pythonVer = & $candidate --version 2>&1 | Out-String
    } catch {}
    break
  }
}
if ($python) {
  Write-Host "  [OK] $pythonVer.Trim()" -ForegroundColor Green
  Write-Host "       Path: $python" -ForegroundColor Gray
} else {
  Write-Host "  [FAIL] Python 3 not found!" -ForegroundColor Red
  Write-Host "  Install from: https://www.python.org/downloads/windows/" -ForegroundColor Yellow
  Write-Host "  IMPORTANT: Check 'Add Python to PATH' during installation" -ForegroundColor Yellow
}
Write-Host ""

# ── SWI-Prolog ─────────────────────────────────────────────────────────────
Write-Host "── [2/4] SWI-Prolog ──" -ForegroundColor Cyan
$swipl = $null
foreach ($candidate in @("swipl.exe", "swipl")) {
  $exe = Get-Command $candidate -ErrorAction SilentlyContinue
  if ($exe) { $swipl = $exe.Source; break }
}
if (-not $swipl) {
  $paths = @(
    "${env:ProgramFiles}\swipl\bin\swipl.exe",
    "${env:ProgramFiles(x86)}\swipl\bin\swipl.exe",
    "${env:LOCALAPPDATA}\Programs\swipl\bin\swipl.exe"
  )
  foreach ($p in $paths) {
    if (Test-Path $p) { $swipl = $p; break }
  }
}
if ($swipl) {
  Write-Host "  [OK] SWI-Prolog found" -ForegroundColor Green
  Write-Host "       Path: $swipl" -ForegroundColor Gray
  # Try to get version
  $ver = & $swipl --version 2>&1 | Out-String
  if ($ver) {
    Write-Host "       Version: $($ver.Trim())" -ForegroundColor Gray
  }
} else {
  Write-Host "  [FAIL] SWI-Prolog not found!" -ForegroundColor Red
  Write-Host "  Install from: https://www.swi-prolog.org/download/stable" -ForegroundColor Yellow
  Write-Host "  Download the Windows installer (swipl-*.exe) and run it." -ForegroundColor Yellow
  Write-Host "  Default install path: C:\Program Files\swipl" -ForegroundColor Gray
}
Write-Host ""

# ── Lean 4 ─────────────────────────────────────────────────────────────────
Write-Host "── [3/4] Lean 4 ──" -ForegroundColor Cyan
$lean = Get-Command "lean" -ErrorAction SilentlyContinue
if ($lean) {
  Write-Host "  [OK] Lean 4 found" -ForegroundColor Green
  Write-Host "       Path: $($lean.Source)" -ForegroundColor Gray
} else {
  Write-Host "  [..] Lean 4 not found (optional)" -ForegroundColor DarkYellow
  Write-Host "       Install from: https://leanprover.github.io/lean4/install/" -ForegroundColor Yellow
}
Write-Host ""

# ── File Structure ─────────────────────────────────────────────────────────
Write-Host "── [4/4] File Structure ──" -ForegroundColor Cyan
$required = @(
  @{Path="evo.py"; Label="CLI entry point"}
  @{Path="run.ps1"; Label="PowerShell launcher"}
  @{Path="test.ps1"; Label="PowerShell test suite"}
  @{Path="core/engine.pl"; Label="Core inference engine"}
  @{Path="core/assumptions.pl"; Label="Assumption management"}
  @{Path="core/consistency.pl"; Label="Consistency checker"}
  @{Path="core/proof_trace.pl"; Label="Proof trace generator"}
  @{Path="core/tiers.pl"; Label="Tier dispatch"}
  @{Path="harness/reason_harness.pl"; Label="Reason harness"}
  @{Path="prove/evos_first_theorem.lean"; Label="Lean theorems"}
)
$allOk = $true
foreach ($item in $required) {
  if (Test-Path $item.Path) {
    Write-Host "  [OK] $($item.Label): $($item.Path)" -ForegroundColor Green
  } else {
    Write-Host "  [MISS] $($item.Label): $($item.Path)" -ForegroundColor Red
    $allOk = $false
  }
}

Write-Host ""
if ($python -and $swipl -and $allOk) {
  Write-Host "═══════════════════════════════════════════════════════════" -ForegroundColor Green
  Write-Host "  SETUP COMPLETE — EVO is ready to run!" -ForegroundColor Green
  Write-Host "═══════════════════════════════════════════════════════════" -ForegroundColor Green
  Write-Host ""
  Write-Host "  Quick start:" -ForegroundColor Cyan
  Write-Host "    .\run.ps1 self-test        # Run all tests" -ForegroundColor White
  Write-Host "    .\run.ps1 solve            # Solve a problem" -ForegroundColor White
  Write-Host "    .\run.ps1 shell            # Interactive Prolog shell" -ForegroundColor White
  Write-Host ""
  Write-Host "  Or directly with Python:" -ForegroundColor Cyan
  Write-Host "    python evo.py self-test" -ForegroundColor White
  Write-Host "    python evo.py solve 'Socrates is mortal'" -ForegroundColor White
} else {
  Write-Host "═══════════════════════════════════════════════════════════" -ForegroundColor Red
  Write-Host "  SETUP INCOMPLETE — install missing dependencies above" -ForegroundColor Red
  Write-Host "═══════════════════════════════════════════════════════════" -ForegroundColor Red
}
Write-Host ""
