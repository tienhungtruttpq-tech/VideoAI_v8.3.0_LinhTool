"""
Wrapper launcher that bypasses machine authentication.
Run this instead of main.py after applying the binary patch.

This provides runtime-level protection as a safety net:
1. Monkey-patches machineid to return a consistent ID
2. Intercepts process termination calls
3. Then launches the app normally
"""
import sys
import os
import types
import importlib

# ============================================================
# STEP 1: Monkey-patch machineid module BEFORE any app imports
# ============================================================
FIXED_MACHINE_ID = "00000000-0000-0000-0000-000000000000"

fake_machineid = types.ModuleType("machineid")
fake_machineid.id = lambda winregistry=True: FIXED_MACHINE_ID
fake_machineid.hashed_id = lambda app_id="", winregistry=True: FIXED_MACHINE_ID
sys.modules["machineid"] = fake_machineid
sys.modules["py_machineid"] = fake_machineid

# ============================================================
# STEP 2: Intercept os._exit to prevent forced termination
# ============================================================
_real_os_exit = os._exit

def _safe_os_exit(code=0):
    if code != 0:
        print(f"[NoAuth] Blocked os._exit({code}) - auth kill prevented", flush=True)
        return
    _real_os_exit(code)

os._exit = _safe_os_exit

# ============================================================
# STEP 3: Intercept ctypes-based TerminateProcess (if used)
# ============================================================
try:
    import ctypes
    if hasattr(ctypes, "windll"):
        _real_kernel32 = ctypes.windll.kernel32

        class _SafeKernel32:
            def __getattr__(self, name):
                if name in ("TerminateProcess", "ExitProcess"):
                    return lambda *a, **kw: 1
                return getattr(_real_kernel32, name)

        ctypes.windll.kernel32 = _SafeKernel32()

        try:
            _real_msvcrt = ctypes.cdll.msvcrt

            class _SafeMsvcrt:
                def __getattr__(self, name):
                    if name in ("_exit", "exit", "_Exit", "abort"):
                        return lambda *a, **kw: None
                    return getattr(_real_msvcrt, name)

            ctypes.cdll.msvcrt = _SafeMsvcrt()
        except Exception:
            pass
except ImportError:
    pass

# ============================================================
# STEP 4: Launch the app
# ============================================================
from modules.app_runner import run

if __name__ == "__main__":
    sys.exit(run())
