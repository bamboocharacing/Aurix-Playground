#include "corestats.h"

// TODO: Needs to have A2L annotation
CORE0_DLMU_NC CoreStats_t g_coreStats[CPU_CORE_COUNT];

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