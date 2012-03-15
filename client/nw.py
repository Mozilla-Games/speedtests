# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this file,
# You can obtain one at http://mozilla.org/MPL/2.0/.

import _winreg
import os

IF_ID_FILENAME = 'nwifid'

class NwDisabler(object):
    IFS_SUBKEY = 'SYSTEM\CurrentControlSet\services\Tcpip\Parameters\Interfaces'

    def __init__(self, if_id=None):
        self.if_id = if_id
    
    def if_subkey(self, if_id=None):
        if if_id is None:
            if_id = self.if_id
        return '%s\\{%s}' % (NwDisabler.IFS_SUBKEY, if_id)
    
    def change_nameserver(self, nameserver):
        hdl = _winreg.OpenKey(_winreg.HKEY_LOCAL_MACHINE, self.if_subkey(), 0, _winreg.KEY_ALL_ACCESS)
        _winreg.SetValueEx(hdl, 'NameServer', 0, _winreg.REG_SZ, nameserver)
        _winreg.CloseKey(hdl)
        os.system('ipconfig /renew')

    def disable_nw(self):
        self.change_nameserver('127.0.0.1')

    def enable_nw(self):
        self.change_nameserver('')

    def get_if_id(self, ip):
        hdl = _winreg.OpenKey(_winreg.HKEY_LOCAL_MACHINE, NwDisabler.IFS_SUBKEY)
        i = 0
        if_id = None
        while True:
            try:
                subkey = _winreg.EnumKey(hdl, i)
            except WindowsError:
                break
            hdl2 = _winreg.OpenKey(hdl, subkey)
            try:
                if_ip = _winreg.QueryValueEx(hdl2, 'DhcpIPAddress')[0]
            except WindowsError:
                pass
            _winreg.CloseKey(hdl2)
            if if_ip == ip:
                if_id = subkey[1:-1]  # strip surrounding braces
                break
            i += 1
        _winreg.CloseKey(hdl)
        return if_id
        
if __name__ == '__main__':
    import sys, errno
    usage = '%s <enable|disable>\n%s setif <ip>' % (sys.argv[0], sys.argv[0])
    if len(sys.argv) < 2:
        print usage
        sys.exit(errno.EINVAL)
    if sys.argv[1] == 'setif':
        if len(sys.argv) < 3:
            print usage
            sys.exit(errno.EINVAL)
        nw_disabler = NwDisabler()
        if_id = nw_disabler.get_if_id(sys.argv[2])
        if if_id == None:
            print 'Could not find interface with IP %s.' % sys.argv[2]
        else:
            print 'Interface found; writing to config file.'
            file(IF_ID_FILENAME, 'w').write(if_id)
    else:
        try:
            f = file(IF_ID_FILENAME, 'r')
        except IOError:
            print 'Interface ID not found.  Run "setif" command first.'
            sys.exit(errno.EINVAL)
        if_id = f.read().strip()
        f.close()
        nw_disabler = NwDisabler(if_id)
        if sys.argv[1] == 'enable':
            nw_disabler.enable_nw()
        elif sys.argv[1] == 'disable':
            nw_disabler.disable_nw()
        else:
            print 'Invalid command "%s".' % sys.argv[1]
            print usage
            sys.exit(errno.EINVAL)
        
