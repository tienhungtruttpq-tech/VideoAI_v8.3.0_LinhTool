"""
Reconstructed app module - replaces the machine-locked app.pyd.
Author recovery after source code loss.

This module provides AuthScreen (bypassed) and MainApp classes,
connecting to the existing unprotected sub-modules.
"""
import sys
import os
import asyncio

from PyQt5.QtWidgets import (
    QMainWindow, QTabWidget, QWidget, QVBoxLayout, QHBoxLayout,
    QDockWidget, QApplication, QLabel, QMenuBar, QAction,
    QStatusBar, QMessageBox, QSplitter
)
from PyQt5.QtCore import Qt, QTimer


class AuthScreen(QWidget):
    """Bypassed auth screen - goes directly to MainApp."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.machine_id = "local"
        self.license_key = "local"

    async def boot(self):
        app_window = MainApp()
        await app_window.boot()
        app_window.show()
        self.close()
        return app_window


class MainApp(QMainWindow):
    """Main application window with tabs for each AI video service."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.tabs = {}
        self.tab_widget = None
        self.merge_dock = None
        self._services = None
        self._queue_managers = {}

    async def boot(self):
        self._setup_window()
        self._setup_tabs()
        self._setup_merge_video_dock()
        self._setup_menu()
        await self._init_services()

    def _setup_window(self):
        self.setWindowTitle("VideoAI v8.3.0")
        self.resize(1400, 900)
        self.tab_widget = QTabWidget()
        self.setCentralWidget(self.tab_widget)
        self.statusBar().showMessage("Ready")

    def _setup_tabs(self):
        tab_configs = []

        try:
            from modules.veo3.frontend.main.veo3_text_to_video_tab import TextToVideoTab as Veo3T2V
            tab_configs.append(("Veo3 Text→Video", Veo3T2V))
        except ImportError as e:
            print(f"[WARN] Veo3 T2V not loaded: {e}")

        try:
            from modules.veo3.frontend.main.veo3_image_to_video_tab import ImageToVideoTab as Veo3I2V
            tab_configs.append(("Veo3 Image→Video", Veo3I2V))
        except ImportError as e:
            print(f"[WARN] Veo3 I2V not loaded: {e}")

        try:
            from modules.veo3.frontend.main.veo3_text_image_to_image_tab import TextImageToImageTab as Veo3TI2I
            tab_configs.append(("Veo3 Text→Image", Veo3TI2I))
        except ImportError as e:
            print(f"[WARN] Veo3 TI2I not loaded: {e}")

        try:
            from modules.veo3.frontend.main.veo3_reference_to_video_tab import ReferenceToVideoTab as Veo3Ref
            tab_configs.append(("Veo3 Ref→Video", Veo3Ref))
        except ImportError as e:
            print(f"[WARN] Veo3 Ref not loaded: {e}")

        try:
            from modules.veo3.frontend.main.veo3_start_end_to_video_tab import StartEndToVideoTab as Veo3SE
            tab_configs.append(("Veo3 Start/End", Veo3SE))
        except ImportError as e:
            print(f"[WARN] Veo3 SE not loaded: {e}")

        try:
            from modules.sora2.frontend.main.sora2_text_image_to_video_tab import TextImageToVideoTab as Sora2Tab
            tab_configs.append(("Sora2", Sora2Tab))
        except ImportError as e:
            print(f"[WARN] Sora2 not loaded: {e}")

        try:
            from modules.grok.frontend.main.grok_text_image_to_video_tab import GrokTextImageToVideoTab as GrokTab
            tab_configs.append(("Grok", GrokTab))
        except ImportError as e:
            print(f"[WARN] Grok not loaded: {e}")

        try:
            from modules.seedance.frontend.main.seedance_text_image_to_video_tab import SeedanceTextImageToVideoTab as SeedanceTab
            tab_configs.append(("Seedance", SeedanceTab))
        except ImportError as e:
            print(f"[WARN] Seedance not loaded: {e}")

        for name, TabClass in tab_configs:
            try:
                tab = TabClass()
                self.tab_widget.addTab(tab, name)
                self.tabs[name] = tab
            except Exception as e:
                print(f"[ERROR] Failed to create tab '{name}': {e}")
                placeholder = QWidget()
                layout = QVBoxLayout(placeholder)
                layout.addWidget(QLabel(f"Failed to load: {e}"))
                self.tab_widget.addTab(placeholder, f"{name} (error)")

    def _setup_merge_video_dock(self):
        try:
            from modules.utils.merge_video_sidebar import MergeVideoSidebarWidget
            sidebar = MergeVideoSidebarWidget()
            self.merge_dock = QDockWidget("Merge Video", self)
            self.merge_dock.setWidget(sidebar)
            self.merge_dock.setAllowedAreas(Qt.RightDockWidgetArea | Qt.LeftDockWidgetArea)
            self.addDockWidget(Qt.RightDockWidgetArea, self.merge_dock)
            self.merge_dock.setVisible(False)
        except Exception as e:
            print(f"[WARN] Merge video sidebar not loaded: {e}")

    def _toggle_merge_video_dock(self):
        if self.merge_dock:
            self.merge_dock.setVisible(not self.merge_dock.isVisible())

    def _setup_menu(self):
        menubar = self.menuBar()

        view_menu = menubar.addMenu("View")
        toggle_merge = QAction("Toggle Merge Video", self)
        toggle_merge.triggered.connect(self._toggle_merge_video_dock)
        view_menu.addAction(toggle_merge)

        settings_menu = menubar.addMenu("Settings")

        providers = [
            ("Veo3", "modules.veo3.frontend.settings.settings_dialog", "SettingsDialog"),
            ("Sora2", "modules.sora2.frontend.settings.settings_dialog", "SettingsDialog"),
            ("Grok", "modules.grok.frontend.settings.settings_dialog", "SettingsDialog"),
            ("Seedance", "modules.seedance.frontend.settings.settings_dialog", "SettingsDialog"),
        ]
        for provider_name, mod_path, cls_name in providers:
            action = QAction(f"{provider_name} Settings...", self)
            action.setData((mod_path, cls_name))
            action.triggered.connect(lambda checked, mp=mod_path, cn=cls_name: self._open_settings(mp, cn))
            settings_menu.addAction(action)

        settings_menu.addSeparator()

        cred_providers = [
            ("Veo3", "modules.veo3.frontend.settings.credentials_dialog", "CredentialsDialog"),
            ("Sora2", "modules.sora2.frontend.settings.credentials_dialog", "CredentialsDialog"),
            ("Grok", "modules.grok.frontend.settings.credentials_dialog", "CredentialsDialog"),
            ("Seedance", "modules.seedance.frontend.settings.credentials_dialog", "CredentialsDialog"),
        ]
        for provider_name, mod_path, cls_name in cred_providers:
            action = QAction(f"{provider_name} Credentials...", self)
            action.triggered.connect(lambda checked, mp=mod_path, cn=cls_name: self._open_settings(mp, cn))
            settings_menu.addAction(action)

    def _open_settings(self, module_path, class_name):
        try:
            import importlib
            mod = importlib.import_module(module_path)
            dialog_cls = getattr(mod, class_name)
            dialog = dialog_cls(self)
            dialog.exec_()
        except Exception as e:
            QMessageBox.warning(self, "Error", f"Cannot open settings: {e}")

    async def _init_services(self):
        try:
            from modules.services import AppServices
            self._services = AppServices()
            await self._services.initialize()
        except Exception as e:
            print(f"[WARN] Services init failed: {e}")

        for name, tab in self.tabs.items():
            try:
                if hasattr(tab, "boot"):
                    result = tab.boot()
                    if asyncio.iscoroutine(result):
                        await result
            except Exception as e:
                print(f"[WARN] Tab '{name}' boot failed: {e}")

    def afe(self):
        pass

    def closeEvent(self, event):
        if self._services and hasattr(self._services, "shutdown"):
            try:
                loop = asyncio.get_event_loop()
                if loop.is_running():
                    asyncio.ensure_future(self._services.shutdown())
                else:
                    loop.run_until_complete(self._services.shutdown())
            except Exception:
                pass
        event.accept()
