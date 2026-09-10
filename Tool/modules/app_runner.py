"""
Reconstructed app_runner module - replaces the compiled app_runner.pyd.
Launches the application with qasync event loop.
"""
import sys
import os
import asyncio


def run():
    from PyQt5.QtWidgets import QApplication
    import qasync

    print("[app_runner] Starting...")
    app = QApplication(sys.argv)

    loop = qasync.QEventLoop(app)
    asyncio.set_event_loop(loop)

    main_window = None

    async def main_async():
        nonlocal main_window
        print("[app_runner] Importing app module...")
        from modules.app import AuthScreen
        print("[app_runner] Creating AuthScreen...")
        auth = AuthScreen()
        print("[app_runner] Booting...")
        main_window = await auth.boot()
        print(f"[app_runner] Boot complete, window={main_window}")
        return main_window

    try:
        with loop:
            loop.run_until_complete(main_async())
            if main_window is not None:
                print("[app_runner] Entering event loop...")
                loop.run_forever()
            else:
                print("[app_runner] ERROR: main_window is None")
    except Exception as e:
        print(f"[app_runner] FATAL: {e}")
        import traceback
        traceback.print_exc()

    return 0
