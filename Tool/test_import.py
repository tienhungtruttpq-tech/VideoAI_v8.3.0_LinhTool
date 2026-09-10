"""
The PE import of TerminateProcess IS the actual call mechanism!
When we replaced the string, the DLL couldn't load because the import
resolution failed. Let's instead not modify the import name but
instead find and NOP the actual CALL instructions.

Wait - the import string patch should still let the DLL load since
GetCurrentThread IS a valid kernel32 function. The crash might be
because the import resolution puts GetCurrentThread's address where
TerminateProcess was expected, and then calling GetCurrentThread with
wrong params causes issues.

Actually, the crash is before any Python code runs (during DLL load/init).
The TerminateProcess call happens in the C init code (PyInit_app).

Let me try: COMBINE both approaches:
1. Patch import string (TerminateProcess -> GetCurrentThread)
2. Also patch _fz878ct function to return early
3. Also patch _secvio to return early
4. Also patch _ausi to return early

But make the return values SAFE - return the correct values
for Cython internal functions.
"""
import struct
import os

backup_path = os.path.abspath(r"modules\app.cp313-win_amd64.pyd.bak")
patched_path = os.path.abspath(r"modules\app.cp313-win_amd64_patched_v3.pyd")

print("Reading from backup...")
with open(backup_path, 'rb') as f:
    data = bytearray(f.read())

text_va = 0x1000
text_raw = 0x400
text_size = 0x13da00

# ===== PATCH 1: Replace TerminateProcess import name =====
tp_pos = data.find(b'TerminateProcess')
if tp_pos >= 0:
    print(f"Patch 1: TerminateProcess at {hex(tp_pos)} -> GetCurrentThread")
    data[tp_pos:tp_pos+16] = b'GetCurrentThread'

# ===== PATCH 2: Find ALL `FF 15` CALL [rip+disp] that resolve to =====
# the IAT entry for TerminateProcess
# IAT for TerminateProcess is at a specific RVA
# From earlier analysis: thunk_rva=0x153108
# But after we change the import name, the thunk will contain GetCurrentThread addr
# So we need to find the original thunk RVA

# The IAT (.idata$5) RVA for TerminateProcess/GetCurrentThread
# Let's parse from the original data to find the IAT RVA
# Actually, we need to find it from the first thunk (IAT) 

import pefile
pe = pefile.PE(data=bytes(data))

iat_rva = None
for entry in pe.DIRECTORY_ENTRY_IMPORT:
    if b'KERNEL32' in entry.dll.upper():
        for imp in entry.imports:
            # After patching, the name is GetCurrentThread now
            # But the thunk structure position is the same
            if imp.name and imp.name.decode('ascii', errors='replace') == 'GetCurrentThread':
                # Check if this is our patched entry by looking at all GetCurrentThread imports
                # There might be 2 now - original and our patched one
                pass
            # Let's use the ordinal position instead
            # The original order was: DisableThreadLibraryCalls, RtlCaptureContext, ...
            # GetCurrentProcess was at thunk_rva=0x1530f4
            # TerminateProcess (now GetCurrentThread) was at thunk_rva=0x153108
pe.close()

# From previous analysis, TerminateProcess thunk was at RVA 0x153108
# This is in the .idata section, which is part of .rdata
iat_terminate_rva = 0x153108

print(f"\nPatch 2: Searching for CALL/JMP to IAT entry at RVA {hex(iat_terminate_rva)}")

# On x64, calls through IAT look like: FF 15 xx xx xx xx (CALL [rip+disp32])
# Where rip+6+disp32 = IAT entry RVA
calls_found = 0
for i in range(text_raw, text_raw + text_size - 6):
    if data[i] == 0xFF and data[i+1] == 0x15:
        disp = struct.unpack_from('<i', data, i + 2)[0]
        instr_rva = text_va + (i - text_raw)
        target_rva = instr_rva + 6 + disp
        if target_rva == iat_terminate_rva:
            print(f"  CALL [rip+{hex(disp)}] at offset {hex(i)}, RVA {hex(instr_rva)}")
            # NOP this: 6 bytes of 0x90
            data[i:i+6] = b'\x90\x90\x90\x90\x90\x90'
            calls_found += 1
    # Also check for JMP [rip+disp32]: FF 25 xx xx xx xx
    if data[i] == 0xFF and data[i+1] == 0x25:
        disp = struct.unpack_from('<i', data, i + 2)[0]
        instr_rva = text_va + (i - text_raw)
        target_rva = instr_rva + 6 + disp
        if target_rva == iat_terminate_rva:
            print(f"  JMP [rip+{hex(disp)}] at offset {hex(i)}, RVA {hex(instr_rva)}")
            data[i:i+6] = b'\x90\x90\x90\x90\x90\x90'
            calls_found += 1

