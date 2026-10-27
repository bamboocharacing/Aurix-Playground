#ifndef __CORESTATS_H__
#define __CORESTATS_H__

#include "Ifx_Types.h"

#include "cpu.h"
#include "sharedmemory.h"

/** \brief Rolling statistics for one core. Written by that core only.
 * \note Struct lives in LMU. LMU is 64bit wide. Therefore make sure that
 * future properties are aligned with that structure to avoid weird operations.
 */
typedef struct
{
    uint32 execUs;          /**< Busy Time in the last Window [us] \a2l_unit us */
    uint32 execMaxUs;       /**< Longest Single Task Dispatch since boot [us] \a2l_unit us */
    /** Busy Fraction of the Window [per mille]
     * \a2l_unit       %
     * \a2l_conversion 0.1 0
     * \a2l_format     %5.1
     */
    uint32 loadPmil;
    uint32 aliveCounter;    /**< +1 per window | Frozen => Core is Stuck. */
} CoreStats_t;

extern volatile CoreStats_t g_coreStats[CPU_CORE_COUNT];

extern void CoreStats_Init(uint8 coreId);

#endif