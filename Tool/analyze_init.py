import struct

with open(r'modules\app.cp313-win_amd64.pyd.bak', 'rb') as f:
    data = f.read()

text_va = 0x1000
text_raw = 0x400
rdata_va = 0x13f000
rdata_raw = 0x13de00
data_va = 0x154000
data_raw = 0x152200

# The CRT uses __xi_a to __xi_z and __xc_a to __xc_z arrays
# to call initialization functions at DLL load time.
# These are arrays of function pointers in .CRT$XIA, .CRT$XIZ, etc.
# In the PE file, they're merged into .rdata or .data section.

# Let's find function pointer arrays that point into .text
# In .data section (writable), look for 8-byte pointers

# Image base is 0x180000000
image_base = 0x180000000

# But in the file, relocations haven't been applied.
# The pointers are stored as image_base + RVA
# So we look for values like 0x180001000 to 0x18013e000

print("Scanning .data section for function pointers into .text...")
found_ptrs = []
for i in range(data_raw, data_raw + 0x8800 - 8, 8):
    ptr = struct.unpack_from('<Q', data, i)[0]
    if image_base + text_va <= ptr < image_base + text_va + 0x13da00:
        rva = ptr - image_base
        found_ptrs.append((i, rva))

# Group consecutive pointers (these form arrays)
print(f"Found {len(found_ptrs)} function pointers in .data")
if found_ptrs:
    # Find groups
    groups = []
    current_group = [found_ptrs[0]]
    for j in range(1, len(found_ptrs)):
        if found_ptrs[j][0] == found_ptrs[j-1][0] + 8:
            current_group.append(found_ptrs[j])
        else:
            if len(current_group) >= 1:
                groups.append(current_group)
            current_group = [found_ptrs[j]]
    groups.append(current_group)
    
    for group in groups:
        if len(group) >= 1:
            start_offset = group[0][0]
            data_offset_in_section = start_offset - data_raw
            print(f"\n  Function pointer array at .data+{hex(data_offset_in_section)} (file offset {hex(start_offset)}), {len(group)} entries:")
            for offset, rva in group:
                # Check if this points to a security function
                marker = ""
                if 0x5b00 <= rva <= 0x9000:
                    marker = " <-- NEAR _fz878ct!"
                if 0x6630 <= rva <= 0x6650:
                    marker = " <-- _secvio!"
                if 0x1096 <= rva <= 0x10d1:
                    marker = " <-- _ausi!"
                print(f"    -> RVA {hex(rva)}{marker}")

# Also scan .rdata for function pointers  
print("\n\nScanning .rdata for CRT init function pointer arrays...")
found_rdata_ptrs = []
for i in range(rdata_raw, rdata_raw + 0x14400 - 8, 8):
    ptr = struct.unpack_from('<Q', data, i)[0]
    if image_base + text_va <= ptr < image_base + text_va + 0x13da00:
        rva = ptr - image_base
        found_rdata_ptrs.append((i, rva))

print(f"Found {len(found_rdata_ptrs)} function pointers in .rdata")

# Look specifically around .CRT sections  
# These are at known offsets. Let's check
# In MSVC, .CRT$XCA/XCZ are for C++ ctors
# .CRT$XIA/XIZ are for CRT initializers
# .CRT$XPA/XPZ are for pre-terminators
# .CRT$XTA/XTZ are for terminators

# Let's find the .CRT section markers
for marker in [b'.CRT$XCA', b'.CRT$XCZ', b'.CRT$XIA', b'.CRT$XIZ', b'.CRT$XPA', b'.CRT$XPZ']:
    pos = data.find(marker)
    if pos >= 0:
        print(f"  {marker.decode()}: at file offset {hex(pos)}")

# Actually the .CRT markers are in the PE section headers, not in data
# Let's look at PE headers more carefully
pe_offset = struct.unpack_from('<I', data, 0x3C)[0]
num_sections = struct.unpack_from('<H', data, pe_offset + 6)[0]
opt_header_size = struct.unpack_from('<H', data, pe_offset + 20)[0]
section_start = pe_offset + 24 + opt_header_size

print("\n\nAll PE sections:")
for i in range(num_sections):
    offset = section_start + i * 40
    name = data[offset:offset+8]
    virtual_size = struct.unpack_from('<I', data, offset + 8)[0]
    virtual_addr = struct.unpack_from('<I', data, offset + 12)[0]
    raw_size = struct.unpack_from('<I', data, offset + 16)[0]
    raw_offset = struct.unpack_from('<I', data, offset + 20)[0]
    print(f"  {name}: VA={hex(virtual_addr)}, VSize={hex(virtual_size)}, Raw={hex(raw_offset)}, RawSize={hex(raw_size)}")

# The .CRT data is within the .rdata section
# Let's look at the data directory for TLS callbacks  
tls_dir_rva = struct.unpack_from('<I', data, pe_offset + 24 + 9 * 8)[0]
tls_dir_size = struct.unpack_from('<I', data, pe_offset + 24 + 9 * 8 + 4)[0]
print(f"\nTLS Directory: RVA={hex(tls_dir_rva)}, Size={hex(tls_dir_size)}")

if tls_dir_rva > 0:
    # TLS callback can run code before DllMain!
    tls_file = rdata_raw + (tls_dir_rva - rdata_va) if tls_dir_rva >= rdata_va else data_raw + (tls_dir_rva - data_va)
    print(f"  TLS Directory at file offset: {hex(tls_file)}")
    # TLS Directory structure (64-bit):
    # StartAddressOfRawData (8) + EndAddressOfRawData (8) + AddressOfIndex (8) + AddressOfCallBacks (8) + ...
    callbacks_addr = struct.unpack_from('<Q', data, tls_file + 24)[0]
    print(f"  TLS Callbacks address: {hex(callbacks_addr)}")
    if callbacks_addr > 0:
        callbacks_rva = callbacks_addr - image_base
        callbacks_file = rdata_raw + (callbacks_rva - rdata_va) if callbacks_rva >= rdata_va else data_raw + (callbacks_rva - data_va)
        print(f"  TLS Callbacks array at file offset: {hex(callbacks_file)}")
        # Read callback pointers
        j = 0
        while True:
            cb = struct.unpack_from('<Q', data, callbacks_file + j * 8)[0]
            if cb == 0:
                break
            cb_rva = cb - image_base
            print(f"    TLS Callback {j}: RVA {hex(cb_rva)}")
            j += 1
