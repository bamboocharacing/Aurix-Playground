#ifndef __LED_H__
#define __LED_H__

#include "Ifx_Types.h"
#include "IfxPort.h"

typedef struct
{
    Ifx_P           *port;
    uint8           pin;
    IfxPort_State   state;
} Led_t;

extern void Led_Init(Led_t *led, Ifx_P *port, uint8 pin);
extern void Led_Toggle(Led_t *led);
extern void Led_On(Led_t *led);
extern void Led_Off(Led_t *led);

#endif