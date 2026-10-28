"""Stage 3 of the A2L pipeline: render the resolved JSON as an ASAP2 1.71 file."""

import argparse
import json
import os
import struct
import sys

INT_RANGES = {"UBYTE": (0, 0xFF), "SBYTE": (-0x80, 0x7F), "UWORD": (0, 0xFFFF), "SWORD": (-0x8000, 0x7FFF),
              "ULONG": (0, 0xFFFFFFFF), "SLONG": (-0x80000000, 0x7FFFFFFF),
              "A_UINT64": (0, 0xFFFFFFFFFFFFFFFF), "A_INT64": (-0x8000000000000000, 0x7FFFFFFFFFFFFFFF)}
FLOAT_MAX = {"FLOAT32_IEEE": struct.unpack("<f", b"\xff\xff\x7f\x7f")[0], "FLOAT64_IEEE": sys.float_info.max}

# Subset of the ASAM XCP A2ML covering exactly what IF_DATA XCP below emits.
XCP_A2ML = """\
    /begin A2ML
      struct Protocol_Layer {
        uint;  /* XCP protocol layer version */
        uint;  /* T1 */
        uint;  /* T2 */
        uint;  /* T3 */
        uint;  /* T4 */
        uint;  /* T5 */
        uint;  /* T6 */
        uint;  /* T7 */
        uchar; /* MAX_CTO */
        uint;  /* MAX_DTO */
        enum { "BYTE_ORDER_MSB_LAST" = 0, "BYTE_ORDER_MSB_FIRST" = 1 };
        enum { "ADDRESS_GRANULARITY_BYTE" = 1, "ADDRESS_GRANULARITY_WORD" = 2, "ADDRESS_GRANULARITY_DWORD" = 4 };
      };
      struct Event {
        char[101]; /* EVENT_CHANNEL_NAME */
        char[9];   /* EVENT_CHANNEL_SHORT_NAME */
        uint;      /* EVENT_CHANNEL_NUMBER */
        enum { "DAQ" = 1, "STIM" = 2, "DAQ_STIM" = 3 };
        uchar;     /* MAX_DAQ_LIST */
        uchar;     /* TIME_CYCLE */
        uchar;     /* TIME_UNIT */
        uchar;     /* PRIORITY */
      };
      struct Daq {
        enum { "STATIC" = 0, "DYNAMIC" = 1 };
        uint;  /* MAX_DAQ */
        uint;  /* MAX_EVENT_CHANNEL */
        uchar; /* MIN_DAQ */
        enum { "OPTIMISATION_TYPE_DEFAULT" = 0, "OPTIMISATION_TYPE_ODT_TYPE_16" = 1,
               "OPTIMISATION_TYPE_ODT_TYPE_32" = 2, "OPTIMISATION_TYPE_ODT_TYPE_64" = 3,
               "OPTIMISATION_TYPE_ODT_TYPE_ALIGNMENT" = 4, "OPTIMISATION_TYPE_MAX_ENTRY_SIZE" = 5 };
        enum { "ADDRESS_EXTENSION_FREE" = 0, "ADDRESS_EXTENSION_ODT" = 1, "ADDRESS_EXTENSION_DAQ" = 3 };
        enum { "IDENTIFICATION_FIELD_TYPE_ABSOLUTE" = 0, "IDENTIFICATION_FIELD_TYPE_RELATIVE_BYTE" = 1,
               "IDENTIFICATION_FIELD_TYPE_RELATIVE_WORD" = 2, "IDENTIFICATION_FIELD_TYPE_RELATIVE_WORD_ALIGNED" = 3 };
        enum { "GRANULARITY_ODT_ENTRY_SIZE_DAQ_BYTE" = 1, "GRANULARITY_ODT_ENTRY_SIZE_DAQ_WORD" = 2,
               "GRANULARITY_ODT_ENTRY_SIZE_DAQ_DWORD" = 4, "GRANULARITY_ODT_ENTRY_SIZE_DAQ_DLONG" = 8 };
        uchar; /* MAX_ODT_ENTRY_SIZE_DAQ */
        enum { "NO_OVERLOAD_INDICATION" = 0, "OVERLOAD_INDICATION_PID" = 1, "OVERLOAD_INDICATION_EVENT" = 2 };
        taggedstruct {
          block "TIMESTAMP_SUPPORTED" struct {
            uint; /* TIMESTAMP_TICKS */
            enum { "NO_TIME_STAMP" = 0, "SIZE_BYTE" = 1, "SIZE_WORD" = 2, "SIZE_DWORD" = 4 };
            enum { "UNIT_1NS" = 0, "UNIT_10NS" = 1, "UNIT_100NS" = 2, "UNIT_1US" = 3, "UNIT_10US" = 4,
                   "UNIT_100US" = 5, "UNIT_1MS" = 6, "UNIT_10MS" = 7, "UNIT_100MS" = 8, "UNIT_1S" = 9,
                   "UNIT_1PS" = 10, "UNIT_10PS" = 11, "UNIT_100PS" = 12 };
          };
          (block "EVENT" struct Event)*;
        };
      };
      taggedstruct Common_Parameters {
        block "PROTOCOL_LAYER" struct Protocol_Layer;
        block "DAQ" struct Daq;
      };
      struct IP_Parameters {
        uint; /* XCP on UDP_IP / TCP_IP version */
        uint; /* PORT */
        taggedstruct { /* optional: omitted when the ECU gets its IP by DHCP */
          "HOST_NAME" char[256];
          "ADDRESS" char[15];
        };
      };
      block "IF_DATA" taggedunion if_data {
        "XCP" struct {
          taggedstruct Common_Parameters;
          taggedstruct {
            block "XCP_ON_UDP_IP" struct {
              struct IP_Parameters;
              taggedstruct Common_Parameters;
            };
            block "XCP_ON_TCP_IP" struct {
              struct IP_Parameters;
              taggedstruct Common_Parameters;
            };
          };
        };
      };
    /end A2ML
"""


