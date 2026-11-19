@echo off
setlocal enabledelayedexpansion

title Project Kaalu Launcher with Resume Builder
cd /d "%~dp0"

echo ============================================================
echo          STARTING RESUME BUILDER ^& PROJECT KAALU
echo ============================================================
echo.

:: 1. Locate and Launch Resume Builder (CareerForge AI)
set "RB_DIR="
if exist "%~dp0..\Resume_Builder_V2\notest_start.bat" set "RB_DIR=%~dp0..\Resume_Builder_V2"
if not defined RB_DIR if exist "%~dp0..\AI-Resume-Builder\notest_start.bat" set "RB_DIR=%~dp0..\AI-Resume-Builder"
if not defined RB_DIR if exist "%~dp0..\Resume-Builder\notest_start.bat" set "RB_DIR=%~dp0..\Resume-Builder"
if not defined RB_DIR if exist "%~dp0..\Resume_Builder_2\notest_start.bat" set "RB_DIR=%~dp0..\Resume_Builder_2"
if not defined RB_DIR if exist "%~dp0..\Resume_Builder_V2" set "RB_DIR=%~dp0..\Resume_Builder_V2"
if not defined RB_DIR if exist "%~dp0..\AI-Resume-Builder" set "RB_DIR=%~dp0..\AI-Resume-Builder"

if defined RB_DIR (
    echo [1/4] Launching Resume Builder from: "!RB_DIR!"...
    cmd /c "cd /d "!RB_DIR!" && call notest_start.bat"
    echo [OK] Resume Builder launch sequence initiated [Frontend: :5173, Backend: :8005].
) else (
    echo [WARN] Resume Builder directory not found in:
    echo        "%~dp0..\Resume_Builder_V2"
    echo Skipping Resume Builder startup.
)
echo.

:: Ensure working directory is restored to Project-Kaalu-V2
cd /d "%~dp0"

:: 2. Check Python Virtual Environment for Project Kaalu
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

:: 3. Set PYTHONPATH to central_communication_system
set "PROJECT_DIR=%~dp0central_communication_system"
set "PYTHONPATH=%PROJECT_DIR%"

:: Check for Administrator privileges
net session >nul 2>&1
if %errorLevel% == 0 (
    echo [Privilege] Running with Administrator privileges - full process control enabled.
) else (
    echo [Privilege] Running as Standard User.
    echo Tip: Run as Administrator to allow closing elevated apps like Task Manager.
)
echo.

echo [2/4] Launching RGS Central Hub (Port 8000)...
start "RGS Central Hub" cmd /k "title RGS Central Hub && cd /d "%PROJECT_DIR%" && set "PYTHONPATH=%PROJECT_DIR%" && "%PYTHON_EXE%" -m uvicorn rgs_hub.main:app --host 127.0.0.1 --port 8000 --reload"

:: Brief delay to allow FastAPI / WebSocket server to bind port 8000
echo Waiting for RGS Hub to initialize...
timeout /t 3 /nobreak >nul

echo [3/4] Launching Faulkner System Agent...
start "Faulkner System Agent" cmd /k "title Faulkner System Agent && cd /d "%PROJECT_DIR%" && set "PYTHONPATH=%PROJECT_DIR%" && "%PYTHON_EXE%" -m faulkner_system.agent_runner"

:: 4. Inform about David Browser Agent
echo.
echo ============================================================
echo [Notice] David Browser Agent (Chrome Extension):
echo   1. Open Google Chrome and navigate to: chrome://extensions
echo   2. Enable "Developer mode" in the top right.
echo   3. Click "Load unpacked" and select:
echo      "%PROJECT_DIR%\david_browser_agent"
echo ============================================================
echo.

:: 5. Start Kaalu Master Orchestrator in current console
echo [4/4] Launching Kaalu Master Orchestrator in this window...
title Kaalu Master Orchestrator
cd /d "%PROJECT_DIR%"
"%PYTHON_EXE%" -m kaalu_orchestrator.agent_runner

echo.
echo ============================================================
echo Kaalu Orchestrator session has ended.
echo ============================================================
pause
