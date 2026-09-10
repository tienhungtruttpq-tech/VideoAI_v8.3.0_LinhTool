@echo off
echo ============================================
echo  VideoAI v8.3.0 - Machine Auth Removal Tool
echo  Author recovery after hard drive failure
echo ============================================
echo.

call venv\Scripts\activate

echo Step 1: Applying binary patch...
python patch_remove_machine_auth.py
if errorlevel 1 (
    echo.
    echo ERROR: Patch failed! Check the output above.
    pause
    exit /b 1
)

echo.
echo Step 2: Launching app with runtime protection...
set QT_QPA_PLATFORM_PLUGIN_PATH=C:\qt5_plugins\platforms
python main_noauth.py
pause
