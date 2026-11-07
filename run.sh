#!/usr/bin/env sh
set -e
cd "$(dirname "$0")"
[ -d .venv ] || python3 -m venv .venv
. .venv/bin/activate
pip install -q -r requirements.txt
echo "Installing OCR packages for Smart KYC..."
pip install -q -r requirements-ocr.txt || echo "OCR packages could not be installed. KYC still works: install Tesseract, or customers type the details."
python make_env.py
echo "Customer app: http://127.0.0.1:8000    Back office: http://127.0.0.1:8000/backoffice"
exec python app.py
