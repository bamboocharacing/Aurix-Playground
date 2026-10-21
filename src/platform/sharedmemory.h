#ifndef __SHAREDMEMORY_H__
#define __SHAREDMEMORY_H__

#include "Ifx_Types.h"

#include "corestats.h"

#ifdef __GNUC__
#define CORE0_DLMU_NC    __attribute__((section(".cpu0_dlmu_nc"))) volatile
#define CORE1_DLMU_NC    __attribute__((section(".cpu1_dlmu_nc"))) volatile
#define CORE2_DLMU_NC    __attribute__((section(".cpu2_dlmu_nc"))) volatile

#define CORE0_DLMU      __attribute__((section(".lmubss_cpu0"))) volatile
#define CORE1_DLMU      __attribute__((section(".lmubss_cpu1"))) volatile
#define CORE2_DLMU      __attribute__((section(".lmubss_cpu2"))) volatile
#endif 

// TODO: Maybe add Tasking Compiler variants

#endif