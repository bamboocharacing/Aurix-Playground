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
    /** Busy Time in the last Window [STM ticks, 10 ns]
     * \a2l_unit       us
     * \a2l_conversion 0.01 0
     * \a2l_format     %9.2
     */
    uint32 execTicks;
    /** Longest Single Task Dispatch since boot [STM ticks, 10 ns]
     * \a2l_unit       us
     * \a2l_conversion 0.01 0
     * \a2l_format     %9.2
     */
    uint32 execMaxTicks;
    /** Busy Fraction of the Window [ppm]
     * \a2l_unit       %
     * \a2l_conversion 0.0001 0
     * \a2l_format     %7.4
     */
    uint32 loadPpm;
    uint32 aliveCounter;    /**< +1 per window | Frozen => Core is Stuck. */
} CoreStats_t;

extern volatile CoreStats_t g_coreStats[CPU_CORE_COUNT];

extern void CoreStats_Init(uint8 coreId);

#endif