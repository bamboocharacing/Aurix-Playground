#ifndef __A2L_COMPU_METHODS_H__
#define __A2L_COMPU_METHODS_H__

/** \file
 * \brief Shared A2L compu methods (conversion rules raw -> physical).
 *
 * Every block below defines one named COMPU_METHOD for the generated A2L file
 * (see Tools/a2l). A definition is a Doxygen comment of its own, starting with
 * \c \\a2l_compu_method <name>, followed by at most one conversion tag and
 * optionally \c \\a2l_unit and \c \\a2l_format. Without a conversion tag the
 * method is IDENTICAL.
 *
 * Reference a method from any annotated variable or struct member with
 * \c \\a2l_compu_ref <name>. The variable inherits unit and format; its own
 * \c \\a2l_unit / \c \\a2l_format override them. Inline conversion tags on the
 * variable itself (e.g. \c \\a2l_conversion) are still possible for one-off
 * conversions. See src/examples/a2l_example.c for usage.
 *
 * This header contains no code and does not need to be included anywhere.
 */

/** \brief Engine speed, raw value is already in rpm.
 * \a2l_compu_method CM_Rpm
 * \a2l_unit         rpm
 * \a2l_format       %6.0
 */

/** \brief Temperature in 0.1 degC steps with -40 degC offset: phys = 0.1 * raw - 40.
 * \a2l_compu_method CM_Temp_0p1degC
 * \a2l_conversion   0.1 -40
 * \a2l_unit         degC
 * \a2l_format       %5.1
 */

/** \brief Voltage stored in mV, displayed in V.
 * RAT_FUNC coefficients describe physical -> raw: raw = (a*V^2 + b*V + c) / (d*V^2 + e*V + f).
 * \a2l_compu_method CM_Voltage_mV
 * \a2l_rat_func     0 1000 0 0 0 1
 * \a2l_unit         V
 * \a2l_format       %6.3
 */

/** \brief Free-form formula; X1 is the raw value. Objects using it need explicit limits.
 * \a2l_compu_method CM_Pressure_kPa
 * \a2l_formula      "X1 * 0.05 + 100"
 * \a2l_unit         kPa
 * \a2l_format       %7.1
 */

/** \brief NTC characteristic: 12-bit ADC counts -> degC, linearly interpolated.
 * \a2l_compu_method CM_NtcTemp
 * \a2l_tab_intp     0=150 1024=85 2048=25 3072=-10 4095=-40
 * \a2l_unit         degC
 * \a2l_format       %5.1
 */

/** \brief Fan stage -> duty cycle, no interpolation between stages.
 * \a2l_compu_method CM_FanStage
 * \a2l_tab_nointp   0=0 1=25 2=50 3=75 4=100
 * \a2l_unit         %
 * \a2l_format       %3.0
 */

/** \brief Boolean switch.
 * \a2l_compu_method CM_OnOff
 * \a2l_enum         0=Off 1=On
 */

#endif
