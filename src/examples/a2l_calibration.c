#include "a2l_calibration.h"

/* Example: calibration objects for the generated A2L file.
 *
 * - VALUE / VAL_BLK:  scalar and array characteristics without axes
 * - AXIS_PTS:         shared axis breakpoints (g_calAxis*), referenced by name
 * - CURVE / MAP / CUBOID: arrays with 1 / 2 / 3 axis tags
 *   - \a2l_axis_x <axis_pts>  -> COM_AXIS, the axis is shared with other tables
 *   - \a2l_axis_x fix ...     -> FIX_AXIS, axis computed as offset + i * step
 *
 * C index order is [z][y][x]: x is the innermost index. Characteristics must
 * live in RAM (not const) so that XCP can write them.
 */

extern uint16 g_exEngineSpeed;
extern uint8  g_exThrottle;
extern uint16 g_exCoolantTemp;
extern uint16 g_exBatteryVoltage;
extern uint8  g_exFanStage;

/* ---- Shared axes ------------------------------------------------------- */

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
 * \a2l_format     %5.1
 * \a2l_input      g_exThrottle
 */
uint8 g_calAxisLoad[6] = { 0u, 20u, 60u, 100u, 160u, 200u };

/** \brief Coolant temperature breakpoints: -20, 0, 40, 80, 110 degC.
 * \a2l_axis_pts
 * \a2l_compu_ref CM_Temp_0p1degC
 * \a2l_input     g_exCoolantTemp
 */
uint16 g_calAxisCoolant[5] = { 200u, 400u, 800u, 1200u, 1500u };

/* ---- Characteristics without axes -------------------------------------- */

/** \brief Target idle speed.
 * \a2l_characteristic
 * \a2l_compu_ref CM_Rpm
 * \a2l_limits    500 1500
 */
uint16 g_calIdleSpeed = 850u;

/** \brief Fan duty cycle per fan stage 1..4 (VAL_BLK).
 * \a2l_characteristic
 * \a2l_unit   %
 * \a2l_limits 0 100
 */
uint8 g_calFanDuty[4] = { 25u, 50u, 75u, 100u };

/* ---- Curves ------------------------------------------------------------ */

/** \brief Warm-up enrichment over coolant temperature (CURVE, shared axis).
 * \a2l_characteristic
 * \a2l_axis_x     g_calAxisCoolant
 * \a2l_conversion 0.01 0
 * \a2l_unit       -
 * \a2l_format     %4.2
 */
uint8 g_calWarmupFactor[5] = { 180u, 150u, 120u, 100u, 100u };

/** \brief Injector dead time over battery voltage 10..15 V (CURVE, fixed axis).
 * Axis raw values are 10000 + i * 1000 mV, shown in V through CM_Voltage_mV.
 * \a2l_characteristic
 * \a2l_axis_x fix 10000 1000 CM_Voltage_mV
 * \a2l_unit   us
 * \a2l_limits 0 5000
 */
sint16 g_calDeadTime[6] = { 1200, 900, 700, 550, 450, 400 };

/* ---- Maps: both share the rpm and load axes ---------------------------- */

/** \brief Ignition advance over speed (x) and load (y).
 * \a2l_characteristic
 * \a2l_axis_x     g_calAxisRpm
 * \a2l_axis_y     g_calAxisLoad
 * \a2l_conversion 0.5 0
 * \a2l_unit       deg
 * \a2l_format     %5.1
 */
sint8 g_calIgnitionMap[6][8] = { [0 ... 5] = { 10, 14, 18, 22, 26, 30, 34, 36 } };

/** \brief Lambda target over speed (x) and load (y), reusing the ignition map axes.
 * \a2l_characteristic
 * \a2l_axis_x     g_calAxisRpm
 * \a2l_axis_y     g_calAxisLoad
 * \a2l_conversion 0.001 0
 * \a2l_unit       -
 * \a2l_format     %5.3
 * \a2l_limits     0.5 1.5
 */
uint16 g_calLambdaMap[6][8] = { [0 ... 5] = { [0 ... 7] = 1000u } };

/** \brief Torque limit over speed (x, shared axis) and gear 1..4 (y, fixed axis).
 * \a2l_characteristic
 * \a2l_axis_x g_calAxisRpm
 * \a2l_axis_y fix 1 1
 * \a2l_unit   Nm
 * \a2l_limits 0 600
 */
