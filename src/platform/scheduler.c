#include "scheduler.h"

/** \brief Initializes the Scheduler.
 * \returns TRUE if the Task Scheduler has been initialized.
 * FALSE if the Scheduler was not Intialized because core ID was out of range.
 * \param sched Pointer to the Scheduler_t structure instance.
 * \param stm Pointer to the STM (System Timer Module).
 * \param coreId Defines on which core the Scheduler runs on.
 */
boolean Scheduler_Init(
    Scheduler_t *sched, 
    Ifx_STM *stm, 
    uint8 coreId)
{
    if (coreId >= CPU_CORE_COUNT)
    {
        return FALSE;
    }

    sched->stm          = stm;
    sched->taskCount    = 0u;
    sched->coreId       = coreId;
    sched->busyTicks    = 0u;
    sched->maxTicks     = 0u;
    sched->windowStart  = IfxStm_getLower(stm);

    CoreStats_Init(coreId);

    return TRUE;
}

/** \brief Adds a task to the scheduler.
 * \returns TRUE if the Task has been added.
 * FALSE if the task was not added because fn is NULL or the maximum task count is reached.
 * \param sched Pointer to the Scheduler_t structure instance.
 * \param fn Pointer to the task function.
 * \param period Execution Period of the Task in STM ticks. 0 runs the task on every pass.
 */
boolean Scheduler_AddTask(
    Scheduler_t *sched, 
    Scheduler_TaskFn_t fn, 
    uint32 period)
{
    uint8 idx;

    if (fn == NULL ||
        sched->taskCount >= SCHEDULER_MAX_TASKS)
    {
        return FALSE;
    }

    idx = sched->taskCount;

    sched->tasks[idx].fn        = fn;
    sched->tasks[idx].period    = period;
    sched->tasks[idx].lastRun   = IfxStm_getLower(sched->stm);

    sched->taskCount++;

    return TRUE;
}

/** \brief Runs one pass of the scheduler.
 * Must be called repeatedly from the core's main loop.
 * \param sched Pointer to the scheduler instance.
 */
void Scheduler_Run(Scheduler_t *sched)
{
    uint8 i;
    uint32 now = IfxStm_getLower(sched->stm);
    uint32 elapsed;

    for (i = 0u; i < sched->taskCount; i++)
    {
        if ((uint32)(now - sched->tasks[i].lastRun) >= sched->tasks[i].period)
        {
            uint32 taskStart;
            uint32 taskTicks;

            /* Advance by one period to stay on the original time grid */
            sched->tasks[i].lastRun += sched->tasks[i].period;

            /* Overrun: more than one period behind, skip missed slots 
             and resync */
            if ((uint32)(now - sched->tasks[i].lastRun) >= sched->tasks[i].period)
            {
                sched->tasks[i].lastRun = now;
            }

            /* Perf Measurement Start */
            taskStart = IfxStm_getLower(sched->stm);

            sched->tasks[i].fn();

            taskTicks = IfxStm_getLower(sched->stm) - taskStart;
            /* Perf Measurement End*/

            sched->busyTicks += taskTicks;

            if (taskTicks > sched->maxTicks)
            {
                sched->maxTicks = taskTicks;
            }
        }
    }

    elapsed = IfxStm_getLower(sched->stm) - sched->windowStart;

    if (elapsed >= SCHEDULER_STATS_WINDOW)
    {
        uint8 id = sched->coreId;

        if (id < CPU_CORE_COUNT)
        {
            /* Raw ticks keep sub-us resolution; the A2L scales to us / % */
            g_coreStats[id].execTicks    = sched->busyTicks;
            g_coreStats[id].execMaxTicks = sched->maxTicks;
            g_coreStats[id].loadPpm      = (uint32)(((uint64)sched->busyTicks * 1000000u) / elapsed);

            g_coreStats[id].aliveCounter++;
        }

        sched->busyTicks = 0u;
        sched->windowStart = IfxStm_getLower(sched->stm);
    }
}