def a2l_string(s):
    return '"' + str(s).replace("\\", "\\\\").replace('"', '\\"') + '"'


def num(x):
    return str(int(x)) if float(x).is_integer() and abs(x) < 1e15 else repr(float(x))


IDENTICAL = {"type": "IDENTICAL"}


class GenerateError(Exception):
    pass


def default_format(compu_type, datatype=None):
    if compu_type == "TAB_VERB" or (compu_type == "IDENTICAL" and datatype in INT_RANGES):
        return "%.0"
    return "%.3"


def compu_params(compu):
    """Hashable form of a conversion's parameters (for deduplication)."""
    if "coeffs" in compu:
        return tuple(compu["coeffs"])
    if "table" in compu:
        return tuple(tuple(e) for e in compu["table"])
    return compu.get("formula")


class CompuMethods:
    """Named compu methods from the sources plus deduplicated anonymous ones
    for inline conversions."""

    def __init__(self, named):
        self.methods = {}
        self._anonymous = {}
        for name, cm in named.items():
            self._add(name, cm, cm.get("format") or default_format(cm["type"]), cm.get("unit", ""),
                      cm.get("description", ""))

    def _add(self, name, compu, fmt, unit, description):
        self.methods[name] = {"compu": compu, "format": fmt, "unit": unit, "description": description}

    def for_object(self, obj):
        """Return (compu method name, conversion, is_reference)."""
        compu = obj.get("compu") or IDENTICAL
        if "ref" in compu:
            if compu["ref"] not in self.methods:
                raise GenerateError(f"{obj['file']}:{obj['line']}: unknown compu method '{compu['ref']}'")
            return compu["ref"], self.methods[compu["ref"]]["compu"], True
        fmt = obj.get("format") or default_format(compu["type"], obj["datatype"])
        unit = obj.get("unit", "")
        key = (compu["type"], compu_params(compu), fmt, unit)
        if key not in self._anonymous:
            n = len(self._anonymous)
            while f"CM_auto_{n}" in self.methods:
                n += 1
            self._anonymous[key] = f"CM_auto_{n}"
            self._add(self._anonymous[key], compu, fmt, unit, "")
        return self._anonymous[key], compu, False

    def render(self):
        out = []
        tables = []
        for name, m in self.methods.items():
            compu, ctype = m["compu"], m["compu"]["type"]
            out.append(f"    /begin COMPU_METHOD {name} {a2l_string(m['description'])}\n"
                       f"      {ctype} {a2l_string(m['format'])} {a2l_string(m['unit'])}\n")
            if ctype == "LINEAR":
                out.append("      COEFFS_LINEAR " + " ".join(num(c) for c in compu["coeffs"]) + "\n")
            elif ctype == "RAT_FUNC":
                out.append("      COEFFS " + " ".join(num(c) for c in compu["coeffs"]) + "\n")
            elif ctype == "FORM":
                out.append(f"      /begin FORMULA {a2l_string(compu['formula'])}\n      /end FORMULA\n")
            elif ctype.startswith("TAB_"):
                tab = f"{'VT' if ctype == 'TAB_VERB' else 'CT'}_{name}"
                out.append(f"      COMPU_TAB_REF {tab}\n")
                tables.append((tab, compu))
            out.append("    /end COMPU_METHOD\n")
        for tab, compu in tables:
            block = "COMPU_VTAB" if compu["type"] == "TAB_VERB" else "COMPU_TAB"
            out.append(f"    /begin {block} {tab} \"\" {compu['type']} {len(compu['table'])}\n")
            for raw, value in compu["table"]:
                text = a2l_string(value) if compu["type"] == "TAB_VERB" else num(value)
                out.append(f"      {num(raw)} {text}\n")
            out.append(f"    /end {block}\n")
        return "".join(out)


