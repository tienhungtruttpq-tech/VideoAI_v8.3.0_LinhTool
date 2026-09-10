"""Test importing the patched app module"""
import sys, os, traceback, faulthandler, importlib.util

faulthandler.enable()

log_file = open('test_import_log.txt', 'w', encoding='utf-8')

def log(msg):
    log_file.write(str(msg) + '\n')
    log_file.flush()
    print(msg, flush=True)

sys.path.insert(0, '.')
os.environ['QT_QPA_PLATFORM_PLUGIN_PATH'] = r'C:\qt5_plugins\platforms'

# Intercept os._exit
original_os_exit = os._exit
def fake_os_exit(code=0):
    log(f"os._exit called with code: {code}")
    import io
    f = io.StringIO()
    traceback.print_stack(file=f)
    log(f.getvalue())
    log_file.close()
    original_os_exit(code)
os._exit = fake_os_exit

patched_pyd = os.path.abspath(r"modules\app.cp313-win_amd64_patched.pyd")
log(f"Loading patched PYD: {patched_pyd}")

try:
    # Create a proper package structure
    import types
    modules_pkg = types.ModuleType('modules')
    modules_pkg.__path__ = [os.path.abspath('modules')]
    modules_pkg.__package__ = 'modules'
    sys.modules['modules'] = modules_pkg
    
    spec = importlib.util.spec_from_file_location(
        "modules.app",
        patched_pyd,
        submodule_search_locations=[os.path.abspath('modules')]
    )
    log(f"Spec: {spec}")
    
    mod = importlib.util.module_from_spec(spec)
    sys.modules['modules.app'] = mod
    
    log("Executing module...")
    spec.loader.exec_module(mod)
    log(f"SUCCESS! Module loaded!")
    log(f"dir(mod) = {dir(mod)}")
    
    # Check for AuthScreen and MainApp
    if hasattr(mod, 'AuthScreen'):
        log(f"AuthScreen: {mod.AuthScreen}")
    if hasattr(mod, 'MainApp'):
        log(f"MainApp: {mod.MainApp}")
        
except SystemExit as e:
    log(f"SystemExit: {e}")
except Exception as e:
    log(f"Exception: {traceback.format_exc()}")

log("Script completed")
log_file.close()
