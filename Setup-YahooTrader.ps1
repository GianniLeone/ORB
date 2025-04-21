# Setup-YahooTrader.ps1
# PowerShell script to set up and run Yahoo Finance ORB Trading Bot

# Check if running with administrative privileges
$isAdmin = ([Security.Principal.WindowsPrincipal] [Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)

if (-not $isAdmin) {
    Write-Host "This script is not running with administrative privileges. Some operations may fail." -ForegroundColor Yellow
}

# Set paths
$ScriptDir = $PSScriptRoot
$VenvDir = Join-Path $ScriptDir "venv"
$PythonExe = Join-Path $VenvDir "Scripts\python.exe"
$YahooTraderScript = Join-Path $ScriptDir "yahoo_orb_trader.py"
$YahooSchedulerScript = Join-Path $ScriptDir "yahoo_orb_scheduler.py"

# Function to activate virtual environment
function Activate-Venv {
    $ActivateScript = Join-Path $VenvDir "Scripts\Activate.ps1"
    if (Test-Path $ActivateScript) {
        & $ActivateScript
        Write-Host "Virtual environment activated" -ForegroundColor Green
        return $true
    } else {
        Write-Host "Virtual environment not found at $VenvDir" -ForegroundColor Red
        return $false
    }
}

# Function to install required packages
function Install-Requirements {
    Write-Host "Installing required packages..." -ForegroundColor Cyan
    
    # Check if requirements.txt exists
    $RequirementsFile = Join-Path $ScriptDir "requirements.txt"
    if (-not (Test-Path $RequirementsFile)) {
        Write-Host "requirements.txt not found. Creating a minimal version..." -ForegroundColor Yellow
        
        @"
# Trading Bot Requirements
openai>=1.0.0
requests>=2.28.0
alpaca-trade-api>=3.0.0
python-dotenv>=1.0.0
pytz>=2023.3
pandas>=1.5.0
numpy>=1.22.0
yfinance>=0.2.18

# For Windows Service
pywin32>=305; platform_system=="Windows"
pywin32-ctypes>=0.2.0
pypiwin32>=223; platform_system=="Windows"

# For data analysis
matplotlib>=3.6.0
seaborn>=0.12.0
"@ | Out-File -FilePath $RequirementsFile -Encoding utf8
    }
    
    # Install packages
    & $PythonExe -m pip install --upgrade pip
    & $PythonExe -m pip install -r $RequirementsFile
    
    if ($LASTEXITCODE -eq 0) {
        Write-Host "Package installation completed successfully." -ForegroundColor Green
        return $true
    } else {
        Write-Host "Package installation failed." -ForegroundColor Red
        return $false
    }
}

# Function to check API keys
function Check-APIKeys {
    Write-Host "Checking API keys..." -ForegroundColor Cyan
    
    # Check if .env file exists
    $EnvFile = Join-Path $ScriptDir ".env"
    $createNew = $false
    
    if (-not (Test-Path $EnvFile)) {
        Write-Host ".env file not found. Creating a new one..." -ForegroundColor Yellow
        $createNew = $true
    } else {
        $choice = Read-Host "Would you like to update your API keys? (y/n)"
        if ($choice -eq "y") {
            $createNew = $true
        }
    }
    
    if ($createNew) {
        # Collect API keys
        Write-Host "Please enter your API keys:" -ForegroundColor Cyan
        $alpacaApiKey = Read-Host "Alpaca API Key"
        $alpacaSecretKey = Read-Host "Alpaca API Secret Key"
        $openaiApiKey = Read-Host "OpenAI API Key"
        $newsApiKey = Read-Host "NewsAPI Key"
        
        @"
# Alpaca API credentials
APCA_API_KEY_ID=$alpacaApiKey
APCA_API_SECRET_KEY=$alpacaSecretKey
ALPACA_PAPER_URL=https://paper-api.alpaca.markets

# These are for backward compatibility with your existing code
ALPACA_API_KEY=$alpacaApiKey
ALPACA_SECRET_KEY=$alpacaSecretKey

# OpenAI API
OPENAI_API_KEY=$openaiApiKey

# News API
NEWS_API_KEY=$newsApiKey
"@ | Out-File -FilePath $EnvFile -Encoding utf8
        
        Write-Host ".env file created with your API keys." -ForegroundColor Green
    } else {
        Write-Host "Using existing API keys from .env file." -ForegroundColor Green
    }
    
    return $true
}

# Function to run the single trader
function Run-SingleTrader {
    Write-Host "`nRunning Yahoo ORB Trader once..." -ForegroundColor Cyan
    
    if (-not (Test-Path $YahooTraderScript)) {
        Write-Host "Error: Yahoo ORB Trader script not found at $YahooTraderScript" -ForegroundColor Red
        return
    }
    
    Write-Host "Starting trader... This will run one full trading cycle." -ForegroundColor Cyan
    & $PythonExe $YahooTraderScript
    
    Write-Host "Trading cycle completed." -ForegroundColor Green
}

# Function to run the scheduler
function Run-Scheduler {
    Write-Host "`nRunning Yahoo ORB Scheduler for continuous trading..." -ForegroundColor Cyan
    
    if (-not (Test-Path $YahooSchedulerScript)) {
        Write-Host "Error: Yahoo ORB Scheduler script not found at $YahooSchedulerScript" -ForegroundColor Red
        return
    }
    
    Write-Host "Starting scheduler... Press Ctrl+C to stop." -ForegroundColor Cyan
    & $PythonExe $YahooSchedulerScript
    
    Write-Host "Scheduler stopped." -ForegroundColor Green
}

# Function to view log files
function View-Logs {
    Write-Host "`nAvailable log files:" -ForegroundColor Cyan
    
    $LogFiles = @(
        "orb_news_trader.log",
        "orb_scheduler.log",
        "trade_queue.log"
    )
    
    for ($i = 0; $i -lt $LogFiles.Length; $i++) {
        $LogFile = Join-Path $ScriptDir $LogFiles[$i]
        if (Test-Path $LogFile) {
            Write-Host "$($i+1). $($LogFiles[$i])" -ForegroundColor White
        } else {
            Write-Host "$($i+1). $($LogFiles[$i]) (not found)" -ForegroundColor Gray
        }
    }
    
    $choice = Read-Host "`nEnter the number of the log file to view (or 'q' to go back)"
    
    if ($choice -eq 'q') {
        return
    }
    
    $index = [int]$choice - 1
    if ($index -ge 0 -and $index -lt $LogFiles.Length) {
        $LogFile = Join-Path $ScriptDir $LogFiles[$index]
        if (Test-Path $LogFile) {
            Get-Content $LogFile -Tail 50 | Out-Host
            Write-Host "(Showing last 50 lines)" -ForegroundColor Gray
            Read-Host "Press Enter to continue"
        } else {
            Write-Host "Log file not found" -ForegroundColor Red
            Read-Host "Press Enter to continue"
        }
    }
}

# Main function
function Main {
    Clear-Host
    Write-Host "======================================================" -ForegroundColor Green
    Write-Host "          Yahoo Finance ORB Trading Bot Setup         " -ForegroundColor Green
    Write-Host "======================================================" -ForegroundColor Green
    Write-Host
    
    # Step 1: Check and activate virtual environment
    if (-not (Activate-Venv)) {
        Write-Host "Virtual environment not found. Please create one first." -ForegroundColor Red
        Write-Host "You can create a virtual environment with the command:" -ForegroundColor Yellow
        Write-Host "   python -m venv venv" -ForegroundColor Yellow
        return
    }
    
    # Step 2: Install required packages
    if (-not (Install-Requirements)) {
        Write-Host "Failed to install required packages. Please check the errors above." -ForegroundColor Red
        return
    }
    
    # Step 3: Check API keys
    if (-not (Check-APIKeys)) {
        Write-Host "Failed to configure API keys. Please check the errors above." -ForegroundColor Red
        return
    }
    
    # Step 4: Create directories if they don't exist
    Write-Host "Creating required directories..." -ForegroundColor Cyan
    @("data", "data/orders", "data/orb_data") | ForEach-Object {
        $dir = Join-Path $ScriptDir $_
        if (-not (Test-Path $dir)) {
            New-Item -ItemType Directory -Path $dir | Out-Null
        }
    }
    
    # Step 5: Show menu
    while ($true) {
        Clear-Host
        Write-Host "======================================================" -ForegroundColor Green
        Write-Host "          Yahoo Finance ORB Trading Bot Menu          " -ForegroundColor Green
        Write-Host "======================================================" -ForegroundColor Green
        Write-Host
        Write-Host "1. Run trader once (single trading cycle)" -ForegroundColor White
        Write-Host "2. Run scheduler (continuous 24-hour trading)" -ForegroundColor White
        Write-Host "3. View log files" -ForegroundColor White
        Write-Host "4. Exit" -ForegroundColor White
        Write-Host
        
        $choice = Read-Host "Enter your choice (1-4)"
        
        switch ($choice) {
            "1" { Run-SingleTrader }
            "2" { Run-Scheduler }
            "3" { View-Logs }
            "4" { return }
            default { Write-Host "Invalid choice. Please try again." -ForegroundColor Red }
        }
        
        if ($choice -ne "3") {
            Read-Host "Press Enter to return to menu"
        }
    }
}

# Run main function
Main