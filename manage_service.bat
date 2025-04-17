@echo off
REM Trading Bot Service Manager
REM This batch file helps manage the Trading Bot Windows Service

SETLOCAL

REM Set paths
SET SCRIPT_DIR=%~dp0
SET VENV_DIR=%SCRIPT_DIR%venv
SET PYTHON_EXE=%VENV_DIR%\Scripts\python.exe
SET SERVICE_SCRIPT=%SCRIPT_DIR%trading_bot_service.py

echo ORB News Trading Bot Service Manager
echo ===================================
echo.

REM Check if virtual environment exists
IF NOT EXIST "%VENV_DIR%" (
    echo ERROR: Virtual environment not found at %VENV_DIR%
    echo Please create a virtual environment first.
    echo Example: python -m venv venv
    exit /b 1
)

REM Check if service script exists
IF NOT EXIST "%SERVICE_SCRIPT%" (
    echo ERROR: Service script not found at %SERVICE_SCRIPT%
    exit /b 1
)

REM Parse command line argument
IF "%1"=="" (
    goto :show_menu
) ELSE (
    goto :process_arg
)

:process_arg
IF "%1"=="install" (
    call :install_service
    exit /b
)
IF "%1"=="uninstall" (
    call :uninstall_service
    exit /b
)
IF "%1"=="start" (
    call :start_service
    exit /b
)
IF "%1"=="stop" (
    call :stop_service
    exit /b
)
IF "%1"=="status" (
    call :check_status
    exit /b
)
IF "%1"=="restart" (
    call :restart_service
    exit /b
)
IF "%1"=="menu" (
    goto :show_menu
)

echo Unknown command: %1
echo Available commands: install, uninstall, start, stop, status, restart, menu
exit /b 1

:show_menu
echo Choose an option:
echo 1. Install service
echo 2. Uninstall service
echo 3. Start service
echo 4. Stop service
echo 5. Check service status
echo 6. Restart service
echo 7. Exit
echo.

set /p option="Enter option (1-7): "

IF "%option%"=="1" call :install_service
IF "%option%"=="2" call :uninstall_service
IF "%option%"=="3" call :start_service
IF "%option%"=="4" call :stop_service
IF "%option%"=="5" call :check_status
IF "%option%"=="6" call :restart_service
IF "%option%"=="7" exit /b 0

goto :show_menu

:install_service
echo Installing service...
"%PYTHON_EXE%" "%SERVICE_SCRIPT%" install
IF %ERRORLEVEL% NEQ 0 (
    echo ERROR: Failed to install service
) ELSE (
    echo Service installed successfully
)
goto :eof

:uninstall_service
echo Uninstalling service...
"%PYTHON_EXE%" "%SERVICE_SCRIPT%" remove
IF %ERRORLEVEL% NEQ 0 (
    echo ERROR: Failed to uninstall service
) ELSE (
    echo Service uninstalled successfully
)
goto :eof

:start_service
echo Starting service...
"%PYTHON_EXE%" "%SERVICE_SCRIPT%" start
IF %ERRORLEVEL% NEQ 0 (
    echo ERROR: Failed to start service
) ELSE (
    echo Service started successfully
)
goto :eof

:stop_service
echo Stopping service...
"%PYTHON_EXE%" "%SERVICE_SCRIPT%" stop
IF %ERRORLEVEL% NEQ 0 (
    echo ERROR: Failed to stop service
) ELSE (
    echo Service stopped successfully
)
goto :eof

:check_status
echo Checking service status...
"%PYTHON_EXE%" "%SERVICE_SCRIPT%" status
goto :eof

:restart_service
echo Restarting service...
call :stop_service
timeout /t 5 /nobreak
call :start_service
goto :eof

ENDLOCAL