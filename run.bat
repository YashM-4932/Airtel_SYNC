@echo off
setlocal
cd /d "%~dp0"
where py >nul 2>nul && (set "PY=py -3") || (set "PY=python")
if not exist .venv (
  echo Creating virtual environment...
  %PY% -m venv .venv || goto :error
)
call .venv\Scripts\activate.bat
python -m pip install --disable-pip-version-check -q -r requirements.txt || goto :error
echo Installing OCR packages for Smart KYC...
python -m pip install --disable-pip-version-check -q -r requirements-ocr.txt || echo OCR packages could not be installed. KYC still works: install Tesseract, or customers type the details.
python make_env.py
set PYTHONUTF8=1
echo.
echo Customer app:  http://127.0.0.1:8000
echo Back office:   http://127.0.0.1:8000/backoffice   (Ctrl+C to stop)
python app.py
goto :eof
:error
echo Setup failed. Install Python 3.10 or newer from python.org and tick "Add to PATH".
pause
