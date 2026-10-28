"""Stage 2 of the A2L pipeline: resolve annotations against the linked ELF.

Fills the address placeholders from the ELF symbol table and the type layout
(datatype, array dimensions, struct members) from DWARF. Struct and array-of-
struct variables are flattened into one entry per leaf member, with struct
member annotations merged in. The EPK string is read from the ELF as well.

The XCP settings for IF_DATA come from the code, not from a config file: the
event table (XcpDaq_Events, built by XCP_DAQ_DEFINE_EVENT) is decoded from the
ELF, and the configuration macros (MAX_CTO, DAQ type, timestamps, port, ...)
from the compiled probe object of a2l_probe.c, which also provides the data
type alignments for MOD_COMMON. The A2L project / module names come from the
\\a2l_project annotation.
"""

import argparse
import itertools
import json
import os
import sys

from elftools.elf.elffile import ELFFile
from elftools.elf.sections import SymbolTableSection

# DW_ATE_* encodings
ATE_BOOLEAN, ATE_FLOAT, ATE_SIGNED, ATE_SIGNED_CHAR, ATE_UNSIGNED, ATE_UNSIGNED_CHAR = 2, 4, 5, 6, 7, 8
DW_OP_PLUS_UCONST = 0x23

INT_TYPES = {(1, False): "UBYTE", (1, True): "SBYTE", (2, False): "UWORD", (2, True): "SWORD",
             (4, False): "ULONG", (4, True): "SLONG", (8, False): "A_UINT64", (8, True): "A_INT64"}
FLOAT_TYPES = {4: "FLOAT32_IEEE", 8: "FLOAT64_IEEE"}

# TriCore core-local windows (PSPR 0xC..., DSPR 0xD...). XCP runs on another
# core than most data, so only global addresses are usable in the A2L.
LOCAL_SEGMENTS = (0xC, 0xD)


class ResolveError(Exception):
    pass


def read_symbols(elf):
    """Return {name: [(value, size, bind, file)]} for data objects."""
    symbols = {}
    for section in elf.iter_sections():
        if not isinstance(section, SymbolTableSection):
            continue
        current_file = None
        for sym in section.iter_symbols():
            stype, bind = sym["st_info"]["type"], sym["st_info"]["bind"]
            if stype == "STT_FILE":
                current_file = os.path.basename(sym.name)
            elif stype == "STT_OBJECT" and sym["st_shndx"] != "SHN_UNDEF":
                symbols.setdefault(sym.name, []).append(
                    (sym["st_value"], sym["st_size"], bind, current_file if bind == "STB_LOCAL" else None))
    return symbols


def lookup_symbol(symbols, obj):
    where = f"{obj['file']}:{obj['line']}"
    candidates = symbols.get(obj["symbol"], [])
    if not candidates:
        raise ResolveError(f"{where}: symbol '{obj['symbol']}' not found in ELF "
                           "(unused and removed by --gc-sections?)")
    globals_ = [c for c in candidates if c[2] != "STB_LOCAL"]
    if globals_:
        return globals_[0]
    base = os.path.basename(obj["file"])
    locals_ = [c for c in candidates if c[3] == base]
    if len(locals_) != 1:
        raise ResolveError(f"{where}: cannot uniquely resolve static symbol '{obj['symbol']}'")
    return locals_[0]


def read_variable_dies(dwarf):
    """Return {name: [(cu_basename, type_die)]} for file-scope variables."""
    variables = {}
    for cu in dwarf.iter_CUs():
        top = cu.get_top_DIE()
        cu_name = os.path.basename(top.attributes["DW_AT_name"].value.decode()) \
            if "DW_AT_name" in top.attributes else ""
        for die in top.iter_children():
            if die.tag != "DW_TAG_variable":
                continue
            decl = die
            if "DW_AT_specification" in die.attributes:
                decl = die.get_DIE_from_attribute("DW_AT_specification")
            # A definition may complete the declared type (e.g. extern T a[]; T a[3];).
            typed = die if "DW_AT_type" in die.attributes else decl
            if "DW_AT_name" not in decl.attributes or "DW_AT_type" not in typed.attributes:
                continue
            name = decl.attributes["DW_AT_name"].value.decode()
            is_definition = "DW_AT_declaration" not in die.attributes
            variables.setdefault(name, []).append(
                (cu_name, is_definition, typed.get_DIE_from_attribute("DW_AT_type")))
    return variables


def lookup_type(variables, obj):
    entries = variables.get(obj["symbol"], [])
    if not entries:
        raise ResolveError(f"{obj['file']}:{obj['line']}: no DWARF info for '{obj['symbol']}' "
                           "(build with -g)")
    base = os.path.basename(obj["file"])
    # Prefer the definition in the annotated file, then any definition.
    entries = sorted(entries, key=lambda e: (e[0] != base, not e[1]))
    return entries[0][2]


