@echo off
echo Reverting to original .pyd files...
call venv\Scripts\activate
python setup_noauth.py --revert
pause
