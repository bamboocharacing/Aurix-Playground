rwildcard = $(foreach dir, $(wildcard $(1:=/*)), $(call rwildcard, $(dir), $2) $(filter $(subst *, %, $2), $(dir)))

SRC_DIR := .
BUILD_DIR := build
BIN_DIR := bin

TARGET_NAME = target
TARGET_MAP := $(BIN_DIR)/$(TARGET_NAME).map
TARGET_HEX := $(BIN_DIR)/$(TARGET_NAME).hex
TARGET_SIZ := $(BIN_DIR)/$(TARGET_NAME).siz
TARGET_ELF := $(BIN_DIR)/$(TARGET_NAME).elf
TARGET_A2L := $(BIN_DIR)/$(TARGET_NAME).a2l

A2L_DIR := $(BUILD_DIR)/a2l
A2L_TOOLS := Tools/a2l
A2L_ANNOTATIONS := $(A2L_DIR)/annotations.json
A2L_RESOLVED := $(A2L_DIR)/resolved.json
A2L_PROBE := $(A2L_DIR)/a2l_probe.o
A2L_EPK_SYMBOL := Xcp_EEPROM_Kennung
A2L_EXCLUDES := --exclude Libraries --exclude $(BUILD_DIR) --exclude $(BIN_DIR) --exclude Debug --exclude Tools
PYTHON ?= python

# Tools/ holds host-side helpers (e.g. the A2L probe), not firmware sources.
SOURCES = $(filter-out $(SRC_DIR)/Tools/%, $(call rwildcard, $(SRC_DIR), *.c))
HEADERS = $(call rwildcard, $(SRC_DIR), *.h)
OBJECTS := $(SOURCES:$(SRC_DIR)/%.c=$(BUILD_DIR)/%.o)
DEPS := $(OBJECTS:.o=.d)
IFILES := $(OBJECTS:.o=.i)

USER_INCLUDES := -ILibraries/cxcp/inc -ICalibration
LWIP_INCLUDE := -ILibraries\Ethernet\lwip\port\include -ILibraries\Ethernet\lwip\src\include -ILibraries\Ethernet\Phy_Dp83825i -ILibraries\UART
INCLUDES := $(USER_INCLUDES) $(LWIP_INCLUDE) -IConfigurations -ILibraries -ILibraries/Infra -ILibraries/Infra/Platform -ILibraries/Infra/Platform/Tricore -ILibraries/Infra/Platform/Tricore/Compilers -ILibraries/Infra/Sfr -ILibraries/Infra/Sfr/TC37x -ILibraries/Infra/Ssw -ILibraries/Infra/Ssw/TC3xx -ILibraries/Infra/Ssw/TC3xx/Tricore -ILibraries/Service -ILibraries/Service/CpuGeneric -ILibraries/Service/CpuGeneric/If -ILibraries/Service/CpuGeneric/If/Ccu6If -ILibraries/Service/CpuGeneric/StdIf -ILibraries/Service/CpuGeneric/SysSe -ILibraries/Service/CpuGeneric/SysSe/Bsp -ILibraries/Service/CpuGeneric/SysSe/Comm -ILibraries/Service/CpuGeneric/SysSe/General -ILibraries/Service/CpuGeneric/SysSe/Math -ILibraries/Service/CpuGeneric/SysSe/Time -ILibraries/Service/CpuGeneric/_Utilities -ILibraries/iLLD -ILibraries/iLLD/TC3xx -ILibraries/iLLD/TC3xx/Tricore -ILibraries/iLLD/TC3xx/Tricore/Asclin -ILibraries/iLLD/TC3xx/Tricore/Asclin/Asc -ILibraries/iLLD/TC3xx/Tricore/Asclin/Lin -ILibraries/iLLD/TC3xx/Tricore/Asclin/Spi -ILibraries/iLLD/TC3xx/Tricore/Asclin/Std -ILibraries/iLLD/TC3xx/Tricore/Can -ILibraries/iLLD/TC3xx/Tricore/Can/Can -ILibraries/iLLD/TC3xx/Tricore/Can/Std -ILibraries/iLLD/TC3xx/Tricore/Ccu6 -ILibraries/iLLD/TC3xx/Tricore/Ccu6/Icu -ILibraries/iLLD/TC3xx/Tricore/Ccu6/PwmBc -ILibraries/iLLD/TC3xx/Tricore/Ccu6/PwmHl -ILibraries/iLLD/TC3xx/Tricore/Ccu6/Std -ILibraries/iLLD/TC3xx/Tricore/Ccu6/TPwm -ILibraries/iLLD/TC3xx/Tricore/Ccu6/Timer -ILibraries/iLLD/TC3xx/Tricore/Ccu6/TimerWithTrigger -ILibraries/iLLD/TC3xx/Tricore/Cif -ILibraries/iLLD/TC3xx/Tricore/Cif/Cam -ILibraries/iLLD/TC3xx/Tricore/Cif/Std -ILibraries/iLLD/TC3xx/Tricore/Convctrl -ILibraries/iLLD/TC3xx/Tricore/Convctrl/Std -ILibraries/iLLD/TC3xx/Tricore/Cpu -ILibraries/iLLD/TC3xx/Tricore/Cpu/Irq -ILibraries/iLLD/TC3xx/Tricore/Cpu/Std -ILibraries/iLLD/TC3xx/Tricore/Cpu/Trap -ILibraries/iLLD/TC3xx/Tricore/Dma -ILibraries/iLLD/TC3xx/Tricore/Dma/Dma -ILibraries/iLLD/TC3xx/Tricore/Dma/Std -ILibraries/iLLD/TC3xx/Tricore/Dts -ILibraries/iLLD/TC3xx/Tricore/Dts/Dts -ILibraries/iLLD/TC3xx/Tricore/Dts/Std -ILibraries/iLLD/TC3xx/Tricore/Ebu -ILibraries/iLLD/TC3xx/Tricore/Ebu/BFlashSpansion -ILibraries/iLLD/TC3xx/Tricore/Ebu/BFlashSt -ILibraries/iLLD/TC3xx/Tricore/Ebu/Dram -ILibraries/iLLD/TC3xx/Tricore/Ebu/Sram -ILibraries/iLLD/TC3xx/Tricore/Ebu/Std -ILibraries/iLLD/TC3xx/Tricore/Edsadc -ILibraries/iLLD/TC3xx/Tricore/Edsadc/Edsadc -ILibraries/iLLD/TC3xx/Tricore/Edsadc/Std -ILibraries/iLLD/TC3xx/Tricore/Emem -ILibraries/iLLD/TC3xx/Tricore/Emem/Std -ILibraries/iLLD/TC3xx/Tricore/Eray -ILibraries/iLLD/TC3xx/Tricore/Eray/Eray -ILibraries/iLLD/TC3xx/Tricore/Eray/Std -ILibraries/iLLD/TC3xx/Tricore/Evadc -ILibraries/iLLD/TC3xx/Tricore/Evadc/Adc -ILibraries/iLLD/TC3xx/Tricore/Evadc/Std -ILibraries/iLLD/TC3xx/Tricore/Fce -ILibraries/iLLD/TC3xx/Tricore/Fce/Crc -ILibraries/iLLD/TC3xx/Tricore/Fce/Std -ILibraries/iLLD/TC3xx/Tricore/Flash -ILibraries/iLLD/TC3xx/Tricore/Flash/Std -ILibraries/iLLD/TC3xx/Tricore/Geth -ILibraries/iLLD/TC3xx/Tricore/Geth/Eth -ILibraries/iLLD/TC3xx/Tricore/Geth/Std -ILibraries/iLLD/TC3xx/Tricore/Gpt12 -ILibraries/iLLD/TC3xx/Tricore/Gpt12/IncrEnc -ILibraries/iLLD/TC3xx/Tricore/Gpt12/Std -ILibraries/iLLD/TC3xx/Tricore/Gtm -ILibraries/iLLD/TC3xx/Tricore/Gtm/Atom -ILibraries/iLLD/TC3xx/Tricore/Gtm/Atom/Dtm_PwmHl -ILibraries/iLLD/TC3xx/Tricore/Gtm/Atom/Pwm -ILibraries/iLLD/TC3xx/Tricore/Gtm/Atom/PwmHl -ILibraries/iLLD/TC3xx/Tricore/Gtm/Atom/Timer -ILibraries/iLLD/TC3xx/Tricore/Gtm/Pwm -ILibraries/iLLD/TC3xx/Tricore/Gtm/Std -ILibraries/iLLD/TC3xx/Tricore/Gtm/Tim -ILibraries/iLLD/TC3xx/Tricore/Gtm/Tim/In -ILibraries/iLLD/TC3xx/Tricore/Gtm/Tim/Timer -ILibraries/iLLD/TC3xx/Tricore/Gtm/Tom -ILibraries/iLLD/TC3xx/Tricore/Gtm/Tom/Dtm_PwmHl -ILibraries/iLLD/TC3xx/Tricore/Gtm/Tom/Pwm -ILibraries/iLLD/TC3xx/Tricore/Gtm/Tom/PwmHl -ILibraries/iLLD/TC3xx/Tricore/Gtm/Tom/Timer -ILibraries/iLLD/TC3xx/Tricore/Gtm/Trig -ILibraries/iLLD/TC3xx/Tricore/Hspdm -ILibraries/iLLD/TC3xx/Tricore/Hspdm/Std -ILibraries/iLLD/TC3xx/Tricore/Hssl -ILibraries/iLLD/TC3xx/Tricore/Hssl/Hssl -ILibraries/iLLD/TC3xx/Tricore/Hssl/Std -ILibraries/iLLD/TC3xx/Tricore/I2c -ILibraries/iLLD/TC3xx/Tricore/I2c/I2c -ILibraries/iLLD/TC3xx/Tricore/I2c/Std -ILibraries/iLLD/TC3xx/Tricore/Iom -ILibraries/iLLD/TC3xx/Tricore/Iom/Driver -ILibraries/iLLD/TC3xx/Tricore/Iom/Iom -ILibraries/iLLD/TC3xx/Tricore/Iom/Std -ILibraries/iLLD/TC3xx/Tricore/Msc -ILibraries/iLLD/TC3xx/Tricore/Msc/Msc -ILibraries/iLLD/TC3xx/Tricore/Msc/Std -ILibraries/iLLD/TC3xx/Tricore/Mtu -ILibraries/iLLD/TC3xx/Tricore/Mtu/Std -ILibraries/iLLD/TC3xx/Tricore/Pms -ILibraries/iLLD/TC3xx/Tricore/Pms/Std -ILibraries/iLLD/TC3xx/Tricore/Port -ILibraries/iLLD/TC3xx/Tricore/Port/Io -ILibraries/iLLD/TC3xx/Tricore/Port/Std -ILibraries/iLLD/TC3xx/Tricore/Psi5 -ILibraries/iLLD/TC3xx/Tricore/Psi5/Psi5 -ILibraries/iLLD/TC3xx/Tricore/Psi5/Std -ILibraries/iLLD/TC3xx/Tricore/Psi5s -ILibraries/iLLD/TC3xx/Tricore/Psi5s/Psi5s -ILibraries/iLLD/TC3xx/Tricore/Psi5s/Std -ILibraries/iLLD/TC3xx/Tricore/Qspi -ILibraries/iLLD/TC3xx/Tricore/Qspi/SpiMaster -ILibraries/iLLD/TC3xx/Tricore/Qspi/SpiSlave -ILibraries/iLLD/TC3xx/Tricore/Qspi/Std -ILibraries/iLLD/TC3xx/Tricore/Rif -ILibraries/iLLD/TC3xx/Tricore/Rif/Rif -ILibraries/iLLD/TC3xx/Tricore/Rif/Std -ILibraries/iLLD/TC3xx/Tricore/Scu -ILibraries/iLLD/TC3xx/Tricore/Scu/Std -ILibraries/iLLD/TC3xx/Tricore/Sdmmc -ILibraries/iLLD/TC3xx/Tricore/Sdmmc/Emmc -ILibraries/iLLD/TC3xx/Tricore/Sdmmc/Sd -ILibraries/iLLD/TC3xx/Tricore/Sdmmc/Std -ILibraries/iLLD/TC3xx/Tricore/Sent -ILibraries/iLLD/TC3xx/Tricore/Sent/Sent -ILibraries/iLLD/TC3xx/Tricore/Sent/Std -ILibraries/iLLD/TC3xx/Tricore/Smu -ILibraries/iLLD/TC3xx/Tricore/Smu/Smu -ILibraries/iLLD/TC3xx/Tricore/Smu/Std -ILibraries/iLLD/TC3xx/Tricore/Spu -ILibraries/iLLD/TC3xx/Tricore/Spu/Std -ILibraries/iLLD/TC3xx/Tricore/Src -ILibraries/iLLD/TC3xx/Tricore/Src/Std -ILibraries/iLLD/TC3xx/Tricore/Stm -ILibraries/iLLD/TC3xx/Tricore/Stm/Std -ILibraries/iLLD/TC3xx/Tricore/Stm/Timer -ILibraries/iLLD/TC3xx/Tricore/_Impl -ILibraries/iLLD/TC3xx/Tricore/_Impl/TC37x -ILibraries/iLLD/TC3xx/Tricore/_Lib -ILibraries/iLLD/TC3xx/Tricore/_Lib/DataHandling -ILibraries/iLLD/TC3xx/Tricore/_Lib/InternalMux -ILibraries/iLLD/TC3xx/Tricore/_PinMap -ILibraries/iLLD/TC3xx/Tricore/_PinMap/TC37x 

CCACHE := ccache
# GCC_DIR := C:\Infineon\AURIX-Configuration-Studio-1.0.24\eclipse\tricore-gcc11\bin
GCC_DIR := C:\Users\max.holder\source\repos\AURIX\tricore-gcc-13.4.1-win32\bin
GCC := tricore-elf-gcc.exe
OBJCPY := tricore-elf-objcopy.exe
ELFSIZETOOL := tricore-elf-size.exe

export PATH := $(GCC_DIR):$(PATH)

.PHONY: all clean

# $(info SOURCES=$(SOURCES))
# $(info OBJECTS=$(OBJECTS))
# $(info DEPS=$(DEPS))

all: $(TARGET_ELF) $(TARGET_HEX) $(TARGET_SIZ) $(TARGET_A2L)

$(A2L_ANNOTATIONS): $(SOURCES) $(HEADERS) $(A2L_TOOLS)/a2l_extract.py
	@echo A2L Extract Annotations
	$(PYTHON) $(A2L_TOOLS)/a2l_extract.py $(SRC_DIR) $(A2L_EXCLUDES) -o "$@"
	@echo " "

$(A2L_PROBE): $(A2L_TOOLS)/a2l_probe.c
	@echo A2L Target and XCP Configuration Probe
	@if not exist "$(dir $@)" mkdir "$(dir $@)"
	$(GCC) $(INCLUDES) -O0 -mtc162 -MMD -MP -MF"$(@:.o=.d)" -MT"$@" -c "$<" -o "$@"
	@echo " "

$(A2L_RESOLVED): $(TARGET_ELF) $(A2L_ANNOTATIONS) $(A2L_PROBE) $(A2L_TOOLS)/a2l_resolve.py
	@echo A2L Resolve Addresses
	$(PYTHON) $(A2L_TOOLS)/a2l_resolve.py "$(A2L_ANNOTATIONS)" "$(TARGET_ELF)" --epk-symbol $(A2L_EPK_SYMBOL) --probe "$(A2L_PROBE)" -o "$@"
	@echo " "

$(TARGET_A2L): $(A2L_RESOLVED) $(A2L_TOOLS)/a2l_generate.py
	@echo A2L Generate
	$(PYTHON) $(A2L_TOOLS)/a2l_generate.py "$(A2L_RESOLVED)" -o "$@"
	@echo Output: "$@"
	@echo " "

$(TARGET_SIZ): $(TARGET_ELF)
	@echo TriCore GCC Print Size
	$(ELFSIZETOOL) --format=berkeley "$(TARGET_ELF)"
	@echo " "

$(TARGET_HEX): $(TARGET_ELF)
	@echo TriCore GCC Create Flash Image (.hex)
	$(OBJCPY) "$(TARGET_ELF)" -O ihex "$(TARGET_HEX)"
	@echo Output: "$(TARGET_HEX)"
	@echo " "

$(TARGET_ELF): $(OBJECTS)
	@echo TriCore GCC Linker
	@if not exist "$(dir $(TARGET_ELF))" mkdir "$(dir $(TARGET_ELF))"
	$(GCC) -T"Lcf_Gcc_Tricore_Tc.lsl" -nocrt0 -Xlinker --gc-sections -Xlinker --no-warn-rwx-segments -Wl,-Map,"$(TARGET_MAP)" -mtc162 -o "$(TARGET_ELF)" $(OBJECTS) 
	@echo Output: "$(TARGET_ELF)"
	@echo Output: "$(TARGET_MAP)"
	@echo " "

$(BUILD_DIR)/%.i: $(SRC_DIR)/%.c
	@echo TriCore GCC Compiler (Preprocessor Only)
	@echo Compile $< (Out: $@)
	@echo "Current working directory: $(CURDIR)"
	@if not exist "$(dir $@)" mkdir "$(dir $@)"
	$(CCACHE) $(GCC) $(INCLUDES) -E -CC -P "$@" -o "$(@:.o=.i)"
	@echo " "

$(BUILD_DIR)/%.o: $(SRC_DIR)/%.c
	@echo TriCore GCC Compiler
	@echo Compile $< (Out: $@)
	@echo "Current working directory: $(CURDIR)"
	@if not exist "$(dir $@)" mkdir "$(dir $@)"
	$(CCACHE) $(GCC) -MMD -MT "$@" $(INCLUDES) -Og -fdata-sections -ffunction-sections -fstrict-volatile-bitfields -g -gdwarf-2 -Wall -std=gnu99 -Wa,-adhlns="$@.lst" -pipe -c -fmessage-length=0 -MMD -MP -MF"$(@:.o=.d)" -MT"$@" -mtc162 -o "$@" "$<"
	$(CCACHE) $(GCC) $(INCLUDES) -E -CC -P "$<" -o "$(@:.o=.i)"
	@echo " "

clean:
	@echo Cleaning up...
	@if exist $(BUILD_DIR) rmdir $(BUILD_DIR) /s /q
	@echo Build directory removed.
	@echo " "
	@echo Cleaning up binaries...
	@if exist $(BIN_DIR) rmdir $(BIN_DIR) /s /q
	@echo Removed binaries.
	@echo " "

-include $(DEPS) $(A2L_PROBE:.o=.d)