def die_name(die):
    attr = die.attributes.get("DW_AT_name")
    return attr.value.decode() if attr else None


def member_offset(die):
    attr = die.attributes.get("DW_AT_data_member_location")
    if attr is None:
        return 0  # union member
    if isinstance(attr.value, int):
        return attr.value
    expr = attr.value
    if not expr or expr[0] != DW_OP_PLUS_UCONST:
        raise ResolveError(f"unsupported member location expression {expr}")
    value, shift = 0, 0
    for byte in expr[1:]:
        value |= (byte & 0x7F) << shift
        shift += 7
        if not byte & 0x80:
            break
    return value


def layout_of(die, where, typedef_name=None):
    """Build a JSON-serialisable layout description for a DWARF type."""
    tag = die.tag
    if tag in ("DW_TAG_typedef", "DW_TAG_volatile_type", "DW_TAG_const_type", "DW_TAG_restrict_type"):
        if tag == "DW_TAG_typedef":
            typedef_name = die_name(die)
        return layout_of(die.get_DIE_from_attribute("DW_AT_type"), where, typedef_name)
    if tag == "DW_TAG_base_type":
        size = die.attributes["DW_AT_byte_size"].value
        enc = die.attributes["DW_AT_encoding"].value
        if enc == ATE_FLOAT:
            dtype = FLOAT_TYPES.get(size)
        elif enc in (ATE_SIGNED, ATE_SIGNED_CHAR):
            dtype = INT_TYPES.get((size, True))
        elif enc in (ATE_UNSIGNED, ATE_UNSIGNED_CHAR, ATE_BOOLEAN):
            dtype = INT_TYPES.get((size, False))
        else:
            dtype = None
        if dtype is None:
            raise ResolveError(f"{where}: unsupported base type '{die_name(die)}'")
        return {"kind": "base", "datatype": dtype, "size": size}
    if tag == "DW_TAG_enumeration_type":
        size = die.attributes["DW_AT_byte_size"].value
        signed = any(c.attributes["DW_AT_const_value"].value < 0 for c in die.iter_children()
                     if c.tag == "DW_TAG_enumerator" and "DW_AT_const_value" in c.attributes)
        return {"kind": "base", "datatype": INT_TYPES[(size, signed)], "size": size}
    if tag == "DW_TAG_pointer_type":
        size = die.attributes["DW_AT_byte_size"].value if "DW_AT_byte_size" in die.attributes else 4
        return {"kind": "base", "datatype": INT_TYPES[(size, False)], "size": size}
    if tag == "DW_TAG_array_type":
        dims = []
        for sub in die.iter_children():
            if sub.tag != "DW_TAG_subrange_type":
                continue
            if "DW_AT_count" in sub.attributes:
                dims.append(sub.attributes["DW_AT_count"].value)
            elif "DW_AT_upper_bound" in sub.attributes:
                dims.append(sub.attributes["DW_AT_upper_bound"].value + 1)
            else:
                raise ResolveError(f"{where}: array without known size")
        element = layout_of(die.get_DIE_from_attribute("DW_AT_type"), where)
        count = 1
        for d in dims:
            count *= d
        return {"kind": "array", "dims": dims, "element": element, "size": count * element["size"]}
    if tag in ("DW_TAG_structure_type", "DW_TAG_union_type"):
        members = []
        for m in die.iter_children():
            if m.tag != "DW_TAG_member":
                continue
            name = die_name(m)
            if "DW_AT_bit_size" in m.attributes:
                print(f"a2l_resolve: warning: {where}: bitfield member '{name}' skipped", file=sys.stderr)
                continue
            members.append({"name": name, "offset": member_offset(m),
                            "layout": layout_of(m.get_DIE_from_attribute("DW_AT_type"), where)})
        return {"kind": "struct", "names": [n for n in (typedef_name, die_name(die)) if n],
                "size": die.attributes["DW_AT_byte_size"].value, "members": members}
    raise ResolveError(f"{where}: unsupported type {tag}")


ATTR_KEYS = ("description", "unit", "format", "limits", "compu", "input", "axis_x", "axis_y", "axis_z")


