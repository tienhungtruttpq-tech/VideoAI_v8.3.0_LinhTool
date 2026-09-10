"""
Patch app.cp313-win_amd64.pyd to remove machine authentication.
Author recovery tool - run this on Windows after hard drive replacement.

This script patches the compiled .pyd to:
1. Redirect TerminateProcess import to GetCurrentThread (harmless)
2. NOP all CALL instructions targeting TerminateProcess IAT entry
3. Patch _secvio (security violation/kill function) to return safely
4. Patch _ausi (auth check) to return Py_None instead of checking machine_id

Usage: python patch_remove_machine_auth.py
"""
import struct
import os
import sys
import shutil
from datetime import datetime

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
ORIGINAL_PYD = os.path.join(SCRIPT_DIR, "modules", "app.cp313-win_amd64.pyd")
BACKUP_PYD = os.path.join(SCRIPT_DIR, "modules", "app.cp313-win_amd64.pyd.original_backup")
OUTPUT_PYD = os.path.join(SCRIPT_DIR, "modules", "app.cp313-win_amd64_noauth.pyd")


def rva_to_file(rva, text_va=0x1000, text_raw=0x400):
    return text_raw + (rva - text_va)


def parse_pe_sections(data):
    pe_off = struct.unpack_from("<I", data, 0x3C)[0]
    num_sections = struct.unpack_from("<H", data, pe_off + 6)[0]
    opt_header_size = struct.unpack_from("<H", data, pe_off + 20)[0]
    section_start = pe_off + 24 + opt_header_size
    sections = {}
    for i in range(num_sections):
        offset = section_start + i * 40
        name = data[offset:offset + 8].rstrip(b"\x00").decode("ascii", errors="replace")
        vsize = struct.unpack_from("<I", data, offset + 8)[0]
        vaddr = struct.unpack_from("<I", data, offset + 12)[0]
        raw_size = struct.unpack_from("<I", data, offset + 16)[0]
        raw_off = struct.unpack_from("<I", data, offset + 20)[0]
        sections[name] = (vaddr, vsize, raw_off, raw_size)
    return sections


def find_iat_entries(data, sections):
    """Parse PE imports to find IAT RVAs for key symbols."""
    pe_off = struct.unpack_from("<I", data, 0x3C)[0]
    import_dir_rva = struct.unpack_from("<I", data, pe_off + 24 + 8)[0]

    def rva_to_fo(rva):
        for sname, (va, vs, ro, rs) in sections.items():
            if va <= rva < va + max(vs, rs):
                return ro + (rva - va)
        return None

    iat_map = {}
    imp_fo = rva_to_fo(import_dir_rva)
    if imp_fo is None:
        return iat_map

    i = 0
    while True:
        entry_off = imp_fo + i * 20
        if entry_off + 20 > len(data):
            break
        name_rva = struct.unpack_from("<I", data, entry_off + 12)[0]
        if name_rva == 0:
            break
        name_fo = rva_to_fo(name_rva)
        if name_fo is None:
            i += 1
            continue
        end = data.index(b"\x00", name_fo)
        dll_name = data[name_fo:end].decode("ascii", errors="replace")

        orig_thunk_rva = struct.unpack_from("<I", data, entry_off)[0]
        first_thunk_rva = struct.unpack_from("<I", data, entry_off + 16)[0]

        thunk_fo = rva_to_fo(orig_thunk_rva)
        if thunk_fo is None:
            i += 1
            continue

        j = 0
        while True:
            if thunk_fo + j * 8 + 8 > len(data):
                break
            hint_val = struct.unpack_from("<Q", data, thunk_fo + j * 8)[0]
            if hint_val == 0:
                break
            iat_rva = first_thunk_rva + j * 8
            if not (hint_val & (1 << 63)):
                hint_fo = rva_to_fo(hint_val & 0x7FFFFFFF)
                if hint_fo and hint_fo + 2 < len(data):
                    sym_end = data.index(b"\x00", hint_fo + 2)
                    sym = data[hint_fo + 2:sym_end].decode("ascii", errors="replace")
                    iat_map[sym] = iat_rva
            j += 1
        i += 1

    return iat_map


