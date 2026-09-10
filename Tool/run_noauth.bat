@echo off
call venv\Scripts\activate
set QT_QPA_PLATFORM_PLUGIN_PATH=C:\qt5_plugins\platforms
python main.py
pause
