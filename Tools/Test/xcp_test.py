from pyxcp.cmdline import ArgumentParser
from pyxcp import Master
import struct

ap = ArgumentParser(description="pyXCP hello world")

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


with ap.run() as x:
    x.connect()
    identifier = x.identifier(0x01)
    print(f"ID: {identifier!r}")

    read_float(x, 0x7000A7B0)

    read_uint32(x, 0x7000A7B4)
    write_uint32(x, 0x7000A7B4, 200)
    read_uint32(x, 0x7000A7B4)
    
    x.disconnect()