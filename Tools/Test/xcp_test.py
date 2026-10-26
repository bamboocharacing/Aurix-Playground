from pyxcp.cmdline import ArgumentParser
from pyxcp import Master
from pyxcp.daq_stim import DaqList, DaqToCsv, DaqRecorder
import time
import struct

ap = ArgumentParser(description="pyXCP hello world")

DAQ_LISTS = [
    DaqList(
        name="EVT 100ms",
        event_num=0,
        stim=False,
        enable_timestamps=False,
        measurements=[
            ("g_VarA", 0x7000A7E0, 0, "U32")
        ],
        priority=0,
        prescaler=1,
    )
]

def read_float(x, addr):
    data_float = x.shortUpload(4, addr)
    value_float = struct.unpack("<f", data_float)[0]
    print(f"Value: {value_float}")

def read_uint32(x, addr):
    data_int = x.shortUpload(4, addr)
    value_int = struct.unpack("<I", data_int)[0]    
    print(f"Value: {value_int}")

def write_uint32(x: Master, addr, value):
    x.shortDownload(addr, 0x00, struct.pack("<I", value))


daq_parser = DaqToCsv(DAQ_LISTS)
with ap.run(policy=daq_parser) as x:
    x.connect()
    identifier = x.identifier(0x01)
    print(f"ID: {identifier!r}")

    read_float(x, 0x7000A7DC)

    read_uint32(x, 0x7000A7E0)
    write_uint32(x, 0x7000A7E0, 200)
    read_uint32(x, 0x7000A7E0)

    daq_info = x.getDaqInfo()
    print(daq_info)

    daq_parser.setup()
    daq_parser.start()
    time.sleep(10);
    daq_parser.stop()

    x.disconnect()

    if hasattr(daq_parser, "files"):  # `files` attribute is specific to `DaqToCsv`.
        print("Data written to:")
        print("================")
        for fl in daq_parser.files.values():
            print(fl.name)