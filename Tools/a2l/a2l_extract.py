"""Stage 1 of the A2L pipeline: extract \\a2l_* Doxygen tags from C sources.

Scans C/H files for Doxygen comments (/** ... */ or /**< ... */) containing
\\a2l_* (or @a2l_*) tags and associates each comment with the declaration it
documents. Writes a JSON file in which addresses and type layouts are still
placeholders (null); they are filled in by a2l_resolve.py from the linked ELF.

Supported tags (arguments run to the end of the line or the next tag):
    \\a2l_measurement             mark a variable as MEASUREMENT
    \\a2l_characteristic          mark a variable as CHARACTERISTIC
    \\a2l_name       <ident>      A2L name (default: symbol name)
    \\a2l_unit       <text>       physical unit
    \\a2l_format     <%L.P>       display format, e.g. %6.2
    \\a2l_limits     <lo> <hi>    physical limits (default: derived from datatype
                                 and conversion; required for FORM / RAT_FUNC)

Conversion tags (at most one per comment; none means IDENTICAL):
    \\a2l_conversion <a> <b>          LINEAR    phys = a * raw + b
    \\a2l_rat_func   <a> <b> <c> <d> <e> <f>
                                     RAT_FUNC  raw = (a*p^2 + b*p + c) / (d*p^2 + e*p + f)
    \\a2l_formula    "<expr in X1>"   FORM      e.g. "X1 * 0.05 + 1"
    \\a2l_tab_intp   <raw>=<phys>..   TAB_INTP  interpolated table
    \\a2l_tab_nointp <raw>=<phys>..   TAB_NOINTP table without interpolation
    \\a2l_enum       <v>=<text>..     TAB_VERB  e.g. 0=Off 1="Half on"
    \\a2l_compu_ref  <name>           reference to a named compu method

Named compu methods are defined in a comment of their own (not attached to a
declaration) that starts with \\a2l_compu_method <name>, followed by one
conversion tag and optionally \\brief, \\a2l_unit and \\a2l_format. Objects
that reference one inherit its unit and format; their own \\a2l_unit /
\\a2l_format override them.

Project (exactly one stand-alone comment in the code base):
    \\a2l_project    <ident>      A2L PROJECT name; \\brief is the description
    \\a2l_module     <ident>      A2L MODULE name (default: project name)

Axes, curves and maps:
    \\a2l_axis_pts                mark a 1-D array as AXIS_PTS (shared axis breakpoints)
    \\a2l_input      <name>       AXIS_PTS only: measurement the axis is looked up with
    \\a2l_axis_x     <axis_pts>   characteristic axis referencing an AXIS_PTS (COM_AXIS)
    \\a2l_axis_x     fix <offset> <step> [<compu method>]
                                 fixed axis offset + i * step (FIX_AXIS, raw values)
    \\a2l_axis_y / \\a2l_axis_z   same for the 2nd / 3rd axis

A characteristic array with axis tags becomes CURVE (1 axis), MAP (2) or
CUBOID (3); the number of axes must equal the number of array dimensions. The
C index order is [z][y][x], i.e. x is the innermost (last) index. Without axis
tags an array characteristic is a VAL_BLK. One AXIS_PTS can be referenced by
any number of curves and maps.

Tags on struct members (inside a struct/typedef body) apply to every annotated
variable of that struct type and override the variable-level tags. They must
not contain \\a2l_measurement / \\a2l_characteristic.
"""

import argparse
import json
import os
import re
import shlex
import sys

KIND_TAGS = {"measurement", "characteristic", "axis_pts"}
CONVERSION_TAGS = {"conversion", "rat_func", "formula", "tab_intp", "tab_nointp", "enum", "compu_ref"}
AXIS_TAGS = ("axis_x", "axis_y", "axis_z")
VALUE_TAGS = {"name", "unit", "format", "limits", "input", "module"} | CONVERSION_TAGS | set(AXIS_TAGS)
# Stand-alone comment blocks (not attached to a declaration): tag -> example name.
NAMED_BLOCK_TAGS = {"compu_method": "CM_Temperature", "project": "My_Project"}

COMMENT_RE = re.compile(r"/\*[\s\S]*?\*/|//[^\n]*")
# Doxygen-escaped tags (\\a2l_...) in prose are not tags.
TAG_RE = re.compile(r"(?<!\\)[\\@](a2l_\w+|brief)\b[ \t]*((?:(?![\\@](?:a2l_|brief\b))[^\n])*)")
IDENT_RE = re.compile(r"[A-Za-z_]\w*")
FORMAT_RE = re.compile(r"^%\d*\.\d+$")


