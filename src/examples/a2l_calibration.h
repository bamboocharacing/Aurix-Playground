#ifndef __A2L_CALIBRATION_H__
#define __A2L_CALIBRATION_H__

#include "Ifx_Types.h"

/** \brief Looks up the example calibration tables with the example signals.
 * Call periodically after A2lExample_Update().
 */
extern void A2lCalibration_Update(void);

#endif
