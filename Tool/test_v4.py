import sys, os, traceback, faulthandler, importlib.util, types

faulthandler.enable()
sys.path.insert(0, '.')
os.environ['QT_QPA_PLATFORM_PLUGIN_PATH'] = r'C:\qt5_plugins\platforms'

pyd_path = os.path.abspath(r"modules\app.cp313-win_amd64_patched_v4.pyd")
print(f"Loading: {pyd_path}")

try:
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
    
    print("Executing module...")
    spec.loader.exec_module(mod)
    
    print(f"\nSUCCESS!")
    print(f"dir(mod) = {dir(mod)}")
    
    if hasattr(mod, 'AuthScreen'):
        print(f"AuthScreen: {mod.AuthScreen}")
    if hasattr(mod, 'MainApp'):
        print(f"MainApp: {mod.MainApp}")
        
except SystemExit as e:
    print(f"SystemExit: {e}")
except Exception as e:
    print(f"Exception: {traceback.format_exc()}")

print("Script completed")