class ExtractError(Exception):
    pass


def mask_source(text):
    """Return text with comments, string/char literals and preprocessor lines
    replaced by spaces (newlines kept), so offsets stay identical."""
    out = list(text)
    i, n = 0, len(text)
    at_line_start = True

    def blank(a, b):
        for k in range(a, b):
            if out[k] != "\n":
                out[k] = " "

    while i < n:
        c = text[i]
        if at_line_start and c in " \t":
            i += 1
            continue
        if at_line_start and c == "#":
            j = i
            while j < n and text[j] != "\n":
                if text[j] == "\\" and j + 1 < n and text[j + 1] == "\n":
                    j += 2
                    continue
                j += 1
            blank(i, j)
            i = j
            continue
        at_line_start = False
        if c == "\n":
            at_line_start = True
            i += 1
        elif text.startswith("/*", i):
            j = text.find("*/", i + 2)
            j = n if j < 0 else j + 2
            blank(i, j)
            i = j
        elif text.startswith("//", i):
            j = text.find("\n", i)
            j = n if j < 0 else j
            blank(i, j)
            i = j
        elif c in "\"'":
            j = i + 1
            while j < n and text[j] != c and text[j] != "\n":
                j += 2 if text[j] == "\\" else 1
            blank(i, min(j + 1, n))
            i = j + 1
        else:
            i += 1
    return "".join(out)


def line_of(text, pos):
    return text.count("\n", 0, pos) + 1


def comment_body(raw):
    """Strip comment delimiters and leading '*' of each line."""
    body = raw[3:-2]
    if body.startswith("<"):
        body = body[1:]
    lines = [re.sub(r"^\s*\*?", "", ln, count=1) for ln in body.split("\n")]
    return "\n".join(lines)


def parse_tags(body, where):
    """Parse the tags of one comment. Returns (kind, attrs, description)."""
    kind = None
    attrs = {}
    brief = None
    for m in TAG_RE.finditer(body):
        tag, args = m.group(1), m.group(2).strip()
        if tag == "brief":
            brief = args
            continue
        tag = tag[len("a2l_"):]
        if tag in KIND_TAGS or tag in NAMED_BLOCK_TAGS:
            if kind is not None:
                raise ExtractError(f"{where}: more than one of \\a2l_measurement / \\a2l_characteristic "
                                   "/ \\a2l_axis_pts / \\a2l_compu_method / \\a2l_project")
            if tag in NAMED_BLOCK_TAGS:
                if not IDENT_RE.fullmatch(args):
                    raise ExtractError(f"{where}: \\a2l_{tag} needs a name, e.g. {NAMED_BLOCK_TAGS[tag]}")
                attrs["name"] = args
            elif args:
                raise ExtractError(f"{where}: \\a2l_{tag} takes no arguments")
            kind = tag
        elif tag in VALUE_TAGS:
            if tag in attrs:
                raise ExtractError(f"{where}: duplicate tag \\a2l_{tag}")
            attrs[tag] = parse_value(tag, args, where)
        else:
            raise ExtractError(f"{where}: unknown tag \\a2l_{tag}")

    conversions = [t for t in attrs if t in CONVERSION_TAGS]
    if len(conversions) > 1:
        raise ExtractError(f"{where}: " + " and ".join(f"\\a2l_{t}" for t in conversions)
                           + " are mutually exclusive")
    if conversions:
        attrs["compu"] = attrs.pop(conversions[0])

    axes = [t for t in AXIS_TAGS if t in attrs]
    if axes and kind != "characteristic":
        raise ExtractError(f"{where}: \\a2l_{axes[0]} is only allowed on a \\a2l_characteristic")
    if axes != list(AXIS_TAGS[:len(axes)]):
        raise ExtractError(f"{where}: axes must be given in order x, y, z without gaps")
    if "input" in attrs and kind != "axis_pts":
        raise ExtractError(f"{where}: \\a2l_input is only allowed on an \\a2l_axis_pts")
    if "module" in attrs and kind != "project":
        raise ExtractError(f"{where}: \\a2l_module is only allowed together with \\a2l_project")
    if kind == "project" and set(attrs) - {"name", "module"}:
        raise ExtractError(f"{where}: \\a2l_project only takes \\a2l_module and \\brief")

    if brief is None:
        # Free text before the first command is the description.
        brief = re.split(r"[\\@]\w+", body, maxsplit=1)[0]
    description = " ".join(brief.split())
    return kind, attrs, description


def parse_number(s, tag, where):
    try:
        return float(s)
    except ValueError:
        raise ExtractError(f"{where}: \\a2l_{tag}: '{s}' is not a number") from None


