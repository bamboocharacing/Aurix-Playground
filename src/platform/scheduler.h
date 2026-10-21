#ifndef __SCHEDULER_H__
#define __SCHEDULER_H__

#include "Ifx_Types.h"
#include "IfxStm.h"

#include "cpu.h"
#include "corestats.h"

/*
 * Macros to help defining the time schedule.
 * The STM (System Timer Module) runs at 100MHz after PLL initialization.
 * 1 ms = 100 000 ticks
 */
#define SCHEDULER_MS(ms)        ((uint32)((ms) * 100000UL))
#define SCHEDULER_US(us)        ((uint32)((us) * 100UL))

#ifndef SCHEDULER_MAX_TASKS
#define SCHEDULER_MAX_TASKS     12u
#endif

/*
 * Execution-time accounting window.
 */
#ifndef SCHEDULE_STATS_WINDOW
#define SCHEDULE_STATS_WIDNOW   SCHEDULER_MS(100u)
#endif

#define SCHEDULER_TICKS_PER_US  (100u)

typedef void (*Scheduler_TaskFn_t)(void);

typedef struct
{
    Scheduler_TaskFn_t  fn;
    uint32              period;     /** Period in STM Ticks. */
    uint32              lastRun;    /** STM Tick at last dispatch */
} Scheduler_Task_t;

typedef struct
{
    Ifx_STM             *stm;
    uint8               taskCount;
    uint8               coreId;
    uint32              busyTicks;
    uint32              maxTicks;
    uint32              windowStart;
    Scheduler_Task_t    tasks[SCHEDULER_MAX_TASKS];
} Scheduler_t;

extern boolean Scheduler_Init(Scheduler_t *sched, Ifx_STM *stm, uint8 coreId);
extern boolean Scheduler_AddTask(Scheduler_t *sched, Scheduler_TaskFn_t fn, uint32 period);
extern void    Scheduler_Run(Scheduler_t *sched);

#endif