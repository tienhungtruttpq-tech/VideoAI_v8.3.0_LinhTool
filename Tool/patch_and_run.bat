@echo off
echo ============================================
echo  VideoAI v8.3.0 - Author Recovery Setup
echo  Replaces locked .pyd with clean .py sources
echo ============================================
echo.

call venv\Scripts\activate

echo Step 1: Disabling machine-locked .pyd modules...
python setup_noauth.py
if errorlevel 1 (
    echo.
    echo ERROR: Setup failed!
    pause
    exit /b 1
)

echo.
echo Step 2: Launching app...
set QT_QPA_PLATFORM_PLUGIN_PATH=C:\qt5_plugins\platforms
python main.py
pause
