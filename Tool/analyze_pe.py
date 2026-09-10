"""
Analyze the app.pyd PE structure to find exact IAT addresses needed for patching.
Author recovery tool - rebuilding after source code loss.
"""
import struct
import sys
import os

PYD_PATH = os.path.join(os.path.dirname(__file__), "modules", "app.cp313-win_amd64.pyd")

def main():
    with open(PYD_PATH, "rb") as f:
        data = f.read()

    pe_off = struct.unpack_from("<I", data, 0x3C)[0]
    num_sections = struct.unpack_from("<H", data, pe_off + 6)[0]
    opt_header_size = struct.unpack_from("<H", data, pe_off + 20)[0]

    section_start = pe_off + 24 + opt_header_size
    sections = {}
    print("=== PE Sections ===")
    for i in range(num_sections):
        offset = section_start + i * 40
        name = data[offset : offset + 8].rstrip(b"\x00").decode("ascii", errors="replace")
        vsize = struct.unpack_from("<I", data, offset + 8)[0]
        vaddr = struct.unpack_from("<I", data, offset + 12)[0]
        raw_size = struct.unpack_from("<I", data, offset + 16)[0]
        raw_off = struct.unpack_from("<I", data, offset + 20)[0]
        print(f"  {name}: VA={hex(vaddr)} VSize={hex(vsize)} Raw={hex(raw_off)} RawSize={hex(raw_size)}")
        sections[name] = (vaddr, vsize, raw_off, raw_size)

    def rva_to_fo(rva):
        for sname, (va, vs, ro, rs) in sections.items():
            if va <= rva < va + max(vs, rs):
                return ro + (rva - va)
        return None

    # Import directory
    import_dir_rva = struct.unpack_from("<I", data, pe_off + 24 + 8 * 1)[0]
    imp_fo = rva_to_fo(import_dir_rva)

    print("\n=== Key IAT Entries ===")
    targets = {
        "_Py_NoneStruct", "_Py_TrueStruct", "_Py_FalseStruct",
        "TerminateProcess", "GetCurrentProcess", "GetCurrentProcessId",
        "ExitProcess", "GetCurrentThread",
    }

    iat_map = {}
    i = 0
    while True:
        entry_off = imp_fo + i * 20
        name_rva = struct.unpack_from("<I", data, entry_off + 12)[0]
        if name_rva == 0:
            break
        name_fo = rva_to_fo(name_rva)
        dll_name = data[name_fo : data.index(b"\x00", name_fo)].decode("ascii", errors="replace")

        orig_thunk_rva = struct.unpack_from("<I", data, entry_off)[0]
        first_thunk_rva = struct.unpack_from("<I", data, entry_off + 16)[0]

        thunk_fo = rva_to_fo(orig_thunk_rva)
        j = 0
        while True:
            hint_val = struct.unpack_from("<Q", data, thunk_fo + j * 8)[0]
            if hint_val == 0:
                break
            iat_rva = first_thunk_rva + j * 8
            if not (hint_val & (1 << 63)):
                hint_fo = rva_to_fo(hint_val & 0x7FFFFFFF)
                if hint_fo:
                    sym = data[hint_fo + 2 : data.index(b"\x00", hint_fo + 2)].decode("ascii", errors="replace")
                    if sym in targets:
                        print(f"  {dll_name}!{sym}: IAT_RVA={hex(iat_rva)}")
                        iat_map[sym] = iat_rva
            j += 1
        i += 1

    # Find TerminateProcess call sites in .text
    text_va, text_vs, text_raw, text_rs = sections[".text"]
    tp_iat = iat_map.get("TerminateProcess")
    if tp_iat:
        print(f"\n=== TerminateProcess call sites (IAT RVA {hex(tp_iat)}) ===")
        for off in range(text_raw, text_raw + text_rs - 6):
            if data[off] == 0xFF and data[off + 1] == 0x15:
                disp = struct.unpack_from("<i", data, off + 2)[0]
                instr_rva = text_va + (off - text_raw)
                target_rva = instr_rva + 6 + disp
                if target_rva == tp_iat:
                    print(f"  CALL at file_offset={hex(off)}, RVA={hex(instr_rva)}")

    # Verify function entry points
    print("\n=== Protection Function Entry Points ===")
    for name, rva in [("_secvio", 0x66390), ("_ausi", 0x109640), ("_fz878ct_approx", 0x685F)]:
        fo = rva_to_fo(rva)
        if fo and fo < len(data) - 16:
            first_bytes = data[fo : fo + 16].hex()
            print(f"  {name}: RVA={hex(rva)} file_offset={hex(fo)} first_bytes={first_bytes}")

    # Find TerminateProcess import string location
    tp_pos = data.find(b"TerminateProcess")
    if tp_pos >= 0:
        print(f"\n  TerminateProcess string at file_offset={hex(tp_pos)}")

    # Write IAT map for use by patch script
    print("\n=== IAT Map (for patch script) ===")
    for sym, rva in sorted(iat_map.items()):
        print(f"  {sym} = {hex(rva)}")

    return iat_map

if __name__ == "__main__":
    main()
