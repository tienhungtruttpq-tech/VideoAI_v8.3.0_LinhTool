"""
Better approach: Instead of making functions return NULL (which crashes callers),
find and patch the actual kill mechanism.

The _fz878ct function uses ctypes to call TerminateProcess.
Since the strings are compressed (CYTHON_COMPRESS_STRINGS), the function
likely decompresses them at runtime.

Alternative strategy: Patch the PE import of TerminateProcess to point to
a harmless function. Even if ctypes resolves it, the actual function at
that address won't kill the process.

Wait - ctypes resolves from kernel32.dll directly, not from our import table.
So patching our IAT won't help for ctypes.

NEW STRATEGY: Instead of patching the .pyd file, create a hook that 
intercepts the ctypes resolution at the Python level.
We'll create a wrapper main.py that hooks ctypes before importing the module.
"""
import sys, os, traceback, types, importlib, importlib.util

sys.path.insert(0, '.')
os.environ['QT_QPA_PLATFORM_PLUGIN_PATH'] = r'C:\qt5_plugins\platforms'

# ====== STRATEGY: Hook ctypes BEFORE module load ======

import ctypes
import ctypes.wintypes

# Save original ctypes.WINFUNCTYPE and ctypes.CFUNCTYPE
_orig_WINFUNCTYPE = ctypes.WINFUNCTYPE
_orig_CFUNCTYPE = ctypes.CFUNCTYPE

# Track function type creations for debugging
created_functypes = []

def hooked_WINFUNCTYPE(restype, *argtypes, **kwargs):
    """Intercept WINFUNCTYPE creation"""
    ft = _orig_WINFUNCTYPE(restype, *argtypes, **kwargs)
    created_functypes.append(('WINFUNCTYPE', restype, argtypes, ft))
    
    # Wrap the functype so that when it's called with an address,
    # we can intercept the call
    original_ft = ft
    class SafeFuncType(ft):
        def __init__(self, *args, **kw):
            super().__init__(*args, **kw)
        def __call__(self, *args, **kw):
            # Check if this looks like a TerminateProcess call
            # TerminateProcess(HANDLE, UINT) 
            print(f"[HOOK] WINFUNCTYPE called with args: {args}", flush=True)
            return 0  # Return success without actually calling
    
    return ft  # Don't use SafeFuncType yet, just debug first

ctypes.WINFUNCTYPE = hooked_WINFUNCTYPE

def hooked_CFUNCTYPE(restype, *argtypes, **kwargs):
    """Intercept CFUNCTYPE creation"""
    ft = _orig_CFUNCTYPE(restype, *argtypes, **kwargs)
    created_functypes.append(('CFUNCTYPE', restype, argtypes, ft))
    return ft

ctypes.CFUNCTYPE = hooked_CFUNCTYPE

# Also hook kernel32 attribute access to intercept GetProcAddress-like calls
# In Python ctypes, kernel32.TerminateProcess resolves the function
_orig_windll_kernel32 = ctypes.windll.kernel32

class HookedKernel32:
    """Proxy for kernel32 that intercepts dangerous function lookups"""
    def __getattr__(self, name):
        if name in ('TerminateProcess', 'ExitProcess'):
            print(f"[HOOK] Intercepted kernel32.{name} lookup!", flush=True)
            # Return the address of a harmless function instead
            return getattr(_orig_windll_kernel32, 'GetCurrentThread')
        return getattr(_orig_windll_kernel32, name)

# Replace kernel32 in windll
ctypes.windll.kernel32 = HookedKernel32()

# Also hook msvcrt._exit and _cexit
try:
    _orig_cdll_msvcrt = ctypes.cdll.msvcrt
    class HookedMsvcrt:
        def __getattr__(self, name):
            if name in ('_exit', 'exit', '_Exit', 'abort', '_cexit'):
                print(f"[HOOK] Intercepted msvcrt.{name} lookup!", flush=True)
                return getattr(_orig_windll_kernel32, 'GetCurrentThread')
            return getattr(_orig_cdll_msvcrt, name)
    ctypes.cdll.msvcrt = HookedMsvcrt()
except:
    pass

# Also intercept os._exit
_orig_os_exit = os._exit
def safe_os_exit(code=0):
    print(f"[HOOK] os._exit({code}) intercepted!", flush=True)
    traceback.print_stack()
    # Don't actually exit
os._exit = safe_os_exit

# Also intercept sys.exit
_orig_sys_exit = sys.exit
def safe_sys_exit(code=0):
    print(f"[HOOK] sys.exit({code}) intercepted!", flush=True)
    traceback.print_stack()
    raise SystemExit(code)
sys.exit = safe_sys_exit

print("Hooks installed. Now importing module...")

# Use the ORIGINAL (unpatched) .pyd
pyd_path = os.path.abspath(r"modules\app.cp313-win_amd64.pyd")
print(f"Loading: {pyd_path}")

try:
    # Set up modules package
    modules_pkg = types.ModuleType('modules')
    modules_pkg.__path__ = [os.path.abspath('modules')]
    modules_pkg.__package__ = 'modules'
    sys.modules['modules'] = modules_pkg
    
    spec = importlib.util.spec_from_file_location(
        "modules.app",
        pyd_path,
        submodule_search_locations=[os.path.abspath('modules')]
    )
    mod = importlib.util.module_from_spec(spec)
    sys.modules['modules.app'] = mod
    
    spec.loader.exec_module(mod)
    
    print(f"\nSUCCESS! Module loaded!")
    print(f"dir(mod) = {dir(mod)}")
    
except SystemExit as e:
    print(f"SystemExit caught: {e}")
except Exception as e:
    print(f"Exception: {traceback.format_exc()}")

print(f"\nCreated function types: {len(created_functypes)}")
for ft_type, restype, argtypes, ft in created_functypes:
    print(f"  {ft_type}({restype}, {argtypes})")

print("\nDone!")