def parse_value(tag, args, where):
    if not args:
        raise ExtractError(f"{where}: \\a2l_{tag} needs an argument")
    if tag == "name":
        if not re.fullmatch(r"[A-Za-z_][\w.\[\]]*", args):
            raise ExtractError(f"{where}: \\a2l_name: '{args}' is not a valid A2L identifier")
        return args
    if tag == "unit":
        return args[1:-1] if len(args) >= 2 and args[0] == args[-1] == '"' else args
    if tag == "format":
        if not FORMAT_RE.match(args):
            raise ExtractError(f"{where}: \\a2l_format: '{args}' must look like %6.2")
        return args
    if tag in ("conversion", "limits", "rat_func"):
        parts = args.split()
        count = 6 if tag == "rat_func" else 2
        if len(parts) != count:
            raise ExtractError(f"{where}: \\a2l_{tag} needs exactly {count} numbers")
        numbers = [parse_number(p, tag, where) for p in parts]
        if tag == "conversion":
            return {"type": "LINEAR", "coeffs": numbers}
        if tag == "rat_func":
            return {"type": "RAT_FUNC", "coeffs": numbers}
        return numbers
    if tag == "formula":
        formula = args[1:-1] if len(args) >= 2 and args[0] == args[-1] == '"' else args
        if "X" not in formula.upper():
            raise ExtractError(f"{where}: \\a2l_formula: '{formula}' does not use the input variable X1")
        return {"type": "FORM", "formula": formula}
    if tag == "module":
        if not IDENT_RE.fullmatch(args):
            raise ExtractError(f"{where}: \\a2l_module: '{args}' is not a valid identifier")
        return args
    if tag == "input":
        if not re.fullmatch(r"[A-Za-z_][\w.\[\]]*", args):
            raise ExtractError(f"{where}: \\a2l_input: '{args}' is not a valid A2L identifier")
        return args
    if tag in AXIS_TAGS:
        parts = args.split()
        if parts[0] == "fix":
            if len(parts) not in (3, 4):
                raise ExtractError(f"{where}: \\a2l_{tag} fix needs <offset> <step> [<compu method>]")
            axis = {"fix": [parse_number(p, tag, where) for p in parts[1:3]]}
            if len(parts) == 4:
                if not IDENT_RE.fullmatch(parts[3]):
                    raise ExtractError(f"{where}: \\a2l_{tag}: '{parts[3]}' is not a valid identifier")
                axis["compu_ref"] = parts[3]
            if axis["fix"][1] == 0:
                raise ExtractError(f"{where}: \\a2l_{tag}: fixed axis step must not be 0")
            return axis
        if len(parts) != 1 or not re.fullmatch(r"[A-Za-z_][\w.\[\]]*", parts[0]):
            raise ExtractError(f"{where}: \\a2l_{tag} needs an AXIS_PTS name or 'fix <offset> <step>'")
        return {"ref": parts[0]}
    if tag == "compu_ref":
        if not IDENT_RE.fullmatch(args):
            raise ExtractError(f"{where}: \\a2l_compu_ref: '{args}' is not a valid identifier")
        return {"ref": args}
    if tag in ("enum", "tab_intp", "tab_nointp"):
        entries = []
        try:
            tokens = shlex.split(args, posix=True)
        except ValueError as e:
            raise ExtractError(f"{where}: \\a2l_{tag}: {e}") from None
        for tok in tokens:
            value, sep, text = tok.partition("=")
            if not sep or not text:
                raise ExtractError(f"{where}: \\a2l_{tag}: '{tok}' must be <raw>=<value>")
            if tag == "enum":
                try:
                    entries.append([int(value, 0), text])
                except ValueError:
                    raise ExtractError(f"{where}: \\a2l_enum: '{value}' is not an integer") from None
            else:
                entries.append([parse_number(value, tag, where), parse_number(text, tag, where)])
        raws = [e[0] for e in entries]
        if len(set(raws)) != len(raws):
            raise ExtractError(f"{where}: \\a2l_{tag}: duplicate raw value")
        if tag == "enum":
            return {"type": "TAB_VERB", "table": entries}
        if len(entries) < 2:
            raise ExtractError(f"{where}: \\a2l_{tag} needs at least two points")
        return {"type": tag.upper(), "table": sorted(entries)}
    raise AssertionError(tag)