def to_physical(compu, raw):
    """Physical value for a raw value, or None if not derivable."""
    ctype = compu["type"]
    if ctype == "IDENTICAL":
        return raw
    if ctype == "LINEAR":
        a, b = compu["coeffs"]
        return a * raw + b
    if ctype == "RAT_FUNC":
        a, b, c, d, e, f = compu["coeffs"]
        if a == d == e == 0 and b != 0:  # linear case: raw = (b*phys + c) / f
            return (f * raw - c) / b
    return None


def limits(obj, compu):
    if obj.get("limits"):
        return obj["limits"]
    ctype = compu["type"]
    if ctype == "TAB_VERB":
        values = [v for v, _ in compu["table"]]
        return [min(values), max(values)]
    if ctype in ("TAB_INTP", "TAB_NOINTP"):
        values = [p for _, p in compu["table"]]
        return [min(values), max(values)]
    if obj["datatype"] in FLOAT_MAX and ctype != "FORM":
        m = FLOAT_MAX[obj["datatype"]]
        return [-m, m]
    lo, hi = INT_RANGES.get(obj["datatype"], (None, None))
    phys = [to_physical(compu, r) for r in (lo, hi)] if lo is not None else [None]
    if None in phys:
        raise GenerateError(f"{obj['file']}:{obj['line']}: '{obj['name']}' uses a {ctype} conversion; "
                            "add \\a2l_limits <lo> <hi>")
    return sorted(phys)


AXIS_TAGS = ("axis_x", "axis_y", "axis_z")


def axis_descr(axis, size, by_name, compu_methods, where):
    """AXIS_DESCR block for one axis of a CURVE / MAP / CUBOID."""
    if "ref" in axis:
        points = by_name.get(axis["ref"])
        if points is None or points["kind"] != "axis_pts":
            raise GenerateError(f"{where}: axis '{axis['ref']}' is not an \\a2l_axis_pts object")
        if points["dims"] != [size]:
            raise GenerateError(f"{where}: axis '{axis['ref']}' has {points['dims'][0]} points "
                                f"but the array dimension is {size}")
        cm, compu, _ = compu_methods.for_object(points)
        lo, hi = limits(points, compu)
        return (f"      /begin AXIS_DESCR\n"
                f"        COM_AXIS {points.get('input', 'NO_INPUT_QUANTITY')} {cm} {size} {num(lo)} {num(hi)}\n"
                f"        AXIS_PTS_REF {points['name']}\n"
                f"      /end AXIS_DESCR")

    offset, step = axis["fix"]
    cm = axis.get("compu_ref", "NO_COMPU_METHOD")
    compu = compu_methods.methods[cm]["compu"] if cm != "NO_COMPU_METHOD" else IDENTICAL
    phys = [to_physical(compu, raw) for raw in (offset, offset + step * (size - 1))]
    if None in phys:
        raise GenerateError(f"{where}: fixed axis conversion '{cm}' must be IDENTICAL, LINEAR or a linear RAT_FUNC")
    lo, hi = sorted(phys)
    return (f"      /begin AXIS_DESCR\n"
            f"        FIX_AXIS NO_INPUT_QUANTITY {cm} {size} {num(lo)} {num(hi)}\n"
            f"        FIX_AXIS_PAR_DIST {num(offset)} {num(step)} {size}\n"
            f"      /end AXIS_DESCR")


ALIGNMENT_KEYWORDS = {"byte": "ALIGNMENT_BYTE", "word": "ALIGNMENT_WORD", "long": "ALIGNMENT_LONG",
                      "int64": "ALIGNMENT_INT64", "float32": "ALIGNMENT_FLOAT32_IEEE",
                      "float64": "ALIGNMENT_FLOAT64_IEEE"}


