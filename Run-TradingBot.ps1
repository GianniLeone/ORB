# Run-TradingBot.ps1
# PowerShell script to launch the ORB News Trading Bot

# Set paths
$ScriptDir = $PSScriptRoot
$VenvDir = Join-Path $ScriptDir "venv"
$PythonExe = Join-Path $VenvDir "Scripts\python.exe"
$TraderScript = Join-Path $ScriptDir "windows_orb_trader.py"
$SchedulerScript = Join-Path $ScriptDir "windows_orb_scheduler.py"
$TestScript = Join-Path $ScriptDir "test_trading_bot.py"

# Activate virtual environment
function Activate-Venv {
    $ActivateScript = Join-Path $VenvDir "Scripts\Activate.ps1"
    if (Test-Path $ActivateScript) {
        & $ActivateScript
        Write-Host "Virtual environment activated" -ForegroundColor Green
    } else {
        Write-Host "ERROR: Virtual environment not found at $VenvDir" -ForegroundColor Red
        Write-Host "Please create a virtual environment first with: python -m venv venv" -ForegroundColor Yellow
        exit
    }
}

# Check if scripts exist
function Check-Scripts {
    if (-not (Test-Path $TraderScript)) {
        Write-Host "ERROR: Trading bot script not found at $TraderScript" -ForegroundColor Red
        exit
    }

    if (-not (Test-Path $SchedulerScript)) {
        Write-Host "ERROR: Scheduler script not found at $SchedulerScript" -ForegroundColor Red
        exit
    }
}

# Run the trading bot once
function Run-Bot {
    Clear-Host
    Write-Host "`nRunning trading bot in manual mode..." -ForegroundColor Cyan
    Write-Host "This will execute one full trading cycle and then exit." -ForegroundColor Cyan
    Write-Host "`nCommand: $PythonExe $TraderScript" -ForegroundColor Gray
    Write-Host "Results will be saved in the data directory.`n" -ForegroundColor Cyan
    
    & $PythonExe $TraderScript
    
    Write-Host "`nTrading bot execution completed.`n" -ForegroundColor Green
    Read-Host "Press Enter to continue"
}

# Run the scheduler for continuous operation
function Run-Scheduler {
    Clear-Host
    Write-Host "`nRunning trading bot scheduler in continuous mode (24h test)..." -ForegroundColor Cyan
    Write-Host "This will execute the bot at scheduled intervals based on market hours." -ForegroundColor Cyan
    Write-Host "`nCommand: $PythonExe $SchedulerScript" -ForegroundColor Gray
    Write-Host "Press Ctrl+C to stop the scheduler.`n" -ForegroundColor Yellow
    
    & $PythonExe $SchedulerScript
    
    Write-Host "`nScheduler has stopped.`n" -ForegroundColor Green
    Read-Host "Press Enter to continue"
}

# Test API connections
function Test-Connections {
    Clear-Host
    Write-Host "`nTesting API connections...`n" -ForegroundColor Cyan
    
    if (Test-Path $TestScript) {
        Write-Host "Command: $PythonExe $TestScript" -ForegroundColor Gray
        & $PythonExe $TestScript
    } else {
        Write-Host "Test script not found. Running simple connection test..." -ForegroundColor Yellow
        & $PythonExe -c "import alpaca_trade_api as tradeapi; import os; from dotenv import load_dotenv; load_dotenv(); api = tradeapi.REST(); account = api.get_account(); print(f'Connected to Alpaca account: {account.id}'); print(f'Portfolio value: ${float(account.portfolio_value):.2f}')"
    }
    
    Write-Host "`nConnection test completed.`n" -ForegroundColor Green
    Read-Host "Press Enter to continue"
}

