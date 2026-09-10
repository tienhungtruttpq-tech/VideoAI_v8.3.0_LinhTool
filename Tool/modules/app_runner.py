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

    app = QApplication(sys.argv)

    loop = qasync.QEventLoop(app)
    asyncio.set_event_loop(loop)

    async def main_async():
        from modules.app import AuthScreen
        auth = AuthScreen()
        main_window = await auth.boot()
        return main_window

    with loop:
        loop.run_until_complete(main_async())
        loop.run_forever()

    return 0
