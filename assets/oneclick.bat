@echo off
chcp 65001 >nul
cd /d "%~dp0"
set PYTHONIOENCODING=utf-8
set PYTHONUTF8=1

echo ============================================
echo  WeLearn Auto Runner
echo ============================================

if not exist "..\scripts\wl_run.py" (
  echo [ERROR] scripts\wl_run.py not found
  echo         run this bat from the assets folder of the repo
  pause
  exit /b 1
)

if not exist "wl_config.json" (
  echo [ERROR] wl_config.json not found in assets
  pause
  exit /b 1
)

python -c "import websocket, requests" 2>nul
if errorlevel 1 (
  echo [INFO] installing deps...
  python -m pip install websocket-client requests
)

echo [1/3] checking debug port...
python -c "import requests;requests.get('http://127.0.0.1:9224/json/version',timeout=3)" 2>nul
if errorlevel 1 (
  echo [WARN] port 9224 offline
  echo        msedge.exe --remote-debugging-port=9224 --user-data-dir=PROFILE --remote-allow-origins=*
  echo.
)

echo [2/3] scanning catalog...
pushd ..\scripts
python wl_run.py --scan
if errorlevel 1 (
  echo [ERROR] scan failed
  popd
  pause
  exit /b 1
)

echo.
echo [3/3] running...
python wl_run.py
popd

echo.
echo ============================================
echo  done. log: scripts\wl_run_log.json
echo ============================================
pause