def render(resolved):
    out = []
    w = out.append
    compu_methods = CompuMethods(resolved.get("compu_methods", {}))
    layouts = set()

    axis_layouts = set()
    objects = sorted(resolved["objects"], key=lambda o: o["name"])
    by_name = {o["name"]: o for o in objects}

    body = []
    for obj in objects:
        where = f"{obj['file']}:{obj['line']}"
        cm, compu, is_ref = compu_methods.for_object(obj)
        lo, hi = limits(obj, compu)
        desc = a2l_string(obj.get("description", ""))
        axes = [obj[t] for t in AXIS_TAGS if obj.get(t)]
        extra = []
        if axes:
            if len(axes) != len(obj["dims"]):
                raise GenerateError(f"{where}: '{obj['name']}' has {len(obj['dims'])} array dimension(s) "
                                    f"but {len(axes)} axis tag(s)")
            # C index order is [z][y][x]: the last dimension belongs to the x axis.
            for axis, size in zip(axes, reversed(obj["dims"])):
                extra.append(axis_descr(axis, size, by_name, compu_methods, where))
        elif obj["dims"] and obj["kind"] != "axis_pts":
            extra.append("      MATRIX_DIM " + " ".join(str(d) for d in obj["dims"]))
        if is_ref and obj.get("format"):
            extra.append(f"      FORMAT {a2l_string(obj['format'])}")
        if is_ref and obj.get("unit"):
            extra.append(f"      PHYS_UNIT {a2l_string(obj['unit'])}")
        extra.append(f"      SYMBOL_LINK {a2l_string(obj['symbol'])} {obj['symbol_offset']}")
        extra = "".join(e + "\n" for e in extra)

        if obj["kind"] == "measurement":
            body.append(f"    /begin MEASUREMENT {obj['name']} {desc}\n"
                        f"      {obj['datatype']} {cm} 0 0 {num(lo)} {num(hi)}\n"
                        f"      ECU_ADDRESS 0x{obj['address']:08X}\n"
                        f"{extra}    /end MEASUREMENT\n")
        elif obj["kind"] == "axis_pts":
            if len(obj["dims"]) != 1:
                raise GenerateError(f"{where}: AXIS_PTS '{obj['name']}' must be a one-dimensional array")
            input_quantity = obj.get("input", "NO_INPUT_QUANTITY")
            if input_quantity != "NO_INPUT_QUANTITY" and by_name.get(input_quantity, {}).get("kind") != "measurement":
                raise GenerateError(f"{where}: \\a2l_input '{input_quantity}' is not a measurement")
            axis_layouts.add(obj["datatype"])
            body.append(f"    /begin AXIS_PTS {obj['name']} {desc}\n"
                        f"      0x{obj['address']:08X} {input_quantity} RL_AX_{obj['datatype']} 0 {cm}"
                        f" {obj['dims'][0]} {num(lo)} {num(hi)}\n"
                        f"{extra}    /end AXIS_PTS\n")
        else:
            layouts.add(obj["datatype"])
            if axes:
                ctype = ("CURVE", "MAP", "CUBOID")[len(axes) - 1]
            else:
                ctype = "VAL_BLK" if obj["dims"] else "VALUE"
            body.append(f"    /begin CHARACTERISTIC {obj['name']} {desc}\n"
                        f"      {ctype} 0x{obj['address']:08X} RL_{obj['datatype']} 0 {cm} {num(lo)} {num(hi)}\n"
                        f"{extra}    /end CHARACTERISTIC\n")

    project = resolved["project"]
    description = a2l_string(project["description"])
    w("ASAP2_VERSION 1 71\n")
    w(f"/begin PROJECT {project['project']} {description}\n")
    w(f"  /begin MODULE {project['module']} {description}\n")
    xcp = resolved.get("xcp")
    if xcp:
        w(XCP_A2ML)

    w("    /begin MOD_COMMON \"\"\n")
    w(f"      BYTE_ORDER {resolved['byte_order']}\n")
    for key, value in resolved["alignment"].items():
        w(f"      {ALIGNMENT_KEYWORDS[key]} {value}\n")
    w("    /end MOD_COMMON\n")

    epk = resolved.get("epk")
    if epk:
        w("    /begin MOD_PAR \"\"\n"
          f"      ADDR_EPK 0x{epk['address']:08X}\n"
          f"      EPK {a2l_string(epk['value'])}\n"
          "    /end MOD_PAR\n")

    if xcp:
        w(render_if_data(xcp))

    # Values only (axes live in AXIS_PTS objects or are fixed). ROW_DIR: x varies fastest, as in C [y][x].
    for dtype in sorted(layouts):
        w(f"    /begin RECORD_LAYOUT RL_{dtype}\n      FNC_VALUES 1 {dtype} ROW_DIR DIRECT\n    /end RECORD_LAYOUT\n")
    for dtype in sorted(axis_layouts):
        w(f"    /begin RECORD_LAYOUT RL_AX_{dtype}\n      AXIS_PTS_X 1 {dtype} INDEX_INCR DIRECT\n"
          "    /end RECORD_LAYOUT\n")

    w(compu_methods.render())

    out.extend(body)
    w("  /end MODULE\n")
    w("/end PROJECT\n")
    return "".join(out)


