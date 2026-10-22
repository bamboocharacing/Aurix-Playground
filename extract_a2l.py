import sys
import struct
from elftools.elf.elffile import ELFFile

def get_str(elf, vaddr):
    if vaddr == 0:
        return "NO_COMPU_METHOD"

    for s in elf.iter_sections():
        if s['sh_addr'] <= vaddr < s['sh_addr'] + s['sh_size']:
            offset = vaddr - s['sh_addr']
            d = s.data()
            end = d.find(b'\x00', offset)

            return d[offset:end].decode('utf-8')

    return "UNKNOWN"

def run_extraction(elf_path, out_path):
    with open(elf_path, 'rb') as f:
        elf = ELFFile(f)
        section = elf.get_section_by_name('.a2l_metadata')

        if not section:
            print("Error: .a2l_metadata section missing in ELF.")
            sys.exit(1)

        data = section.data()    
        idx = 0

        print(section.compressed)

        characteristics = []
        measurements = []
        compu_method = []

        hdr_fmt = "<IB3xII"
        hdr_size = struct.calcsize(hdr_fmt)

        while idx < len(data):
            if idx + hdr_size > len(data):
                break;

            print(data[idx:idx+hdr_size])
            magic, obj_type, name_ptr, desc_ptr = struct.unpack(hdr_fmt, data[idx:idx+hdr_size])

            if magic != 0x41324C21:
                idx += 4
                continue

            name = get_str(elf, name_ptr)
            desc = get_str(elf, desc_ptr)
            p_off = idx + hdr_size

            
            if obj_type == 1:   # CHARACTERISTIC
                # Layout: vaddr(4), dtype(1), pad(3), cm_ptr(4), low(4), high(4) (20)
                vaddr, dtype, cm_ptr, low, high = struct.unpack("<IB3xIff", data[p_off:p_off + 20])
                characteristics.append((name, desc, vaddr, "ULONG", get_str(elf, cm_ptr), low, high)) # resolve data tyoe
                idx += hdr_size + 24
            elif obj_type == 2: # MEASUREMENT
                # Layout: vaddr(4), dtype(1), pad(3), cm_ptr(4), format_ptr(4), phys_unit_ptr(4) (20)
                vaddr, dtype, cm_ptr, format_ptr, phys_unit_ptr = struct.unpack("<IB3xIII", data[p_off:p_off + 20])
                measurements.append((name, desc, vaddr, "ULONG", get_str(elf, cm_ptr), get_str(elf, format_ptr), get_str(elf, phys_unit_ptr))) # resolve data tyoe
                idx += hdr_size + 24
            elif obj_type == 3: # COMPU_METHOD
                # Layout: type_ptr(4), format_ptr(4), unit_ptr(4), cA(4), cB(4), cC(4), cD(4), cE(4), cF(4), tab_ptr(4) (40)
                type_ptr, format_ptr, unit_ptr, cA, cB, cC, cD, cE, cF, tab_ptr = struct.unpack("<IB3xIIffffffI", data[p_off:p_off + 40])
                compu_method.append((get_str(elf, type_ptr), get_str(elf, format_ptr), get_str(elf, unit_ptr), cA, cB, cC, cD, cE, cF, get_str(elf, tab_ptr)))
                idx += hdr_size + 40
            else:
                idx += 4

            a2l = [
                "ASAP2_VERSION 1 61",
                "/begin PROJECT AURIX_PLAYGROUND \"AURX PLAYGROUND GENERATED A2L\"",
                "    /begin HEADER \"Automated Metadata Extraction\" /end HEADER",
                "    /begin MODULE ECUMODULE \"No Title\"",
                "        /begin MOD_COMMON \"\" BYTE_ORDER MSB_FIRST /end MOD_COMMON"
            ]

            a2l.append("""
        /begin RECORD_LAYOUT Scalar_BYTE FNC_VALUES 1 UBYTE DIRECT POSITION_0000 INDEX_INCR /end RECORD_LAYOUT
        /begin RECORD_LAYOUT Scalar_BYTE FNC_VALUES 1 UWORD DIRECT POSITION_0000 INDEX_INCR /end RECORD_LAYOUT
        /begin RECORD_LAYOUT Scalar_BYTE FNC_VALUES 1 ULONG DIRECT POSITION_0000 INDEX_INCR /end RECORD_LAYOUT
        /begin RECORD_LAYOUT Scalar_BYTE FNC_VALUES 1 FLOAT32_IEEE DIRECT POSITION_0000 INDEX_INCR /end RECORD_LAYOUT
            """)

            for type, format, unit, a, b, c, d, e, f, tab in compu_method:
                a2l.append(f'        /begin COMPU_METHOD {name}')

            with open(out_path, 'w') as out_f:
                out_f.write("\n".join(a2l))

            print(f"A2L Erfolgreich generiert: {out_path}")



if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("Usage: python extract_a2l.py <input.elf> <output.a2l>");
        sys.exit(1);

    run_extraction(sys.argv[1], sys.argv[2])