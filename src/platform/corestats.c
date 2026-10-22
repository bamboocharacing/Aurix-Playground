#include "corestats.h"

// TODO: Needs to have A2L annotation
CORE0_DLMU_NC CoreStats_t g_coreStats[CPU_CORE_COUNT];

// TODO: Remove again, just a test for A2L generation
CORE0_DLMU_NC uint16 g_engine_rpm = 0;
A2L_MEASUREMENT(g_engine_rpm, "Engine RPM", "Description for Engine RPM Measurement", A2L_TYPE_UWORD, "rpm");
A2L_COMPU_METHOD_LINEAR(CM_RPM, "Linear Conversion for RPM", "%6.0", "rpm", 1.0f, 0.0f);

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