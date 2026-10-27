#include "corestats.h"

/** \brief Per-core load statistics, indexed by core ID.
 * \a2l_measurement
 */
CORE0_DLMU_NC CoreStats_t g_coreStats[CPU_CORE_COUNT];

// TODO: Remove again, just a test for A2L generation
/** \brief Engine speed (test signal for A2L generation).
 * \a2l_measurement
 * \a2l_compu_ref  CM_Rpm
 */
CORE0_DLMU_NC uint16 g_engine_rpm = 0;

/** \brief Resets the Core Statistics for one Core.
 * \param coreId The ID of the Core to reset.
 */
void CoreStats_Init(uint8 coreId)
{
    if (coreId < CPU_CORE_COUNT)
    {
        g_coreStats[coreId].execUs          = 0u;
        g_coreStats[coreId].execMaxUs       = 0u;
        g_coreStats[coreId].loadPmil        = 0u;
        g_coreStats[coreId].aliveCounter    = 0u;
    }
}