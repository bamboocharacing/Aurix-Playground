#ifndef __PROCESSOR_HEALTH_H__
#define __PROCESSOR_HEALTH_H__

#include "Ifx_Types.h"

#include "Dts/Dts/IfxDts_Dts.h"
#include "Pms/Std/IfxPmsEvr.h"

#include "sharedmemory.h"

#define PROCESSOR_HEALTH_AVG    4u

typedef struct
{
    /** \brief Internal: Die Temperature
     * \a2l_unit degC
     */
    float32 temperature_die;

    /** \brief Voltage Rail: VDD
     * \a2l_unit V
     */
    float32 voltage_vdd;    /* 1.25V  */

    /** \brief Voltage Rail: VDDP3
     * \a2l_unit V
     */
    float32 voltage_vddp3;  /* 3.3V */

    /** \brief Voltage Rail: VEXT
     * \a2l_unit V
     */
    float32 voltage_vext;   /* 5V or 3.3V */
} Processor_Health_t;

void Processor_Health_Init(void);
void Processor_Health_UpdateMeasurements(void);

#endif