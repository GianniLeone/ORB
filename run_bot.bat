@echo off
REM Run this script to start the ORB News Trading Bot

SETLOCAL

REM Activate virtual environment
call venv\Scripts\activate.bat

REM Display menu
:menu
cls
echo ======================================================
echo           Windows ORB News Trading Bot Menu
echo ======================================================
echo.
echo 1. Run trader once (single trading cycle)
echo 2. Run continuous scheduler (24-hour testing)
echo 3. View log files
echo 4. Exit
echo.

set /p choice="Enter your choice (1-4): "

if "%choice%"=="1" goto :run_once
if "%choice%"=="2" goto :run_scheduler
if "%choice%"=="3" goto :view_logs
if "%choice%"=="4" goto :exit

echo Invalid choice. Please try again.
timeout /t 2 >nul
goto :menu

:run_once
cls
echo Running trading bot once...
echo.
python windows_trader.py
echo.
echo Trading cycle completed.
pause
goto :menu

:run_scheduler
cls
echo Starting continuous scheduler...
echo This will run the trading bot at regular intervals.
echo Press Ctrl+C to stop.
echo.
python windows_scheduler.py
echo.
echo Scheduler stopped.
pause
goto :menu

:view_logs
cls
echo Available log files:
echo.
echo 1. Trading bot log (windows_trader.log)
echo 2. Scheduler log (windows_scheduler.log)
echo 3. Back to main menu
echo.

set /p log_choice="Select log file to view (1-3): "

if "%log_choice%"=="1" (
    cls
    echo Trading bot log:
    echo ---------------
    type windows_trader.log | more
    pause
    goto :view_logs
)

if "%log_choice%"=="2" (
    cls
    echo Scheduler log:
    echo --------------
    type windows_scheduler.log | more
    pause
    goto :view_logs
)

if "%log_choice%"=="3" goto :menu

echo Invalid choice. Please try again.
timeout /t 2 >nul
goto :view_logs

:exit
echo Exiting...
ENDLOCAL