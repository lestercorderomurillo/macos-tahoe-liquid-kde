#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""Inject a key chord only inside the disposable qualification VM."""
import os,fcntl,struct,time,sys
from pathlib import Path
assert Path('/sys/class/dmi/id/product_name').read_text().strip()=='MTTKDE release capture'
keys=[int(k) for k in sys.argv[1:]]
fd=os.open('/dev/uinput',os.O_WRONLY|os.O_NONBLOCK)
fcntl.ioctl(fd,0x40045564,1)
for k in keys: fcntl.ioctl(fd,0x40045565,k)
os.write(fd,struct.pack('80sHHHHi',b'Clipboard qualification keyboard',3,1,1,1,0)+bytes(1024))
fcntl.ioctl(fd,0x5501)
time.sleep(.4)
def event(kind,code,value): os.write(fd,struct.pack('llHHi',0,0,kind,code,value))
for value,sequence in ((1,keys),(0,list(reversed(keys)))):
 for k in sequence: event(1,k,value)
 event(0,0,0);time.sleep(.1)
fcntl.ioctl(fd,0x5502);os.close(fd)
