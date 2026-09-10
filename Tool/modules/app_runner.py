"""
Reconstructed app_runner module - replaces the compiled app_runner.pyd.
Launches the application with qasync event loop.
"""
import sys
import os
import asyncio
import traceback


def run():
    try:
        from PyQt5.QtWidgets import QApplication
        import qasync

        app = QApplication(sys.argv)

        loop = qasync.QEventLoop(app)
        asyncio.set_event_loop(loop)

        main_window = None

        async def main_async():
            nonlocal main_window
            from modules.app import AuthScreen
            auth = AuthScreen()
            main_window = await auth.boot()
            return main_window

        with loop:
            loop.run_until_complete(main_async())
            if main_window is not None:
                loop.run_forever()

    except Exception as e:
        print(f"\n[FATAL ERROR] {e}")
        traceback.print_exc()
        input("\nPress Enter to exit...")
        return 1

    return 0