def declarator_name(decl, where):
    """Return the identifier declared by a C declaration like
    'CORE0_DLMU_NC volatile uint16 g_rpm[4] = {0}'."""
    depth = 0
    cut = len(decl)
    for k, ch in enumerate(decl):
        if ch in "([{":
            depth += 1
        elif ch in ")]}":
            depth -= 1
        elif ch == "=" and depth == 0:
            cut = k
            break
    decl = decl[:cut]
    if re.search(r"\)\s*$", decl) and "(" in decl and not decl.lstrip().startswith("__attribute__"):
        raise ExtractError(f"{where}: A2L tags on a function declaration are not supported")
    decl = re.sub(r"\[[^\]]*\]", " ", decl)
    decl = re.sub(r"__attribute__\s*\(\(.*?\)\)", " ", decl)
    decl = re.sub(r"\([^()]*\)", " ", decl)  # macro arguments like IFX_ALIGN(4)
    idents = IDENT_RE.findall(decl)
    if not idents:
        raise ExtractError(f"{where}: cannot find the declared symbol")
    return idents[-1]


def enclosing_scope(masked, pos):
    """Return (kind, struct_name) of the brace scope at pos.
    kind is 'file', 'struct' or 'block'."""
    depth = 0
    k = pos - 1
    while k >= 0:
        ch = masked[k]
        if ch == "}":
            depth += 1
        elif ch == "{":
            if depth == 0:
                break
            depth -= 1
        k -= 1
    if k < 0:
        return "file", None
    head = masked[max(0, k - 200):k]
    m = re.search(r"\b(struct|union)\s*(\w*)\s*$", head)
    if not m:
        return "block", None
    tag_name = m.group(2) or None
    # Find the matching '}' and an optional typedef name after it.
    depth = 0
    for j in range(k, len(masked)):
        if masked[j] == "{":
            depth += 1
        elif masked[j] == "}":
            depth -= 1
            if depth == 0:
                tail = masked[j + 1:j + 200]
                tm = re.match(r"\s*(\w+)\s*;", tail)
                is_typedef = re.search(r"\btypedef\s+(struct|union)\s*\w*\s*$", head)
                if tm and is_typedef:
                    return "struct", tm.group(1)
                break
    if tag_name:
        return "struct", tag_name
    raise ExtractError("anonymous struct without typedef name")


def extract_file(path, rel):
    with open(path, encoding="utf-8", errors="replace") as f:
        text = f.read()
    masked = mask_source(text)
    variables, members, compu_methods, projects = [], [], [], []

    for m in COMMENT_RE.finditer(text):
        raw = m.group(0)
        if not (raw.startswith("/**") or raw.startswith("/*!")) or raw == "/**/":
            continue
        if not re.search(r"[\\@]a2l_", raw):
            continue
        line = line_of(text, m.start())
        where = f"{rel}:{line}"
        trailing = raw.startswith("/**<") or raw.startswith("/*!<")
        kind, attrs, description = parse_tags(comment_body(raw), where)
        if kind is None and not attrs:
            continue  # only escaped tags, e.g. documentation about the tags

        if kind in NAMED_BLOCK_TAGS and trailing:
            raise ExtractError(f"{where}: \\a2l_{kind} must be in a comment of its own")

        if kind == "project":
            projects.append({"project": attrs["name"], "module": attrs.get("module", attrs["name"]),
                             "description": description, "file": rel, "line": line})
            continue

        if kind == "compu_method":
            # Stand-alone definition, not attached to a declaration.
            for tag in ("limits",):
                if tag in attrs:
                    raise ExtractError(f"{where}: \\a2l_{tag} is not allowed in a compu method definition")
            compu = attrs.get("compu", {"type": "IDENTICAL"})
            if "ref" in compu:
                raise ExtractError(f"{where}: a compu method definition cannot reference another one")
            compu_methods.append({"name": attrs["name"], "file": rel, "line": line, "description": description,
                                  **{k: attrs[k] for k in ("unit", "format") if k in attrs}, **compu})
            continue

        if trailing:
            # Declaration precedes the comment, terminated by ';' or ','.
            end = m.start()
            seg = masked[:end].rstrip()
            if not seg or seg[-1] not in ";,":
                raise ExtractError(f"{where}: trailing comment does not follow a declaration")
            decl_end = len(seg) - 1
            start = max(seg.rfind(";", 0, decl_end), seg.rfind("{", 0, decl_end), seg.rfind("}", 0, decl_end)) + 1
            decl_pos = start
            decl = masked[start:decl_end]
        else:
            semi = masked.find(";", m.end())
            if semi < 0:
                raise ExtractError(f"{where}: no declaration after A2L comment")
            decl_pos = m.end()
            decl = masked[decl_pos:semi]
            if "{" in decl.split("=", 1)[0]:
                raise ExtractError(f"{where}: A2L comment must precede a variable declaration")

        decl = " ".join(decl.split())
        symbol = declarator_name(decl, where)
        if re.search(r"\b(typedef)\b", decl):
            raise ExtractError(f"{where}: A2L tags on a typedef are not supported; annotate the variable")

        try:
            scope, struct_name = enclosing_scope(masked, decl_pos)
        except ExtractError as e:
            raise ExtractError(f"{where}: {e}") from None

        if scope == "struct":
            if kind is not None:
                raise ExtractError(f"{where}: struct member '{symbol}' must not carry \\a2l_{kind}; "
                                   "annotate the variable instead")
            members.append({"struct": struct_name, "member": symbol, "file": rel, "line": line,
                            "description": description, **attrs})
        elif scope == "block":
            raise ExtractError(f"{where}: '{symbol}' is not at file scope")
        else:
            if kind is None:
                raise ExtractError(f"{where}: '{symbol}' needs \\a2l_measurement, \\a2l_characteristic "
                                   "or \\a2l_axis_pts")
            if re.search(r"\bextern\b", decl):
                raise ExtractError(f"{where}: annotate the definition of '{symbol}', not the extern declaration")
            variables.append({"kind": kind, "symbol": symbol, "name": attrs.pop("name", symbol),
                              "file": rel, "line": line, "description": description, **attrs,
                              "address": None, "layout": None})
    return variables, members, compu_methods, projects