def flatten(obj, layout, struct_members):
    """Yield one leaf entry per scalar / array-of-scalar in the variable."""
    where = f"{obj['file']}:{obj['line']}"

    def walk(name, address, layout, attrs):
        if layout["kind"] == "base":
            yield {**attrs, "name": name, "address": address, "datatype": layout["datatype"],
                   "size": layout["size"], "dims": []}
        elif layout["kind"] == "array" and layout["element"]["kind"] == "base":
            el = layout["element"]
            yield {**attrs, "name": name, "address": address, "datatype": el["datatype"],
                   "size": el["size"], "dims": layout["dims"]}
        elif layout["kind"] == "array":
            el = layout["element"]
            for i, idx in enumerate(itertools.product(*(range(d) for d in layout["dims"]))):
                suffix = "".join(f"[{k}]" for k in idx)
                yield from walk(name + suffix, address + i * el["size"], el, attrs)
        else:
            annotations = {}
            for n in layout["names"]:
                annotations.update(struct_members.get(n, {}))
            for m in layout["members"]:
                member_attrs = dict(attrs)
                ann = annotations.get(m["name"], {})
                member_attrs.update({k: ann[k] for k in ATTR_KEYS if ann.get(k)})
                yield from walk(f"{name}.{m['name']}", address + m["offset"], m["layout"], member_attrs)

    base_attrs = {"kind": obj["kind"], "symbol": obj["symbol"], "file": obj["file"], "line": obj["line"],
                  **{k: obj[k] for k in ATTR_KEYS if k in obj}}
    leaves = list(walk(obj["name"], obj["address"], layout, base_attrs))
    if not leaves:
        raise ResolveError(f"{where}: '{obj['symbol']}' has no measurable members")
    for leaf in leaves:
        leaf["symbol_offset"] = leaf["address"] - obj["address"]
    return leaves


SHF_ALLOC = 0x2


def read_bytes(elf, address, size, where):
    """Initialised data at a load address; size None reads to the section end."""
    for section in elf.iter_sections():
        start, length = section["sh_addr"], section["sh_size"]
        if (section["sh_flags"] & SHF_ALLOC and section["sh_type"] != "SHT_NOBITS"
                and start <= address < start + length):
            data = section.data()[address - start:]
            return data if size is None else data[:size]
    raise ResolveError(f"{where}: no initialised data at 0x{address:08X}")


def read_string(elf, address, where):
    data = read_bytes(elf, address, None, where)
    end = data.find(b"\0")
    return data[:end if end >= 0 else len(data)].decode("ascii", errors="replace")


def read_probe(path):
    """Read the a2l_probe_* constants of the compiled a2l_probe.c."""
    prefix = "a2l_probe_"
    values = {}
    with open(path, "rb") as f:
        obj = ELFFile(f)
        order = "little" if obj.little_endian else "big"
        for section in obj.iter_sections():
            if not isinstance(section, SymbolTableSection):
                continue
            for sym in section.iter_symbols():
                if not sym.name.startswith(prefix) or sym["st_info"]["type"] != "STT_OBJECT":
                    continue
                data_section = obj.get_section(sym["st_shndx"])
                data = data_section.data()[sym["st_value"]:sym["st_value"] + sym["st_size"]]
                key = sym.name[len(prefix):]
                values[key] = list(data) if key == "eth_ip" else int.from_bytes(data, order)
    return values


ALIGNMENT_KEYS = ("byte", "word", "long", "int64", "float32", "float64")

EVENT_DIRECTIONS = {0x04: "DAQ", 0x08: "STIM", 0x0C: "DAQ_STIM"}


def read_events(elf, symbols, variables):
    """Decode the XcpDaq_Events table built by XCP_DAQ_DEFINE_EVENT."""
    obj = {"symbol": "XcpDaq_Events", "file": "<xcp>", "line": 0}
    if obj["symbol"] not in symbols:
        return []
    address = lookup_symbol(symbols, obj)[0]
    layout = layout_of(lookup_type(variables, obj), obj["symbol"])
    element = layout["element"]
    offset = {m["name"]: m["offset"] for m in element["members"]}
    order = "little" if elf.little_endian else "big"

    events, short_names = [], set()
    for number in range(layout["dims"][0]):
        raw = read_bytes(elf, address + number * element["size"], element["size"], obj["symbol"])
        name_ptr = int.from_bytes(raw[offset["name"]:offset["name"] + 4], order)
        if name_ptr == 0:
            continue  # unused slot up to XCP_DAQ_MAX_EVENT_CHANNEL
        name = read_bytes(elf, name_ptr, raw[offset["nameLen"]], obj["symbol"]).decode("ascii", errors="replace")
        short = "".join(c for c in name if c.isalnum() or c == "_")[:8] or f"EV{number}"
        while short in short_names:
            short = short[:6] + f"{number:02d}"
        short_names.add(short)
        events.append({"number": number, "name": name, "short_name": short,
                       "direction": EVENT_DIRECTIONS.get(raw[offset["properties"]] & 0x0C, "DAQ"),
                       "cycle": raw[offset["cycle"]], "unit": raw[offset["timeunit"]]})
    return events


