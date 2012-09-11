# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this file,
# You can obtain one at http://mozilla.org/MPL/2.0/.

import re
import threading

from Zeroconf import Zeroconf, ServiceBrowser
from devicemanager import NetworkTools
from droid import DroidSUT, DroidADB

class ZeroconfListener(object):
    def __init__(self, hwid, evt):
        self.hwid = hwid
        self.evt = evt

    # Format is 'SUTAgent [hwid:015d2bc2825ff206] [ip:10_242_29_221]._sutagent._tcp.local.'
    def addService(self, zeroconf, type, name):
        #print "Found _sutagent service broadcast:", name
        if not name.startswith("SUTAgent"):
            return

        sutname = name.split('.')[0]
        m = re.search('\[hwid:([^\]]*)\]', sutname)
        if m is None:
            return

        hwid = m.group(1)

        m = re.search('\[ip:([0-9_]*)\]', sutname)
        if m is None:
            return

        ip = m.group(1).replace("_", ".")
        
        if self.hwid == hwid:
            self.ip = ip
            self.evt.set()

    def removeService(self, zeroconf, type, name):
        pass

def ConnectByHWID(hwid, timeout=30, force_adb=False):
    """Try to connect to the given device by waiting for it to show up using mDNS with the given timeout;
if that fails, then look for it as part of the local adb devices.  If force_adb is specified, then
only look for it via adb."""

    if not force_adb:
        nt = NetworkTools()
        local_ip = nt.getLanIp()

        zc = Zeroconf(local_ip)

        evt = threading.Event()
        listener = ZeroconfListener(hwid, evt)
        sb = ServiceBrowser(zc, "_sutagent._tcp.local.", listener)
        foundIP = None
        if evt.wait(timeout):
            # we found the hwid 
            foundIP = listener.ip
            sb.cancel()
            zc.close()

        if foundIP is not None:
            # use SUT
            print "Connecting via SUT to", foundIP
            return DroidSUT(foundIP)

    # either adb force, or we didn't find a running SUT
    return DroidADB(deviceSerial=hwid)

if __name__ == '__main__':
    dm = ConnectByHWID("015d2bc2825ff206", timeout=5, force_adb=True)
    print dm.getInfo("os")
    print dm.getInfo("id")
    print dm.getInfo("screen")
