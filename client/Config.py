import platform
import os
import sys
import socket
import time
import traceback
import ConfigParser

def find_local_port():
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.bind(("", 0))
    local_port = s.getsockname()[1]
    s.close()
    return local_port

class Config(object):
    DEFAULT_CONF_FILE = 'speedtests.conf'
    
    def __init__(self):
        self.cfg = None

        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.connect(('8.8.8.8', 80))
            self.local_ip = s.getsockname()[0]
            s.close()
        except:
            self.local_ip = '127.0.0.1'
            print "Using localhost as local IP, hope that's ok!"
            #raise Exception("Couldn't find local IP!")

        defaults = dict()
        defaults['64bit'] = "False"
        defaults['local_port'] = 0
        defaults['results_server'] = None
        #defaults['platform'] = platform.system()
        defaults['client'] = self.local_ip

        self.defaults = defaults

        self.ignore = False
        self.verbose = False
        self.platform = platform.system()

    def read(self, noresults=False, ignore=False,
             conf_file=None):
        self.noresults = noresults
        self.ignore = ignore
        if not conf_file:
            conf_file = Config.DEFAULT_CONF_FILE

        if not os.path.exists(conf_file):
            raise Exception("Config file '" + conf_file + "' not found!")

        self.cfg = ConfigParser.ConfigParser(self.defaults)
        self.cfg.read(conf_file)

        self.sixtyfour_bit = self.cfg.getboolean('speedtests', '64bit')
        self.local_port = self.cfg.getint('speedtests', 'local_port')
        self.client = self.get_str('speedtests', 'client')
        self.results_server = self.cfg.get('speedtests', 'results_server')

        try:
            self.test_base_url = self.cfg.get('speedtests', 'test_base_url').rstrip('/')
        except (ConfigParser.NoSectionError, ConfigParser.NoOptionError):
            print "test_base_url must be specified in config file!"
            raise

        if not self.local_port:
            self.local_port = find_local_port()
            print "Using port %d" % (self.local_port)

    def get_str(self, section, param, default=None):
        try:
            val = self.cfg.get(section, param)
        except (ConfigParser.NoSectionError, ConfigParser.NoOptionError):
            val = default
        return val

    def get_int(self, section, param, default=None):
        try:
            val = int(self.cfg.get(section, param))
        except (ConfigParser.NoSectionError, ConfigParser.NoOptionError):
            val = default
        return val

config = Config()
