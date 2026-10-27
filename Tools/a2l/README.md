# A2L generation from Doxygen annotations

The A2L file (`bin/target.a2l`) is generated during `make all` from `\a2l_*` tags in Doxygen comments. You annotate *what* a variable means (kind, unit, conversion, axes). Addresses, data types, array sizes and struct layouts are read from the linked ELF, so the annotations never have to repeat them.

## Contents

- [How the A2L is built](#how-the-a2l-is-built)
- [Quick start](#quick-start)
- [General rules](#general-rules)
- [Tag reference](#tag-reference)
- [Conversions (compu methods)](#conversions-compu-methods)
- [Struct members](#struct-members)
- [Characteristics, axes, curves and maps](#characteristics-axes-curves-and-maps)
- [XCP settings, alignment and EPK](#xcp-settings-alignment-and-epk)
- [Troubleshooting](#troubleshooting)

## How the A2L is built

```
C sources ──a2l_extract.py──► build/a2l/annotations.json   (tags; addresses = null)
                                     │
bin/target.elf ─────────────┐        ▼
build/a2l/a2l_probe.o ──────┴─a2l_resolve.py──► build/a2l/resolved.json   (addresses, types, XCP)
                                                         │
                              a2l_generate.py ◄──────────┘──► bin/target.a2l
```

There is no configuration file. Everything in the A2L comes from annotations, the ELF, or the compiled probe.

| Step | Script | What it does |
|---|---|---|
| Extract | `a2l_extract.py` | Scans `*.c` / `*.h` outside `Libraries/`, `Tools/`, `build/`, `bin/` and `Debug/` for tags. |
| Resolve | `a2l_resolve.py` | Reads addresses from the ELF symbol table and types from DWARF. Expands structs and arrays of structs into one entry per member. Reads the XCP events and the EPK from the ELF. |
| Generate | `a2l_generate.py` | Writes ASAP2 1.71: MEASUREMENT, CHARACTERISTIC, AXIS_PTS, COMPU_METHOD/TAB/VTAB, RECORD_LAYOUT and IF_DATA XCP. |

The JSON files in `build/a2l/` are kept on disk, so you can look at them when something goes wrong. The only Python dependency is `pyelftools` (`pip install -r Tools/a2l/requirements.txt`).

## Quick start

```c
/** \brief Engine speed.
 * \a2l_measurement
 * \a2l_unit   rpm
 * \a2l_format %6.0
 */
uint16 g_engineSpeed = 0u;
```

Run `make all`. `g_engineSpeed` then appears in `bin/target.a2l` as a `UWORD` MEASUREMENT at its linked address.

### Project information

The code base must contain **exactly one** stand-alone `\a2l_project` block. It is in [Configurations/a2l_project.h](../../Configurations/a2l_project.h), a comments-only header that doesn't need to be included anywhere.

```c
/** \brief AURIX TC375 Lite Kit playground
 * \a2l_project Aurix_Playground
 * \a2l_module  TC375
 */
```

| Tag | A2L | Notes |
|---|---|---|
| `\a2l_project <ident>` | `/begin PROJECT <ident> "<brief>"` | required |
| `\a2l_module <ident>` | `/begin MODULE <ident> "<brief>"` | optional; defaults to the project name |
| `\brief` | description of PROJECT and MODULE | |

## General rules

- **Comment style.** Use `/** … */` before a declaration or `/**< … */` after it on the same line. `\a2l_x` and `@a2l_x` are both accepted.
- **Tag arguments** run to the end of the line or to the next tag, so several tags may share a line:
  `/**< Busy time [us] \a2l_unit us */`
- **Description.** The A2L description is the `\brief` text. Without `\brief`, it is the free text before the first command.
- **Where to annotate.** Annotate the **definition** at file scope, not the `extern` declaration in a header, and not a local variable.
- **Linker garbage collection.** Annotated variables must be **used** by the firmware. The build links with `--gc-sections`, so an unused variable is removed and the resolve step fails with "symbol not found". A `(void)x;` statement doesn't keep a variable alive.
- **Global addresses only.** Annotated variables must not sit at core-local addresses (0xC…/0xD…), because XCP runs on CPU2. Default sections and the `CORE*_DLMU*` sections are fine.
- **Characteristics must be writable.** A characteristic must not be `const`; a `const` variable lives in flash, where XCP cannot write it.
- **Mentioning a tag in prose.** Escape it the Doxygen way (`\\a2l_unit`), and the extractor ignores it. Example: [a2l_compu_methods.h](../../src/platform/a2l_compu_methods.h).
- **Doxygen output.** To have Doxygen render the tags, add `@INCLUDE = Tools/a2l/Doxyfile.a2l_aliases` to the Doxyfile.

## Tag reference

### Object kind (exactly one per variable)

| Tag | A2L object | Applies to |
|---|---|---|
| `\a2l_measurement` | MEASUREMENT | any scalar, array, struct, or array of structs |
| `\a2l_characteristic` | CHARACTERISTIC: VALUE, VAL_BLK, CURVE, MAP or CUBOID | scalar or array |
| `\a2l_axis_pts` | AXIS_PTS (shared axis breakpoints) | 1-D array |
| `\a2l_compu_method <Name>` | named COMPU_METHOD | a comment of its own, not attached to a declaration |

### Attributes

| Tag | Arguments | Meaning |
|---|---|---|
| `\a2l_name` | `<ident>` | A2L name. Default: the C symbol name. |
| `\a2l_unit` | `<text>` | Physical unit. Surrounding quotes are optional. |
| `\a2l_format` | `%<len>.<prec>` | Display format, e.g. `%6.2`. |
| `\a2l_limits` | `<lo> <hi>` | Physical limits. Defaults to the datatype range converted to physical values. Required for FORM and non-linear RAT_FUNC conversions. |
| `\a2l_input` | `<measurement>` | AXIS_PTS only: the measurement used to show the current position on the axis. |
| `\a2l_axis_x`, `_y`, `_z` | `<axis_pts>` or `fix <offset> <step> [<compu>]` | Characteristic axes. See [below](#characteristics-axes-curves-and-maps). |

The data type, address and array dimensions are **never** annotated; they come from the ELF.

## Conversions (compu methods)

Each object has **at most one** conversion. Without one, the conversion is IDENTICAL (phys = raw).

| Tag | A2L type | Example | Notes |
|---|---|---|---|
| none | IDENTICAL | | |
| `\a2l_conversion a b` | LINEAR | `\a2l_conversion 0.1 -40` | phys = a · raw + b |
| `\a2l_rat_func a b c d e f` | RAT_FUNC | `\a2l_rat_func 0 1000 0 0 0 1` | **physical → raw:** raw = (a·p² + b·p + c) / (d·p² + e·p + f) |
| `\a2l_formula "<expr>"` | FORM | `\a2l_formula "X1 * 0.05 + 100"` | `X1` is the raw value. Needs `\a2l_limits`. |
| `\a2l_tab_intp raw=phys …` | TAB_INTP | `\a2l_tab_intp 0=150 2048=25 4095=-40` | Interpolated table. Sorted automatically. |
| `\a2l_tab_nointp raw=phys …` | TAB_NOINTP | `\a2l_tab_nointp 0=0 1=25 2=50` | Table without interpolation. |
| `\a2l_enum v=text …` | TAB_VERB | `\a2l_enum 0=Off 1="Half on"` | Verbal table. Quote texts that contain spaces. |
| `\a2l_compu_ref <Name>` | reference | `\a2l_compu_ref CM_Rpm` | Uses a named compu method. |

### Inline conversion (one-off)

An inline conversion becomes an anonymous `CM_auto_N` compu method. Identical inline conversions are merged.

```c
/** \brief Throttle position.
 * \a2l_measurement
 * \a2l_conversion 0.4 0
 * \a2l_unit       %
 * \a2l_format     %5.1
 */
uint8 g_exThrottle = 0u;
```

### Named compu method (define once, reference many times)

Shared definitions live in [src/platform/a2l_compu_methods.h](../../src/platform/a2l_compu_methods.h). That header holds comments only and doesn't need to be included anywhere. A definition is a comment of its own containing:

- `\a2l_compu_method <Name>`
- at most one conversion tag (none means IDENTICAL)
- optionally `\brief`, `\a2l_unit` and `\a2l_format`

`\a2l_limits` and `\a2l_compu_ref` are not allowed inside a definition.

```c
/** \brief Temperature in 0.1 degC steps with -40 degC offset.
 * \a2l_compu_method CM_Temp_0p1degC
 * \a2l_conversion   0.1 -40
 * \a2l_unit         degC
 * \a2l_format       %5.1
 */

/** \brief Voltage stored in mV, displayed in V.
 * \a2l_compu_method CM_Voltage_mV
 * \a2l_rat_func     0 1000 0 0 0 1
 * \a2l_unit         V
 * \a2l_format       %6.3
 */

/** \brief Boolean switch.
 * \a2l_compu_method CM_OnOff
 * \a2l_enum         0=Off 1=On
 */
```

Reference a definition with `\a2l_compu_ref`. The variable inherits the definition's unit and format. Its own `\a2l_unit` or `\a2l_format` overrides them; these are written to the A2L as `PHYS_UNIT` / `FORMAT`.

```c
/** \brief Coolant temperature.
 * \a2l_measurement
 * \a2l_compu_ref CM_Temp_0p1degC
 */
uint16 g_exCoolantTemp = 600u;

/** \brief Oil temperature: same conversion, different display format.
 * \a2l_measurement
 * \a2l_compu_ref CM_Temp_0p1degC
 * \a2l_format    %4.0
 */
uint16 g_exOilTemp = 600u;

/** \brief Boost pressure (FORM conversion, so limits are required).
 * \a2l_measurement
 * \a2l_compu_ref CM_Pressure_kPa
 * \a2l_limits    100 3376.75
 */
uint16 g_exBoostPressure = 0u;
```

More examples: [src/examples/a2l_example.c](../../src/examples/a2l_example.c).

## Struct members

When a struct variable (or an array of structs) is annotated, it is expanded into **one A2L object per member**, named like `g_coreStats[1].execUs`.

To give individual members a unit or conversion, annotate them **in the typedef**:

- Member tags apply to every annotated variable of that struct type.
- Member tags override the variable-level tags.
- A member without its own description uses the variable's description.
- Members must **not** carry a kind tag (`\a2l_measurement` etc.).
- Bitfields are skipped, with a warning.

```c
typedef struct
{
    uint32 execUs;          /**< Busy time in the last window [us] \a2l_unit us */
    uint32 execMaxUs;       /**< Longest dispatch since boot [us] \a2l_unit us */
    /** Busy fraction of the window [per mille]
     * \a2l_unit       %
     * \a2l_conversion 0.1 0
     * \a2l_format     %5.1
     */
    uint32 loadPmil;
    uint32 aliveCounter;    /**< +1 per window */
} CoreStats_t;

/** \brief Per-core load statistics, indexed by core ID.
 * \a2l_measurement
 */
CORE0_DLMU_NC CoreStats_t g_coreStats[CPU_CORE_COUNT];
```

## Characteristics, axes, curves and maps

The A2L type of a characteristic follows from its C shape and its axis tags:

| C declaration | Axis tags | A2L type |
|---|---|---|
| `T x;` | none | VALUE |
| `T x[N];` / `T x[M][N];` | none | VAL_BLK (with MATRIX_DIM) |
| `T x[N];` | `axis_x` | CURVE |
| `T x[Ny][Nx];` | `axis_x`, `axis_y` | MAP |
| `T x[Nz][Ny][Nx];` | `axis_x`, `axis_y`, `axis_z` | CUBOID |

- **C index order is `[z][y][x]`.** The x axis belongs to the **last** (innermost) index. Values are written with record layout `ROW_DIR`, meaning x varies fastest.
- **Axis count.** The number of axis tags must equal the number of array dimensions. Axes are given in order x, y, z.

### Scalar and array characteristics

```c
/** \brief Target idle speed.
 * \a2l_characteristic
 * \a2l_compu_ref CM_Rpm
 * \a2l_limits    500 1500
 */
uint16 g_calIdleSpeed = 850u;

/** \brief Fan duty per fan stage 1..4.
 * \a2l_characteristic
 * \a2l_unit   %
 * \a2l_limits 0 100
 */
uint8 g_calFanDuty[4] = { 25u, 50u, 75u, 100u };
```

### Shared axes (AXIS_PTS / COM_AXIS)

Declare the breakpoints once as a 1-D `\a2l_axis_pts` array. Any number of curves, maps and cuboids can then reference it by A2L name.

- The axis gets its own conversion, unit and limits.
- `\a2l_input` links the axis to the measurement used to look it up.
- The number of axis points must equal the table dimension it is used for.

```c
/** \brief Engine speed breakpoints, shared by all speed-based tables.
 * \a2l_axis_pts
 * \a2l_compu_ref CM_Rpm
 * \a2l_input     g_exEngineSpeed
 */
uint16 g_calAxisRpm[8] = { 800u, 1200u, 1600u, 2000u, 2500u, 3000u, 4000u, 6000u };

/** \brief Engine load breakpoints (0.5 % resolution).
 * \a2l_axis_pts
 * \a2l_conversion 0.5 0
 * \a2l_unit       %
 * \a2l_input      g_exThrottle
 */
uint8 g_calAxisLoad[6] = { 0u, 20u, 60u, 100u, 160u, 200u };
```

### Fixed axes (FIX_AXIS)

A fixed axis is computed as `offset + i * step` and needs no memory.

- `offset` and `step` are **raw** values.
- The optional compu method converts them for display. It must be IDENTICAL, LINEAR or a linear RAT_FUNC.
- Without a compu method, the axis uses `NO_COMPU_METHOD`.

```
\a2l_axis_x fix <offset> <step> [<compu method>]
```

### Curve examples

```c
/** \brief Warm-up enrichment over coolant temperature (shared axis).
 * \a2l_characteristic
 * \a2l_axis_x     g_calAxisCoolant
 * \a2l_conversion 0.01 0
 * \a2l_unit       -
 */
uint8 g_calWarmupFactor[5] = { 180u, 150u, 120u, 100u, 100u };

/** \brief Injector dead time over battery voltage 10..15 V (fixed axis).
 * \a2l_characteristic
 * \a2l_axis_x fix 10000 1000 CM_Voltage_mV
 * \a2l_unit   us
 * \a2l_limits 0 5000
 */
sint16 g_calDeadTime[6] = { 1200, 900, 700, 550, 450, 400 };
```

### Map examples

The first two maps reuse the same rpm and load axes. The third mixes a shared axis with a fixed one.

```c
/** \brief Ignition advance over speed (x) and load (y).
 * \a2l_characteristic
 * \a2l_axis_x     g_calAxisRpm
 * \a2l_axis_y     g_calAxisLoad
 * \a2l_conversion 0.5 0
 * \a2l_unit       deg
 */
sint8 g_calIgnitionMap[6][8];            /* [y = load][x = rpm] */

/** \brief Lambda target, reusing the ignition map axes.
 * \a2l_characteristic
 * \a2l_axis_x     g_calAxisRpm
 * \a2l_axis_y     g_calAxisLoad
 * \a2l_conversion 0.001 0
 * \a2l_limits     0.5 1.5
 */
uint16 g_calLambdaMap[6][8];

/** \brief Torque limit over speed (shared axis) and gear 1..4 (fixed axis).
 * \a2l_characteristic
 * \a2l_axis_x g_calAxisRpm
 * \a2l_axis_y fix 1 1
 * \a2l_unit   Nm
 */
uint16 g_calTorqueLimit[4][8];           /* [y = gear][x = rpm] */
```

### Cuboid example

```c
/** \brief Base injection time over speed (x), load (y) and coolant temperature (z).
 * \a2l_characteristic
 * \a2l_axis_x     g_calAxisRpm
 * \a2l_axis_y     g_calAxisLoad
 * \a2l_axis_z     g_calAxisCoolant
 * \a2l_conversion 0.01 0
 * \a2l_unit       ms
 * \a2l_limits     0 50
 */
uint16 g_calInjectionCube[5][6][8];      /* [z = coolant][y = load][x = rpm] */
```

Full working examples: [src/examples/a2l_calibration.c](../../src/examples/a2l_calibration.c).

## XCP settings, alignment and EPK

`MOD_COMMON`, `MOD_PAR` and the `IF_DATA XCP` section are **derived from the code**. Don't annotate them.

| A2L content | Source |
|---|---|
| Events (name, cycle, time unit, DAQ/STIM) | the `XCP_DAQ_DEFINE_EVENT` entries (`Cpu2_Main.c`), read from the `XcpDaq_Events` table in the ELF |
| MAX_CTO/DTO, versions, DAQ type, maximum lists and events, ODT entry size, timestamp, UDP/TCP, port | macros in `Configurations/xcp_config.h`, evaluated by the compiler through [a2l_probe.c](a2l_probe.c) |
| ALIGNMENT_BYTE … ALIGNMENT_FLOAT64_IEEE | `offsetof(struct { char c; T v; }, v)` in [a2l_probe.c](a2l_probe.c): the alignment the compiler actually uses for a struct member of type `T`. On TriCore, 64-bit types align to 4. |
| BYTE_ORDER | ELF header |
| ECU IP address | only if `XCP_ON_ETHERNET_IP_OCTETS` is defined. With DHCP (the default), `XCP_ON_UDP_IP` has no address, and the IP is set in the measurement tool. |
| EPK / ADDR_EPK | symbol `Xcp_EEPROM_Kennung`, if it is linked (requires `XCP_ENABLE_GET_ID_EPK`) |

How the probe works:

- `a2l_probe.c` is compiled with the firmware's compiler, target flag and include paths into `build/a2l/a2l_probe.o`.
- It is **not** linked into the firmware.
- It is rebuilt automatically whenever one of its headers changes.

To add a value, add an `A2L_PROBE(key, EXPRESSION)` line to `a2l_probe.c`, then read `probe["key"]` in `a2l_resolve.py`.

## Troubleshooting

All errors stop the build and name the source file and line.

| Message | Cause and fix |
|---|---|
| `unknown tag \a2l_…` | A typo in the tag name. |
| `symbol '…' not found in ELF (unused and removed by --gc-sections?)` | The variable is never used, so the linker removed it. Use it in code. |
| `is at core-local address 0x…` | Move the variable to a globally addressed section. |
| `annotate the definition of '…', not the extern declaration` | Move the comment to the `.c` definition. |
| `unknown compu method '…'` | The `\a2l_compu_ref` name or a fixed-axis compu name isn't defined. |
| `… are mutually exclusive` | More than one conversion tag on one object. |
| `uses a FORM / RAT_FUNC conversion; add \a2l_limits` | Physical limits can't be derived. Add `\a2l_limits`. |
| `has N array dimension(s) but M axis tag(s)` | Add or remove axis tags to match the array. |
| `axis '…' has N points but the array dimension is M` | The AXIS_PTS length doesn't match the table dimension. Check the `[z][y][x]` order. |
| `axis '…' is not an \a2l_axis_pts object` | The axis reference points to something else. |
| `\a2l_input '…' is not a measurement` | The axis input must name an A2L MEASUREMENT. |
| warning: `EPK symbol … not linked` | The A2L is written without an EPK. Enable `XCP_ENABLE_GET_ID_EPK` if you need one. |
| `no \a2l_project block found` / `\a2l_project already defined` | There must be exactly one project block. See [Project information](#project-information). |
