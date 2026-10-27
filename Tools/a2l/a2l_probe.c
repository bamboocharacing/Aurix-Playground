/* Compile-time probe of target and XCP configuration for the A2L generator.
 *
 * Compiled with the firmware's compiler, flags and include paths (but not
 * linked into it). Every a2l_probe_<key> constant holds a value as the compiler
 * evaluates it; a2l_resolve.py reads them from the object file and puts them
 * into MOD_COMMON (alignments) and IF_DATA XCP of the A2L file.
 */
#include <stddef.h>
#include <stdint.h>
#include "xcp.h"

#define A2L_PROBE(key, value) __attribute__((used)) const uint32_t a2l_probe_##key = (uint32_t)(value)

/* Alignment of a type as a struct member, i.e. how the ABI actually lays it out. */
#define A2L_ALIGNMENT(type) offsetof(struct { char c; type v; }, v)

A2L_PROBE(align_byte, A2L_ALIGNMENT(uint8_t));
A2L_PROBE(align_word, A2L_ALIGNMENT(uint16_t));
A2L_PROBE(align_long, A2L_ALIGNMENT(uint32_t));
A2L_PROBE(align_int64, A2L_ALIGNMENT(uint64_t));
A2L_PROBE(align_float32, A2L_ALIGNMENT(float));
#if __SIZEOF_DOUBLE__ == 8
A2L_PROBE(align_float64, A2L_ALIGNMENT(double));
#elif __SIZEOF_LONG_DOUBLE__ == 8
A2L_PROBE(align_float64, A2L_ALIGNMENT(long double));
#endif

A2L_PROBE(protocol_version, (XCP_PROTOCOL_VERSION_MAJOR << 8) | XCP_PROTOCOL_VERSION_MINOR);
A2L_PROBE(transport_version, (XCP_TRANSPORT_LAYER_VERSION_MAJOR << 8) | XCP_TRANSPORT_LAYER_VERSION_MINOR);
A2L_PROBE(max_cto, XCP_MAX_CTO);
A2L_PROBE(max_dto, XCP_MAX_DTO);
A2L_PROBE(byte_order, XCP_BYTE_ORDER);
A2L_PROBE(address_granularity, XCP_ADDRESS_GRANULARITY);

#if XCP_ENABLE_DAQ_COMMANDS == XCP_ON
A2L_PROBE(daq_config_type, XCP_DAQ_CONFIG_TYPE);
A2L_PROBE(daq_max_dynamic_entities, XCP_DAQ_MAX_DYNAMIC_ENTITIES);
A2L_PROBE(daq_max_event_channel, XCP_DAQ_MAX_EVENT_CHANNEL);
A2L_PROBE(daq_max_odt_entry_size, XCP_DAQ_MAX_ODT_ENTRY_SIZE);
    #if XCP_DAQ_ENABLE_PREDEFINED_LISTS == XCP_ON
A2L_PROBE(daq_predefined_lists, 1);
    #endif
    #if XCP_DAQ_ENABLE_TIMESTAMPING == XCP_ON
A2L_PROBE(daq_timestamp_unit, XCP_DAQ_TIMESTAMP_UNIT);
A2L_PROBE(daq_timestamp_size, XCP_DAQ_TIMESTAMP_SIZE);
    #endif
#endif

#if XCP_TRANSPORT_LAYER == XCP_ON_ETHERNET
A2L_PROBE(eth_protocol, XCP_ON_ETHERNET_PROTOCOL);
A2L_PROBE(eth_port, XCP_ON_ETHERNET_PORT);
    #if defined(XCP_ON_ETHERNET_IP_OCTETS)
__attribute__((used)) const uint8_t a2l_probe_eth_ip[4] = { XCP_ON_ETHERNET_IP_OCTETS };
    #endif
#endif
