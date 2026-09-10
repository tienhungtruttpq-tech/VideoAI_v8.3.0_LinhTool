"""
Setup script: Disable machine-locked .pyd modules so Python loads
the reconstructed .py source files instead.

On Windows, Python prefers .pyd over .py for the same module name.
This script renames the locked .pyd files so the clean .py files load.

Usage: python setup_noauth.py
To revert: python setup_noauth.py --revert
"""
import os
import sys
import shutil

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
MODULES_DIR = os.path.join(SCRIPT_DIR, "modules")

LOCKED_FILES = [
    "app.cp313-win_amd64.pyd",
    "app_runner.cp313-win_amd64.pyd",
]

BACKUP_SUFFIX = ".locked_backup"


def setup():
    print("=== Disabling machine-locked .pyd modules ===\n")
    for filename in LOCKED_FILES:
        pyd_path = os.path.join(MODULES_DIR, filename)
        backup_path = pyd_path + BACKUP_SUFFIX

        if not os.path.exists(pyd_path):
            if os.path.exists(backup_path):
                print(f"  [OK] {filename} already disabled (backup exists)")
            else:
                print(f"  [SKIP] {filename} not found")
            continue

        # Also check corresponding .py exists
        py_name = filename.split(".")[0] + ".py"
        py_path = os.path.join(MODULES_DIR, py_name)
        if not os.path.exists(py_path):
            print(f"  [ERROR] {py_name} not found! Cannot disable {filename}")
            continue

        shutil.move(pyd_path, backup_path)
        print(f"  [OK] {filename} -> {filename}{BACKUP_SUFFIX}")

    # Also handle patched versions that might interfere
    for f in os.listdir(MODULES_DIR):
        if f.startswith("app.cp313") and f.endswith(".pyd") and "patched" in f:
            old = os.path.join(MODULES_DIR, f)
            new = old + BACKUP_SUFFIX
            if os.path.exists(old) and not os.path.exists(new):
                shutil.move(old, new)
                print(f"  [OK] {f} -> {f}{BACKUP_SUFFIX}")

    print("\nDone! Now use run.bat or run_noauth.bat to start the app.")
    print("The .py source files will be loaded instead of the locked .pyd files.")


def revert():
    print("=== Reverting: Re-enabling original .pyd modules ===\n")
    for filename in LOCKED_FILES:
        pyd_path = os.path.join(MODULES_DIR, filename)
        backup_path = pyd_path + BACKUP_SUFFIX

        if not os.path.exists(backup_path):
            print(f"  [SKIP] No backup for {filename}")
            continue

        if os.path.exists(pyd_path):
            os.remove(pyd_path)

        shutil.move(backup_path, pyd_path)
        print(f"  [OK] {filename}{BACKUP_SUFFIX} -> {filename}")

    # Revert patched versions too
    for f in os.listdir(MODULES_DIR):
        if f.endswith(BACKUP_SUFFIX) and "patched" in f:
            old = os.path.join(MODULES_DIR, f)
            new = old[: -len(BACKUP_SUFFIX)]
            shutil.move(old, new)
            basename = os.path.basename(new)
            print(f"  [OK] {basename}{BACKUP_SUFFIX} -> {basename}")

    print("\nDone! Original .pyd files restored.")


def main():
    if "--revert" in sys.argv:
        revert()
    else:
        setup()


if __name__ == "__main__":
    main()
