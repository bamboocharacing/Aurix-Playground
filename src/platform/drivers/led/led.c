#include "led.h"

// TODO: Documentation

void Led_Init(Led_t *led, Ifx_P *port, uint8 pin)
{
    // TODO: Make Configurable if Active High or Low

    led->port = port;
    led->pin = pin;
    led->state = IfxPort_State_high;    // Active Low

    IfxPort_setPinMode(port, pin, IfxPort_Mode_outputPushPullGeneral);
    IfxPort_setPinState(port, pin, IfxPort_State_high);
}

void Led_Toggle(Led_t *led)
{
    led->state = (led->state == IfxPort_State_high)
        ? IfxPort_State_low
        : IfxPort_State_high;

    IfxPort_setPinState(led->port, led->pin, led->state);
}

void Led_On(Led_t *led)
{
    // Active Low
    led->state = IfxPort_State_low;

    IfxPort_setPinState(led->port, led->pin, led->state);
}

void Led_Off(Led_t *led)
{
    // Active Low
    led->state = IfxPort_State_high;

    IfxPort_setPinState(led->port, led->pin, led->state);
}