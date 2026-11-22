@echo off
setlocal enabledelayedexpansion

title Project Kaalu GUI Launcher
cd /d "%~dp0"

echo ============================================================
echo           STARTING PROJECT KAALU GUI SYSTEM
echo ============================================================
echo.

:: 1. Check Python Virtual Environment
set "PYTHON_EXE=%~dp0.venv\Scripts\python.exe"
if not exist "%PYTHON_EXE%" (
    echo [ERROR] Virtual environment not found at:
    echo         "%~dp0.venv"
    echo Please create the virtual environment and install dependencies:
    echo         python -m venv .venv
    echo         .venv\Scripts\pip install -r requirements.txt
    echo.
    pause
    exit /b 1
)

:: 2. Set PYTHONPATH to central_communication_system and flag GUI Mode
set "PROJECT_DIR=%~dp0central_communication_system"
set "PYTHONPATH=%PROJECT_DIR%"
set "KAALU_GUI_MODE=1"

:: Check for Administrator privileges
net session >nul 2>&1
if %errorLevel% == 0 (
    echo [Privilege] Running with Administrator privileges - full process control enabled.
) else (
    echo [Privilege] Running as Standard User.
    echo Tip: Run as Administrator to allow closing elevated apps like Task Manager.
)
echo.

echo [1/3] Launching RGS Central Hub (Port 8000)...
start "RGS Central Hub" cmd /k "title RGS Central Hub && cd /d "%PROJECT_DIR%" && set "PYTHONPATH=%PROJECT_DIR%" && set "KAALU_GUI_MODE=1" && "%PYTHON_EXE%" -m uvicorn rgs_hub.main:app --host 127.0.0.1 --port 8000 --reload"

:: Brief delay to allow FastAPI / WebSocket server to bind port 8000
echo Waiting for RGS Hub to initialize...
timeout /t 3 /nobreak >nul

echo [2/3] Launching Faulkner System Agent...
start "Faulkner System Agent" cmd /k "title Faulkner System Agent && cd /d "%PROJECT_DIR%" && set "PYTHONPATH=%PROJECT_DIR%" && "%PYTHON_EXE%" -m faulkner_system.agent_runner"

:: 3. Inform about David Browser Agent
echo.
echo ============================================================
echo [Notice] David Browser Agent (Chrome Extension):
echo   1. Open Google Chrome and navigate to: chrome://extensions
echo   2. Enable "Developer mode" in the top right.
echo   3. Click "Load unpacked" and select:
echo      "%PROJECT_DIR%\david_browser_agent"
echo ============================================================
echo.

:: 4. Start Kaalu Master Orchestrator in GUI Listener Mode
echo [3/3] Launching Kaalu Master Orchestrator (GUI Mode)...
start "Kaalu Orchestrator" cmd /k "title Kaalu Orchestrator (GUI) && cd /d "%PROJECT_DIR%" && set "PYTHONPATH=%PROJECT_DIR%" && set "KAALU_GUI_MODE=1" && "%PYTHON_EXE%" -m kaalu_orchestrator.agent_runner --gui"

:: 5. Locate Google Chrome for App Mode (fallback to default browser)
echo.
echo Launching Project Kaalu GUI Interface...
set "CHROME_EXE="
if exist "%ProgramFiles%\Google\Chrome\Application\chrome.exe" set "CHROME_EXE=%ProgramFiles%\Google\Chrome\Application\chrome.exe"
if not defined CHROME_EXE if exist "%ProgramFiles(x86)%\Google\Chrome\Application\chrome.exe" set "CHROME_EXE=%ProgramFiles(x86)%\Google\Chrome\Application\chrome.exe"
if not defined CHROME_EXE if exist "%LocalAppData%\Google\Chrome\Application\chrome.exe" set "CHROME_EXE=%LocalAppData%\Google\Chrome\Application\chrome.exe"

timeout /t 2 /nobreak >nul

if defined CHROME_EXE (
    echo Opening Kaalu GUI in Chrome App Mode...
    start "" "!CHROME_EXE!" --app=http://127.0.0.1:8000/gui
) else (
    echo Opening Kaalu GUI in default browser...
    start http://127.0.0.1:8000/gui
)

echo.
echo ============================================================
echo Project Kaalu GUI is running at: http://127.0.0.1:8000/gui
echo Tab 1: Live Editable Working Terminal
echo Tab 2: Hologram Video Avatar, Markdown Output, and Voice Ears
echo ============================================================
pause
