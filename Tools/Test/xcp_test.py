from pyxcp.cmdline import ArgumentParser

ap = ArgumentParser(description="pyXCP hello world")

with ap.run() as x:
    x.connect()
    identifier = x.identifier(0x01)
    print(f"ID: {identifier!r}")
    print(x.slaveProperties)
    x.disconnect()