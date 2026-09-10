"""Test script to identify which module import crashes."""
import sys
import faulthandler

faulthandler.enable()
sys.stdout.reconfigure(line_buffering=True)

print("=== Module Import Test ===")
print(f"Python: {sys.version}")

test_modules = [
    "modules.utils.helpers",
    "modules.utils.flow_layout",
    "modules.services",
    "modules.veo3.frontend.common.base_generation_tab",
    "modules.veo3.frontend.main.veo3_text_to_video_tab",
]

for mod_name in test_modules:
    print(f"\nImporting {mod_name}...", flush=True)
    try:
        __import__(mod_name)
        print(f"  OK", flush=True)
    except Exception as e:
        print(f"  FAILED: {type(e).__name__}: {e}", flush=True)

print("\n=== Done ===")