uint16 g_calTorqueLimit[4][8] = { [0 ... 3] = { 200u, 260u, 320u, 380u, 400u, 400u, 380u, 300u } };

/* ---- Cuboid ------------------------------------------------------------ */

/** \brief Base injection time over speed (x), load (y) and coolant temperature (z).
 * \a2l_characteristic
 * \a2l_axis_x     g_calAxisRpm
 * \a2l_axis_y     g_calAxisLoad
 * \a2l_axis_z     g_calAxisCoolant
 * \a2l_conversion 0.01 0
 * \a2l_unit       ms
 * \a2l_format     %5.2
 * \a2l_limits     0 50
 */
uint16 g_calInjectionCube[5][6][8] = { [0 ... 4] = { [0 ... 5] = { [0 ... 7] = 250u } } };

/* ---- Lookup results ---------------------------------------------------- */

/** \brief Ignition advance from g_calIgnitionMap.
 * \a2l_measurement
 * \a2l_conversion 0.5 0
 * \a2l_unit       deg
 */
sint8 g_calOutIgnition = 0;

/** \brief Injection time from g_calInjectionCube, corrected by warm-up factor.
 * \a2l_measurement
 * \a2l_conversion 0.01 0
 * \a2l_unit       ms
 */
uint16 g_calOutInjection = 0u;

/** \brief Torque limit from g_calTorqueLimit.
 * \a2l_measurement
 * \a2l_unit Nm
 */
uint16 g_calOutTorqueLimit = 0u;

/** \brief Injector dead time from g_calDeadTime.
 * \a2l_measurement
 * \a2l_unit us
 */
sint16 g_calOutDeadTime = 0;

/** \brief Lambda target from g_calLambdaMap.
 * \a2l_measurement
 * \a2l_conversion 0.001 0
 * \a2l_unit       -
 */
uint16 g_calOutLambda = 0u;

/** \brief Fan duty from g_calFanDuty for the current fan stage.
 * \a2l_measurement
 * \a2l_unit %
 */
uint8 g_calOutFanDuty = 0u;

/** \brief Engine speed minus target idle speed (g_calIdleSpeed).
 * \a2l_measurement
 * \a2l_unit rpm
 */
sint16 g_calOutIdleDelta = 0;

/* Index of the last breakpoint <= value (no interpolation, example only). */
static uint8 A2lCalibration_IndexU16(const uint16 *axis, uint8 count, uint16 value)
{
    uint8 i = 0u;
    while ((i + 1u < count) && (axis[i + 1u] <= value))
    {
        i++;
    }
    return i;
}

static uint8 A2lCalibration_IndexU8(const uint8 *axis, uint8 count, uint8 value)
{
    uint8 i = 0u;
    while ((i + 1u < count) && (axis[i + 1u] <= value))
    {
        i++;
    }
    return i;
}

void A2lCalibration_Update(void)
{
    /* Throttle raw is 0.4 %/bit, load axis raw is 0.5 %/bit. */
    uint8 load    = (uint8)(((uint16)g_exThrottle * 4u) / 5u);
    uint8 xRpm    = A2lCalibration_IndexU16(g_calAxisRpm, 8u, g_exEngineSpeed);
    uint8 yLoad   = A2lCalibration_IndexU8(g_calAxisLoad, 6u, load);
    uint8 zTemp   = A2lCalibration_IndexU16(g_calAxisCoolant, 5u, g_exCoolantTemp);
    uint8 gear    = (uint8)((g_exEngineSpeed / 1500u) % 4u);
    sint32 volt   = ((sint32)g_exBatteryVoltage - 10000) / 1000;
    uint8 xVolt   = (uint8)((volt < 0) ? 0 : ((volt > 5) ? 5 : volt));

    g_calOutIgnition    = g_calIgnitionMap[yLoad][xRpm];
    g_calOutInjection   = (uint16)(((uint32)g_calInjectionCube[zTemp][yLoad][xRpm] * g_calWarmupFactor[zTemp]) / 100u);
    g_calOutTorqueLimit = g_calTorqueLimit[gear][xRpm];
    g_calOutDeadTime    = g_calDeadTime[xVolt];
    g_calOutLambda      = g_calLambdaMap[yLoad][xRpm];
    g_calOutFanDuty     = (g_exFanStage == 0u) ? 0u : g_calFanDuty[g_exFanStage - 1u];
    g_calOutIdleDelta   = (sint16)((sint32)g_exEngineSpeed - (sint32)g_calIdleSpeed);
}
