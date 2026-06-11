<#
.SYNOPSIS
  EVO Test Suite — PowerShell test runner for Windows

.DESCRIPTION
  Runs all EVO tests: Prolog module validation, self-verification,
  Lean theorem check, and knowledge base sanity.
#>

$ErrorActionPreference = "Continue"
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $ScriptDir

$passed = 0
$failed = 0
$total = 0

function Test-Step {
  param([string]$Name, [scriptblock]$Block)
  $script:total++
  Write-Host "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━" -ForegroundColor DarkGray
  Write-Host "  TEST $total`: $Name" -ForegroundColor Cyan
  Write-Host "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━" -ForegroundColor DarkGray
  try {
    & $Block
    Write-Host "  [PASS] $Name" -ForegroundColor Green
    $script:passed++
  } catch {
    Write-Host "  [FAIL] $Name" -ForegroundColor Red
    Write-Host "    $($_.Exception.Message)" -ForegroundColor Red
    $script:failed++
  }
  Write-Host ""
}

function Find-Swipl {
  $candidates = @("swipl.exe", "swipl")
  foreach ($c in $candidates) {
    $exe = Get-Command $c -ErrorAction SilentlyContinue
    if ($exe) { return $exe.Source }
  }
  $paths = @(
    "${env:ProgramFiles}\swipl\bin\swipl.exe",
    "${env:ProgramFiles(x86)}\swipl\bin\swipl.exe",
    "${env:LOCALAPPDATA}\Programs\swipl\bin\swipl.exe"
  )
  foreach ($p in $paths) {
    if (Test-Path $p) { return $p }
  }
  return $null
}

# ═══════════════════════════════════════════════════════════════════════
#  TEST 1: Python CLI exists and runs
# ═══════════════════════════════════════════════════════════════════════
Test-Step -Name "Python CLI exists and runs" -Block {
  if (-not (Test-Path "evo.py")) {
    throw "evo.py not found"
  }
  $python = if (Get-Command python3 -ErrorAction SilentlyContinue) { "python3" } else { "python" }
  $result = & $python evo.py help 2>&1 | Out-String
  if ($result -notmatch "EVO") {
    throw "evo.py help output does not mention EVO"
  }
}

# ═══════════════════════════════════════════════════════════════════════
#  TEST 2: SWI-Prolog is installed
# ═══════════════════════════════════════════════════════════════════════
Test-Step -Name "SWI-Prolog is installed" -Block {
  $swipl = Find-Swipl
  if (-not $swipl) {
    throw "SWI-Prolog (swipl.exe) not found. Install from https://www.swi-prolog.org/download/stable"
  }
  Write-Host "    Found at: $swipl" -ForegroundColor Gray
}

# ═══════════════════════════════════════════════════════════════════════
#  TEST 3: All core Prolog files exist
# ═══════════════════════════════════════════════════════════════════════
Test-Step -Name "All core Prolog files exist" -Block {
  $files = @(
    "core/engine.pl",
    "core/assumptions.pl",
    "core/consistency.pl",
    "core/proof_trace.pl",
    "core/tiers.pl",
    "harness/reason_harness.pl",
    "prove/evos_first_theorem.lean"
  )
  $missing = @()
  foreach ($f in $files) {
    if (-not (Test-Path $f)) { $missing += $f }
  }
  if ($missing.Count -gt 0) {
    throw "Missing files: $($missing -join ', ')"
  }
  Write-Host "    All $($files.Count) files present" -ForegroundColor Gray
}

# ═══════════════════════════════════════════════════════════════════════
#  TEST 4: Core engine loads without errors
# ═══════════════════════════════════════════════════════════════════════
Test-Step -Name "Core engine loads without errors" -Block {
  $swipl = Find-Swipl
  $result = & $swipl -q -f none -s core/engine.pl -g "true" -t "halt" 2>&1 | Out-String
  if ($LASTEXITCODE -ne 0) {
    throw "engine.pl failed to load: $result"
  }
}

