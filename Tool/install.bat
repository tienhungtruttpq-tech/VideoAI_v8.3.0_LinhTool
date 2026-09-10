@echo off
echo Installing dependencies...
py -3.13 -m venv venv
call venv\Scripts\activate
python -m pip install --upgrade pip
pip install -r requirements.txt
echo.
echo Installation complete! Run: run.bat
pause