print(f"  Found and NOP'd {calls_found} calls to TerminateProcess")

# ===== PATCH 3: Also find calls to GetCurrentProcess (usually before TerminateProcess) =====
iat_getcurprocess_rva = 0x1530f4
print(f"\nPatch 3: Searching for CALL to GetCurrentProcess at RVA {hex(iat_getcurprocess_rva)}")
for i in range(text_raw, text_raw + text_size - 6):
    if data[i] == 0xFF and data[i+1] == 0x15:
        disp = struct.unpack_from('<i', data, i + 2)[0]
        instr_rva = text_va + (i - text_raw)
        target_rva = instr_rva + 6 + disp
        if target_rva == iat_getcurprocess_rva:
            print(f"  CALL GetCurrentProcess at offset {hex(i)}, RVA {hex(instr_rva)}")
            # Don't NOP GetCurrentProcess as it might be used legitimately
            # Just note it for context

# ===== PATCH 4: Patch _secvio function =====
# _secvio at file offset 0x65790 (PDATA: 0x66390-0x6644a)
print(f"\nPatch 4: _secvio at 0x65790")
# Make it return 0 safely (xor rax,rax; ret)
data[0x65790:0x65790+4] = bytes([0x48, 0x31, 0xC0, 0xC3])
print(f"  Patched to xor rax,rax; ret")

# ===== PATCH 5: Patch _ausi function =====
# _ausi at file offset 0x108a40 (PDATA: 0x109640-0x10d01a)
print(f"\nPatch 5: _ausi at 0x108a40")
data[0x108a40:0x108a40+4] = bytes([0x48, 0x31, 0xC0, 0xC3])
print(f"  Patched to xor rax,rax; ret")

# ===== PATCH 6: Look at the CRT __security_init_cookie and similar =====
# The CRT startup code in .text section includes UnhandledExceptionFilter setup
# and TerminateProcess calls for security failures
# These are in the CRT init code at the END of .text section

# Let's also search for CRT-specific patterns
print(f"\nPatch 6: Searching CRT TerminateProcess calls in ALL sections")
for section_name, raw, size in [('.text', 0x400, 0x13da00)]:
    for i in range(raw, raw + size - 6):
        if data[i] == 0xFF and data[i+1] == 0x15:
            disp = struct.unpack_from('<i', data, i + 2)[0]
            instr_rva = text_va + (i - raw)
            target_rva = instr_rva + 6 + disp
            # Check if target is in the import range for KERNEL32
            # Import thunks are around 0x153000-0x153200
            if 0x153100 <= target_rva <= 0x153110:
                # This is near TerminateProcess IAT entry (0x153108)
                if target_rva == iat_terminate_rva:
                    print(f"  Additional CALL at offset {hex(i)}, RVA {hex(instr_rva)}")

# ===== PATCH 7: Find the MSVC __report_rangecheckfailure / __security_check_cookie =====
# These use TerminateProcess internally. Let's check for indirect calls.
# Actually, these are CRT internal functions that should only trigger on buffer overflow.
# The real issue might be that the protection code uses a DIRECT function pointer
# obtained during module init.

# Let's look at what's inside _fz878ct (0x685f-0x81a1)
# This is a 6466-byte function. Let's scan it for IAT calls
print(f"\nPatch 7: Scanning _fz878ct body for IAT calls")
fz_start = text_raw + (0x685f - text_va)
fz_end = text_raw + (0x81a1 - text_va)
for i in range(fz_start, fz_end - 6):
    if data[i] == 0xFF and data[i+1] == 0x15:
        disp = struct.unpack_from('<i', data, i + 2)[0]
        instr_rva = text_va + (i - text_raw)
        target_rva = instr_rva + 6 + disp
        print(f"  CALL [rip+{hex(disp)}] at offset {hex(i)}, RVA {hex(instr_rva)} -> target RVA {hex(target_rva)}")

# Also check _ausi body
print(f"\nScanning _ausi body for IAT calls")
ausi_start = text_raw + (0x109640 - text_va)
ausi_end = text_raw + (0x10d01a - text_va)
for i in range(ausi_start, ausi_end - 6):
    if data[i] == 0xFF and data[i+1] == 0x15:
        disp = struct.unpack_from('<i', data, i + 2)[0]
        instr_rva = text_va + (i - text_raw)
        target_rva = instr_rva + 6 + disp
        if 0x153000 <= target_rva <= 0x153200:
            print(f"  CALL at offset {hex(i)}, RVA {hex(instr_rva)} -> IAT RVA {hex(target_rva)}")

# Save
print(f"\n=== Saving ===")
with open(patched_path, 'wb') as f:
    f.write(data)
print(f"Saved to: {patched_path}")
