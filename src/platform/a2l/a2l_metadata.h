#ifndef __A2L_METADATA_H__
#define __A2L_METADATA_H__

#include "Ifx_Types.h"

#define A2L_SECTION __attribute__((section(".a2l_metadata"), used))

#define A2L_MAGIC   0x41324C21

typedef enum
{
    A2L_OBJ_CHARACTERISTIC  = 1,
    A2L_OBJ_MEASUREMENT     = 2,
    A2L_OBJ_COMPU_METHOD    = 3
} A2L_ObjectType;

typedef enum 
{
    A2L_TYPE_UBYTE          = 1,
    A2L_TYPE_SBYTE          = 2,
    A2L_TYPE_UWORD          = 3,
    A2L_TYPE_SWORD          = 4,
    A2L_TYPE_ULONG          = 5,
    A2L_TYPE_SLONG          = 6,
    A2L_TYPE_A_UINT64       = 7,
    A2L_TYPE_FLOAT32_IEEE   = 8,
    A2L_TYPE_FLOAT64_IEEE   = 9
} A2L_DataType;

typedef struct __attribute__((packed, aligned(4)))
{
    uint32 magic;
    uint8 obj_type;
    uint8 reserved[3];

    const char* name;
    const char* desc;

    union __attribute__((packed))
    {
        struct __attribute__((packed))
        {
            const volatile void* vaddr;
            uint8 data_type;
            uint8 reserved[3];
            const char* compu_method;
            float32 lower_limit;
            float32 upper_limit;
        } characteristic;

        struct __attribute__((packed))
        {
            const volatile void* vaddr;
            uint8 data_type;
            uint8 reserved[3];
            const char* compu_method;
            const char* format;
            const char* phys_unit;
        } measurement;

        struct __attribute__((packed))
        {
            const char* type;
            const char* format;
            const char* unit;
            float32 coeff_a;
            float32 coeff_b;
            float32 coeff_c;
            float32 coeff_d;
            float32 coeff_e;
            float32 coeff_f;
            const char* tab_ref;
        } compu_method;
    } data;
} A2L_Block;

#define A2L_MEASUREMENT(_property, _name, _desc, _data_type, _phys_unit) \
    A2L_SECTION const A2L_Block a2l_metadata_measurement_##_property =  \
    { \
        .magic = A2L_MAGIC,  \
        .obj_type = A2L_OBJ_MEASUREMENT, \
        .name = _name, \
        .desc = _desc, \
        .data.measurement = { \
            .vaddr = &_property, \
            .data_type = _data_type,  \
            .phys_unit = _phys_unit \
        } \
    } \

#define A2L_COMPU_METHOD_LINEAR(_name, _desc, _format, _unit, _scale, _offset) \
    A2L_SECTION const A2L_Block a2l_metadata_compu_method_##_name = \
    { \
        .magic = A2L_MAGIC, \
        .obj_type = A2L_OBJ_COMPU_METHOD, \
        .name = #_name, \
        .desc = _desc, \
        .data.compu_method = { \
            .type = "LINEAR", \
            .format = _format, \
            .unit = _unit, \
            .coeff_a = _scale, \
            .coeff_b = _offset \
        } \
    } \

#define A2L_COMPU_METHOD_IDENTICAL(_name, _desc, _format, _unit) \
    A2L_SECTION const A2L_Block a2l_metadata_compu_method_##_name = \
    { \
        .magic = A2L_MAGIC, \
        .obj_type = A2L_OBJ_COMPU_METHOD, \
        .name = #_name, \
        .desc = _desc, \
        .data.compu_method = { \
            .type = "IDENTICAL", \
            .format = _format, \
            .unit = _unit, \
            .coeff_a = 1.0f, \
            .coeff_b = 0.0f \
        } \
    } \

#define A2L_COMPU_METHOD_RATFUNC(_name, _desc, _format, _unit, _coeff_b, _coeff_c, _coeff_f) \
    A2L_COMPU_METHOD_RATFUNC_EX(_name, _desc, _format, _unit, 0.0f, _coeff_b, _coeff_c, 0.0f, 0.0f, _coeff_f)

#define A2L_COMPU_METHOD_RATFUNC_EX(_name, _desc, _format, _unit, _coeff_a, _coeff_b, _coeff_c, _coeff_d, _coeff_e, _coeff_f) \
    A2L_SECTION const A2L_Block a2l_metadata_compu_method_##_name = \
    { \
        .magic = A2L_MAGIC, \
        .obj_type = A2L_OBJ_COMPU_METHOD, \
        .name = #_name, \
        .desc = _desc, \
        .data.compu_method = { \
            .type = "RAT_FUNC", \
            .format = _format, \
            .unit = _unit, \
            .coeff_a = _coeff_a, \
            .coeff_b = _coeff_b, \
            .coeff_c = _coeff_c, \
            .coeff_d = _coeff_d, \
            .coeff_e = _coeff_e, \
            .coeff_f = _coeff_f, \
        } \
    } \

// TODO: COMPU METHOD TAB_NOINTP
// TODO: COMPU METHOD TAB_INTP
// TODO: COMPU METHOD TAB_VERB
// TODO: COMPU METHOD FORM

// TODO: COMPU_VTAB
// TODO: COMPU_TAB

#endif