def main():
    if not os.path.exists(ORIGINAL_PYD):
        # Try backup
        if os.path.exists(BACKUP_PYD):
            print(f"Using backup: {BACKUP_PYD}")
            src = BACKUP_PYD
        else:
            print(f"ERROR: Cannot find {ORIGINAL_PYD}")
            sys.exit(1)
    else:
        src = ORIGINAL_PYD

    # Create backup if not exists
    if not os.path.exists(BACKUP_PYD) and src == ORIGINAL_PYD:
        shutil.copy2(ORIGINAL_PYD, BACKUP_PYD)
        print(f"Backup created: {BACKUP_PYD}")

    print(f"Reading: {src}")
    with open(src, "rb") as f:
        data = bytearray(f.read())

    original_size = len(data)
    sections = parse_pe_sections(data)
    iat_map = find_iat_entries(data, sections)

    text_va, text_vs, text_raw, text_rs = sections[".text"]
    patches_applied = 0

    # =====================================================
    # PATCH 1: Replace TerminateProcess import name
    # =====================================================
    tp_pos = data.find(b"TerminateProcess")
    if tp_pos >= 0:
        # Both are 16 characters, exact replacement
        data[tp_pos:tp_pos + 16] = b"GetCurrentThread"
        print(f"[PATCH 1] TerminateProcess -> GetCurrentThread at offset {hex(tp_pos)}")
        patches_applied += 1
    else:
        print("[PATCH 1] SKIP: TerminateProcess string not found (may already be patched)")

    # =====================================================
    # PATCH 2: NOP all CALL [rip+disp32] to TerminateProcess IAT
    # =====================================================
    tp_iat_rva = iat_map.get("TerminateProcess")
    if tp_iat_rva is None:
        # After patch 1, it will be under GetCurrentThread
        # Use the known RVA from previous analysis
        tp_iat_rva = 0x153108
        print(f"[PATCH 2] Using known TerminateProcess IAT RVA: {hex(tp_iat_rva)}")

    nop_count = 0
    for off in range(text_raw, text_raw + text_rs - 6):
        # FF 15 = CALL [rip+disp32]
        if data[off] == 0xFF and data[off + 1] == 0x15:
            disp = struct.unpack_from("<i", data, off + 2)[0]
            instr_rva = text_va + (off - text_raw)
            target_rva = instr_rva + 6 + disp
            if target_rva == tp_iat_rva:
                data[off:off + 6] = b"\x90" * 6  # NOP
                nop_count += 1
                print(f"  NOP'd CALL at offset {hex(off)}, RVA {hex(instr_rva)}")
        # FF 25 = JMP [rip+disp32]
        if data[off] == 0xFF and data[off + 1] == 0x25:
            disp = struct.unpack_from("<i", data, off + 2)[0]
            instr_rva = text_va + (off - text_raw)
            target_rva = instr_rva + 6 + disp
            if target_rva == tp_iat_rva:
                data[off:off + 6] = b"\x90" * 6
                nop_count += 1
                print(f"  NOP'd JMP at offset {hex(off)}, RVA {hex(instr_rva)}")

    print(f"[PATCH 2] NOP'd {nop_count} calls/jumps to TerminateProcess")
    if nop_count > 0:
        patches_applied += 1

    # Also NOP calls to ExitProcess if present
    ep_iat_rva = iat_map.get("ExitProcess")
    if ep_iat_rva:
        ep_count = 0
        for off in range(text_raw, text_raw + text_rs - 6):
            if data[off] == 0xFF and data[off + 1] in (0x15, 0x25):
                disp = struct.unpack_from("<i", data, off + 2)[0]
                instr_rva = text_va + (off - text_raw)
                target_rva = instr_rva + 6 + disp
                if target_rva == ep_iat_rva:
                    data[off:off + 6] = b"\x90" * 6
                    ep_count += 1
        if ep_count:
            print(f"  Also NOP'd {ep_count} calls to ExitProcess")

    # =====================================================
    # PATCH 3: Patch _secvio (kill function) to return safely
    # RVA 0x66390 -> xor eax, eax; ret (return 0)
    # =====================================================
    secvio_rva = 0x66390
    secvio_fo = rva_to_file(secvio_rva)
    if secvio_fo < len(data) - 4:
        print(f"[PATCH 3] _secvio at RVA {hex(secvio_rva)}, offset {hex(secvio_fo)}")
        print(f"  Before: {data[secvio_fo:secvio_fo+8].hex()}")
        # xor eax, eax; ret (3 bytes, safe for both 32-bit and 64-bit return)
        data[secvio_fo:secvio_fo + 3] = bytes([0x31, 0xC0, 0xC3])
        print(f"  After:  {data[secvio_fo:secvio_fo+8].hex()}")
        patches_applied += 1

    # =====================================================
    # PATCH 4: Patch _ausi (auth check) to return Py_None
    # RVA 0x109640
    # We need to: load _Py_NoneStruct address and return it
    # =====================================================
    ausi_rva = 0x109640
    ausi_fo = rva_to_file(ausi_rva)

    # Find _Py_NoneStruct IAT RVA
    none_iat_rva = iat_map.get("_Py_NoneStruct")
    true_iat_rva = iat_map.get("_Py_TrueStruct")

    # Prefer Py_True (truthy) over Py_None
    use_iat_rva = true_iat_rva or none_iat_rva

    if use_iat_rva and ausi_fo < len(data) - 16:
        # Build: mov rax, [rip+disp32]; ret
        # FF 15 is CALL, we want MOV RAX
        # 48 8B 05 disp32 = mov rax, [rip+disp32]  (7 bytes)
        # C3               = ret                     (1 byte)
        # Total: 8 bytes

        # disp = target_rva - (instr_rva + 7)
        # instr_rva = ausi_rva, instruction length for mov rax,[rip+d32] = 7
        disp = use_iat_rva - (ausi_rva + 7)

        patch = struct.pack("<3bi", 0x48, 0x8B, 0x05, disp) + b"\xC3"
        sym_name = "_Py_TrueStruct" if use_iat_rva == true_iat_rva else "_Py_NoneStruct"
        print(f"[PATCH 4] _ausi at RVA {hex(ausi_rva)}, offset {hex(ausi_fo)}")
        print(f"  Patching to return {sym_name} (IAT RVA {hex(use_iat_rva)})")
        print(f"  Before: {data[ausi_fo:ausi_fo+16].hex()}")
        data[ausi_fo:ausi_fo + len(patch)] = patch
        print(f"  After:  {data[ausi_fo:ausi_fo+16].hex()}")
        patches_applied += 1
    else:
        # Fallback: return NULL but with _secvio patched, process won't die
        print(f"[PATCH 4] _ausi at RVA {hex(ausi_rva)}, offset {hex(ausi_fo)}")
        print(f"  WARNING: Could not find _Py_NoneStruct/_Py_TrueStruct IAT")
        print(f"  Falling back to xor rax,rax; ret (return NULL)")
        data[ausi_fo:ausi_fo + 4] = bytes([0x48, 0x31, 0xC0, 0xC3])
        patches_applied += 1

    # =====================================================
    # PATCH 5: Also NOP GetCurrentProcess calls that precede
    # TerminateProcess (they get the process handle for the kill)
    # =====================================================
    gcp_iat_rva = iat_map.get("GetCurrentProcess")
    if gcp_iat_rva is None:
        gcp_iat_rva = 0x1530F4  # Known from previous analysis

    # We only NOP GetCurrentProcess calls that are within 20 bytes
    # before a (now-NOP'd) TerminateProcess call site
    # Actually, since TerminateProcess is already NOP'd, this is less critical
    # But let's still log them
    gcp_count = 0
    for off in range(text_raw, text_raw + text_rs - 6):
        if data[off] == 0xFF and data[off + 1] == 0x15:
            disp = struct.unpack_from("<i", data, off + 2)[0]
            instr_rva = text_va + (off - text_raw)
            target_rva = instr_rva + 6 + disp
            if target_rva == gcp_iat_rva:
                gcp_count += 1
    print(f"[INFO] Found {gcp_count} calls to GetCurrentProcess (not patched - harmless)")

    # =====================================================
    # VERIFY
    # =====================================================
    assert len(data) == original_size, "File size changed!"
    print(f"\n=== {patches_applied} patches applied successfully ===")

    # Save
    with open(OUTPUT_PYD, "wb") as f:
        f.write(data)
    print(f"Saved to: {OUTPUT_PYD}")

    # Also overwrite the original (with backup already saved)
    with open(ORIGINAL_PYD, "wb") as f:
        f.write(data)
    print(f"Also updated: {ORIGINAL_PYD}")

    print(f"\nDone! The tool should now work without machine authentication.")
    print(f"Original backup: {BACKUP_PYD}")


if __name__ == "__main__":
    main()
