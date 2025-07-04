# PowerShell script to run COM port tests for Gilbarco SK700-II
# This script will set up the environment and run the comprehensive COM port test suite

param(
    [string]$Port = "",
    [switch]$ScanAll = $false,
    [switch]$Verbose = $false,
    [switch]$Help = $false
)

Write-Host "============================================" -ForegroundColor Cyan
Write-Host "Gilbarco SK700-II COM Port Testing Suite" -ForegroundColor Cyan
Write-Host "============================================" -ForegroundColor Cyan
Write-Host ""

if ($Help) {
    Write-Host "Usage:" -ForegroundColor Yellow
    Write-Host "  .\run_comport_tests.ps1                 - Interactive mode" -ForegroundColor White
    Write-Host "  .\run_comport_tests.ps1 -ScanAll        - Test all available COM ports" -ForegroundColor White
    Write-Host "  .\run_comport_tests.ps1 -Port COM1      - Test specific port" -ForegroundColor White
    Write-Host "  .\run_comport_tests.ps1 -Verbose        - Enable verbose logging" -ForegroundColor White
    Write-Host "  .\run_comport_tests.ps1 -Help           - Show this help" -ForegroundColor White
    Write-Host ""
    Write-Host "Examples:" -ForegroundColor Yellow
    Write-Host "  .\run_comport_tests.ps1 -Port COM3 -Verbose" -ForegroundColor White
    Write-Host "  .\run_comport_tests.ps1 -ScanAll -Verbose" -ForegroundColor White
    exit 0
}

# Check if Python is available
try {
    $pythonVersion = python --version 2>&1
    Write-Host "Found Python: $pythonVersion" -ForegroundColor Green
} catch {
    Write-Host "ERROR: Python is not installed or not in PATH" -ForegroundColor Red
    Write-Host "Please install Python 3.7 or higher from https://python.org" -ForegroundColor Yellow
    Read-Host "Press Enter to exit"
    exit 1
}

# Check if virtual environment exists
if (-not (Test-Path "venv")) {
    Write-Host "Creating Python virtual environment..." -ForegroundColor Yellow
    python -m venv venv
}

# Activate virtual environment
Write-Host "Activating virtual environment..." -ForegroundColor Yellow
if (Test-Path "venv\Scripts\Activate.ps1") {
    . .\venv\Scripts\Activate.ps1
} else {
    Write-Host "ERROR: Could not find virtual environment activation script" -ForegroundColor Red
    exit 1
}

# Install/upgrade dependencies
Write-Host "Installing dependencies..." -ForegroundColor Yellow
pip install -r requirements.txt --quiet

# Run the COM port test
Write-Host ""
Write-Host "Starting COM port tests..." -ForegroundColor Green
Write-Host ""

# Build command arguments
$args = @()

if ($ScanAll) {
    $args += "--scan-all"
}

if ($Port -ne "") {
    $args += "--port"
    $args += $Port
}

if ($Verbose) {
    $args += "--verbose"
}

# Run the test
try {
    if ($args.Count -gt 0) {
        python test_comport.py @args
    } else {
        python test_comport.py
    }
} catch {
    Write-Host "ERROR: Test execution failed: $($_.Exception.Message)" -ForegroundColor Red
    exit 1
}

Write-Host ""
Write-Host "============================================" -ForegroundColor Cyan
Write-Host "Test completed!" -ForegroundColor Green
Write-Host "Check the generated log files and JSON report for detailed results." -ForegroundColor White
Write-Host "============================================" -ForegroundColor Cyan

# Keep window open
if ($Host.Name -eq "ConsoleHost") {
    Write-Host ""
    Read-Host "Press Enter to exit"
}
