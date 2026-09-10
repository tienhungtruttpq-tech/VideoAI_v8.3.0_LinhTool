
import sys, os, faulthandler, traceback

sys.stdout.reconfigure(encoding='utf-8')
sys.stderr.reconfigure(encoding='utf-8')

# Write to file since stdout may not flush
log = open('v6b_test_log.txt', 'w', encoding='utf-8')
def logprint(msg):
    log.write(str(msg) + '\n')
    log.flush()
    print(msg, flush=True)

faulthandler.enable(file=log, all_threads=True)

sys.path.insert(0, '.')
os.environ['QT_QPA_PLATFORM_PLUGIN_PATH'] = r'C:\qt5_plugins\platforms'

logprint("Starting import test...")

# Override sys.exit and os._exit at Python level
import builtins
original_exit = builtins.exit
def trap_exit(*args):
    logprint(f"builtins.exit called: {args}")
    traceback.print_stack(file=log)
    log.close()
    raise SystemExit(args[0] if args else 0)
builtins.exit = trap_exit

original_quit = builtins.quit
def trap_quit(*args):
    logprint(f"builtins.quit called: {args}")
    traceback.print_stack(file=log)
    log.close()
    raise SystemExit(args[0] if args else 0)
builtins.quit = trap_quit

# Override sys.exit
orig_sys_exit = sys.exit
def trap_sys_exit(code=0):
    logprint(f"sys.exit({code}) called!")
    traceback.print_stack(file=log)
    log.close()
    raise SystemExit(code)
sys.exit = trap_sys_exit

# Override os._exit
orig_os_exit = os._exit  
def trap_os_exit(code=0):
    logprint(f"os._exit({code}) called!")
    traceback.print_stack(file=log)
    log.close()
    orig_os_exit(code)
os._exit = trap_os_exit

import atexit
def on_atexit():
    with open('v6b_atexit.txt', 'w', encoding='utf-8') as f:
        f.write('atexit triggered\n')
        traceback.print_stack(file=f)
atexit.register(on_atexit)

logprint("Hooks installed, importing...")

try:
    import importlib.util, types
    
    modules_pkg = types.ModuleType('modules')
    modules_pkg.__path__ = [os.path.abspath('modules')]
    modules_pkg.__package__ = 'modules'
    sys.modules['modules'] = modules_pkg
    
    pyd_path = os.path.abspath(r"modules\app.cp313-win_amd64_patched_v6b.pyd")
    logprint(f"PYD: {pyd_path}")
    
    spec = importlib.util.spec_from_file_location(
        "modules.app",
        pyd_path,
        submodule_search_locations=[os.path.abspath('modules')]
    )
    mod = importlib.util.module_from_spec(spec)
    sys.modules['modules.app'] = mod
    
    logprint("Calling exec_module...")
    spec.loader.exec_module(mod)
    
    logprint("SUCCESS!")
    logprint(f"dir(mod) = {dir(mod)}")
    
except SystemExit as e:
    logprint(f"SystemExit caught: {e}")
except BaseException as e:
    logprint(f"BaseException: {type(e).__name__}: {e}")
    traceback.print_exc(file=log)

logprint("Script end")
log.close()
