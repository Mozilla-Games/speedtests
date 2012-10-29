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
        self.sixtyfour_bit = False
        self.local_port = 8111
        self.server_html_url = 'http://brasstacks.mozilla.com/speedtests'
        self.server_api_url = 'http://brasstacks.mozilla.com/speedtests/api'
        self.local_test_base_path = ''
        self.ignore = False
        self.platform = platform.system()
        self.verbose = False

    @property
    def local_test_base_url(self):
        #return self.server_html_url + self.local_test_base_path
        # IE has issues loading pages from localhost, so we'll use the
        # external IP.
        return 'http://%s:%d%s' % (self.local_ip, self.local_port, self.local_test_base_path)

    def read(self, testmode=False, noresults=False, ignore=False,
             conf_file=None):
        self.testmode = testmode
        self.noresults = noresults
        self.ignore = ignore
        if not conf_file:
            conf_file = Config.DEFAULT_CONF_FILE
        self.cfg = ConfigParser.ConfigParser()
        self.cfg.read(conf_file)

        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.connect(('8.8.8.8', 80))
            self.local_ip = s.getsockname()[0]
            s.close()
        except:
            self.local_ip = '127.0.0.1'
            print "Using localhost as local IP, hope that's ok!"
            #raise Exception("Couldn't find local IP!")

        try:
            self.sixtyfour_bit = self.cfg.getboolean('speedtests', '64bit')
        except (ConfigParser.NoSectionError, ConfigParser.NoOptionError):
            pass
        
        try:
            self.local_port = self.cfg.getint('speedtests', 'local_port')
        except (ConfigParser.NoSectionError, ConfigParser.NoOptionError):
            self.local_port = find_local_port()
            print "Using port %d" % (self.local_port)
        
        try:
            self.server_html_url = self.cfg.get('speedtests', 'test_base_url').rstrip('/').replace("SELF_IP", self.local_ip)
        except (ConfigParser.NoSectionError, ConfigParser.NoOptionError):
            pass

        try:
            self.server_api_url = self.cfg.get('speedtests', 'server_url').rstrip('/').replace("SELF_IP", self.local_ip)
        except (ConfigParser.NoSectionError, ConfigParser.NoOptionError):
            self.server_api_url = self.server_html_url + '/api'

        try:
            self.server_results_url = self.cfg.get('speedtests', 'server_results_url').rstrip('/').replace("SELF_IP", self.local_ip) + '/'
        except (ConfigParser.NoSectionError, ConfigParser.NoOptionError):
            self.server_results_url = self.server_api_url + '/testresults/'

        try:
            self.platform = self.cfg.get('speedtests', 'platform')
        except (ConfigParser.NoSectionError, ConfigParser.NoOptionError):
            pass

        self.client = self.get_str('speedtests', 'client')
        if self.client is None:
            self.client = self.local_ip

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