def xcp_settings(probe, events):
    """Translate cxcp configuration values into A2L IF_DATA XCP settings."""
    settings = {
        "protocol_version": probe["protocol_version"],
        "transport_version": probe["transport_version"],
        "max_cto": probe["max_cto"],
        "max_dto": probe["max_dto"],
        "byte_order": "MSB_FIRST" if probe["byte_order"] == 1 else "MSB_LAST",
        "address_granularity": {0: "BYTE", 2: "WORD", 4: "DWORD"}[probe["address_granularity"]],
        "daq": None,
        "ethernet": None,
    }
    if "daq_config_type" in probe:
        timestamp = None
        if "daq_timestamp_unit" in probe:
            timestamp = {"ticks": 1, "size": probe["daq_timestamp_size"], "unit": probe["daq_timestamp_unit"]}
        settings["daq"] = {
            "type": "DYNAMIC" if probe["daq_config_type"] == 1 else "STATIC",
            "max_daq": probe["daq_max_dynamic_entities"],
            "max_event_channel": probe["daq_max_event_channel"],
            "min_daq": 0,
            "max_odt_entry_size": probe["daq_max_odt_entry_size"],
            "timestamp": timestamp,
            "events": events,
        }
    if "eth_port" in probe:
        settings["ethernet"] = {
            "protocol": "TCP" if probe["eth_protocol"] == 1 else "UDP",
            "port": probe["eth_port"],
            "host": ".".join(str(b) for b in probe["eth_ip"]) if "eth_ip" in probe else None,
        }
    return settings


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("annotations", help="JSON written by a2l_extract.py")
    ap.add_argument("elf", help="linked ELF file")
    ap.add_argument("-o", "--output", required=True, help="resolved JSON to write")
    ap.add_argument("--epk-symbol", help="symbol holding the EPK string")
    ap.add_argument("--probe", required=True,
                    help="compiled a2l_probe.c (object file) with target alignments and XCP configuration")
    args = ap.parse_args()

    with open(args.annotations, encoding="utf-8") as f:
        annotations = json.load(f)

    try:
        with open(args.elf, "rb") as f:
            elf = ELFFile(f)
            if not elf.has_dwarf_info():
                raise ResolveError(f"{args.elf}: no DWARF info (build with -g)")
            symbols = read_symbols(elf)
            variables = read_variable_dies(elf.get_dwarf_info())

            objects = []
            for obj in annotations["objects"]:
                where = f"{obj['file']}:{obj['line']}"
                address, size, _, _ = lookup_symbol(symbols, obj)
                if address >> 28 in LOCAL_SEGMENTS:
                    raise ResolveError(f"{where}: '{obj['symbol']}' is at core-local address 0x{address:08X}; "
                                       "place it in a globally addressed section")
                layout = layout_of(lookup_type(variables, obj), where)
                if size and size != layout["size"]:
                    raise ResolveError(f"{where}: symbol size {size} does not match DWARF size {layout['size']}")
                obj = {**obj, "address": address, "layout": layout}
                objects.extend(flatten(obj, layout, annotations["struct_members"]))

            epk = None
            if args.epk_symbol in symbols:
                epk_obj = {"symbol": args.epk_symbol, "file": "<epk>", "line": 0}
                epk_addr = lookup_symbol(symbols, epk_obj)[0]
                epk = {"symbol": args.epk_symbol, "address": epk_addr,
                       "value": read_string(elf, epk_addr, args.epk_symbol)}
            elif args.epk_symbol:
                print(f"a2l_resolve: warning: EPK symbol '{args.epk_symbol}' not linked; "
                      "A2L is written without EPK", file=sys.stderr)

            probe = read_probe(args.probe)
            alignment = {key: probe[f"align_{key}"] for key in ALIGNMENT_KEYS if f"align_{key}" in probe}
            xcp = xcp_settings(probe, read_events(elf, symbols, variables))
            if xcp["daq"] is not None and not xcp["daq"]["events"]:
                print("a2l_resolve: warning: no XcpDaq_Events table linked; A2L has no DAQ events",
                      file=sys.stderr)
            byte_order = "MSB_LAST" if elf.little_endian else "MSB_FIRST"
    except ResolveError as e:
        print(f"a2l_resolve: error: {e}", file=sys.stderr)
        return 1

    names = {}
    for o in objects:
        if o["name"] in names:
            print(f"a2l_resolve: error: duplicate A2L name '{o['name']}'", file=sys.stderr)
            return 1
        names[o["name"]] = o

    os.makedirs(os.path.dirname(os.path.abspath(args.output)), exist_ok=True)
    with open(args.output, "w", encoding="utf-8") as f:
        json.dump({"project": annotations["project"], "byte_order": byte_order, "alignment": alignment,
                   "epk": epk, "xcp": xcp,
                   "compu_methods": annotations.get("compu_methods", {}), "objects": objects}, f, indent=2)
    print(f"a2l_resolve: {len(objects)} A2L objects -> {args.output}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
