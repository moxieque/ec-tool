@echo off
REM EC Sales Management Tool - Windows Startup with logging
setlocal enabledelayedexpansion

set "LOGFILE=%CD%\startup.log"

REM Clear old log
if exist "!LOGFILE!" del "!LOGFILE!"

REM Function to log and display
setlocal enabledelayedexpansion
goto :main

:log_and_display
echo %~1
echo %~1 >> "!LOGFILE!"
goto :eof

:log_error
echo.
echo ================================================
echo   %~1
echo ================================================
echo.
echo %~1 >> "!LOGFILE!"
goto :eof

:main
cls
(
  echo.
  echo ================================================
  echo   EC Sales Management Tool
  echo ================================================
  echo.
  echo Starting... check startup.log for details
  echo.
) >> "!LOGFILE!"

REM Log start
(
  echo ================================================
  echo EC Sales Management Tool - Startup Log
  echo Date: %DATE% %TIME%
  echo ================================================
  echo.
) >> "!LOGFILE!"

REM Check Python
echo [1/4] Checking Python... >> "!LOGFILE!"
set "PYTHON_CMD="

python --version >nul 2>&1
if !errorlevel! equ 0 (
  for /f "tokens=*" %%i in ('python --version 2^>^&1') do (
    set "PYTHON_VER=%%i"
    echo   OK: !PYTHON_VER! >> "!LOGFILE!"
  )
  set "PYTHON_CMD=python"
) else (
  python3 --version >nul 2>&1
  if !errorlevel! equ 0 (
    for /f "tokens=*" %%i in ('python3 --version 2^>^&1') do (
      set "PYTHON_VER=%%i"
      echo   OK: !PYTHON_VER! >> "!LOGFILE!"
    )
    set "PYTHON_CMD=python3"
  ) else (
    (
      echo.
      echo [ERROR] Python3 is NOT installed!
      echo.
      echo Please install Python:
      echo 1. Go to https://www.python.org/downloads/
      echo 2. Download and run the installer
      echo 3. IMPORTANT: CHECK "Add Python to PATH" during setup
      echo 4. Restart your computer
      echo 5. Try Start.bat again
      echo.
      echo Log file: !LOGFILE!
      echo.
    ) >> "!LOGFILE!"

    cls
    echo.
    echo ================================================
    echo   [ERROR] Python3 is NOT installed
    echo ================================================
    echo.
    echo Please install Python from:
    echo   https://www.python.org/downloads/
    echo.
    echo IMPORTANT STEP:
    echo   During installation, CHECK "Add Python to PATH"
    echo.
    echo After installing, restart your computer and
    echo try Start.bat again.
    echo.
    echo Log file has been created:
    echo   !LOGFILE!
    echo.
    pause
    exit /b 1
  )
)

REM Check app.py
echo [2/4] Checking app.py... >> "!LOGFILE!"
if not exist "app.py" (
  (
    echo   ERROR: app.py not found in !CD!
    echo.
    echo [ERROR] File app.py is missing
    echo.
    echo Please make sure:
    echo 1. Zaikore-windows.zip was completely extracted
    echo 2. You are in the correct Zaikore folder
    echo 3. app.py file exists in this folder
    echo.
  ) >> "!LOGFILE!"

  cls
  echo.
  echo ================================================
  echo   [ERROR] File app.py not found
  echo ================================================
  echo.
  echo Current location: !CD!
  echo.
  echo Please make sure:
    echo   1. Zaikore-windows.zip is completely extracted
  echo   2. You are running Start.bat from the Zaikore folder
  echo   3. Check that app.py exists in this folder
  echo.
  pause
  exit /b 1
)
echo   OK: app.py found >> "!LOGFILE!"

REM Check libraries
echo [3/4] Checking libraries... >> "!LOGFILE!"
!PYTHON_CMD! -m pip show flask >nul 2>&1
if !errorlevel! equ 0 (
  echo   OK: Libraries installed >> "!LOGFILE!"
) else (
  echo   INFO: Installing libraries... >> "!LOGFILE!"
  !PYTHON_CMD! -m pip install flask flask-cors playwright --quiet --disable-pip-version-check 2>> "!LOGFILE!"

  if !errorlevel! neq 0 (
    (
      echo.
      echo [ERROR] Failed to install libraries
      echo Please check internet connection and try again
      echo.
    ) >> "!LOGFILE!"

    cls
    echo.
    echo ================================================
    echo   [ERROR] Library installation failed
    echo ================================================
    echo.
    echo Please check:
      echo   1. Internet connection is working
    echo   2. Run as Administrator
    echo   3. Try again
    echo.
    pause
    exit /b 1
  )
  echo   OK: Libraries installed >> "!LOGFILE!"
)

REM Start server
echo [4/4] Starting server... >> "!LOGFILE!"
echo   Opening http://localhost:8080 >> "!LOGFILE!"

(
  echo.
  echo ================================================
  echo Server is starting...
  echo Opening: http://localhost:8080
  echo Press Ctrl+C to stop the server
  echo ================================================
  echo.
) >> "!LOGFILE!"

echo.
echo Starting server...
echo Browser should open automatically
echo.

timeout /t 2 /nobreak >nul
start http://localhost:8080

!PYTHON_CMD! app.py 2>> "!LOGFILE!"

(
  echo.
  echo ================================================
  echo Server stopped
  echo ================================================
) >> "!LOGFILE!"

echo.
echo ================================================
echo   Server stopped
echo ================================================
echo.
echo Log file: !LOGFILE!
echo.
pause
