@echo off
setlocal
cd /d "%~dp0"
if not exist ".venv\Scripts\python.exe" (
  py -3 -m venv .venv
  if errorlevel 1 (
    echo Could not create virtual environment.
    pause
    exit /b 1
  )
)
call ".venv\Scripts\activate.bat"
python -m pip install --upgrade pip
pip install -r requirements.txt
if errorlevel 1 (
  echo Dependency installation failed.
  pause
  exit /b 1
)
python preflight.py
if errorlevel 1 (
  echo Preflight failed.
  pause
  exit /b 1
)
streamlit run app\ui\dashboard.py
pause