# View log files
function View-Logs {
    Clear-Host
    Write-Host "`nAvailable log files:`n" -ForegroundColor Cyan
    Write-Host "1. Trading bot log (orb_news_trader.log)" -ForegroundColor White
    Write-Host "2. Scheduler log (orb_scheduler.log)" -ForegroundColor White
    Write-Host "3. Test log (test_bot.log)" -ForegroundColor White
    Write-Host "4. Back to main menu" -ForegroundColor White
    Write-Host "`n"
    
    $logOption = Read-Host "Select log file to view (1-4)"
    
    switch ($logOption) {
        "1" {
            Clear-Host
            Write-Host "Trading bot log:" -ForegroundColor Cyan
            Write-Host "---------------" -ForegroundColor Cyan
            if (Test-Path "orb_news_trader.log") {
                Get-Content "orb_news_trader.log" | more
            } else {
                Write-Host "Log file not found!" -ForegroundColor Red
            }
        }
        "2" {
            Clear-Host
            Write-Host "Scheduler log:" -ForegroundColor Cyan
            Write-Host "--------------" -ForegroundColor Cyan
            if (Test-Path "orb_scheduler.log") {
                Get-Content "orb_scheduler.log" | more
            } else {
                Write-Host "Log file not found!" -ForegroundColor Red
            }
        }
        "3" {
            Clear-Host
            Write-Host "Test log:" -ForegroundColor Cyan
            Write-Host "---------" -ForegroundColor Cyan
            if (Test-Path "test_bot.log") {
                Get-Content "test_bot.log" | more
            } else {
                Write-Host "Log file not found!" -ForegroundColor Red
            }
        }
        "4" { return }
        default { Write-Host "Invalid option" -ForegroundColor Red }
    }
    
    Read-Host "`nPress Enter to continue"
    View-Logs
}

# Check account status
function Check-AccountStatus {
    Clear-Host
    Write-Host "`nChecking Alpaca account status...`n" -ForegroundColor Cyan
    
    & $PythonExe -c "
import alpaca_trade_api as tradeapi
import os
from dotenv import load_dotenv
load_dotenv()
try:
    api = tradeapi.REST()
    account = api.get_account()
    print(f'Account ID: {account.id}')
    print(f'Account status: {account.status}')
    print(f'Cash: ${float(account.cash):.2f}')
    print(f'Portfolio value: ${float(account.portfolio_value):.2f}')
    print(f'Buying power: ${float(account.buying_power):.2f}')
    print(f'Day trade count: {account.daytrade_count}')
    print(f'\nCurrent positions:')
    positions = api.list_positions()
    print(f'Total positions: {len(positions)}')
    for p in positions:
        print(f'  {p.symbol}: {p.qty} shares @ ${float(p.avg_entry_price):.2f}, current: ${float(p.current_price):.2f}, P&L: ${float(p.unrealized_pl):.2f} ({float(p.unrealized_plpc)*100:.2f}%)')
except Exception as e:
    print(f'Error accessing Alpaca account: {e}')
"
    
    Read-Host "`nPress Enter to continue"
}

# Main menu
function Show-Menu {
    Clear-Host
    Write-Host "ORB News Trading Bot Launcher" -ForegroundColor Green
    Write-Host "==============================" -ForegroundColor Green
    Write-Host
    Write-Host "Choose an option:" -ForegroundColor Cyan
    Write-Host "1. Run the trading bot once (manual mode)" -ForegroundColor White
    Write-Host "2. Run the scheduler (continuous mode for 24h testing)" -ForegroundColor White
    Write-Host "3. Test API connections" -ForegroundColor White
    Write-Host "4. View log files" -ForegroundColor White
    Write-Host "5. View account status" -ForegroundColor White
    Write-Host "6. Exit" -ForegroundColor White
    Write-Host
    
    $option = Read-Host "Enter option (1-6)"
    
    switch ($option) {
        "1" { Run-Bot }
        "2" { Run-Scheduler }
        "3" { Test-Connections }
        "4" { View-Logs }
        "5" { Check-AccountStatus }
        "6" { Exit-Script }
        default { Write-Host "Invalid option selected. Please try again." -ForegroundColor Red; Start-Sleep -Seconds 2 }
    }
    
    Show-Menu
}

function Exit-Script {
    Write-Host "`nExiting ORB News Trading Bot Launcher..." -ForegroundColor Cyan
    Write-Host "Thank you for using our trading system!`n" -ForegroundColor Green
    exit
}

# Main script execution
Clear-Host
Write-Host "ORB News Trading Bot Launcher" -ForegroundColor Green
Write-Host "==============================" -ForegroundColor Green
Write-Host

# Activate virtual environment
Activate-Venv

# Check if scripts exist
Check-Scripts

# Show main menu
Show-Menu