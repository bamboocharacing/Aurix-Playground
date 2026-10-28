#include "processor_health.h"

/** \brief Processor Health: Die temperature and PMS supply rails
 * \a2l_measurement
 */
CORE0_DLMU_NC Processor_Health_t g_processor_health;

void Processor_Health_Init(void)
{
    g_processor_health.temperature_die = 0.0f;
    g_processor_health.voltage_vdd = 0.0f;
    g_processor_health.voltage_vddp3 = 0.0f;
    g_processor_health.voltage_vext = 0.0f;
}

void Processor_Health_UpdateMeasurements(void)
{
    static uint32 sumVdd;
    static uint32 sumVddp3;
    static uint32 sumVext;
    static uint8 measurements_taken;

    Ifx_PMS_EVRADCSTAT s;
    s.U = MODULE_PMS.EVRADCSTAT.U;

    sumVdd += s.B.ADCCV;
    sumVddp3 += s.B.ADC33V;
    sumVext += s.B.ADCSWDV;

    if (++measurements_taken >= PROCESSOR_HEALTH_AVG)
    {
        g_processor_health.voltage_vdd = IfxPmsEvr_getAdcVddResult((float32)sumVdd / PROCESSOR_HEALTH_AVG);
        g_processor_health.voltage_vddp3 = IfxPmsEvr_getAdcVddp3Result((float32)sumVddp3 / PROCESSOR_HEALTH_AVG);
        g_processor_health.voltage_vext = IfxPmsEvr_getAdcVextResult((float32)sumVext / PROCESSOR_HEALTH_AVG);

        sumVdd = 0u;
        sumVddp3 = 0u;
        sumVext = 0u;
        measurements_taken = 0u;
    }

    g_processor_health.temperature_die = IfxDts_Dts_getTemperatureCelsius();
}