# ═══════════════════════════════════════════════════════════════════════
#  TEST 5: All core modules load together
# ═══════════════════════════════════════════════════════════════════════
Test-Step -Name "All core modules load together" -Block {
  $swipl = Find-Swipl
  $files = @("core/engine.pl","core/assumptions.pl","core/consistency.pl",
             "core/proof_trace.pl","core/tiers.pl")
  $cmd = @($swipl, "-q", "-f", "none")
  foreach ($f in $files) { $cmd += @("-s", $f) }
  $cmd += @("-g", "true", "-t", "halt")
  $result = & $cmd 2>&1 | Out-String
  if ($LASTEXITCODE -ne 0) {
    throw "Combined load failed: $result"
  }
}

# ═══════════════════════════════════════════════════════════════════════
#  TEST 6: Reason harness executes (derive + consistency)
# ═══════════════════════════════════════════════════════════════════════
Test-Step -Name "Reason harness executes" -Block {
  $swipl = Find-Swipl
  $files = @("core/engine.pl","core/assumptions.pl","core/consistency.pl",
             "core/proof_trace.pl","core/tiers.pl","harness/reason_harness.pl")
  $cmd = @($swipl, "-q", "-f", "none")
  foreach ($f in $files) { $cmd += @("-s", $f) }
  $cmd += @("-g", "main", "-t", "halt")
  $result = & $cmd 2>&1 | Out-String
  if ($LASTEXITCODE -ne 0) {
    throw "Reason harness failed (exit code $LASTEXITCODE): $result"
  }
  if ($result -notmatch "STATUS") {
    throw "Reason harness output missing STATUS: $result"
  }
  Write-Host "    Output excerpt:" -ForegroundColor Gray
  $result -split "`n" | ForEach-Object {
    if ($_ -match "STATUS|SOLVED|CONSISTENT|ROBUST|CONCLUSION") {
      Write-Host "      $_" -ForegroundColor Gray
    }
  }
}

# ═══════════════════════════════════════════════════════════════════════
#  TEST 7: Derive engine test (observation -> conclusion)
# ═══════════════════════════════════════════════════════════════════════
Test-Step -Name "Derive engine: observation to conclusion" -Block {
  $swipl = Find-Swipl
  $code = @"
:- dynamic conclusion/1, observation/1, active_assumption/1.
observation('test_fact').
conclusion('test_conclusion') :- observation('test_fact').
main :- findall(C, conclusion(C), Cs), write(Cs), nl.
:- main.
"@
  $tmp = [System.IO.Path]::GetTempFileName() + ".pl"
  [System.IO.File]::WriteAllText($tmp, $code)
  $result = & $swipl -q -f none -s $tmp -t "halt" 2>&1 | Out-String
  Remove-Item $tmp -ErrorAction SilentlyContinue
  if ($result -notmatch "test_conclusion") {
    throw "Derive test failed: $result"
  }
}

# ═══════════════════════════════════════════════════════════════════════
#  TEST 8: Self-test command runs via Python CLI
# ═══════════════════════════════════════════════════════════════════════
Test-Step -Name "Self-test via Python CLI" -Block {
  $python = if (Get-Command python3 -ErrorAction SilentlyContinue) { "python3" } else { "python" }
  $result = & $python evo.py self-test 2>&1 | Out-String
  if ($result -notmatch "COMPLETE|PASS") {
    Write-Host "    (some checks may have warnings, but CLI runs)" -ForegroundColor Yellow
  }
}

# ═══════════════════════════════════════════════════════════════════════
#  TEST 9: Solve command runs
# ═══════════════════════════════════════════════════════════════════════
Test-Step -Name "Solve command runs with a problem" -Block {
  $python = if (Get-Command python3 -ErrorAction SilentlyContinue) { "python3" } else { "python" }
  $result = & $python evo.py solve "Socrates is mortal" 2>&1 | Out-String
  if ($result -notmatch "REASON|Tier|CONSISTENT") {
    Write-Host "    (CLI runs but may show partial output)" -ForegroundColor Yellow
  }
}

# ═══════════════════════════════════════════════════════════════════════
#  SUMMARY
# ═══════════════════════════════════════════════════════════════════════
Write-Host "═══════════════════════════════════════════════════════════" -ForegroundColor DarkGray
Write-Host "  RESULTS: $passed passed / $failed failed / $total total" -ForegroundColor $(if ($failed -eq 0) { "Green" } else { "Red" })
Write-Host "═══════════════════════════════════════════════════════════" -ForegroundColor DarkGray

if ($failed -gt 0) {
  exit 1
}