def iter_sources(roots, excludes):
    for root in roots:
        if os.path.isfile(root):
            yield root
            continue
        for dirpath, dirnames, filenames in os.walk(root):
            dirnames[:] = sorted(d for d in dirnames
                                 if os.path.normpath(os.path.join(dirpath, d)) not in excludes)
            for fn in sorted(filenames):
                if fn.endswith((".c", ".h")):
                    yield os.path.join(dirpath, fn)


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("roots", nargs="+", help="source files or directories to scan")
    ap.add_argument("-o", "--output", required=True, help="annotations JSON to write")
    ap.add_argument("--exclude", action="append", default=[], help="directory to skip (repeatable)")
    args = ap.parse_args()

    excludes = {os.path.normpath(e) for e in args.exclude}
    variables, members, compu_methods = [], {}, {}
    project = None
    seen = {}
    try:
        for path in iter_sources(args.roots, excludes):
            rel = os.path.relpath(path).replace("\\", "/")
            v, m, cms, projects = extract_file(path, rel)
            for p in projects:
                if project:
                    raise ExtractError(f"{p['file']}:{p['line']}: \\a2l_project already defined at "
                                       f"{project['file']}:{project['line']}")
                project = p
            for cm in cms:
                other = compu_methods.get(cm["name"])
                if other:
                    raise ExtractError(f"{cm['file']}:{cm['line']}: compu method '{cm['name']}' already "
                                       f"defined at {other['file']}:{other['line']}")
                compu_methods[cm["name"]] = cm
            for obj in v:
                for key in ("symbol", "name"):
                    other = seen.get((key, obj[key]))
                    if other:
                        raise ExtractError(f"{obj['file']}:{obj['line']}: duplicate A2L {key} "
                                           f"'{obj[key]}' (first at {other})")
                    seen[(key, obj[key])] = f"{obj['file']}:{obj['line']}"
            variables += v
            for mem in m:
                per_struct = members.setdefault(mem.pop("struct"), {})
                if mem["member"] in per_struct:
                    raise ExtractError(f"{mem['file']}:{mem['line']}: member '{mem['member']}' annotated twice")
                per_struct[mem.pop("member")] = mem

        # References may point to definitions in any file, so check them last.
        annotated = variables + [m for per_struct in members.values() for m in per_struct.values()]
        for a in annotated:
            refs = [a.get("compu", {}).get("ref")] + [a[t].get("compu_ref") for t in AXIS_TAGS if t in a]
            for ref in refs:
                if ref and ref not in compu_methods:
                    raise ExtractError(f"{a['file']}:{a['line']}: unknown compu method '{ref}'")
        if project is None:
            raise ExtractError("no \\a2l_project block found; add one (see Configurations/a2l_project.h)")
    except ExtractError as e:
        print(f"a2l_extract: error: {e}", file=sys.stderr)
        return 1

    os.makedirs(os.path.dirname(os.path.abspath(args.output)), exist_ok=True)
    with open(args.output, "w", encoding="utf-8") as f:
        json.dump({"project": project, "objects": variables, "struct_members": members,
                   "compu_methods": compu_methods}, f, indent=2)
    print(f"a2l_extract: {len(variables)} objects, "
          f"{sum(len(v) for v in members.values())} struct member annotations, "
          f"{len(compu_methods)} compu methods -> {args.output}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
