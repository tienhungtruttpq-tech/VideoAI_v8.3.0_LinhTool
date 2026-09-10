"""
Refined patch: The v4 patch successfully prevented process kill but broke module init.
The error is "NULL result without error in PyObject_Call" at line 240.

We patched too many functions. Need to find exactly which function causes the error.
The key is: _fz878ct runs during module init to SET UP the kill mechanism.
We need it to succeed (return properly) but NOT actually set up the kill.

Strategy: Instead of making _fz878ct return NULL, let's make it SUCCEED 
but without the dangerous parts. We need to understand what _fz878ct does
and patch only the dangerous calls within it.

Alternative: Only patch _secvio (the kill function) and _ausi (the auth check),
and let _fz878ct set up its function pointers harmlessly.
If _secvio is patched to do nothing, calling it won't kill the process.
"""
import struct
import os

backup_path = os.path.abspath(r"modules\app.cp313-win_amd64.pyd.bak")
patched_path = os.path.abspath(r"modules\app.cp313-win_amd64_patched_v5.pyd")

print("Reading from backup...")
with open(backup_path, 'rb') as f:
    data = bytearray(f.read())

text_va = 0x1000
text_raw = 0x400

def rva_to_file(rva):
    return text_raw + (rva - text_va)

# xor rax, rax; ret - returns NULL/0
ret_null = bytes([0x48, 0x31, 0xC0, 0xC3])

print("\n=== Minimal patches - only disable kill & auth ===")

# PATCH 1: Only patch _secvio (the kill function)
# This is the function that actually calls TerminateProcess/_exit
# If we make it return without killing, the process survives
fo = rva_to_file(0x66390)
print(f"1. _secvio at RVA 0x66390, file {hex(fo)}")
print(f"   Before: {data[fo:fo+8].hex()}")
data[fo:fo+len(ret_null)] = ret_null
print(f"   After:  {data[fo:fo+8].hex()}")

# PATCH 2: Patch _ausi to return NULL
# This is the auth check. If it returns NULL, the caller should
# handle the error and continue.
fo = rva_to_file(0x109640)
print(f"2. _ausi at RVA 0x109640, file {hex(fo)}")
print(f"   Before: {data[fo:fo+8].hex()}")
data[fo:fo+len(ret_null)] = ret_null
print(f"   After:  {data[fo:fo+8].hex()}")

# PATCH 3: Replace TerminateProcess import with harmless function
tp_pos = data.find(b'TerminateProcess')
if tp_pos >= 0:
    print(f"3. TerminateProcess import at {hex(tp_pos)} -> GetCurrentThread")
    data[tp_pos:tp_pos+16] = b'GetCurrentThread'

# DO NOT patch _fz878ct - let it set up its structures normally
# The kill mechanism will be set up but _secvio won't actually kill

# Save
print(f"\n=== Saving ===")
with open(patched_path, 'wb') as f:
    f.write(data)
print(f"Saved to: {patched_path}")
print("Done!")
