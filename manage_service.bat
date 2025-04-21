@echo off
REM ORB News Trading Bot Launcher
REM Run this script to start the trading bot system

SETLOCAL

REM Set paths
SET SCRIPT_DIR=%~dp0
SET VENV_DIR=%SCRIPT_DIR%venv
SET PYTHON_EXE=%VENV_DIR%\Scripts\python.exe
SET TRADER_SCRIPT=%SCRIPT_DIR%windows_orb_trader.py
SET SCHEDULER_SCRIPT=%SCRIPT_DIR%windows_orb_scheduler.py
SET TEST_SCRIPT=%SCRIPT_DIR%test_trading_bot.py
SET LOG_FILE=%SCRIPT_DIR%bot_launcher.log

echo ORB News Trading Bot Launcher
echo ==============================
echo.

REM Activate virtual environment
call %VENV_DIR%\Scripts\activate.bat

echo Virtual environment activated

REM Check if scripts exist
IF NOT EXIST "%TRADER_SCRIPT%" (
    echo ERROR: Trading bot script not found at %TRADER_SCRIPT%
    exit /b 1
)

IF NOT EXIST "%SCHEDULER_SCRIPT%" (
    echo ERROR: Scheduler script not found at %SCHEDULER_SCRIPT%
    exit /b 1
)

:menu
cls
echo ORB News Trading Bot Launcher
echo ==============================
echo.
echo Choose an option:
echo 1. Run the trading bot once (manual mode)
echo 2. Run the scheduler (continuous mode for 24h testing)
echo 3. Test API connections
echo 4. View log files
echo 5. View account status
echo 6. Exit
echo.

set /p option="Enter option (1-6): "

IF "%option%"=="1" goto :run_bot
IF "%option%"=="2" goto :run_scheduler
IF "%option%"=="3" goto :test_connections
IF "%option%"=="4" goto :view_logs
IF "%option%"=="5" goto :account_status
IF "%option%"=="6" goto :exit

echo Invalid option selected. Please try again.
timeout /t 2 >nul
goto :menu

:run_bot
cls
echo.
echo Running trading bot in manual mode...
echo This will execute one full trading cycle and then exit.
echo.
echo Command: "%PYTHON_EXE%" "%TRADER_SCRIPT%"
echo Results will be saved in the data directory.
echo.
"%PYTHON_EXE%" "%TRADER_SCRIPT%"
echo.
echo Trading bot execution completed.
echo.
pause
goto :menu

:run_scheduler
cls
echo.
echo Running trading bot scheduler in continuous mode (24h test)...
echo This will execute the bot at scheduled intervals based on market hours.
echo.
echo Command: "%PYTHON_EXE%" "%SCHEDULER_SCRIPT%"
echo Press Ctrl+C to stop the scheduler.
echo.
"%PYTHON_EXE%" "%SCHEDULER_SCRIPT%"
echo.
echo Scheduler has stopped.
echo.
pause
goto :menu

:test_connections
cls
echo.
echo Testing API connections...
echo.
IF EXIST "%TEST_SCRIPT%" (
    echo Command: "%PYTHON_EXE%" "%TEST_SCRIPT%"
    "%PYTHON_EXE%" "%TEST_SCRIPT%"
) ELSE (
    echo Test script not found. Running simple connection test...
    "%PYTHON_EXE%" -c "import alpaca_trade_api as tradeapi; import os; from dotenv import load_dotenv; load_dotenv(); api = tradeapi.REST(); account = api.get_account(); print(f'Connected to Alpaca account: {account.id}'); print(f'Portfolio value: ${float(account.portfolio_value):.2f}')"
)
echo.
echo Connection test completed.
echo.
pause
goto :menu

:view_logs
cls
echo.
echo Available log files:
echo.
echo 1. Trading bot log (orb_news_trader.log)
echo 2. Scheduler log (orb_scheduler.log)
echo 3. Test log (test_bot.log)
echo 4. Back to main menu
echo.
set /p log_option="Select log file to view (1-4): "

IF "%log_option%"=="1" (
    cls
    echo Trading bot log:
    echo ---------------
    type orb_news_trader.log | more
)
IF "%log_option%"=="2" (
    cls
    echo Scheduler log:
    echo --------------
    type orb_scheduler.log | more
)
IF "%log_option%"=="3" (
    cls
    echo Test log:
    echo ---------
    type test_bot.log | more
)
IF "%log_option%"=="4" goto :menu

echo.
pause
goto :view_logs

:account_status
cls
echo.
echo Checking Alpaca account status...
echo.
"%PYTHON_EXE%" -c "import alpaca_trade_api as tradeapi; import os; from dotenv import load_dotenv; load_dotenv(); api = tradeapi.REST(); account = api.get_account(); print(f'Account ID: {account.id}'); print(f'Account status: {account.status}'); print(f'Cash: ${float(account.cash):.2f}'); print(f'Portfolio value: ${float(account.portfolio_value):.2f}'); print(f'Buying power: ${float(account.buying_power):.2f}'); print(f'Day trade count: {account.daytrade_count}'); print(f'\nCurrent positions:'); positions = api.list_positions(); print(f'Total positions: {len(positions)}'); [print(f'  {p.symbol}: {p.qty} shares @ ${float(p.avg_entry_price):.2f}, current: ${float(p.current_price):.2f}, P&L: ${float(p.unrealized_pl):.2f} ({float(p.unrealized_plpc)*100:.2f}%)') for p in positions]"
echo.
pause
goto :menu

:exit
echo.
echo Exiting ORB News Trading Bot Launcher...
echo Thank you for using our trading system!
echo.
exit /b 0

ENDLOCAL