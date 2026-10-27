#include "a2l_example.h"

/* Example: referencing the shared compu methods from src/platform/a2l_compu_methods.h.
 * The signals are synthetic and only exist to show the generated A2L. */

/** \brief Engine speed.
 * \a2l_measurement
 * \a2l_compu_ref CM_Rpm
 */
uint16 g_exEngineSpeed = 800u;

/** \brief Coolant temperature.
 * \a2l_measurement
 * \a2l_compu_ref CM_Temp_0p1degC
 */
uint16 g_exCoolantTemp = 600u;

/** \brief Oil temperature. Same conversion as coolant, but format overridden.
 * \a2l_measurement
 * \a2l_compu_ref CM_Temp_0p1degC
 * \a2l_format    %4.0
 */
uint16 g_exOilTemp = 600u;

/** \brief Battery voltage.
 * \a2l_measurement
 * \a2l_compu_ref CM_Voltage_mV
 */
uint16 g_exBatteryVoltage = 12600u;

/** \brief Boost pressure. FORM conversions need explicit physical limits.
 * \a2l_measurement
 * \a2l_compu_ref CM_Pressure_kPa
 * \a2l_limits    100 3376.75
 */
uint16 g_exBoostPressure = 0u;

/** \brief Raw NTC ADC reading.
 * \a2l_measurement
 * \a2l_compu_ref CM_NtcTemp
 */
uint16 g_exNtcRaw = 2048u;

/** \brief Current fan stage.
 * \a2l_measurement
 * \a2l_compu_ref CM_FanStage
 */
uint8 g_exFanStage = 0u;

/** \brief Throttle position. One-off inline conversion instead of a reference.
 * \a2l_measurement
 * \a2l_conversion 0.4 0
 * \a2l_unit       %
 * \a2l_format     %5.1
 */
uint8 g_exThrottle = 0u;

/** \brief Enables the fan control.
 * \a2l_characteristic
 * \a2l_compu_ref CM_OnOff
 */
uint8 g_exFanEnable = 1u;

/** \brief Coolant temperature at which the fan starts.
 * \a2l_characteristic
 * \a2l_compu_ref CM_Temp_0p1degC
 * \a2l_limits    0 150
 */
uint16 g_exFanOnTemp = 1300u; /* 90 degC */

void A2lExample_Update(void)
{
    static uint32 tick = 0u;
    tick++;

    g_exEngineSpeed    = (uint16)(800u + (tick * 37u) % 5200u);
    g_exThrottle       = (uint8)((tick * 3u) % 251u);
    g_exBoostPressure  = (uint16)((tick * 11u) % 4000u);
    g_exBatteryVoltage = (uint16)(12000u + (tick * 13u) % 2400u);
    g_exNtcRaw         = (uint16)((tick * 5u) % 4096u);
    g_exCoolantTemp    = (uint16)(400u + (tick % 1200u));
    g_exOilTemp        = (uint16)(g_exCoolantTemp + 50u);

    if ((g_exFanEnable != 0u) && (g_exCoolantTemp >= g_exFanOnTemp))
    {
        g_exFanStage = (uint8)(1u + (g_exCoolantTemp - g_exFanOnTemp) / 100u);
        if (g_exFanStage > 4u)
        {
            g_exFanStage = 4u;
        }
    }
    else
    {
        g_exFanStage = 0u;
    }
}