TIMESTAMP_SIZES = {1: "SIZE_BYTE", 2: "SIZE_WORD", 4: "SIZE_DWORD"}
TIMESTAMP_UNITS = ["UNIT_1NS", "UNIT_10NS", "UNIT_100NS", "UNIT_1US", "UNIT_10US", "UNIT_100US", "UNIT_1MS",
                   "UNIT_10MS", "UNIT_100MS", "UNIT_1S", "UNIT_1PS", "UNIT_10PS", "UNIT_100PS"]


def render_if_data(xcp):
    lines = [
        "    /begin IF_DATA XCP",
        "      /begin PROTOCOL_LAYER",
        f"        0x{xcp['protocol_version']:04X} 1000 2000 0 0 0 0 0",
        f"        {xcp['max_cto']} {xcp['max_dto']}",
        f"        BYTE_ORDER_{xcp['byte_order']} ADDRESS_GRANULARITY_{xcp['address_granularity']}",
        "      /end PROTOCOL_LAYER",
    ]
    daq = xcp.get("daq")
    if daq:
        lines += [
            "      /begin DAQ",
            f"        {daq['type']} {daq['max_daq']} {daq['max_event_channel']} {daq['min_daq']}",
            "        OPTIMISATION_TYPE_DEFAULT ADDRESS_EXTENSION_FREE IDENTIFICATION_FIELD_TYPE_ABSOLUTE",
            f"        GRANULARITY_ODT_ENTRY_SIZE_DAQ_BYTE {daq['max_odt_entry_size']} NO_OVERLOAD_INDICATION",
        ]
        ts = daq.get("timestamp")
        if ts:
            lines += ["        /begin TIMESTAMP_SUPPORTED",
                      f"          {ts['ticks']} {TIMESTAMP_SIZES[ts['size']]} {TIMESTAMP_UNITS[ts['unit']]}",
                      "        /end TIMESTAMP_SUPPORTED"]
        for ev in daq["events"]:
            lines += ["        /begin EVENT",
                      f"          {a2l_string(ev['name'])} {a2l_string(ev['short_name'])} {ev['number']}"
                      f" {ev['direction']} 1 {ev['cycle']} {ev['unit']} 0",
                      "        /end EVENT"]
        lines.append("      /end DAQ")
    eth = xcp.get("ethernet")
    if eth:
        # The address is only known if it is fixed in xcp_config.h; with DHCP the tool supplies it.
        address = f" ADDRESS {a2l_string(eth['host'])}" if eth["host"] else ""
        block = f"XCP_ON_{eth['protocol']}_IP"
        lines += [f"      /begin {block}",
                  f"        0x{xcp['transport_version']:04X} {eth['port']}{address}",
                  f"      /end {block}"]
    lines.append("    /end IF_DATA")
    return "\n".join(lines) + "\n"


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("resolved", help="JSON written by a2l_resolve.py")
    ap.add_argument("-o", "--output", required=True, help="A2L file to write")
    args = ap.parse_args()

    with open(args.resolved, encoding="utf-8") as f:
        resolved = json.load(f)

    try:
        text = render(resolved)
    except GenerateError as e:
        print(f"a2l_generate: error: {e}", file=sys.stderr)
        return 1
    os.makedirs(os.path.dirname(os.path.abspath(args.output)), exist_ok=True)
    with open(args.output, "w", encoding="utf-8", newline="\n") as f:
        f.write(text)
    print(f"a2l_generate: {len(resolved['objects'])} objects -> {args.output}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
